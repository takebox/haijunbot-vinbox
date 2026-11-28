package capability

// This file implements the common logic for "browser extension automatic download and update" (cross-platform, no build tag).
//
// Background: the gateway provides GET /api/browser-ext/download, dynamically packaging the repository root's
// browser_extension/ into a zip (the content is the extension source, not a crx). The daemon pulls that zip from the gateway,
// extracts it, and overwrites the local fixed directory ~/.haijunbot/browser_extension, keeping the local extension copy
// consistent with the gateway version; the user only needs to click "refresh" once in chrome://extensions for it to take effect
// (Chrome/Edge do not allow an external program to hot-reload a loaded unpacked extension, nor to silently install one).
//
// Platform differences (credential source, directory resolution) are implemented by files with build tags; this file only holds
// the pure logic shared by both ends: directory resolution, HTTP download, zip extraction and overwrite, and version reading.

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"
	"time"

	"haijunbot-daemon/internal/proxy"
)

// BrowserExtDirName is the fixed local directory name of the extension (under ~/.haijunbot).
//
// Deliberately not split by version: the requirement is to "extract and overwrite the original directory", and the browser
// loads that directory path, so once the path changes the user would have to re-select the directory; therefore the path is kept constant.
const BrowserExtDirName = "browser_extension"

// browserExtDownloadTimeout is the overall timeout for downloading the extension zip.
//
// The extension source contains some JS/HTML and is usually tens of KB after compression; 60s is enough to cover slow networks,
// while avoiding the daemon hanging for a long time when the gateway is unresponsive.
const browserExtDownloadTimeout = 60 * time.Second

// browserExtMaxZipBytes is the maximum number of bytes of the zip allowed to be downloaded (64 MiB).
//
// The extension source is far smaller than this value; the limit is set to prevent an abnormal response (such as a gateway error page
// mistaken for binary, or a maliciously constructed oversized response) from blowing up memory.
const browserExtMaxZipBytes = 64 << 20

// BrowserExtDir returns the local extension directory: ~/.haijunbot/browser_extension.
//
// On Windows os.UserHomeDir returns %USERPROFILE%, consistent with the existing
// ~/.haijunbot convention of config.DefaultPath.
func BrowserExtDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to determine the user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", BrowserExtDirName), nil
}

// DownloadBrowserExtZip downloads the extension zip package from the gateway.
//
// gateway looks like http://127.0.0.1:8000 or https://hjb-ai.cn (the trailing slash is optional);
// token is the gateway JWT, sent as Authorization: Bearer.
func DownloadBrowserExtZip(gateway, token string) ([]byte, error) {
	gateway = strings.TrimRight(strings.TrimSpace(gateway), "/")
	if gateway == "" {
		return nil, fmt.Errorf("the gateway address is empty, cannot download the extension package")
	}
	if strings.TrimSpace(token) == "" {
		return nil, fmt.Errorf("gateway %s has no available Token, cannot download the extension package", gateway)
	}

	url := gateway + "/api/browser-ext/download"
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to build the download request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	client := &http.Client{Timeout: browserExtDownloadTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to download the extension package (%s): %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		// Read a small amount of the response body for troubleshooting (such as a JSON error message returned by the gateway).
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("failed to download the extension package (HTTP %d): %s",
			resp.StatusCode, strings.TrimSpace(string(body)))
	}

	limited := io.LimitReader(resp.Body, browserExtMaxZipBytes+1)
	data, err := io.ReadAll(limited)
	if err != nil {
		return nil, fmt.Errorf("failed to read the extension package response: %w", err)
	}
	if len(data) > browserExtMaxZipBytes {
		return nil, fmt.Errorf("the extension package exceeds the size limit of %d bytes", browserExtMaxZipBytes)
	}
	if len(data) == 0 {
		return nil, fmt.Errorf("the gateway returned an empty extension package")
	}
	return data, nil
}

// httpGetJSON makes a Token-bearing GET request to the gateway and parses the JSON response body.
//
// Reused by lightweight interfaces such as version queries; when not 200 it returns an error containing the status code and a response snippet.
func httpGetJSON(gateway, apiPath, token string) (map[string]any, error) {
	gateway = strings.TrimRight(strings.TrimSpace(gateway), "/")
	if gateway == "" {
		return nil, fmt.Errorf("the gateway address is empty")
	}
	if strings.TrimSpace(token) == "" {
		return nil, fmt.Errorf("gateway %s has no available Token", gateway)
	}

	url := gateway + apiPath
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to build the request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)

	client := &http.Client{Timeout: browserExtDownloadTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request to %s failed: %w", url, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("failed to read the response for %s: %w", url, err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("request to %s failed (HTTP %d): %s",
			url, resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var parsed map[string]any
	if err := json.Unmarshal(body, &parsed); err != nil {
		return nil, fmt.Errorf("failed to parse the response for %s: %w", url, err)
	}
	return parsed, nil
}

