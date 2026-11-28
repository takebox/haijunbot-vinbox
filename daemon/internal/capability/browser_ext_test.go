package capability

// This file tests the browser extension package extraction and version reading logic (cross-platform, no build tag).
//
// The tests construct zip files on the fly with archive/zip, without depending on the network or a real gateway; the download-related
// network paths are covered via httptest (the success/failure branches of DownloadBrowserExtZip).

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// zipEntry describes an entry to be written into a test zip.
type zipEntry struct {
	name  string
	body  string
	isDir bool
	// When mode is non-zero, it is used to set the entry's permission bits (such as os.ModeSymlink).
	mode os.FileMode
}

// buildZip constructs a zip byte stream from entries.
func buildZip(t *testing.T, entries []zipEntry) []byte {
	t.Helper()
	var buf bytes.Buffer
	w := zip.NewWriter(&buf)
	for _, e := range entries {
		hdr := &zip.FileHeader{Name: e.name}
		if e.isDir {
			hdr.Method = zip.Store
			hdr.SetMode(os.ModeDir | 0o755)
		} else if e.mode != 0 {
			hdr.Method = zip.Store
			hdr.SetMode(e.mode)
		} else {
			hdr.Method = zip.Deflate
			hdr.SetMode(0o644)
		}
		fw, err := w.CreateHeader(hdr)
		if err != nil {
			t.Fatalf("failed to create zip entry %s: %v", e.name, err)
		}
		if !e.isDir {
			if _, err := fw.Write([]byte(e.body)); err != nil {
				t.Fatalf("failed to write zip entry %s: %v", e.name, err)
			}
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("failed to close the zip writer: %v", err)
	}
	return buf.Bytes()
}

// manifestJSON returns the manifest.json content for the specified version.
func manifestJSON(version string) string {
	raw, _ := json.Marshal(map[string]any{
		"manifest_version": 3,
		"name":             "HaijunBot Test Extension",
		"version":          version,
	})
	return string(raw)
}

// TestExtractBrowserExtZipOverwrite verifies normal extraction and overwrite: old files are cleaned up, new files are written, and the returned count is correct.
func TestExtractBrowserExtZipOverwrite(t *testing.T) {
	dest := filepath.Join(t.TempDir(), "browser_extension")

	// First place an old version directory containing a stale file that should be cleaned up.
	if err := os.MkdirAll(dest, 0o755); err != nil {
		t.Fatalf("failed to prepare the old directory: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dest, "stale.js"), []byte("old"), 0o644); err != nil {
		t.Fatalf("failed to write the stale file: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dest, "manifest.json"), []byte(manifestJSON("1.0.0")), 0o644); err != nil {
		t.Fatalf("failed to write the old manifest: %v", err)
	}

	data := buildZip(t, []zipEntry{
		{name: "manifest.json", body: manifestJSON("2.0.0")},
		{name: "background.js", body: "console.log('bg')"},
		{name: "content/", isDir: true},
		{name: "content/inject.js", body: "console.log('inject')"},
	})

	count, err := ExtractBrowserExtZip(data, dest)
	if err != nil {
		t.Fatalf("extraction failed: %v", err)
	}
	if count != 3 {
		t.Fatalf("the number of extracted files should be 3, actual %d", count)
	}

	// The stale file must be cleaned up (whole-directory replacement semantics).
	if _, err := os.Stat(filepath.Join(dest, "stale.js")); !os.IsNotExist(err) {
		t.Fatalf("the stale file stale.js should be cleaned up, err=%v", err)
	}
	// The new files must exist.
	for _, rel := range []string{"manifest.json", "background.js", "content/inject.js"} {
		if _, err := os.Stat(filepath.Join(dest, rel)); err != nil {
			t.Fatalf("expected file %s does not exist: %v", rel, err)
		}
	}
	// No temp directory may remain.
	parent := filepath.Dir(dest)
	entries, err := os.ReadDir(parent)
	if err != nil {
		t.Fatalf("failed to read the parent directory: %v", err)
	}
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".browser_extension_tmp_") || strings.HasSuffix(e.Name(), ".bak") {
			t.Fatalf("leftover temp/backup directory: %s", e.Name())
		}
	}

	version, err := ReadBrowserExtVersion(dest)
	if err != nil {
		t.Fatalf("failed to read the version: %v", err)
	}
	if version != "2.0.0" {
		t.Fatalf("the version should be 2.0.0, actual %q", version)
	}
}

// TestExtractBrowserExtZipRejectsTraversal verifies that path traversal entries are rejected and the original directory is not damaged.
func TestExtractBrowserExtZipRejectsTraversal(t *testing.T) {
	cases := []struct {
		name  string
		entry string
	}{
		{"parent directory traversal", "../evil.js"},
		{"nested traversal", "content/../../evil.js"},
		{"absolute path", "/etc/evil.js"},
		{"drive-letter path", "C:/Windows/evil.js"},
		{"backslash traversal", `..\evil.js`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			dest := filepath.Join(t.TempDir(), "browser_extension")
			if err := os.MkdirAll(dest, 0o755); err != nil {
				t.Fatalf("failed to prepare the old directory: %v", err)
			}
			oldManifest := manifestJSON("1.0.0")
			if err := os.WriteFile(filepath.Join(dest, "manifest.json"), []byte(oldManifest), 0o644); err != nil {
				t.Fatalf("failed to write the old manifest: %v", err)
			}

			data := buildZip(t, []zipEntry{
				{name: "manifest.json", body: manifestJSON("2.0.0")},
				{name: tc.entry, body: "pwned"},
			})

			if _, err := ExtractBrowserExtZip(data, dest); err == nil {
				t.Fatalf("the out-of-bounds entry %q should be rejected, but extraction succeeded", tc.entry)
			}
			// The original directory must remain usable (the old manifest was not replaced).
			raw, err := os.ReadFile(filepath.Join(dest, "manifest.json"))
			if err != nil {
				t.Fatalf("the original manifest was lost: %v", err)
			}
			if string(raw) != oldManifest {
				t.Fatalf("the original manifest was damaged: %s", string(raw))
			}
		})
	}
}

