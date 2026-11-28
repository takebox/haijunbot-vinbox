//go:build windows

package capability

import (
	"fmt"
	"strings"
	"time"
)

// This file implements the Windows wait primitives (windows.window.wait / windows.process.wait).
// The pure logic (parameter parsing, state determination, polling loop) is in windows_wait_parse.go (no build tags, unit-testable on Linux).
// The platform-specific parts (window existence/foreground determination, process existence determination) are in this file, implemented via syscall and tasklist.

// windowsProcessWaitTool is the value of the tool field in the result of windows.process.wait.
const windowsProcessWaitTool = "tasklist"

// registerWindowsWait registers the Windows wait primitive capabilities.
func registerWindowsWait(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.window.wait",
		Description: "Poll and wait for a window to enter the specified state, until satisfied or timed out." +
			"Locate the window via window_id or title; state supports visible (the window appears), " +
			"active (the window becomes the foreground), gone (the window disappears). " +
			"Suitable for waiting for a window to appear before operating in scripted automation.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match, case-insensitive), used when window_id is not provided.",
				},
				"state": map[string]any{
					"type":        "string",
					"description": "The target state to wait for: visible (the window appears, default) / active (the window becomes the foreground) / gone (the window disappears).",
				},
				"timeout_ms": map[string]any{
					"type":        "integer",
					"description": "Timeout in milliseconds, default 10000; returns an error if still not satisfied.",
				},
				"interval_ms": map[string]any{
					"type":        "integer",
					"description": "Polling interval in milliseconds, default 200.",
				},
			},
		},
		Handler: handleWindowsWindowWait,
	})

	_ = reg.Register(Capability{
		Name: "windows.process.wait",
		Description: "Poll and wait for the process with the specified PID to exit, until the process disappears or times out." +
			"Suitable for waiting for a process to finish after starting it in scripted automation.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"pid": map[string]any{
					"type":        "integer",
					"description": "The PID of the target process, must be a positive integer.",
				},
				"timeout_ms": map[string]any{
					"type":        "integer",
					"description": "Timeout in milliseconds, default 10000; returns an error if it has still not exited.",
				},
				"interval_ms": map[string]any{
					"type":        "integer",
					"description": "Polling interval in milliseconds, default 200.",
				},
			},
			"required": []string{"pid"},
		},
		Handler: handleWindowsProcessWait,
	})
}

// handleWindowsWindowWait is the implementation of windows.window.wait.
func handleWindowsWindowWait(params map[string]any) (any, error) {
	windowID, title, state, timeout, interval, err := parseWindowWaitParams(params)
	if err != nil {
		return nil, err
	}

	// window_id takes priority: parse a fixed handle and use IsWindow to determine existence.
	var hwnd uintptr
	haveHwnd := false
	if windowID != "" {
		hwnd, err = parseWindowID(windowID)
		if err != nil {
			return nil, err
		}
		haveHwnd = true
	}

	// present determination: window_id uses IsWindow, title uses findWindowByTitle.
	present := func() bool {
		if haveHwnd {
			return windowExists(hwnd)
		}
		_, ok := findWindowByTitle(title)
		return ok
	}
	// foreground determination: the window exists and is the foreground window.
	foreground := func() bool {
		if haveHwnd {
			return windowIsForeground(hwnd)
		}
		info, ok := findWindowByTitle(title)
		if !ok {
			return false
		}
		h, err := parseWindowID(info.WindowID)
		if err != nil {
			return false
		}
		return windowIsForeground(h)
	}

	start := time.Now()
	met, err := waitLoop(timeout, interval, func() (bool, error) {
		return windowWaitConditionMet(state, present(), foreground())
	})
	if err != nil {
		return nil, err
	}
	elapsed := time.Since(start)

	if !met {
		return nil, fmt.Errorf("waiting for window state %s timed out (not satisfied within %s)", state, timeout)
	}

	// Aggregate the final window information.
	var resolvedID, resolvedTitle string
	if haveHwnd {
		resolvedID = formatWindowID(hwnd)
		resolvedTitle = getWindowText(hwnd)
	} else if info, ok := findWindowByTitle(title); ok {
		resolvedID = info.WindowID
		resolvedTitle = info.Title
	}

	return map[string]any{
		"window_id": resolvedID,
		"title":     resolvedTitle,
		"state":     state,
		"met":       true,
		"waited_ms": int(elapsed.Milliseconds()),
		"tool":      windowsGUITool,
	}, nil
}

// handleWindowsProcessWait is the implementation of windows.process.wait.
func handleWindowsProcessWait(params map[string]any) (any, error) {
	pid, timeout, interval, err := parseProcessWaitParams(params)
	if err != nil {
		return nil, err
	}

	start := time.Now()
	met, err := waitLoop(timeout, interval, func() (bool, error) {
		// Wait for the process to disappear: satisfied once the process does not exist.
		return !processExists(pid), nil
	})
	if err != nil {
		return nil, err
	}
	elapsed := time.Since(start)

	if !met {
		return nil, fmt.Errorf("waiting for process %d to exit timed out (still running within %s)", pid, timeout)
	}

	return map[string]any{
		"pid":       pid,
		"exited":    true,
		"waited_ms": int(elapsed.Milliseconds()),
		"tool":      windowsProcessWaitTool,
	}, nil
}

// windowExists determines whether hwnd is still a valid window.
func windowExists(hwnd uintptr) bool {
	r, _, _ := procIsWindow.Call(hwnd)
	return r != 0
}

// windowIsForeground determines whether hwnd is the current foreground window.
func windowIsForeground(hwnd uintptr) bool {
	fg, _, _ := procGetForegroundWindow.Call()
	return fg == hwnd
}

// processExists determines whether pid is still running (using tasklist /FI "PID eq N").
func processExists(pid int) bool {
	out, err := runWindowsProcessCommand("tasklist", "/FO", "CSV", "/NH", "/FI", fmt.Sprintf("PID eq %d", pid))
	if err != nil {
		return false
	}
	return strings.TrimSpace(out) != ""
}
