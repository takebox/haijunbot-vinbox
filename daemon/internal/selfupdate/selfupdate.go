// Package selfupdate implements auto-update for haijunbot-daemon: parsing the update directive sent by the gateway,
// downloading the new version, verifying sha256, unpacking, and atomically replacing its own executable.
//
// Design highlights (see daemon/docs/daemon-self-update-protocol.md):
//   - Downloads only from HTTPS GitHub domains (allowlist check, preventing SSRF / MITM);
//   - After download, verifies sha256 streaming (skips with a warning if the gateway did not provide a checksum);
//   - Unpacking takes only haijunbot-daemon[.exe], implemented with the standard library, zero third-party dependencies;
//   - Replacement uses "same-directory temp file + rename", so a failure does not break the existing executable;
//   - Only Windows and Linux are supported (not macOS).
//
// Platform differences (replacing a running executable) are implemented in files with build tags:
//   - apply_linux.go: directly renames over (a running file can be replaced);
//   - apply_windows.go: a running exe cannot be overwritten, so a helper child process replaces it after the parent exits.
package selfupdate

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"haijunbot-daemon/internal/proxy"
)

// Download and network related constants.
const (
	// downloadTimeout is the overall timeout for a single download. The binary is roughly a few MiB to a dozen MiB;
	// 5 minutes covers slow networks without letting a failed request hang forever.
	downloadTimeout = 5 * time.Minute
	// maxDownloadBytes is the download size cap (64 MiB). Normal artifacts are far below this,
	// and the cap prevents malicious/abnormal large files from exhausting disk and memory.
	maxDownloadBytes = 64 << 20
)

// allowedDownloadHosts is the allowlist of hosts permitted for downloads (lowercased).
//
// Why it is needed: an update replaces a local executable, which is a high-risk operation; if arbitrary URLs were allowed,
// an attacker could achieve SSRF or poisoning via a forged gateway response. Restricted to GitHub's official domains,
// even a compromised gateway can only direct users to artifacts on GitHub (which are auditable).
var allowedDownloadHosts = map[string]bool{
	"github.com":                    true,
	"objects.githubusercontent.com": true,
}

// extraAllowedHosts is only for tests to inject extra allowlisted hosts (e.g. httptest's 127.0.0.1:port).
//
// Production code never writes to it; tests use setExtraAllowedHosts to add temporarily and clear afterwards.
var extraAllowedHosts = map[string]bool{}

// setExtraAllowedHosts temporarily adds hosts to the download allowlist (test only).
func setExtraAllowedHosts(hosts ...string) {
	extraAllowedHosts = map[string]bool{}
	for _, h := range hosts {
		extraAllowedHosts[strings.ToLower(h)] = true
	}
}

// allowInsecureForTest is test-only: when true, the https requirement is relaxed (httptest only serves http).
var allowInsecureForTest bool

// setAllowInsecureForTest sets the test-only "allow http" switch.
func setAllowInsecureForTest(v bool) { allowInsecureForTest = v }

// UpdateInfo is the update directive sent by the gateway with hello_ack (corresponding to the daemon_update object).
//
// The fields map one-to-one to the JSON schema in the design doc; all are optional, and missing fields take their zero values.
type UpdateInfo struct {
	// Available means the gateway determines "an update is needed". When false, the other fields are meaningless.
	Available bool `json:"available"`
	// LatestVersion is the latest version number (e.g. v1.2.0).
	LatestVersion string `json:"latest_version"`
	// CurrentVersion is the current version recorded by the gateway (for log comparison).
	CurrentVersion string `json:"current_version"`
	// URL is the download address of the new version artifact (must be an HTTPS GitHub domain).
	URL string `json:"url"`
	// SHA256 is the artifact's sha256 (lowercase hex); when empty, verification is skipped with a warning.
	SHA256 string `json:"sha256"`
	// Size is the artifact size in bytes (optional; for a rough pre-download check and logs).
	Size int64 `json:"size"`
	// Asset is the artifact file name (for logs and locating the target file during unpacking).
	Asset string `json:"asset"`
	// Note is a release note summary (optional; for logs only).
	Note string `json:"note"`
}

// ErrNotAvailable means the gateway did not send an update, or no update is needed.
var ErrNotAvailable = errors.New("no update available")

