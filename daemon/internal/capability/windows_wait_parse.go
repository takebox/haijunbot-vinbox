package capability

import (
	"fmt"
	"time"
)

// This file implements the pure logic part of the Windows wait primitives (windows.window.wait / windows.process.wait):
// parameter parsing, state judgment, and the generic polling loop. It carries no build tags and can be unit tested on Linux.
//
// Note: this file stays "zero platform dependency" — it does not reference optionalString/optionalInt (they are defined in
// windows_common_windows.go with //go:build windows and linux_script_linux.go with //go:build linux;
// darwin has neither, so referencing them would break cross-platform compilation).
// Therefore equivalent inline waitOptionalString / waitOptionalInt are provided here, with semantics consistent with the platform versions.

// waitOptionalString reads an optional string parameter; returns an empty string when missing or nil.
// Semantics consistent with optionalString in windows_common_windows.go (zero-platform-dependency inline version).
func waitOptionalString(params map[string]any, key string) (string, error) {
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

// waitOptionalInt reads an optional integer parameter; returns the default value when missing or nil.
// It is compatible with the float64 produced by JSON decoding (numbers sent by the gateway may be float64).
// Semantics consistent with optionalInt in windows_common_windows.go (zero-platform-dependency inline version).
func waitOptionalInt(params map[string]any, key string, def int) (int, error) {
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

// windowsWaitDefaultTimeout is the default timeout when timeout_ms is not specified.
const windowsWaitDefaultTimeout = 10 * time.Second

// windowsWaitDefaultInterval is the polling interval.
const windowsWaitDefaultInterval = 200 * time.Millisecond

// windowsWaitValidStates is the set of valid values for the state of windows.window.wait.
var windowsWaitValidStates = map[string]bool{
	"visible": true,
	"active":  true,
	"gone":    true,
}

// parseWindowWaitParams parses the common parameters of windows.window.wait.
func parseWindowWaitParams(params map[string]any) (windowID, title, state string, timeout, interval time.Duration, err error) {
	windowID, err = waitOptionalString(params, "window_id")
	if err != nil {
		return
	}
	title, err = waitOptionalString(params, "title")
	if err != nil {
		return
	}
	if windowID == "" && title == "" {
		err = fmt.Errorf("at least one of parameter window_id and title must be provided")
		return
	}
	state, err = waitOptionalString(params, "state")
	if err != nil {
		return
	}
	if state == "" {
		state = "visible"
	}
	if !windowsWaitValidStates[state] {
		err = fmt.Errorf("parameter state must be one of visible/active/gone, actual %q", state)
		return
	}
	timeout, interval, err = parseWaitTiming(params)
	return
}

// parseProcessWaitParams parses the common parameters of windows.process.wait.
func parseProcessWaitParams(params map[string]any) (pid int, timeout, interval time.Duration, err error) {
	pid, err = waitOptionalInt(params, "pid", 0)
	if err != nil {
		return
	}
	if pid <= 0 {
		err = fmt.Errorf("parameter pid must be a positive integer, actual %d", pid)
		return
	}
	timeout, interval, err = parseWaitTiming(params)
	return
}

// parseWaitTiming parses timeout_ms and interval_ms and converts them to time.Duration.
func parseWaitTiming(params map[string]any) (timeout, interval time.Duration, err error) {
	timeoutMs, err := waitOptionalInt(params, "timeout_ms", int(windowsWaitDefaultTimeout/time.Millisecond))
	if err != nil {
		return
	}
	if timeoutMs <= 0 {
		err = fmt.Errorf("parameter timeout_ms must be a positive integer, actual %d", timeoutMs)
		return
	}
	intervalMs, err := waitOptionalInt(params, "interval_ms", int(windowsWaitDefaultInterval/time.Millisecond))
	if err != nil {
		return
	}
	if intervalMs <= 0 {
		err = fmt.Errorf("parameter interval_ms must be a positive integer, actual %d", intervalMs)
		return
	}
	timeout = time.Duration(timeoutMs) * time.Millisecond
	interval = time.Duration(intervalMs) * time.Millisecond
	return
}

// windowWaitConditionMet determines whether the window wait condition is satisfied.
// present indicates whether the window currently exists; foreground indicates whether the window is currently the foreground window.
func windowWaitConditionMet(state string, present, foreground bool) (bool, error) {
	switch state {
	case "visible":
		return present, nil
	case "active":
		return present && foreground, nil
	case "gone":
		return !present, nil
	default:
		return false, fmt.Errorf("parameter state must be one of visible/active/gone, actual %q", state)
	}
}

// waitLoop polls check at the given interval until it returns true or the timeout elapses.
// It returns (whether it was satisfied before the timeout, error).
func waitLoop(timeout, interval time.Duration, check func() (bool, error)) (bool, error) {
	deadline := time.Now().Add(timeout)
	for {
		ok, err := check()
		if err != nil {
			return false, err
		}
		if ok {
			return true, nil
		}
		if time.Now().After(deadline) {
			return false, nil
		}
		time.Sleep(interval)
	}
}