// ExtractBrowserExtZip extracts the extension zip and overwrites it into destDir.
//
// It adopts the strategy of "first extract to a sibling temp directory, and after validation replace the whole thing", guaranteeing:
//   - a mid-way failure does not leave a half-finished directory (the original directory remains usable);
//   - old-version files are cleaned up, so deleted files do not linger.
//
// Safety checks:
//   - reject absolute paths and entries containing ".." (to prevent path traversal writing outside the target directory);
//   - reject symbolic link entries (a symlink in a zip can point anywhere);
//   - after extraction, manifest.json must exist, otherwise the package is treated as an invalid extension.
//
// Returns the number of extracted files.
func ExtractBrowserExtZip(data []byte, destDir string) (int, error) {
	if destDir == "" {
		return 0, fmt.Errorf("the target directory is empty")
	}
	reader, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return 0, fmt.Errorf("the extension package is not a valid zip: %w", err)
	}

	parent := filepath.Dir(destDir)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return 0, fmt.Errorf("failed to create the parent directory %s: %w", parent, err)
	}
	tmpDir, err := os.MkdirTemp(parent, ".browser_extension_tmp_")
	if err != nil {
		return 0, fmt.Errorf("failed to create the temp directory: %w", err)
	}
	// After a successful replacement tmpDir no longer exists, so RemoveAll is idempotent; on failure it is responsible for cleanup.
	defer os.RemoveAll(tmpDir)

	count, err := extractZipEntries(reader, tmpDir)
	if err != nil {
		return 0, err
	}

	manifestPath := filepath.Join(tmpDir, "manifest.json")
	if info, statErr := os.Stat(manifestPath); statErr != nil || info.IsDir() {
		return 0, fmt.Errorf("the extension package is missing manifest.json and is not a valid extension directory")
	}

	if err := replaceDir(tmpDir, destDir); err != nil {
		return 0, err
	}
	return count, nil
}

// extractZipEntries extracts the zip entries into targetDir and returns the number of extracted files.
//
// Directory entries are created explicitly; for file entries, parent directories are created as needed before writing.
func extractZipEntries(reader *zip.Reader, targetDir string) (int, error) {
	count := 0
	for _, entry := range reader.File {
		rel, err := safeZipEntryPath(entry.Name)
		if err != nil {
			return 0, err
		}
		if rel == "" {
			continue
		}
		dest := filepath.Join(targetDir, filepath.FromSlash(rel))

		if entry.FileInfo().IsDir() {
			if err := os.MkdirAll(dest, 0o755); err != nil {
				return 0, fmt.Errorf("failed to create directory %s: %w", dest, err)
			}
			continue
		}
		// Symlink entries are always rejected: an extracted link could point outside the target directory.
		if entry.Mode()&os.ModeSymlink != 0 {
			return 0, fmt.Errorf("the extension package contains a symbolic link entry %s, rejected", entry.Name)
		}

		if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
			return 0, fmt.Errorf("failed to create directory %s: %w", filepath.Dir(dest), err)
		}
		if err := writeZipEntry(entry, dest); err != nil {
			return 0, err
		}
		count++
	}
	return count, nil
}

// writeZipEntry writes a single zip entry to the dest file.
func writeZipEntry(entry *zip.File, dest string) error {
	src, err := entry.Open()
	if err != nil {
		return fmt.Errorf("failed to open extension package entry %s: %w", entry.Name, err)
	}
	defer src.Close()

	out, err := os.OpenFile(dest, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return fmt.Errorf("failed to create file %s: %w", dest, err)
	}
	if _, err := io.Copy(out, src); err != nil {
		out.Close()
		return fmt.Errorf("failed to write file %s: %w", dest, err)
	}
	if err := out.Close(); err != nil {
		return fmt.Errorf("failed to close file %s: %w", dest, err)
	}
	return nil
}