// ParseUpdateInfo parses the update directive from the raw daemon_update map in hello_ack.
//
// When the raw argument is nil or lacks available=true, ErrNotAvailable is returned,
// so the caller can uniformly use errors.Is to decide "no update needed".
func ParseUpdateInfo(raw map[string]any) (UpdateInfo, error) {
	if raw == nil {
		return UpdateInfo{}, ErrNotAvailable
	}
	// Use a JSON round-trip for a lenient parse: the gateway-side field types may not fully match (e.g. size as float64);
	// encoding/json's tolerance (number → int64) avoids the tedium and error-proneness of per-field assertions.
	blob, err := json.Marshal(raw)
	if err != nil {
		return UpdateInfo{}, fmt.Errorf("failed to serialize the update directive: %w", err)
	}
	var info UpdateInfo
	if err := json.Unmarshal(blob, &info); err != nil {
		return UpdateInfo{}, fmt.Errorf("failed to parse the update directive: %w", err)
	}
	info.URL = strings.TrimSpace(info.URL)
	info.SHA256 = strings.ToLower(strings.TrimSpace(info.SHA256))
	if !info.Available {
		return UpdateInfo{}, ErrNotAvailable
	}
	if info.URL == "" {
		return UpdateInfo{}, fmt.Errorf("the update directive is missing a download URL")
	}
	return info, nil
}

// ValidateDownloadURL validates the download address: must be HTTPS, and the host must be in the allowlist.
//
// Returns the normalized URL string; on validation failure it returns an error (the caller should log it and give up the update).
func ValidateDownloadURL(rawURL string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil {
		return "", fmt.Errorf("invalid download address: %w", err)
	}
	if !strings.EqualFold(u.Scheme, "https") && !allowInsecureForTest {
		return "", fmt.Errorf("download address must be https, got %q", u.Scheme)
	}
	host := strings.ToLower(u.Hostname())
	if !allowedDownloadHosts[host] && !extraAllowedHosts[host] {
		return "", fmt.Errorf("download address host %q is not in the allowlist", host)
	}
	return u.String(), nil
}

// Download downloads url to destPath and streams a checksum check against wantSHA256 (when non-empty).
//
// Behavior:
//   - Sends User-Agent: haijunbot-daemon/<version>, so GitHub-side can identify the source;
//   - Errors immediately if the size exceeds maxDownloadBytes;
//   - Computes sha256 while writing, avoiding loading the whole file into memory;
//   - Deletes the downloaded file and returns an error when verification fails.
//
// When wantSHA256 is empty, verification is skipped (logging is up to the caller) and nil is returned.
func Download(client *http.Client, version, rawURL, destPath, wantSHA256 string) error {
	safeURL, err := ValidateDownloadURL(rawURL)
	if err != nil {
		return err
	}
	if client == nil {
		client = &http.Client{Timeout: downloadTimeout, Transport: proxy.Transport()}
	}

	req, err := http.NewRequest(http.MethodGet, safeURL, nil)
	if err != nil {
		return fmt.Errorf("failed to build the download request: %w", err)
	}
	req.Header.Set("User-Agent", "haijunbot-daemon/"+version)

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("download failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed: HTTP %d", resp.StatusCode)
	}

	// Write to a temp file in the same directory first, then rename to destPath after success, so a half-written file is not mistaken for a valid artifact.
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return fmt.Errorf("failed to create the download directory: %w", err)
	}
	tmp, err := os.CreateTemp(filepath.Dir(destPath), ".haijunbot-daemon-dl-*")
	if err != nil {
		return fmt.Errorf("failed to create the temporary file: %w", err)
	}
	tmpName := tmp.Name()
	cleanup := func() {
		tmp.Close()
		_ = os.Remove(tmpName)
	}

	hasher := sha256.New()
	// Cap the read limit and error out when exceeded (io.LimitReader returns EOF after the limit,
	// so maxDownloadBytes+1 probes whether the limit was exceeded).
	limited := io.LimitReader(resp.Body, maxDownloadBytes+1)
	written, err := io.Copy(io.MultiWriter(tmp, hasher), limited)
	if err != nil {
		cleanup()
		return fmt.Errorf("failed to write the download content: %w", err)
	}
	if written > maxDownloadBytes {
		cleanup()
		return fmt.Errorf("download size exceeds the %d-byte cap", int64(maxDownloadBytes))
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return fmt.Errorf("failed to close the temporary file: %w", err)
	}

	if wantSHA256 != "" {
		got := hex.EncodeToString(hasher.Sum(nil))
		if !strings.EqualFold(got, wantSHA256) {
			_ = os.Remove(tmpName)
			return fmt.Errorf("sha256 verification failed: expected %s, got %s", wantSHA256, got)
		}
	}

	if err := os.Rename(tmpName, destPath); err != nil {
		_ = os.Remove(tmpName)
		return fmt.Errorf("failed to save the downloaded file: %w", err)
	}
	return nil
}

