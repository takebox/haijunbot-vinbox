//go:build linux

package capability

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
)

// Default and upper-bound constraints for the script execution capability.
const (
	// linuxScriptDefaultTimeoutMS is the default timeout (milliseconds) when timeout_ms is not specified.
	linuxScriptDefaultTimeoutMS = 30000
	// linuxScriptMaxTimeoutMS is the maximum allowed value of timeout_ms (milliseconds), preventing the caller from passing an oversized value and causing a hang.
	linuxScriptMaxTimeoutMS = 600000
	// linuxScriptMaxOutputBytes is the maximum number of bytes retained for each of stdout / stderr.
	// The excess is truncated and a truncated flag is set, preventing the output from blowing up memory.
	linuxScriptMaxOutputBytes = 1 << 20 // 1 MiB
)

// linuxScriptInterpreterWhitelist is the whitelist of allowed script interpreters.
//
// Using a whitelist rather than directly executing the string passed in by the caller avoids the caller injecting
// an arbitrary executable through the interpreter parameter (equivalent to arbitrary command execution).
// The values inside the whitelist are all fixed literals and are not parsed by a shell.
var linuxScriptInterpreterWhitelist = []string{
	"/bin/sh",
	"/bin/bash",
	"/usr/bin/sh",
	"/usr/bin/bash",
	"sh",
	"bash",
	"pwsh",
	"powershell",
}

// registerLinuxScript registers the Linux script execution capability.
func registerLinuxScript(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "linux.script.exec",
		Description: "Execute a piece of script content on Linux, returning the exit code, standard output, and standard error. " +
			"The script content is handed to the specified interpreter for execution; the interpreter must be in the whitelist (/bin/sh, /bin/bash, sh, bash, pwsh, powershell). " +
			"Execution is protected by a timeout; on timeout the entire process group is terminated.",
		Platform: PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"script": map[string]any{
					"type":        "string",
					"description": "The script content to execute (handed to the interpreter, not concatenated as a shell command line).",
				},
				"interpreter": map[string]any{
					"type":        "string",
					"description": "Interpreter, default /bin/sh; allowed: /bin/sh, /bin/bash, /usr/bin/sh, /usr/bin/bash, sh, bash, pwsh, powershell.",
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
		Handler: handleLinuxScriptExec,
	})
}

