package selfupdate

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

// TestApply_ReplacesTarget verifies that Apply can replace the new executable into the target path.
//
// On Linux it can be replaced directly; on Windows it also succeeds if the target is not in use (in this test the target file is not being run).
func TestApply_ReplacesTarget(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "src", "haijunbot-daemon")
	dst := filepath.Join(dir, "dst", "haijunbot-daemon")
	if err := os.MkdirAll(filepath.Dir(src), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		t.Fatal(err)
	}
	// Put an old file at the target first to ensure a replacement actually happens.
	if err := os.WriteFile(dst, []byte("old"), 0o755); err != nil {
		t.Fatal(err)
	}
	want := []byte("new-binary-content")
	if err := os.WriteFile(src, want, 0o755); err != nil {
		t.Fatal(err)
	}

	if err := Apply(src, dst); err != nil {
		t.Fatalf("Apply failed: %v", err)
	}
	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatalf("failed to read the target: %v", err)
	}
	if string(got) != string(want) {
		t.Fatalf("target content not replaced: %q", got)
	}
}

// TestApply_MissingSrc verifies that a missing source file errors out.
func TestApply_MissingSrc(t *testing.T) {
	dir := t.TempDir()
	if err := Apply(filepath.Join(dir, "nope"), filepath.Join(dir, "dst")); err == nil {
		t.Fatal("a missing source file should error out")
	}
}

// TestApply_EmptyArgs verifies that empty arguments error out.
func TestApply_EmptyArgs(t *testing.T) {
	if err := Apply("", "x"); err == nil {
		t.Fatal("an empty argument should error out")
	}
	if err := Apply("x", ""); err == nil {
		t.Fatal("an empty argument should error out")
	}
}

// TestSamePath verifies the same-path judgment (case-insensitive on Windows).
func TestSamePath(t *testing.T) {
	if !samePath("/a/b", "/a/b") {
		t.Fatal("the same path should be judged as the same file")
	}
	if samePath("/a/b", "/a/c") {
		t.Fatal("different paths should not be judged as the same file")
	}
	if samePath("", "/a") {
		t.Fatal("an empty path should not be judged as the same file")
	}
	if runtime.GOOS == "windows" {
		if !samePath(`C:\A\b`, `c:\a\B`) {
			t.Fatal("the case should be ignored on Windows")
		}
	}
}

// TestBinaryName verifies the executable file name for the current platform.
func TestBinaryName(t *testing.T) {
	name := binaryName()
	if runtime.GOOS == "windows" {
		if name != "haijunbot-daemon.exe" {
			t.Fatalf("should be haijunbot-daemon.exe on Windows, got %q", name)
		}
		return
	}
	if name != "haijunbot-daemon" {
		t.Fatalf("should be haijunbot-daemon on non-Windows, got %q", name)
	}
}
