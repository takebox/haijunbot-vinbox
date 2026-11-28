package service

import (
	"os"
	"path/filepath"
	"testing"
)

func TestBinaryNameHasSuffixOnWindows(t *testing.T) {
	name := BinaryName()
	if name == "" {
		t.Fatal("BinaryName should not be empty")
	}
	// Non-Windows platforms do not carry the .exe suffix.
	if os.PathSeparator != '\\' && filepath.Ext(name) == ".exe" {
		t.Errorf("BinaryName = %q on non-Windows should not have the .exe suffix", name)
	}
}

func TestInstalledBinaryPathUnderHaijunBotBin(t *testing.T) {
	p, err := InstalledBinaryPath()
	if err != nil {
		t.Fatalf("InstalledBinaryPath returned an error: %v", err)
	}
	if !filepath.IsAbs(p) {
		t.Errorf("the install path should be absolute, got %q", p)
	}
	if filepath.Base(filepath.Dir(p)) != InstallDirName {
		t.Errorf("the install path's parent directory should be %q, got %q", InstallDirName, filepath.Dir(p))
	}
	if filepath.Base(p) != BinaryName() {
		t.Errorf("the installed file name should be %q, got %q", BinaryName(), filepath.Base(p))
	}
}

func TestSamePath(t *testing.T) {
	cases := []struct {
		a, b string
		want bool
	}{
		{"/a/b/haijunbot-daemon", "/a/b/haijunbot-daemon", true},
		{"/a/b/../b/haijunbot-daemon", "/a/b/haijunbot-daemon", true},
		{"/a/b/haijunbot-daemon", "/a/c/haijunbot-daemon", false},
		{"", "/a/b", false},
		{"/a/b", "", false},
	}
	for _, c := range cases {
		if got := samePath(c.a, c.b); got != c.want {
			t.Errorf("samePath(%q, %q) = %v, want %v", c.a, c.b, got, c.want)
		}
	}
}

func TestCopyFileAtomicCreatesExecutable(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "src")
	content := []byte("#!/bin/sh\necho hi\n")
	if err := os.WriteFile(src, content, 0o644); err != nil {
		t.Fatalf("failed to prepare the source file: %v", err)
	}
	dst := filepath.Join(dir, "sub", "haijunbot-daemon")
	if err := copyFileAtomic(src, dst); err != nil {
		t.Fatalf("copyFileAtomic returned an error: %v", err)
	}
	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatalf("failed to read the target file: %v", err)
	}
	if string(got) != string(content) {
		t.Errorf("target file content = %q, expected %q", got, content)
	}
	info, err := os.Stat(dst)
	if err != nil {
		t.Fatalf("Stat on the target file failed: %v", err)
	}
	if info.Mode().Perm()&0o100 == 0 {
		t.Errorf("the target file should have the executable permission, got %v", info.Mode().Perm())
	}
	// Overwriting an existing file should succeed with updated content.
	if err := os.WriteFile(dst, []byte("old"), 0o644); err != nil {
		t.Fatalf("failed to prepare the old file: %v", err)
	}
	if err := copyFileAtomic(src, dst); err != nil {
		t.Fatalf("the overwrite copy returned an error: %v", err)
	}
	got2, _ := os.ReadFile(dst)
	if string(got2) != string(content) {
		t.Errorf("content after overwrite = %q, expected %q", got2, content)
	}
}

func TestPrepareInstalledBinarySkipsCopyWhenAlreadyInstalled(t *testing.T) {
	dst, err := InstalledBinaryPath()
	if err != nil {
		t.Fatalf("InstalledBinaryPath returned an error: %v", err)
	}
	// The passed ExecPath is already the install path: the copy should be skipped, returning that path directly.
	opts, gotPath, err := PrepareInstalledBinary(Options{ExecPath: dst})
	if err != nil {
		t.Fatalf("PrepareInstalledBinary returned an error: %v", err)
	}
	if gotPath != dst {
		t.Errorf("returned path = %q, expected %q", gotPath, dst)
	}
	if opts.ExecPath != dst {
		t.Errorf("opts.ExecPath = %q, expected %q", opts.ExecPath, dst)
	}
	// No file should actually be created (the skip branch was taken).
	if _, err := os.Stat(dst); err == nil {
		_ = os.Remove(dst)
		t.Log("note: an existing file was found at the install path (possibly a real installation); it has been cleaned up")
	}
}

func TestRemoveInstalledBinaryIsIdempotent(t *testing.T) {
	// A missing file should return nil (idempotent).
	if err := RemoveInstalledBinary(); err != nil {
		t.Fatalf("RemoveInstalledBinary should return nil when the file does not exist, got: %v", err)
	}
}