// handleLinuxScriptExec is the implementation of linux.script.exec.
func handleLinuxScriptExec(params map[string]any) (any, error) {
	script, err := requiredString(params, "script")
	if err != nil {
		return nil, err
	}

	interpreter, err := resolveLinuxScriptInterpreter(params)
	if err != nil {
		return nil, err
	}

	timeoutMS, err := optionalInt(params, "timeout_ms", linuxScriptDefaultTimeoutMS)
	if err != nil {
		return nil, err
	}
	if timeoutMS <= 0 {
		return nil, fmt.Errorf("parameter timeout_ms must be a positive integer, actual %d", timeoutMS)
	}
	if timeoutMS > linuxScriptMaxTimeoutMS {
		return nil, fmt.Errorf("parameter timeout_ms exceeds the maximum %d milliseconds, actual %d", linuxScriptMaxTimeoutMS, timeoutMS)
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

	// The script is written to a temporary file and executed as a positional argument of the interpreter, rather than passed via stdin.
	// This has two benefits:
	//  1. stdin can be left for the caller to inject data through the stdin parameter;
	//  2. the script content does not go through command-line concatenation, avoiding argument injection.
	scriptFile, err := os.CreateTemp("", "haijunbot-script-*.sh")
	if err != nil {
		return nil, fmt.Errorf("failed to create script temp file: %w", err)
	}
	scriptPath := scriptFile.Name()
	defer os.Remove(scriptPath)

	if _, err := scriptFile.WriteString(script); err != nil {
		scriptFile.Close()
		return nil, fmt.Errorf("failed to write script temp file: %w", err)
	}
	if err := scriptFile.Close(); err != nil {
		return nil, fmt.Errorf("failed to close script temp file: %w", err)
	}

	cmd := exec.CommandContext(ctx, interpreter, scriptPath)
	if stdin != "" {
		cmd.Stdin = strings.NewReader(stdin)
	}
	if cwd != "" {
		cmd.Dir = cwd
	}
	if len(env) > 0 {
		cmd.Env = append(cmd.Environ(), buildEnvPairs(env)...)
	}

	// Separate process group: on timeout the child processes can be terminated together, avoiding orphan processes.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	// After the timeout, first send SIGKILL as a fallback, then wait for the process to exit, preventing Wait from blocking forever.
	cmd.Cancel = func() error {
		if cmd.Process == nil {
			return nil
		}
		// A negative sign means sending the signal to the entire process group.
		if err := syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL); err != nil {
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

	stdoutStr, stdoutTruncated := truncateOutput(stdout.Bytes(), linuxScriptMaxOutputBytes)
	stderrStr, stderrTruncated := truncateOutput(stderr.Bytes(), linuxScriptMaxOutputBytes)

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

// resolveLinuxScriptInterpreter parses and validates the interpreter parameter.
func resolveLinuxScriptInterpreter(params map[string]any) (string, error) {
	raw, err := optionalString(params, "interpreter")
	if err != nil {
		return "", err
	}
	if raw == "" {
		return "/bin/sh", nil
	}
	for _, allowed := range linuxScriptInterpreterWhitelist {
		if raw == allowed {
			return raw, nil
		}
	}
	return "", fmt.Errorf("parameter interpreter is not in the whitelist: %q, allowed values: %s",
		raw, strings.Join(linuxScriptInterpreterWhitelist, ", "))
}

// buildEnvPairs converts an environment variable map into a "K=V" slice, skipping empty keys.
func buildEnvPairs(env map[string]string) []string {
	out := make([]string, 0, len(env))
	for k, v := range env {
		if k == "" {
			continue
		}
		out = append(out, k+"="+v)
	}
	return out
}

// truncateOutput truncates the output to the maximum number of bytes, returning the content and whether truncation occurred.
func truncateOutput(b []byte, max int) (string, bool) {
	if len(b) <= max {
		return string(b), false
	}
	return string(b[:max]), true
}

// requiredString reads a required string parameter.
func requiredString(params map[string]any, key string) (string, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return "", fmt.Errorf("missing required parameter %s", key)
	}
	s, ok := v.(string)
	if !ok {
		return "", fmt.Errorf("parameter %s must be a string, actual %T", key, v)
	}
	if strings.TrimSpace(s) == "" {
		return "", fmt.Errorf("parameter %s cannot be empty", key)
	}
	return s, nil
}

// optionalString reads an optional string parameter; returns an empty string when missing or nil.
func optionalString(params map[string]any, key string) (string, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return "", nil
	}
	s, ok := v.(string)
	if !ok {
		return "", fmt.Errorf("parameter %s must be a string, actual %T", key, v)
	}
	return s, nil
}

// optionalInt reads an optional integer parameter; returns the default value when missing or nil.
//
// It is compatible with the float64 produced by JSON decoding (numbers sent by the gateway may be float64).
func optionalInt(params map[string]any, key string, def int) (int, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return def, nil
	}
	switch n := v.(type) {
	case int:
		return n, nil
	case int64:
		return int(n), nil
	case float64:
		if n != float64(int(n)) {
			return 0, fmt.Errorf("parameter %s must be an integer, actual %v", key, n)
		}
		return int(n), nil
	default:
		return 0, fmt.Errorf("parameter %s must be an integer, actual %T", key, v)
	}
}

// optionalStringMap reads an optional string map parameter.
func optionalStringMap(params map[string]any, key string) (map[string]string, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return nil, nil
	}
	switch m := v.(type) {
	case map[string]string:
		return m, nil
	case map[string]any:
		out := make(map[string]string, len(m))
		for k, raw := range m {
			s, ok := raw.(string)
			if !ok {
				return nil, fmt.Errorf("parameter %s.%s must be a string, actual %T", key, k, raw)
			}
			out[k] = s
		}
		return out, nil
	default:
		return nil, fmt.Errorf("parameter %s must be an object, actual %T", key, v)
	}
}