// TestExtractBrowserExtZipRejectsSymlink verifies that symbolic link entries are rejected.
func TestExtractBrowserExtZipRejectsSymlink(t *testing.T) {
	dest := filepath.Join(t.TempDir(), "browser_extension")
	data := buildZip(t, []zipEntry{
		{name: "manifest.json", body: manifestJSON("2.0.0")},
		{name: "link.js", body: "/etc/passwd", mode: os.ModeSymlink | 0o777},
	})

	if _, err := ExtractBrowserExtZip(data, dest); err == nil {
		t.Fatalf("the symbolic link entry should be rejected, but extraction succeeded")
	}
	if _, err := os.Stat(dest); !os.IsNotExist(err) {
		t.Fatalf("the target directory should not be created after a failed extraction, err=%v", err)
	}
}

// TestExtractBrowserExtZipRequiresManifest verifies that a missing manifest.json reports an error without damaging the original directory.
func TestExtractBrowserExtZipRequiresManifest(t *testing.T) {
	dest := filepath.Join(t.TempDir(), "browser_extension")
	if err := os.MkdirAll(dest, 0o755); err != nil {
		t.Fatalf("failed to prepare the old directory: %v", err)
	}
	oldManifest := manifestJSON("1.0.0")
	if err := os.WriteFile(filepath.Join(dest, "manifest.json"), []byte(oldManifest), 0o644); err != nil {
		t.Fatalf("failed to write the old manifest: %v", err)
	}

	data := buildZip(t, []zipEntry{
		{name: "background.js", body: "console.log('bg')"},
	})

	if _, err := ExtractBrowserExtZip(data, dest); err == nil {
		t.Fatalf("a missing manifest.json should report an error, but extraction succeeded")
	}
	raw, err := os.ReadFile(filepath.Join(dest, "manifest.json"))
	if err != nil {
		t.Fatalf("the original manifest was lost: %v", err)
	}
	if string(raw) != oldManifest {
		t.Fatalf("the original manifest was damaged: %s", string(raw))
	}
}

// TestExtractBrowserExtZipInvalidZip verifies that non-zip data is rejected.
func TestExtractBrowserExtZipInvalidZip(t *testing.T) {
	dest := filepath.Join(t.TempDir(), "browser_extension")
	if _, err := ExtractBrowserExtZip([]byte("not a zip"), dest); err == nil {
		t.Fatalf("non-zip data should be rejected")
	}
	if _, err := ExtractBrowserExtZip(nil, ""); err == nil {
		t.Fatalf("an empty target directory should be rejected")
	}
}

// TestReadBrowserExtVersion verifies the normal and abnormal paths of version reading.
func TestReadBrowserExtVersion(t *testing.T) {
	dir := t.TempDir()

	// Normal path.
	if err := os.WriteFile(filepath.Join(dir, "manifest.json"), []byte(manifestJSON("5.0.5")), 0o644); err != nil {
		t.Fatalf("failed to write the manifest: %v", err)
	}
	version, err := ReadBrowserExtVersion(dir)
	if err != nil {
		t.Fatalf("failed to read the version: %v", err)
	}
	if version != "5.0.5" {
		t.Fatalf("the version should be 5.0.5, actual %q", version)
	}

	// The directory does not exist.
	if _, err := ReadBrowserExtVersion(filepath.Join(dir, "missing")); err == nil {
		t.Fatalf("it should report an error when the directory does not exist")
	}

	// The manifest is invalid JSON.
	badDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(badDir, "manifest.json"), []byte("{invalid"), 0o644); err != nil {
		t.Fatalf("failed to write the invalid manifest: %v", err)
	}
	if _, err := ReadBrowserExtVersion(badDir); err == nil {
		t.Fatalf("invalid JSON should report an error")
	}
}

