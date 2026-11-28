//go:build windows

package capability

import (
	"fmt"
	"os/exec"
	"strings"
	"syscall"
)

// createNoWindow keeps console programs from creating a new console window.
//
// The daemon runs as a detached process (DETACHED_PROCESS) on Windows and has no console itself;
// if a console program such as powershell / cmd / tasklist is launched without this flag, Windows will
// **create a new console window** for the child process, which manifests as a console window flashing
// every time a capability is called. With CREATE_NO_WINDOW, the child process runs in a windowless, hidden console.
const createNoWindow = 0x08000000

// hideWindow returns the launch attributes that keep the child process from popping up a console window.
func hideWindow() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{CreationFlags: createNoWindow}
}

// This file provides the parameter parsing and external command helper functions shared by Windows-side capabilities.
//
// The reason for not reusing the functions of the same name in linux_script_linux.go: those functions carry the //go:build linux
// tag and do not participate in the Windows build. The function signatures on both sides are kept consistent for easy cross-reference maintenance.

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

// requiredInt reads a required integer parameter.
//
// The difference from optionalInt: this function requires the parameter to be present, for scenarios where "0 is a valid value
// and the default value cannot represent absence" (such as mouse coordinates x/y, which may be 0). Missing or nil returns an error.
//
// It is compatible with the float64 produced by JSON decoding (numbers sent by the gateway may be float64).
func requiredInt(params map[string]any, key string) (int, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return 0, fmt.Errorf("missing required parameter %s", key)
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

// optionalBool reads an optional boolean parameter; returns the default value when missing or nil.
func optionalBool(params map[string]any, key string, def bool) (bool, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return def, nil
	}
	b, ok := v.(bool)
	if !ok {
		return false, fmt.Errorf("parameter %s must be a boolean, actual %T", key, v)
	}
	return b, nil
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

// truncateOutput truncates a byte slice to the given limit, returning the string and whether truncation occurred.
func truncateOutput(b []byte, max int) (string, bool) {
	if len(b) <= max {
		return string(b), false
	}
	return string(b[:max]), true
}

// requireTool checks whether an external command is available (exec.LookPath); when missing, returns an error with an installation hint.
//
// Windows-side capabilities try to use built-in system commands (tasklist / taskkill / reg / wmic, etc.) as much as possible,
// but still uniformly go through this function for detection, to avoid an obscure exec error when the command does not exist.
func requireTool(name, hint string) (string, error) {
	path, err := exec.LookPath(name)
	if err != nil {
		if hint != "" {
			return "", fmt.Errorf("command %s not found: %s", name, hint)
		}
		return "", fmt.Errorf("command %s not found, please make sure it is in PATH", name)
	}
	return path, nil
}
