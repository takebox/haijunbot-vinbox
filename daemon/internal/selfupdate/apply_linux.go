//go:build linux

package selfupdate

import (
	"fmt"
	"os"
)

// isWindows reports whether the current platform is Windows (always false on the Linux implementation).
func isWindows() bool { return false }

// lower returns the lowercase form of s (for Windows path comparison; returns as-is on Linux).
func lower(s string) string { return s }

// replaceExecutable directly renames over the target on Linux.
//
// Why this works: Linux allows replacing an executable that is running—the old process keeps holding the deleted inode,
// while a new process reads the new file on startup. A same-directory rename is atomic, so there is no "half an executable".
func replaceExecutable(tmpPath, targetPath string) error {
	if err := os.Rename(tmpPath, targetPath); err != nil {
		// Clean up the temporary file when rename fails, to avoid leftovers.
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to replace executable: %w", err)
	}
	// Ensure the executable bit (rename preserves the original permissions; here we double-check).
	_ = os.Chmod(targetPath, 0o755)
	return nil
}
