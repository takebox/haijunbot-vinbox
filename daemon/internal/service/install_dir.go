package service

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// Install directory: copies the daemon executable to ~/.haijunbot/bin, so the location the service references is fixed
// and no longer depends on the path from which the user originally ran install (which may be moved or deleted).

// InstallDirName is the install directory name (under the .haijunbot directory in the user home).
const InstallDirName = "bin"

// BinaryName is the installed executable file name (with the .exe suffix on Windows).
func BinaryName() string {
	if runtime.GOOS == "windows" {
		return "haijunbot-daemon.exe"
	}
	return "haijunbot-daemon"
}

// InstallDir returns the absolute path of the install directory: ~/.haijunbot/bin.
func InstallDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get the user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", InstallDirName), nil
}

// InstalledBinaryPath returns the absolute path of the installed executable: ~/.haijunbot/bin/haijunbot-daemon[.exe].
func InstalledBinaryPath() (string, error) {
	dir, err := InstallDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, BinaryName()), nil
}

// samePath determines whether two paths point to the same file (ignoring case differences is especially important on Windows).
func samePath(a, b string) bool {
	if a == "" || b == "" {
		return false
	}
	if runtime.GOOS == "windows" {
		return filepath.Clean(strings.ToLower(a)) == filepath.Clean(strings.ToLower(b))
	}
	return filepath.Clean(a) == filepath.Clean(b)
}

// copyFileAtomic copies src to dst: writes a temp file in the same directory first, then renames, so an interruption does not leave a half-written file.
func copyFileAtomic(src, dst string) error {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return fmt.Errorf("failed to create the install directory: %w", err)
	}
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("failed to open the source file: %w", err)
	}
	defer in.Close()

	tmp, err := os.CreateTemp(filepath.Dir(dst), ".haijunbot-daemon-*")
	if err != nil {
		return fmt.Errorf("failed to create the temporary file: %w", err)
	}
	tmpName := tmp.Name()
	// Any failed step cleans up the temporary file.
	defer func() {
		if tmpName != "" {
			_ = os.Remove(tmpName)
		}
	}()

	if _, err := io.Copy(tmp, in); err != nil {
		tmp.Close()
		return fmt.Errorf("failed to copy the executable: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("failed to write the executable: %w", err)
	}
	// Executable permission (ignored on Windows).
	if err := os.Chmod(tmpName, 0o755); err != nil {
		return fmt.Errorf("failed to set the executable permission: %w", err)
	}
	// On Windows the target may be in use, making rename fail; try deleting the old file first, then rename.
	if err := os.Rename(tmpName, dst); err != nil {
		if rmErr := os.Remove(dst); rmErr != nil && !os.IsNotExist(rmErr) {
			return fmt.Errorf("failed to overwrite the old executable: %w", err)
		}
		if err := os.Rename(tmpName, dst); err != nil {
			return fmt.Errorf("failed to install the executable: %w", err)
		}
	}
	tmpName = "" // renamed successfully, no cleanup needed
	return nil
}

// PrepareInstalledBinary copies the current executable to the fixed install directory and returns Options pointing at that fixed path.
// If the current executable is already that fixed path (e.g. the service is installed and the user runs install again), the copy is skipped and returns directly.
func PrepareInstalledBinary(opts Options) (Options, string, error) {
	src, err := ResolveExecPath(opts)
	if err != nil {
		return opts, "", err
	}
	dst, err := InstalledBinaryPath()
	if err != nil {
		return opts, "", err
	}
	if samePath(src, dst) {
		// Already the install path: no copy needed, continue with the rest of the flow.
		opts.ExecPath = dst
		return opts, dst, nil
	}
	if err := copyFileAtomic(src, dst); err != nil {
		return opts, "", err
	}
	opts.ExecPath = dst
	return opts, dst, nil
}

// RemoveInstalledBinary deletes the executable in the install directory; the directory is also deleted when empty.
// A missing file is treated as success (idempotent).
func RemoveInstalledBinary() error {
	dst, err := InstalledBinaryPath()
	if err != nil {
		return err
	}
	if err := os.Remove(dst); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete the executable: %w", err)
	}
	// Delete the directory if it is empty (non-empty means the user put other things there; keep it).
	if dir, err := InstallDir(); err == nil {
		_ = os.Remove(dir)
	}
	return nil
}
