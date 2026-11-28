package selfupdate

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// UpdateState is the state of the update flow (corresponding to daemon.update.status.state in the protocol).
type UpdateState string

const (
	// StateDownloading is downloading the new version.
	StateDownloading UpdateState = "downloading"
	// StateVerifying is verifying (sha256) and unpacking.
	StateVerifying UpdateState = "verifying"
	// StateApplying is replacing the executable.
	StateApplying UpdateState = "applying"
	// StateRestarting is restarting the service.
	StateRestarting UpdateState = "restarting"
	// StateFailed means the update failed (the error field explains why).
	StateFailed UpdateState = "failed"
	// StateDone means the update is ready (replacement finished on Linux; handed to the helper on Windows).
	StateDone UpdateState = "done"
)

// StatusReporter is provided by the caller to report update progress back to the gateway (optional).
//
// Arguments are the state and the error message (an empty string on success). Implementations should not block too long.
type StatusReporter func(state UpdateState, errMsg string)

// Options is the parameters for running an update.
type Options struct {
	// Info is the update directive sent by the gateway (must have Available=true).
	Info UpdateInfo
	// Version is the current daemon version, used for User-Agent and logs.
	Version string
	// TargetPath is the executable path to replace (usually ~/.haijunbot/bin/haijunbot-daemon[.exe]).
	TargetPath string
	// WorkDir is the temporary directory for downloading and unpacking; when empty, a subdirectory of the system temp directory is used.
	WorkDir string
	// Restart indicates whether to restart the service after a successful replacement.
	Restart bool
	// Report is an optional status report callback.
	Report StatusReporter
	// HTTPClient is optional for test injection; when nil, the default client is used.
	HTTPClient *http.Client
}

// Run executes a complete update flow: download → verify/unpack → replace → (optional) restart.
//
// Design principles: any step failure only returns an error (logged by the caller); it never panics
// and never blocks the WS connection or existing capabilities. Status is reported step by step via opts.Report.
//
// Returning nil means the update has been applied successfully (or has been handed to the helper).
func Run(opts Options) error {
	if !opts.Info.Available {
		return ErrNotAvailable
	}
	if opts.TargetPath == "" {
		return fmt.Errorf("no target path specified for the replacement")
	}
	report := func(s UpdateState, errMsg string) {
		if opts.Report != nil {
			opts.Report(s, errMsg)
		}
	}

	workDir := opts.WorkDir
	if workDir == "" {
		dir, err := os.MkdirTemp("", "haijunbot-daemon-update-*")
		if err != nil {
			report(StateFailed, err.Error())
			return fmt.Errorf("failed to create the temporary directory: %w", err)
		}
		workDir = dir
	} else if err := os.MkdirAll(workDir, 0o700); err != nil {
		report(StateFailed, err.Error())
		return fmt.Errorf("failed to create the temporary directory: %w", err)
	}
	defer func() { _ = os.RemoveAll(workDir) }()

	// 1) Download.
	report(StateDownloading, "")
	asset := opts.Info.Asset
	if asset == "" {
		asset = filepath.Base(opts.Info.URL)
	}
	archivePath := filepath.Join(workDir, asset)
	if opts.Info.SHA256 == "" {
		log.Printf("[selfupdate] gateway did not provide sha256, skipping integrity verification (version %s)", opts.Info.LatestVersion)
	}
	if err := Download(opts.HTTPClient, opts.Version, opts.Info.URL, archivePath, opts.Info.SHA256); err != nil {
		report(StateFailed, err.Error())
		return fmt.Errorf("download failed: %w", err)
	}

	// 2) Unpack the new executable.
	report(StateVerifying, "")
	newBinary := filepath.Join(workDir, binaryName())
	if err := ExtractBinary(archivePath, newBinary, binaryName()); err != nil {
		report(StateFailed, err.Error())
		return fmt.Errorf("unpack failed: %w", err)
	}

	// 3) Replace.
	report(StateApplying, "")
	if err := Apply(newBinary, opts.TargetPath); err != nil {
		// On Windows, when the target is in use, "file retained for later replacement" is returned, so fall back to the helper.
		if pid, herr := SpawnApplyHelper("", newBinary, opts.TargetPath, opts.Restart); herr == nil && pid > 0 {
			log.Printf("[selfupdate] started the update helper (pid=%d), it will finish the replacement after this process exits", pid)
			// Key point: the helper must wait until the target file is no longer in use before replacing it, and the current process holds it.
			// So this process must exit promptly (see the explanation of exitForHelperReplacement: must not go through
			// restartService, which depends on the PID file; the process started by schtasks has no such file, so it would mistakenly
			// decide "the service is not running", skip killing this process, and also spin up another process competing for the port),
			// otherwise the helper keeps waiting until the 60-second timeout, fails its replacement, and the update never takes effect.
			// Both replacement and restart are handled by the helper (the helper carries --restart and restarts the service itself after success).
			report(StateDone, "")
			if opts.Restart {
				report(StateRestarting, "")
			}
			exitForHelperReplacement()
			return nil
		}
		report(StateFailed, err.Error())
		return fmt.Errorf("failed to replace the executable: %w", err)
	}

	// 4) Restart (replacement is complete on Linux, so restart actually happens here; on Windows, if the helper was used, the branch above already returned).
	if opts.Restart {
		report(StateRestarting, "")
		if err := restartService(); err != nil {
			// A restart failure is not an update failure (the file is already the new version); log it only.
			log.Printf("[selfupdate] failed to restart the service (can be restarted manually): %v", err)
		}
	}
	report(StateDone, "")
	log.Printf("[selfupdate] updated to %s (target %s)", opts.Info.LatestVersion, opts.TargetPath)
	return nil
}

// binaryName returns the executable file name for the current platform.
func binaryName() string {
	if isWindows() {
		return "haijunbot-daemon.exe"
	}
	return "haijunbot-daemon"
}

// restartService is implemented by platform files (see restart_linux.go / restart_windows.go /
// restart_other.go) to avoid introducing platform dependencies into this file.

// NowUnix returns the current Unix seconds (for the upper layer to fill in TokenState.SavedAtUnix).
func NowUnix() int64 { return time.Now().Unix() }
