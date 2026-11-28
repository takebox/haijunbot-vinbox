package selfupdate

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

// TestRun_EndToEnd verifies the full flow: download → verify → unpack → replace (without restart).
//
// httptest serves the tar.gz artifact, and 127.0.0.1 is temporarily added to the allowlist.
func TestRun_EndToEnd(t *testing.T) {
	// Build a tar.gz artifact embedding an executable named haijunbot-daemon.
	binaryContent := []byte("fake-daemon-binary-v2")
	var buf bytes.Buffer
	writeTarGzToBuffer(t, &buf, binaryName(), binaryContent)
	payload := buf.Bytes()
	sum := sha256.Sum256(payload)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(payload)
	}))
	defer srv.Close()
	setExtraAllowedHosts("127.0.0.1")
	defer setExtraAllowedHosts()
	setAllowInsecureForTest(true)
	defer setAllowInsecureForTest(false)

	dir := t.TempDir()
	target := filepath.Join(dir, "bin", binaryName())
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(target, []byte("old-daemon"), 0o755); err != nil {
		t.Fatal(err)
	}

	var states []UpdateState
	err := Run(Options{
		Info: UpdateInfo{
			Available:     true,
			LatestVersion: "v2.0.0",
			URL:           srv.URL + "/" + binaryName() + ".tar.gz",
			SHA256:        hex.EncodeToString(sum[:]),
			Asset:         binaryName() + ".tar.gz",
		},
		Version:    "v1.0.0",
		TargetPath: target,
		WorkDir:    filepath.Join(dir, "work"),
		Restart:    false,
		Report: func(s UpdateState, _ string) {
			states = append(states, s)
		},
	})
	if err != nil {
		t.Fatalf("Run failed: %v", err)
	}

	got, err := os.ReadFile(target)
	if err != nil {
		t.Fatalf("failed to read the target: %v", err)
	}
	if !bytes.Equal(got, binaryContent) {
		t.Fatalf("target not updated to the new version: %q", got)
	}
	// Should at least report downloading/verifying/applying/done.
	if len(states) == 0 || states[len(states)-1] != StateDone {
		t.Fatalf("unexpected status reports: %v", states)
	}
}

// TestRun_NotAvailable verifies that Info.Available=false returns ErrNotAvailable.
func TestRun_NotAvailable(t *testing.T) {
	if err := Run(Options{Info: UpdateInfo{Available: false}, TargetPath: "x"}); err == nil {
		t.Fatal("no available update should error out")
	}
}

// TestRun_NoTarget verifies that a missing target path errors out.
func TestRun_NoTarget(t *testing.T) {
	if err := Run(Options{Info: UpdateInfo{Available: true}}); err == nil {
		t.Fatal("a missing target path should error out")
	}
}

// TestRun_DownloadFails verifies that a download failure reports failed and returns an error.
func TestRun_DownloadFails(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	setExtraAllowedHosts("127.0.0.1")
	defer setExtraAllowedHosts()
	setAllowInsecureForTest(true)
	defer setAllowInsecureForTest(false)

	var last UpdateState
	err := Run(Options{
		Info: UpdateInfo{
			Available: true,
			URL:       srv.URL + "/" + binaryName() + ".tar.gz",
		},
		Version:    "v1",
		TargetPath: filepath.Join(t.TempDir(), binaryName()),
		WorkDir:    filepath.Join(t.TempDir(), "work"),
		Report:     func(s UpdateState, _ string) { last = s },
	})
	if err == nil {
		t.Fatal("a download failure should return an error")
	}
	if last != StateFailed {
		t.Fatalf("should report failed, got %q", last)
	}
}
