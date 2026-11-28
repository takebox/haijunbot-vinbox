//go:build windows

package capability

// This file implements the Windows platform script execution capability (windows.script.exec).
//
// The design mirrors the Linux side linux_script_linux.go, keeping the parameters and return structure consistent:
//   - inputs: script (required), interpreter, cwd, env, timeout_ms, stdin;
//   - returns: exit_code, stdout, stderr, timed_out, duration_ms, truncated.
//
// Differences from Linux:
//   - the interpreter whitelist is the Windows side's powershell / pwsh / cmd;
//   - the script is passed to PowerShell via -EncodedCommand (base64 UTF-16LE), avoiding non-ASCII text being
//     corrupted by the ANSI code page on command-line arguments (same cause, same fix as windows_clipboard_windows.go);
//   - the output encoding is uniformly UTF-8 (see windowsPowerShellPreamble in windows_encoding.go).
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success path has not been verified end-to-end.

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// Default and upper-bound constraints for the Windows script execution capability (same magnitude as the Linux side).
const (
	// windowsScriptDefaultTimeoutMS is the default timeout (milliseconds) when timeout_ms is not specified.
	windowsScriptDefaultTimeoutMS = 30000
	// windowsScriptMaxTimeoutMS is the maximum allowed value of timeout_ms (milliseconds), preventing the caller from passing an oversized value and causing a hang.
	windowsScriptMaxTimeoutMS = 600000
	// windowsScriptMaxOutputBytes is the maximum number of bytes retained for each of stdout / stderr.
	// The excess is truncated and a truncated flag is set, preventing the output from blowing up memory.
	windowsScriptMaxOutputBytes = 1 << 20 // 1 MiB
)

// windowsScriptInterpreterWhitelist is the whitelist of allowed script interpreters.
//
// Same reasoning as the Linux side: using a whitelist rather than directly executing the string passed in by the caller avoids injecting an arbitrary
// executable through the interpreter parameter (equivalent to arbitrary command execution). The values inside the whitelist are all fixed literals.
var windowsScriptInterpreterWhitelist = []string{
	"powershell",
	"powershell.exe",
	"pwsh",
	"pwsh.exe",
	"cmd",
	"cmd.exe",
}

// registerWindowsScript registers the Windows script execution capability.
func registerWindowsScript(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.script.exec",
		Description: "Execute a piece of script content on Windows, returning the exit code, standard output, and standard error." +
			"The script content is handed to the specified interpreter for execution; the interpreter must be in the whitelist (powershell, pwsh, cmd). " +
			"PowerShell scripts are passed via -EncodedCommand, so non-ASCII text is not corrupted; the output is uniformly UTF-8. " +
			"Execution is protected by a timeout; on timeout the entire process tree is terminated.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"script": map[string]any{
					"type":        "string",
					"description": "The script content to execute (handed to the interpreter, not concatenated as a shell command line).",
				},
				"interpreter": map[string]any{
					"type":        "string",
					"description": "Interpreter, default powershell; allowed: powershell, powershell.exe, pwsh, pwsh.exe, cmd, cmd.exe.",
				},
				"cwd": map[string]any{
					"type":        "string",
					"description": "Working directory, optional; when empty it inherits the daemon's current directory.",
				},
				"env": map[string]any{
					"type":        "object",
					"description": "Additional environment variables (keys and values are strings), layered on top of the daemon's environment.",
				},
				"timeout_ms": map[string]any{
					"type":        "integer",
					"description": "Timeout in milliseconds, default 30000, maximum 600000.",
				},
				"stdin": map[string]any{
					"type":        "string",
					"description": "Content written to standard input, optional.",
				},
			},
			"required": []string{"script"},
		},
		Handler: handleWindowsScriptExec,
	})
}