// verifySHA256 streams reads r and verifies whether its sha256 equals wantHex (case-insensitive).
//
// Extracted separately for testing and reuse; the download flow computes the hash inline to avoid reading the file twice.
func verifySHA256(r io.Reader, wantHex string) error {
	h := sha256.New()
	if _, err := io.Copy(h, r); err != nil {
		return fmt.Errorf("failed to read the content: %w", err)
	}
	got := hex.EncodeToString(h.Sum(nil))
	if !strings.EqualFold(got, wantHex) {
		return fmt.Errorf("sha256 verification failed: expected %s, got %s", wantHex, got)
	}
	return nil
}

// ExtractBinary extracts the target executable from an archive (judged by extension: .tar.gz/.tgz or .zip)
// and writes it to outPath. targetName is the expected file name (e.g. haijunbot-daemon or haijunbot-daemon.exe).
//
// It only takes entries in the archive whose "base name equals targetName", ignoring directories and other files, to avoid path traversal.
func ExtractBinary(archivePath, outPath, targetName string) error {
	lower := strings.ToLower(archivePath)
	switch {
	case strings.HasSuffix(lower, ".tar.gz"), strings.HasSuffix(lower, ".tgz"):
		return extractTarGz(archivePath, outPath, targetName)
	case strings.HasSuffix(lower, ".zip"):
		return extractZip(archivePath, outPath, targetName)
	default:
		return fmt.Errorf("unsupported archive format: %s", filepath.Base(archivePath))
	}
}

// extractTarGz extracts targetName from a .tar.gz.
func extractTarGz(archivePath, outPath, targetName string) error {
	f, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf("failed to open the archive: %w", err)
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return fmt.Errorf("failed to decompress gzip: %w", err)
	}
	defer gz.Close()

	tr := tar.NewReader(gz)
	for {
		hdr, err := tr.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return fmt.Errorf("failed to read tar: %w", err)
		}
		if hdr.Typeflag != tar.TypeReg {
			continue
		}
		if filepath.Base(hdr.Name) != targetName {
			continue
		}
		return writeExecutable(outPath, tr)
	}
	return fmt.Errorf("target %s not found in the archive", targetName)
}

// extractZip extracts targetName from a .zip.
func extractZip(archivePath, outPath, targetName string) error {
	zr, err := zip.OpenReader(archivePath)
	if err != nil {
		return fmt.Errorf("failed to open zip: %w", err)
	}
	defer zr.Close()
	for _, zf := range zr.File {
		if zf.FileInfo().IsDir() {
			continue
		}
		if filepath.Base(zf.Name) != targetName {
			continue
		}
		rc, err := zf.Open()
		if err != nil {
			return fmt.Errorf("failed to read the zip entry: %w", err)
		}
		defer rc.Close()
		return writeExecutable(outPath, rc)
	}
	return fmt.Errorf("target %s not found in the archive", targetName)
}

// writeExecutable writes the content of r to outPath and sets the executable permission (ignored on Windows).
func writeExecutable(outPath string, r io.Reader) error {
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return fmt.Errorf("failed to create the output directory: %w", err)
	}
	f, err := os.OpenFile(outPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o755)
	if err != nil {
		return fmt.Errorf("failed to create the output file: %w", err)
	}
	if _, err := io.Copy(f, r); err != nil {
		f.Close()
		_ = os.Remove(outPath)
		return fmt.Errorf("failed to write the executable: %w", err)
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(outPath)
		return fmt.Errorf("failed to close the executable: %w", err)
	}
	// Chmod is essentially a no-op on Windows, but the executable bit must be ensured on Linux.
	if err := os.Chmod(outPath, 0o755); err != nil {
		return fmt.Errorf("failed to set the executable permission: %w", err)
	}
	return nil
}