// safeZipEntryPath validates and normalizes a zip entry name, returning a relative path separated by "/".
//
// Directory entries (ending in "/") return the path with the trailing slash removed; an empty entry returns an empty string.
// Absolute paths, drive-letter paths, and paths containing ".." are always rejected.
func safeZipEntryPath(name string) (string, error) {
	cleaned := strings.ReplaceAll(name, "\\", "/")
	// Absolute-path entries are always rejected: filepath.Join ignores the prefix on some platforms, giving unpredictable behavior.
	if strings.HasPrefix(cleaned, "/") {
		return "", fmt.Errorf("the extension package contains an absolute path entry %s, rejected", name)
	}
	cleaned = strings.TrimSuffix(cleaned, "/")
	if cleaned == "" {
		return "", nil
	}
	// A drive-letter form (such as C:/xxx) is treated as an absolute path by filepath.Join on Windows.
	if len(cleaned) >= 2 && cleaned[1] == ':' {
		return "", fmt.Errorf("the extension package contains an absolute path entry %s, rejected", name)
	}
	if cleaned == ".." || strings.HasPrefix(cleaned, "../") ||
		strings.Contains(cleaned, "/../") || strings.HasSuffix(cleaned, "/..") {
		return "", fmt.Errorf("the extension package contains an out-of-bounds path entry %s, rejected", name)
	}
	// path.Clean further eliminates redundant segments such as "./", producing a canonical relative path.
	normalized := path.Clean(cleaned)
	if normalized == "." || normalized == ".." || strings.HasPrefix(normalized, "../") {
		return "", fmt.Errorf("the extension package contains an out-of-bounds path entry %s, rejected", name)
	}
	return normalized, nil
}

// replaceDir replaces destDir entirely with the contents of srcDir.
//
// It first renames destDir to a backup directory, then renames srcDir to destDir, and finally deletes the backup;
// if the second step fails, the backup is rolled back to avoid losing the target directory.
func replaceDir(srcDir, destDir string) error {
	backupDir := ""
	if _, err := os.Stat(destDir); err == nil {
		backupDir = destDir + ".bak"
		_ = os.RemoveAll(backupDir)
		if err := os.Rename(destDir, backupDir); err != nil {
			return fmt.Errorf("failed to back up the original extension directory %s: %w", destDir, err)
		}
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("failed to check the extension directory %s: %w", destDir, err)
	}

	if err := os.Rename(srcDir, destDir); err != nil {
		// Rollback: restore the backup to guarantee the original directory remains usable.
		if backupDir != "" {
			if rbErr := os.Rename(backupDir, destDir); rbErr != nil {
				return fmt.Errorf("failed to replace the extension directory: %w (and rollback failed: %v)", err, rbErr)
			}
		}
		return fmt.Errorf("failed to replace the extension directory %s: %w", destDir, err)
	}

	if backupDir != "" {
		_ = os.RemoveAll(backupDir)
	}
	return nil
}

// ReadBrowserExtVersion reads the version number from manifest.json in the specified extension directory.
//
// When the directory does not exist or reading fails, it returns an empty string and an error, leaving it to the caller to decide how to present it.
func ReadBrowserExtVersion(dir string) (string, error) {
	manifestPath := filepath.Join(dir, "manifest.json")
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		return "", fmt.Errorf("failed to read %s: %w", manifestPath, err)
	}
	var manifest struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return "", fmt.Errorf("failed to parse %s: %w", manifestPath, err)
	}
	return strings.TrimSpace(manifest.Version), nil
}

// LocalBrowserExtVersion returns the version number of the local extension directory; it returns an empty string when the directory does not exist.
//
// Difference from ReadBrowserExtVersion: this function treats "not installed" as a normal state rather than an error,
// for direct use by the status capability.
func LocalBrowserExtVersion() string {
	dir, err := BrowserExtDir()
	if err != nil {
		return ""
	}
	version, err := ReadBrowserExtVersion(dir)
	if err != nil {
		return ""
	}
	return version
}

// BrowserExtDirOrEmpty returns the local extension directory; it returns an empty string when the home directory cannot be determined.
//
// For scenarios such as logging where "a failure should not interrupt the flow".
func BrowserExtDirOrEmpty() string {
	dir, err := BrowserExtDir()
	if err != nil {
		return ""
	}
	return dir
}

// SyncBrowserExt downloads the extension package from the gateway and extracts/overwrites it into the local directory.
//
// Returns the number of extracted files and the version number after being written; it returns an empty string when reading the version
// fails (not treated as a failure, since the files were written successfully).
func SyncBrowserExt(gateway, token string) (int, string, error) {
	data, err := DownloadBrowserExtZip(gateway, token)
	if err != nil {
		return 0, "", err
	}
	dir, err := BrowserExtDir()
	if err != nil {
		return 0, "", err
	}
	count, err := ExtractBrowserExtZip(data, dir)
	if err != nil {
		return 0, "", err
	}
	version, _ := ReadBrowserExtVersion(dir)
	return count, version, nil
}
