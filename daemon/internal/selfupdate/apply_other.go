//go:build !linux && !windows

package selfupdate

import (
	"fmt"
	"os"
	"runtime"
)

// isWindows reports whether the current platform is Windows (always false on other platforms).
func isWindows() bool { return false }

// lower returns the lowercase form of s (returned as-is on other platforms).
func lower(s string) string { return s }

// replaceExecutable best-effort attempts a rename on other platforms (e.g. darwin).
//
// This project only guarantees Windows and Linux; this implementation exists only so the code compiles on darwin,
// and does not guarantee the update flow works on that platform.
func replaceExecutable(tmpPath, targetPath string) error {
	if err := os.Rename(tmpPath, targetPath); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to replace executable (platform %s unsupported): %w", runtime.GOOS, err)
	}
	_ = os.Chmod(targetPath, 0o755)
	return nil
}
