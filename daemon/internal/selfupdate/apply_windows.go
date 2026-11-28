//go:build windows

package selfupdate

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
)

// isWindows reports whether the current platform is Windows.
func isWindows() bool { return true }

// lower returns the lowercase form of s (Windows path comparison needs to ignore case).
func lower(s string) string { return strings.ToLower(s) }

// replaceExecutable replaces the target executable on Windows.
//
// Difficulty: Windows does not allow overwriting/renaming a running exe (the file is exclusively locked).
// So here we cannot simply rename as on Linux; instead we launch a **detached helper child process**
// that completes the replacement after the current process exits (see the self-update-apply subcommand in cmd/haijunbot-daemon).
//
// But the helper approach requires "the parent process exits first", whereas this function is called synchronously within the parent process.
// To preserve Apply's semantics (the on-disk file is the new version after the call), this uses the following strategy:
//   - First place the new file in the target's directory (already tmpPath) and attempt a direct rename;
//   - If it fails because the file is in use, fall back to "scheduled replacement" mode: keep the new file as
//     <target>.new and return a clear error, telling the caller to use the helper subcommand.
//
// Note: the actual "replace while running" is done by cmd/haijunbot-daemon's self-update-apply subcommand
// (run after the parent process exits); this function is only responsible for a best-effort immediate replacement.
func replaceExecutable(tmpPath, targetPath string) error {
	if err := os.Rename(tmpPath, targetPath); err == nil {
		return nil
	}
	// The target is in use: keep the new file as <target>.new and leave the replacement to the helper subcommand after exit.
	pending := targetPath + ".new"
	if err := os.Rename(tmpPath, pending); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("failed to replace executable (and could not keep the pending file): %w", err)
	}
	return fmt.Errorf("the target executable is in use; kept the pending file %s; complete the replacement via the self-update-apply subcommand", filepath.Base(pending))
}

// SpawnApplyHelper launches a detached helper child process that completes the replacement and restart after the current process exits.
//
// Arguments:
//   - exePath: the current executable path (the helper uses it to locate itself, i.e. launch a new copy of itself);
//     Note: the helper should launch from the "new file to be installed", to avoid the old file being in use and unexecutable;
//   - newBinary: the new-version executable path (not yet in place);
//   - target: the final path to replace;
//   - restart: whether to restart the service after replacement.
//
// Returns the helper process PID for logging.
//
// Implementation highlights: uses DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP so the helper is not terminated
// when the parent exits; the helper internally polls until target is no longer in use before replacing.
func SpawnApplyHelper(_ string, newBinary, target string, restart bool) (int, error) {
	// The helper launches from the "new file": first copy the new file to <target>.helper.exe and execute it,
	// so that even if target is in use it does not affect the helper's own execution.
	helperExe := target + ".helper.exe"
	if err := copyFileExecutable(newBinary, helperExe); err != nil {
		return 0, err
	}
	args := []string{"self-update-apply", "--src", helperExe, "--dst", target}
	if restart {
		args = append(args, "--restart")
	}
	cmd := exec.Command(helperExe, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		// CREATE_NO_WINDOW: the helper is also a console program; if the parent has no console and this flag is absent,
		// a new console window is created (a flashing black box).
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP | 0x00000008 | 0x08000000, // DETACHED_PROCESS | CREATE_NO_WINDOW
	}
	cmd.Stdout = nil
	cmd.Stderr = nil
	if err := cmd.Start(); err != nil {
		return 0, fmt.Errorf("failed to start update helper: %w", err)
	}
	pid := cmd.Process.Pid
	// Do not Wait: let the helper run independently; the parent exits afterwards.
	_ = cmd.Process.Release()
	return pid, nil
}
