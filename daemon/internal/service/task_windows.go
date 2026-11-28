//go:build windows

package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// cmdTimeout is the timeout for a single external command call.
const cmdTimeout = 30 * time.Second

// taskService is the scheduled task implementation on Windows.
//
// Auto-start is handled by the scheduled task (triggered at logon); the process lifecycle is tracked via the PID file.
type taskService struct{}

// PidFilePath returns the PID file path: ~/.haijunbot/pids/haijunbot-daemon.pid.
func PidFilePath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get the user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", "pids", "haijunbot-daemon.pid"), nil
}

// BuildTaskCommand generates the command line the scheduled task will execute (including the executable itself).
func BuildTaskCommand(opts Options) (string, error) {
	execPath, err := ResolveExecPath(opts)
	if err != nil {
		return "", err
	}
	parts := append([]string{execPath}, BuildRunArgs(opts)...)
	for i, p := range parts {
		if strings.ContainsAny(p, " \t") {
			parts[i] = `"` + p + `"`
		}
	}
	return strings.Join(parts, " "), nil
}

// BuildCreateArgs generates the schtasks arguments to create the scheduled task.
func BuildCreateArgs(opts Options) ([]string, error) {
	command, err := BuildTaskCommand(opts)
	if err != nil {
		return nil, err
	}
	return []string{
		"/Create",
		"/TN", TaskName,
		"/TR", command,
		"/SC", "ONLOGON",
		"/RL", "HIGHEST",
		"/F",
	}, nil
}

// Install creates the scheduled task that triggers at logon (does not start).
// Before installing, the executable is copied to the fixed install directory ~/.haijunbot/bin so the location the task points at is stable.
func (s *taskService) Install(opts Options) (string, error) {
	opts, installedPath, err := PrepareInstalledBinary(opts)
	if err != nil {
		return "", err
	}
	args, err := BuildCreateArgs(opts)
	if err != nil {
		return "", err
	}
	if _, err := runCmd("schtasks", args...); err != nil {
		return "", fmt.Errorf("failed to create the scheduled task: %w (the task runs with the highest privileges, so install must be run in an **administrator** terminal)", err)
	}
	return fmt.Sprintf("the scheduled task has been created: %s (executable: %s)", TaskName, installedPath), nil
}

// Uninstall stops the service and deletes the scheduled task.
func (s *taskService) Uninstall() (string, error) {
	_, _ = s.Stop()
	if _, err := runCmd("schtasks", "/Delete", "/TN", TaskName, "/F"); err != nil {
		return "", fmt.Errorf("failed to delete the scheduled task: %w", err)
	}
	// Clean up the executable in the install directory (a failure does not block uninstall; it is only noted).
	cleanupNote := ""
	if err := RemoveInstalledBinary(); err != nil {
		cleanupNote = fmt.Sprintf(" (failed to clean up the executable: %v)", err)
	}
	return fmt.Sprintf("the scheduled task has been deleted: %s%s", TaskName, cleanupNote), nil
}

// Start starts the daemon as a detached process and records the PID.
//
// It starts the executable at the **fixed install path** (~/.haijunbot/bin/haijunbot-daemon.exe) rather than the
// current process path: the scheduled task also points at that fixed path, and the two must match, otherwise running
// start from the download directory would start another copy that does not match the process observed by service management (stop/status).
func (s *taskService) Start() (string, error) {
	pidPath, err := PidFilePath()
	if err != nil {
		return "", err
	}
	if pid := readAlivePID(pidPath); pid > 0 {
		return "", fmt.Errorf("the service is already running (PID: %d)", pid)
	}

	execPath, err := InstalledBinaryPath()
	if err != nil {
		return "", err
	}
	if _, statErr := os.Stat(execPath); statErr != nil {
		return "", fmt.Errorf("the installed executable %s was not found; run install first", execPath)
	}
	cmd := exec.Command(execPath, BuildRunArgs(Options{})...)
	cmd.SysProcAttr = detachedProcAttr()
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start the service: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(pidPath), 0o755); err != nil {
		return "", fmt.Errorf("failed to create the PID directory: %w", err)
	}
	if err := os.WriteFile(pidPath, []byte(strconv.Itoa(cmd.Process.Pid)), 0o644); err != nil {
		return "", fmt.Errorf("failed to write the PID file: %w", err)
	}
	return fmt.Sprintf("the service has been started (PID: %d)", cmd.Process.Pid), nil
}

