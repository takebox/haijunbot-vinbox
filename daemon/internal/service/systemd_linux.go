//go:build linux

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

// systemctlTimeout is the timeout for a single systemctl call.
const systemctlTimeout = 10 * time.Second

// proxyEnvVars are the proxy-related environment variables that need to be passed through to the service.
var proxyEnvVars = []string{
	"http_proxy", "HTTP_PROXY",
	"https_proxy", "HTTPS_PROXY",
	"no_proxy", "NO_PROXY",
	"ftp_proxy", "FTP_PROXY",
	"socks_proxy", "SOCKS_PROXY",
}

// systemdService is the systemd user service implementation on Linux.
type systemdService struct{}

// UnitPath returns the absolute path of the service file: ~/.config/systemd/user/haijunbot-daemon.service.
func UnitPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get the user home directory: %w", err)
	}
	return filepath.Join(home, ".config", "systemd", "user", ServiceName), nil
}

// BuildUnit generates the systemd unit file content.
func BuildUnit(opts Options) (string, error) {
	execPath, err := ResolveExecPath(opts)
	if err != nil {
		return "", err
	}

	var b strings.Builder
	b.WriteString("[Unit]\n")
	b.WriteString("Description=HaijunBot Daemon\n")
	b.WriteString("After=network.target\n")
	b.WriteString("\n[Service]\n")
	b.WriteString("Type=simple\n")
	b.WriteString("Environment=PATH=" + buildServicePath(execPath) + "\n")
	for _, name := range proxyEnvVars {
		if v := os.Getenv(name); v != "" {
			b.WriteString("Environment=" + name + "=" + v + "\n")
		}
	}
	b.WriteString("ExecStart=" + execPath + " " + strings.Join(BuildRunArgs(opts), " ") + "\n")
	b.WriteString("Restart=always\n")
	b.WriteString("RestartSec=5\n")
	b.WriteString("\n[Install]\n")
	b.WriteString("WantedBy=default.target\n")
	return b.String(), nil
}

// buildServicePath prepends the executable's directory to the current PATH, so the service can find its own dependencies.
func buildServicePath(execPath string) string {
	current := os.Getenv("PATH")
	dir := filepath.Dir(execPath)
	if dir == "" {
		return current
	}
	for _, p := range strings.Split(current, ":") {
		if p == dir {
			return current
		}
	}
	if current == "" {
		return dir
	}
	return dir + ":" + current
}

// Install writes the unit file, runs daemon-reload, and enables (does not start).
// Before installing, the executable is copied to the fixed install directory ~/.haijunbot/bin so the ExecStart location is stable.
func (s *systemdService) Install(opts Options) (string, error) {
	opts, installedPath, err := PrepareInstalledBinary(opts)
	if err != nil {
		return "", err
	}
	content, err := BuildUnit(opts)
	if err != nil {
		return "", err
	}
	unitPath, err := UnitPath()
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(filepath.Dir(unitPath), 0o755); err != nil {
		return "", fmt.Errorf("failed to create the systemd user directory: %w", err)
	}
	if err := os.WriteFile(unitPath, []byte(content), 0o644); err != nil {
		return "", fmt.Errorf("failed to write the service file: %w", err)
	}
	if _, err := runSystemctl("daemon-reload"); err != nil {
		return "", fmt.Errorf("daemon-reload failed: %w", err)
	}
	if _, err := runSystemctl("enable", ServiceName); err != nil {
		return "", fmt.Errorf("failed to enable the service: %w", err)
	}
	return fmt.Sprintf("the service has been installed and set to auto-start on boot: %s (executable: %s)", unitPath, installedPath), nil
}

// Uninstall stops the service, disables auto-start, and deletes the unit file.
func (s *systemdService) Uninstall() (string, error) {
	unitPath, err := UnitPath()
	if err != nil {
		return "", err
	}
	if _, err := os.Stat(unitPath); err != nil {
		if os.IsNotExist(err) {
			return "", fmt.Errorf("the service is not installed: %s does not exist", unitPath)
		}
		return "", fmt.Errorf("failed to check the service file: %w", err)
	}
	// Stop/disable failures do not block uninstall; the final result is whether the file was deleted.
	_, _ = runSystemctl("stop", ServiceName)
	_, _ = runSystemctl("disable", ServiceName)
	if err := os.Remove(unitPath); err != nil {
		return "", fmt.Errorf("failed to delete the service file: %w", err)
	}
	if _, err := runSystemctl("daemon-reload"); err != nil {
		return "", fmt.Errorf("daemon-reload failed: %w", err)
	}
	// Clean up the executable in the install directory (a failure does not block uninstall; it is only noted).
	cleanupNote := ""
	if err := RemoveInstalledBinary(); err != nil {
		cleanupNote = fmt.Sprintf(" (failed to clean up the executable: %v)", err)
	}
	return fmt.Sprintf("the service has been uninstalled: %s%s", unitPath, cleanupNote), nil
}

// Start starts the service.
func (s *systemdService) Start() (string, error) {
	if _, err := runSystemctl("start", ServiceName); err != nil {
		return "", fmt.Errorf("failed to start the service: %w", err)
	}
	return "the service has been started", nil
}

// Stop stops the service.
func (s *systemdService) Stop() (string, error) {
	if _, err := runSystemctl("stop", ServiceName); err != nil {
		return "", fmt.Errorf("failed to stop the service: %w", err)
	}
	return "the service has been stopped", nil
}

// Restart restarts the service.
func (s *systemdService) Restart() (string, error) {
	if _, err := runSystemctl("restart", ServiceName); err != nil {
		return "", fmt.Errorf("failed to restart the service: %w", err)
	}
	return "the service has been restarted", nil
}

// Status queries the service running and auto-start status.
func (s *systemdService) Status() (Status, error) {
	var st Status

	out, err := runSystemctl("is-active", ServiceName)
	st.Running = err == nil && strings.TrimSpace(out) == "active"

	if _, err := runSystemctl("is-enabled", ServiceName); err == nil {
		st.Enabled = true
	}

	if st.Running {
		pidOut, err := runSystemctl("show", ServiceName, "--property=MainPID")
		if err == nil {
			if v, ok := strings.CutPrefix(strings.TrimSpace(pidOut), "MainPID="); ok {
				if pid, convErr := strconv.Atoi(strings.TrimSpace(v)); convErr == nil && pid > 0 {
					st.PID = pid
				}
			}
		}
	}
	return st, nil
}

// runSystemctl runs the systemctl --user command and returns its standard output.
func runSystemctl(args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), systemctlTimeout)
	defer cancel()

	full := append([]string{"--user"}, args...)
	cmd := exec.CommandContext(ctx, "systemctl", full...)
	out, err := cmd.Output()
	if err != nil {
		if ctx.Err() != nil {
			return "", fmt.Errorf("systemctl %s timed out", strings.Join(args, " "))
		}
		var exitErr *exec.ExitError
		if ok := asExitError(err, &exitErr); ok {
			msg := strings.TrimSpace(string(exitErr.Stderr))
			if msg == "" {
				msg = strings.TrimSpace(string(out))
			}
			return string(out), fmt.Errorf("systemctl %s failed: %s", strings.Join(args, " "), msg)
		}
		return "", fmt.Errorf("failed to run systemctl: %w", err)
	}
	return string(out), nil
}

// asExitError is a thin wrapper around errors.As to avoid importing errors repeatedly in this file.
func asExitError(err error, target **exec.ExitError) bool {
	e, ok := err.(*exec.ExitError)
	if ok {
		*target = e
	}
	return ok
}
