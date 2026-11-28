// Package service is responsible for registering the daemon as a system service:
// systemd user service on Linux, scheduled task on Windows.
package service

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// ServiceName is the systemd service file name on Linux.
const ServiceName = "haijunbot-daemon.service"

// TaskName is the scheduled task name on Windows.
const TaskName = "HaijunBot-Daemon"

// Options is the parameters required to install the service.
type Options struct {
	// ExecPath is the absolute path of the daemon executable; when empty, the current process path is used.
	ExecPath string
	// Listen is the local API listen address.
	Listen string
	// Gateway is the default gateway address, may be empty.
	Gateway string
	// ConfigPath is the config file path, may be empty.
	ConfigPath string
}

// Status is the service status (a unified format across platforms).
type Status struct {
	// Running indicates whether the service is currently running.
	Running bool
	// Enabled indicates whether auto-start on boot is configured.
	Enabled bool
	// PID is the main process ID, or 0 when unknown.
	PID int
	// Detail is supplementary explanation (e.g. the raw error message).
	Detail string
}

// Service is the cross-platform service management interface.
type Service interface {
	// Install writes the service definition and enables auto-start (does not start).
	Install(opts Options) (string, error)
	// Uninstall stops the service and deletes the service definition.
	Uninstall() (string, error)
	// Start starts the service.
	Start() (string, error)
	// Stop stops the service.
	Stop() (string, error)
	// Restart restarts the service.
	Restart() (string, error)
	// Status queries the service status.
	Status() (Status, error)
}

// newPlatformService is provided by the per-platform implementation files (see new_linux.go / new_windows.go).
// Returning nil means service installation is not supported on the current platform.

// New returns the service implementation for the current platform; an implementation that always errors is returned when the platform is unsupported.
func New() Service {
	if svc := newPlatformService(); svc != nil {
		return svc
	}
	return &unsupportedService{goos: runtime.GOOS}
}

// ResolveExecPath returns the absolute executable path: opts.ExecPath is preferred, otherwise the current process path is used.
func ResolveExecPath(opts Options) (string, error) {
	if p := strings.TrimSpace(opts.ExecPath); p != "" {
		abs, err := filepath.Abs(p)
		if err != nil {
			return "", fmt.Errorf("failed to resolve the executable path: %w", err)
		}
		return abs, nil
	}
	exe, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("failed to get the current executable path: %w", err)
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	return exe, nil
}

// BuildRunArgs builds the arguments passed to the daemon when the service starts (not including the executable itself).
func BuildRunArgs(opts Options) []string {
	args := []string{"run"}
	if opts.Listen != "" {
		args = append(args, "--listen", opts.Listen)
	}
	if opts.Gateway != "" {
		args = append(args, "--gateway", opts.Gateway)
	}
	if opts.ConfigPath != "" {
		args = append(args, "--config", opts.ConfigPath)
	}
	return args
}

// unsupportedService is for platforms that are neither Linux nor Windows.
type unsupportedService struct {
	goos string
}

func (s *unsupportedService) err() error {
	return fmt.Errorf("service installation is not supported on platform %s", s.goos)
}

func (s *unsupportedService) Install(Options) (string, error) { return "", s.err() }
func (s *unsupportedService) Uninstall() (string, error)      { return "", s.err() }
func (s *unsupportedService) Start() (string, error)          { return "", s.err() }
func (s *unsupportedService) Stop() (string, error)           { return "", s.err() }
func (s *unsupportedService) Restart() (string, error)        { return "", s.err() }
func (s *unsupportedService) Status() (Status, error)         { return Status{}, s.err() }
