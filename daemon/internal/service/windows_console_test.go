package service

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestWindowsExecCallSitesSetSysProcAttr statically scans all *_windows.go source files in this repository,
// ensuring every exec.Command / exec.CommandContext call site sets SysProcAttr.
//
// Background: the daemon runs as a detached process (no console) on Windows. If console programs such as powershell /
// tasklist / schtasks are started without CREATE_NO_WINDOW, Windows creates a new console window for the child process,
// showing as "a black box flashing on every capability call". This attribute only compiles under the windows
// build, so it cannot run on this machine (Linux); the source scan locks down this invariant to prevent a newly
// added exec call site from being missed in the future.
func TestWindowsExecCallSitesSetSysProcAttr(t *testing.T) {
	root := repoRootForTest(t)
	var checked int
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() {
			// Skip vendor and .git, to avoid scanning third-party code.
			base := filepath.Base(path)
			if base == "vendor" || base == ".git" {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, "_windows.go") || strings.HasSuffix(path, "_windows_test.go") {
			return nil
		}
		data, readErr := os.ReadFile(path)
		if readErr != nil {
			return readErr
		}
		lines := strings.Split(string(data), "\n")
		for i, line := range lines {
			if !strings.Contains(line, "exec.Command") {
				continue
			}
			checked++
			// SysProcAttr is allowed on the same line or within the 8 following lines (a call may span multiple argument lines).
			if !sysProcAttrNearby(lines, i, 8) {
				rel, _ := filepath.Rel(root, path)
				t.Errorf("the exec call at %s:%d does not set SysProcAttr and will pop up a console window on Windows: %s",
					rel, i+1, strings.TrimSpace(line))
			}
		}
		return nil
	})
	if err != nil {
		t.Fatalf("failed to scan the source code: %v", err)
	}
	if checked == 0 {
		t.Fatal("no exec call site was scanned; the test may be broken (wrong path detection)")
	}
}

// sysProcAttrNearby reports whether a SysProcAttr assignment appears within offset lines starting at lines[start].
func sysProcAttrNearby(lines []string, start, offset int) bool {
	end := start + offset
	if end >= len(lines) {
		end = len(lines) - 1
	}
	for i := start; i <= end; i++ {
		if strings.Contains(lines[i], "SysProcAttr") {
			return true
		}
	}
	return false
}

// repoRootForTest walks up from the directory of the test file to find the repository root containing daemon/go.mod.
func repoRootForTest(t *testing.T) string {
	t.Helper()
	dir, err := os.Getwd()
	if err != nil {
		t.Fatalf("failed to get the working directory: %v", err)
	}
	for {
		if _, statErr := os.Stat(filepath.Join(dir, "go.mod")); statErr == nil {
			// The current directory is the daemon module root; its parent is the repository root.
			return filepath.Dir(dir)
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			t.Fatal("no directory containing go.mod was found")
		}
		dir = parent
	}
}