// Stop terminates the daemon and cleans up the PID file.
func (s *taskService) Stop() (string, error) {
	pidPath, err := PidFilePath()
	if err != nil {
		return "", err
	}
	pid := readAlivePID(pidPath)
	if pid <= 0 {
		_ = os.Remove(pidPath)
		return "the service is not running", nil
	}
	if _, err := runCmd("taskkill", "/PID", strconv.Itoa(pid), "/F"); err != nil {
		return "", fmt.Errorf("failed to stop the service: %w", err)
	}
	_ = os.Remove(pidPath)
	return "the service has been stopped", nil
}

// Restart stops first, then starts.
func (s *taskService) Restart() (string, error) {
	if _, err := s.Stop(); err != nil {
		return "", err
	}
	time.Sleep(2 * time.Second)
	return s.Start()
}

// Status queries the running and auto-start status.
func (s *taskService) Status() (Status, error) {
	var st Status

	if pidPath, err := PidFilePath(); err == nil {
		st.PID = readAlivePID(pidPath)
		st.Running = st.PID > 0
	}

	if _, err := runCmd("schtasks", "/Query", "/TN", TaskName); err == nil {
		st.Enabled = true
	}
	return st, nil
}

// readAlivePID reads the PID file and verifies the process is alive; when invalid, it deletes the file and returns 0.
func readAlivePID(pidPath string) int {
	data, err := os.ReadFile(pidPath)
	if err != nil {
		return 0
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil || pid <= 0 {
		_ = os.Remove(pidPath)
		return 0
	}
	out, err := runCmd("tasklist", "/FI", fmt.Sprintf("PID eq %d", pid), "/NH")
	if err != nil || !strings.Contains(out, strconv.Itoa(pid)) {
		_ = os.Remove(pidPath)
		return 0
	}
	return pid
}

// runCmd runs an external command and returns its standard output as UTF-8 text.
//
// Encoding issue: schtasks / taskkill / tasklist are native console programs that write text according to the
// **console output code page** -- GBK/CP936 on Chinese Windows, not UTF-8. Go's os/exec only returns raw bytes,
// so a plain string(out) would interpret GBK as UTF-8, producing garbled text (mojibake) that is unreadable,
// and the user cannot understand the failure reason (this happens in real machines when install fails).
//
// Fix strategy (same approach as windows_encoding.go in internal/capability, without introducing a GBK decoding table):
// wrap execution with PowerShell and let PowerShell do the "GBK decode → UTF-8 output" transcoding:
//
//  1. First read the external command's output using the **system default** [Console]::OutputEncoding (GBK on Chinese systems).
//     This step must happen before changing the encoding, otherwise PowerShell decodes GBK bytes as UTF-8 and gets mojibake.
//  2. Then set [Console]::OutputEncoding to UTF-8 and write out with [Console]::Out.Write.
//     The Go side now reads UTF-8 bytes, and a plain string(out) is the correct text.
//
// The reason `cmd /c chcp 65001` is not used: chcp only changes the output code page of the cmd session, and there is no
// guarantee that native tools honor that code page when stdout is redirected to a pipe; PowerShell's explicit transcoding
// does not depend on child process behavior and is more reliable (also consistent with the existing runWindowsPowerShellCommand path in the project).
//
// The script is passed via -EncodedCommand (base64 UTF-16LE), avoiding non-ASCII characters in the script being corrupted
// when command-line arguments are parsed with the ANSI code page (see the explanation in windows_encoding.go).
func runCmd(name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), cmdTimeout)
	defer cancel()

	script := buildPowerShellScript(name, args)
	cmd := exec.CommandContext(ctx, "powershell.exe",
		"-NoProfile",
		"-NonInteractive",
		"-ExecutionPolicy", "Bypass",
		"-EncodedCommand", encodePowerShellCommand(script),
	)
	// The daemon itself has no console; without this attribute, a new console window is created for PowerShell (a flashing black box).
	cmd.SysProcAttr = hideWindowProcAttr()
	out, err := cmd.Output()
	if err != nil {
		if ctx.Err() != nil {
			return "", fmt.Errorf("%s timed out", name)
		}
		if exitErr, ok := err.(*exec.ExitError); ok {
			msg := strings.TrimSpace(string(exitErr.Stderr))
			if msg == "" {
				// PowerShell writes both the external command's stdout and stderr to its own stdout,
				// possibly mixed with CLIXML noise (see stripPowerShellClixml); it must be cleaned before use.
				msg = stripPowerShellClixml(string(out))
			}
			if msg == "" {
				msg = "the command returned a non-zero exit code with no output"
			}
			return string(out), fmt.Errorf("%s failed: %s", name, msg)
		}
		return "", fmt.Errorf("failed to run %s: %w", name, err)
	}
	return string(out), nil
}
