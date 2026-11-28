package selfupdate

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestParseUpdateInfo_NotAvailable verifies that raw=nil / available=false return ErrNotAvailable.
func TestParseUpdateInfo_NotAvailable(t *testing.T) {
	if _, err := ParseUpdateInfo(nil); !errors.Is(err, ErrNotAvailable) {
		t.Fatalf("nil should return ErrNotAvailable, got %v", err)
	}
	if _, err := ParseUpdateInfo(map[string]any{"available": false}); !errors.Is(err, ErrNotAvailable) {
		t.Fatalf("available=false should return ErrNotAvailable, got %v", err)
	}
}

// TestParseUpdateInfo_OK verifies that normal fields can be parsed and URL/sha256 are normalized.
func TestParseUpdateInfo_OK(t *testing.T) {
	raw := map[string]any{
		"available":       true,
		"latest_version":  "v1.2.0",
		"current_version": "v1.1.0",
		"url":             "  https://github.com/o/r/releases/download/v1.2.0/a.tar.gz  ",
		"sha256":          "  ABCDEF  ",
		"size":            float64(1234),
		"asset":           "a.tar.gz",
	}
	info, err := ParseUpdateInfo(raw)
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}
	if info.LatestVersion != "v1.2.0" || info.CurrentVersion != "v1.1.0" {
		t.Fatalf("version fields wrong: %+v", info)
	}
	if info.URL != "https://github.com/o/r/releases/download/v1.2.0/a.tar.gz" {
		t.Fatalf("URL was not trimmed: %q", info.URL)
	}
	if info.SHA256 != "abcdef" {
		t.Fatalf("sha256 was not lowercased/trimmed: %q", info.SHA256)
	}
	if info.Size != 1234 {
		t.Fatalf("size parsed wrong: %d", info.Size)
	}
}

// TestParseUpdateInfo_MissingURL verifies that available=true but without url errors out.
func TestParseUpdateInfo_MissingURL(t *testing.T) {
	if _, err := ParseUpdateInfo(map[string]any{"available": true}); err == nil {
		t.Fatal("a missing url should error out")
	}
}

// TestValidateDownloadURL verifies the download address allowlist and https constraints.
func TestValidateDownloadURL(t *testing.T) {
	ok := []string{
		"https://github.com/o/r/releases/download/v1/a.tar.gz",
		"https://objects.githubusercontent.com/xxx/a.tar.gz",
	}
	for _, u := range ok {
		if _, err := ValidateDownloadURL(u); err != nil {
			t.Errorf("should pass: %s, err=%v", u, err)
		}
	}
	bad := []string{
		"http://github.com/o/r/a.tar.gz",       // not https
		"https://evil.com/a.tar.gz",            // not in the allowlist
		"https://github.com.evil.com/a.tar.gz", // disguised domain
		"ftp://github.com/a.tar.gz",            // not http(s)
		"",
	}
	for _, u := range bad {
		if _, err := ValidateDownloadURL(u); err == nil {
			t.Errorf("should reject: %s", u)
		}
	}
}

// TestDownload_SHA256OK verifies a normal download with a successful sha256 check (including User-Agent).
func TestDownload_SHA256OK(t *testing.T) {
	payload := []byte("hello-haijunbot-daemon")
	sum := sha256.Sum256(payload)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasPrefix(r.Header.Get("User-Agent"), "haijunbot-daemon/") {
			t.Errorf("User-Agent missing or wrong: %q", r.Header.Get("User-Agent"))
		}
		_, _ = w.Write(payload)
	}))
	defer srv.Close()

	// httptest listens on 127.0.0.1; it must be temporarily added to the allowlist to pass the check.
	setExtraAllowedHosts("127.0.0.1")
	defer setExtraAllowedHosts()
	setAllowInsecureForTest(true)
	defer setAllowInsecureForTest(false)

	dest := filepath.Join(t.TempDir(), "out.bin")
	if err := Download(nil, "test", srv.URL, dest, hex.EncodeToString(sum[:])); err != nil {
		t.Fatalf("download should succeed: %v", err)
	}
	got, err := os.ReadFile(dest)
	if err != nil || !bytes.Equal(got, payload) {
		t.Fatalf("download content mismatch: %q err=%v", got, err)
	}
}

// TestDownload_SHA256Mismatch verifies that a sha256 mismatch errors out and leaves no target file behind.
func TestDownload_SHA256Mismatch(t *testing.T) {
	payload := []byte("hello-haijunbot-daemon")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(payload)
	}))
	defer srv.Close()
	setExtraAllowedHosts("127.0.0.1")
	defer setExtraAllowedHosts()
	setAllowInsecureForTest(true)
	defer setAllowInsecureForTest(false)

	dest := filepath.Join(t.TempDir(), "out.bin")
	if err := Download(nil, "test", srv.URL, dest, "deadbeef"); err == nil {
		t.Fatal("a sha256 mismatch should error out")
	}
	if _, err := os.Stat(dest); !os.IsNotExist(err) {
		t.Fatalf("the target file should not be left behind after verification failure: %v", err)
	}
}

