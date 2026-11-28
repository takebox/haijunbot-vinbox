package selfupdate

import (
	"fmt"
	"os"
	"path/filepath"
)

// Apply replaces the current executable at targetPath with the new executable at newBinaryPath.
//
// Semantics (unified across platforms):
//   - If newBinaryPath and targetPath are not in the same directory, first copy to a temporary file
//     in the same directory as targetPath (only the same filesystem guarantees rename atomicity);
//   - Platform differences are implemented by replaceExecutable (see apply_linux.go / apply_windows.go);
//   - After success newBinaryPath may have been moved/deleted (Linux uses rename).
//
// Note: this function is not responsible for restarting the service; it only does "replace the on-disk executable with the new version".
func Apply(newBinaryPath, targetPath string) error {
	if newBinaryPath == "" || targetPath == "" {
		return fmt.Errorf("incomplete replacement arguments: src=%q dst=%q", newBinaryPath, targetPath)
	}
	if _, err := os.Stat(newBinaryPath); err != nil {
		return fmt.Errorf("new executable not available: %w", err)
	}

	// Uniformly place it in a temporary file in the same directory as targetPath, ensuring the same filesystem as the target (atomic rename).
	tmpPath := filepath.Join(filepath.Dir(targetPath), "."+filepath.Base(targetPath)+".new")
	if !samePath(newBinaryPath, tmpPath) {
		if err := copyFileExecutable(newBinaryPath, tmpPath); err != nil {
			return err
		}
	}
	if err := os.Chmod(tmpPath, 0o755); err != nil {
		return fmt.Errorf("failed to set executable permission: %w", err)
	}
	return replaceExecutable(tmpPath, targetPath)
}

// copyFileExecutable copies src to dst (overwriting) and sets the executable permission.
func copyFileExecutable(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("failed to open new executable: %w", err)
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o755)
	if err != nil {
		return fmt.Errorf("failed to create temporary executable: %w", err)
	}
	if _, err := out.ReadFrom(in); err != nil {
		out.Close()
		_ = os.Remove(dst)
		return fmt.Errorf("failed to copy new executable: %w", err)
	}
	if err := out.Close(); err != nil {
		_ = os.Remove(dst)
		return fmt.Errorf("failed to close temporary executable: %w", err)
	}
	return nil
}

// samePath determines whether two paths point to the same file (case-insensitive on Windows).
func samePath(a, b string) bool {
	if a == "" || b == "" {
		return false
	}
	if isWindows() {
		return filepath.Clean(lower(a)) == filepath.Clean(lower(b))
	}
	return filepath.Clean(a) == filepath.Clean(b)
}