// handleWindowsScriptExec is the implementation of windows.script.exec.
func handleWindowsScriptExec(params map[string]any) (any, error) {
	script, err := requiredString(params, "script")
	if err != nil {
		return nil, err
	}

	interpreter, err := resolveWindowsScriptInterpreter(params)
	if err != nil {
		return nil, err
	}

	timeoutMS, err := optionalInt(params, "timeout_ms", windowsScriptDefaultTimeoutMS)
	if err != nil {
		return nil, err
	}
	if timeoutMS <= 0 {
		return nil, fmt.Errorf("parameter timeout_ms must be a positive integer, actual %d", timeoutMS)
	}
	if timeoutMS > windowsScriptMaxTimeoutMS {
		return nil, fmt.Errorf("parameter timeout_ms exceeds the maximum %d milliseconds, actual %d", windowsScriptMaxTimeoutMS, timeoutMS)
	}

	cwd, err := optionalString(params, "cwd")
	if err != nil {
		return nil, err
	}

	env, err := optionalStringMap(params, "env")
	if err != nil {
		return nil, err
	}

	stdin, err := optionalString(params, "stdin")
	if err != nil {
		return nil, err
	}

	timeout := time.Duration(timeoutMS) * time.Millisecond
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	args, cleanup, err := buildWindowsScriptCommand(interpreter, script)
	if err != nil {
		return nil, err
	}
	defer cleanup()

	cmd := exec.CommandContext(ctx, interpreter, args...)
	// The daemon itself has no console; without this attribute, a new console window would be created for the interpreter (a flashing black box).
	cmd.SysProcAttr = hideWindow()
	if stdin != "" {
		cmd.Stdin = strings.NewReader(stdin)
	}
	if cwd != "" {
		cmd.Dir = cwd
	}
	if len(env) > 0 {
		cmd.Env = append(cmd.Environ(), buildWindowsEnvPairs(env)...)
	}

	// Force-end the process tree after timeout: there is no process-group signal on Windows, so taskkill /T /F is used as a fallback,
	// avoiding leftover child processes spawned by PowerShell. If taskkill is unavailable, fall back to killing the single process.
	cmd.Cancel = func() error {
		if cmd.Process == nil {
			return nil
		}
		kill := exec.Command("taskkill", "/T", "/F", "/PID",
			fmt.Sprintf("%d", cmd.Process.Pid))
		kill.SysProcAttr = hideWindow()
		if err := kill.Run(); err != nil {
			return cmd.Process.Kill()
		}
		return nil
	}
	cmd.WaitDelay = 2 * time.Second

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	start := time.Now()
	runErr := cmd.Run()
	duration := time.Since(start)

	stdoutStr, stdoutTruncated := truncateOutput(stdout.Bytes(), windowsScriptMaxOutputBytes)
	stderrStr, stderrTruncated := truncateOutput(stderr.Bytes(), windowsScriptMaxOutputBytes)

	// When stderr is not a terminal, PowerShell serializes the error stream into CLIXML; restore it to readable text here
	// (see windows_clixml.go). The stderr of a non-PowerShell interpreter (cmd) is plain text, and
	// decodePowerShellStderr returns it as-is, unaffected.
	// Also strip the preamble statement echoed by PowerShell (a non-terminating error echoes the full source of the offending statement).
	stderrStr = decodePowerShellStderr(stderrStr, windowsPowerShellPreamble)

	timedOut := errors.Is(ctx.Err(), context.DeadlineExceeded)

	exitCode := 0
	if runErr != nil {
		var exitErr *exec.ExitError
		if errors.As(runErr, &exitErr) {
			exitCode = exitErr.ExitCode()
		} else if timedOut {
			// When force-killed on timeout, the process may not have time to report an exit code; use -1 to indicate abnormal termination.
			exitCode = -1
		} else {
			return nil, fmt.Errorf("failed to execute script: %w", runErr)
		}
	}

	return map[string]any{
		"exit_code":   exitCode,
		"stdout":      stdoutStr,
		"stderr":      stderrStr,
		"timed_out":   timedOut,
		"duration_ms": duration.Milliseconds(),
		"truncated":   stdoutTruncated || stderrTruncated,
	}, nil
}

// buildWindowsScriptCommand constructs the command-line arguments according to the interpreter, and returns a cleanup function.
//
// PowerShell uses -EncodedCommand (base64 UTF-16LE), completely bypassing the ANSI code page problem of command-line
// arguments; windowsPowerShellPreamble is prepended to the script to set the output encoding to UTF-8.
// cmd uses a temporary .cmd file (avoiding command-line length and escaping issues).
func buildWindowsScriptCommand(interpreter, script string) ([]string, func(), error) {
	base := strings.ToLower(interpreter)
	base = strings.TrimSuffix(base, ".exe")

	switch base {
	case "powershell", "pwsh":
		fullScript := windowsPowerShellPreamble + "\n" + script
		args := []string{
			"-NoProfile",
			"-NonInteractive",
			"-ExecutionPolicy", "Bypass",
			"-EncodedCommand", encodePowerShellCommand(fullScript),
		}
		return args, func() {}, nil
	case "cmd":
		// cmd cannot safely receive a multi-line script from the command line, so write it to a temporary .cmd file and execute it.
		f, err := os.CreateTemp("", "haijunbot-script-*.cmd")
		if err != nil {
			return nil, nil, fmt.Errorf("failed to create script temp file: %w", err)
		}
		path := f.Name()
		if _, err := f.WriteString(script); err != nil {
			f.Close()
			os.Remove(path)
			return nil, nil, fmt.Errorf("failed to write script temp file: %w", err)
		}
		if err := f.Close(); err != nil {
			os.Remove(path)
			return nil, nil, fmt.Errorf("failed to close script temp file: %w", err)
		}
		cleanup := func() { os.Remove(path) }
		// /C exits after execution; use & to invoke the script file path (the path is generated by os.CreateTemp, containing no user input).
		return []string{"/C", path}, cleanup, nil
	default:
		return nil, nil, fmt.Errorf("unsupported script interpreter: %q", interpreter)
	}
}

// resolveWindowsScriptInterpreter parses and validates the interpreter parameter.
func resolveWindowsScriptInterpreter(params map[string]any) (string, error) {
	raw, err := optionalString(params, "interpreter")
	if err != nil {
		return "", err
	}
	if raw == "" {
		return "powershell", nil
	}
	for _, allowed := range windowsScriptInterpreterWhitelist {
		if strings.EqualFold(raw, allowed) {
			return allowed, nil
		}
	}
	return "", fmt.Errorf("parameter interpreter is not in the whitelist: %q, allowed values: %s",
		raw, strings.Join(windowsScriptInterpreterWhitelist, ", "))
}

// buildWindowsEnvPairs converts an environment variable map into a "K=V" slice, skipping empty keys.
//
// The logic is consistent with the Linux side's buildEnvPairs; since the latter carries the //go:build linux tag and
// is unavailable in a Windows build, it is implemented separately here.
func buildWindowsEnvPairs(env map[string]string) []string {
	out := make([]string, 0, len(env))
	for k, v := range env {
		if k == "" {
			continue
		}
		out = append(out, k+"="+v)
	}
	return out
}