// TestDownload_SkipSHA256 verifies that empty wantSHA256 skips verification and lands on disk successfully.
func TestDownload_SkipSHA256(t *testing.T) {
	payload := []byte("no-checksum")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(payload)
	}))
	defer srv.Close()
	setExtraAllowedHosts("127.0.0.1")
	defer setExtraAllowedHosts()
	setAllowInsecureForTest(true)
	defer setAllowInsecureForTest(false)

	dest := filepath.Join(t.TempDir(), "out.bin")
	if err := Download(nil, "test", srv.URL, dest, ""); err != nil {
		t.Fatalf("download should succeed when verification is skipped: %v", err)
	}
}

// TestVerifySHA256 verifies the lower-level sha256 verification function.
func TestVerifySHA256(t *testing.T) {
	payload := []byte("hello-haijunbot-daemon")
	sum := sha256.Sum256(payload)
	if err := verifySHA256(bytes.NewReader(payload), hex.EncodeToString(sum[:])); err != nil {
		t.Fatalf("sha256 verification should pass: %v", err)
	}
	if err := verifySHA256(bytes.NewReader(payload), "deadbeef"); err == nil {
		t.Fatal("a sha256 mismatch should error out")
	}
}

// TestExtractBinary_TarGz verifies extracting the target file from a tar.gz.
func TestExtractBinary_TarGz(t *testing.T) {
	dir := t.TempDir()
	archive := filepath.Join(dir, "a.tar.gz")
	want := []byte("binary-content-targz")
	writeTarGz(t, archive, "haijunbot-daemon", want)

	out := filepath.Join(dir, "out", "haijunbot-daemon")
	if err := ExtractBinary(archive, out, "haijunbot-daemon"); err != nil {
		t.Fatalf("unpack failed: %v", err)
	}
	got, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("failed to read the unpack result: %v", err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("content mismatch: %q", got)
	}
}

// TestExtractBinary_Zip verifies extracting the target file from a zip (including a directory prefix).
func TestExtractBinary_Zip(t *testing.T) {
	dir := t.TempDir()
	archive := filepath.Join(dir, "a.zip")
	want := []byte("binary-content-zip")
	writeZip(t, archive, "sub/dir/haijunbot-daemon.exe", want)

	out := filepath.Join(dir, "out", "haijunbot-daemon.exe")
	if err := ExtractBinary(archive, out, "haijunbot-daemon.exe"); err != nil {
		t.Fatalf("unpack failed: %v", err)
	}
	got, err := os.ReadFile(out)
	if err != nil {
		t.Fatalf("failed to read the unpack result: %v", err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("content mismatch: %q", got)
	}
}

// TestExtractBinary_NotFound verifies that a missing target file in the archive errors out.
func TestExtractBinary_NotFound(t *testing.T) {
	dir := t.TempDir()
	archive := filepath.Join(dir, "a.tar.gz")
	writeTarGz(t, archive, "other-file", []byte("x"))
	out := filepath.Join(dir, "out", "haijunbot-daemon")
	if err := ExtractBinary(archive, out, "haijunbot-daemon"); err == nil {
		t.Fatal("a missing target file should error out")
	}
}

// TestExtractBinary_Unsupported verifies that an unsupported extension errors out.
func TestExtractBinary_Unsupported(t *testing.T) {
	if err := ExtractBinary("a.rar", "out", "haijunbot-daemon"); err == nil {
		t.Fatal("an unsupported format should error out")
	}
}

// writeTarGz generates a tar.gz containing a single file.
func writeTarGz(t *testing.T, path, name string, content []byte) {
	t.Helper()
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := writeTarGzTo(t, f, name, content); err != nil {
		t.Fatal(err)
	}
}

// writeTarGzToBuffer writes a single-file tar.gz to an in-memory buffer (for httptest to return directly).
func writeTarGzToBuffer(t *testing.T, buf *bytes.Buffer, name string, content []byte) {
	t.Helper()
	if err := writeTarGzTo(t, buf, name, content); err != nil {
		t.Fatal(err)
	}
}

// writeTarGzTo writes a single-file tar.gz to any io.Writer.
func writeTarGzTo(t *testing.T, w io.Writer, name string, content []byte) error {
	t.Helper()
	gz := gzip.NewWriter(w)
	tw := tar.NewWriter(gz)
	if err := tw.WriteHeader(&tar.Header{
		Name:     name,
		Mode:     0o755,
		Size:     int64(len(content)),
		Typeflag: tar.TypeReg,
	}); err != nil {
		return err
	}
	if _, err := tw.Write(content); err != nil {
		return err
	}
	if err := tw.Close(); err != nil {
		return err
	}
	return gz.Close()
}

// writeZip generates a zip containing a single file.
func writeZip(t *testing.T, path, name string, content []byte) {
	t.Helper()
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	zw := zip.NewWriter(f)
	w, err := zw.Create(name)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := w.Write(content); err != nil {
		t.Fatal(err)
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
}