// TestSafeZipEntryPath verifies entry path normalization and rejection rules.
func TestSafeZipEntryPath(t *testing.T) {
	cases := []struct {
		name    string
		input   string
		want    string
		wantErr bool
	}{
		{"ordinary file", "background.js", "background.js", false},
		{"nested file", "content/inject.js", "content/inject.js", false},
		{"directory entry", "content/", "content", false},
		{"redundant dot segments", "./content/./a.js", "content/a.js", false},
		{"empty entry", "", "", false},
		{"parent directory", "../evil.js", "", true},
		{"nested parent directory", "a/../../evil.js", "", true},
		{"absolute path", "/etc/passwd", "", true},
		{"drive letter", "C:/x.js", "", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := safeZipEntryPath(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("input %q should report an error, actual returned %q", tc.input, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("input %q should not report an error: %v", tc.input, err)
			}
			if got != tc.want {
				t.Fatalf("input %q should be %q, actual %q", tc.input, tc.want, got)
			}
		})
	}
}

// TestDownloadBrowserExtZip uses httptest to cover the success and failure branches of the download.
func TestDownloadBrowserExtZip(t *testing.T) {
	zipData := buildZip(t, []zipEntry{
		{name: "manifest.json", body: manifestJSON("9.9.9")},
	})

	mux := http.NewServeMux()
	mux.HandleFunc("/api/browser-ext/download", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer good-token" {
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"error":"bad token"}`))
			return
		}
		w.Header().Set("Content-Type", "application/zip")
		_, _ = w.Write(zipData)
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	// Success path.
	data, err := DownloadBrowserExtZip(srv.URL+"/", "good-token")
	if err != nil {
		t.Fatalf("download failed: %v", err)
	}
	if !bytes.Equal(data, zipData) {
		t.Fatalf("the downloaded content does not match the source")
	}

	// Parameter validation.
	if _, err := DownloadBrowserExtZip("", "good-token"); err == nil {
		t.Fatalf("an empty gateway should report an error")
	}
	if _, err := DownloadBrowserExtZip(srv.URL, "  "); err == nil {
		t.Fatalf("an empty Token should report an error")
	}

	// A non-200 response.
	if _, err := DownloadBrowserExtZip(srv.URL, "bad-token"); err == nil {
		t.Fatalf("an authentication failure should report an error")
	}
	if _, err := DownloadBrowserExtZip(srv.URL, "bad-token"); err != nil &&
		!strings.Contains(err.Error(), "401") {
		t.Fatalf("the error message should contain the status code 401, actual: %v", err)
	}
}

// TestHttpGetJSON covers the normal and abnormal branches of httpGetJSON.
func TestHttpGetJSON(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/ok", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"latest_version":"5.0.5"}`))
	})
	mux.HandleFunc("/api/bad", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte("boom"))
	})
	mux.HandleFunc("/api/notjson", func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("plain text"))
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	parsed, err := httpGetJSON(srv.URL, "/api/ok", "tok")
	if err != nil {
		t.Fatalf("the normal request failed: %v", err)
	}
	if parsed["latest_version"] != "5.0.5" {
		t.Fatalf("the parse result does not match: %v", parsed)
	}

	if _, err := httpGetJSON(srv.URL, "/api/bad", "tok"); err == nil {
		t.Fatalf("a 500 response should report an error")
	}
	if _, err := httpGetJSON(srv.URL, "/api/notjson", "tok"); err == nil {
		t.Fatalf("a non-JSON response should report an error")
	}
	if _, err := httpGetJSON(srv.URL, "/api/ok", ""); err == nil {
		t.Fatalf("an empty Token should report an error")
	}
}

// TestBrowserExtDirOrEmpty verifies directory resolution: normal case is non-empty and ends with browser_extension.
func TestBrowserExtDirOrEmpty(t *testing.T) {
	dir := BrowserExtDirOrEmpty()
	if dir == "" {
		t.Skip("cannot determine the user home directory, skipping")
	}
	if filepath.Base(dir) != BrowserExtDirName {
		t.Fatalf("the directory should end with %s, actual %s", BrowserExtDirName, dir)
	}
	if !strings.Contains(dir, ".haijunbot") {
		t.Fatalf("the directory should be under ~/.haijunbot, actual %s", dir)
	}
}
