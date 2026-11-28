//go:build windows

package capability

import (
	"context"
	"fmt"
	"os/exec"
	"sort"
	"strconv"
	"strings"
	"time"
)

// windowsProcessDefaultLimit is the maximum number of processes returned by windows.process.list when limit is not specified.
const windowsProcessDefaultLimit = 200

// windowsProcessMaxLimit is the maximum allowed value of limit, to prevent returning too much data at once.
const windowsProcessMaxLimit = 5000

// windowsProcessTimeout is the timeout for executing tasklist / taskkill.
const windowsProcessTimeout = 20 * time.Second

// registerWindowsProcess registers the Windows process management capability.
func registerWindowsProcess(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.process.list",
		Description: "List currently running processes on Windows, filterable by process name or PID. " +
			"Data comes from the tasklist command; processes that cannot be obtained are skipped.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by process name or PID substring, case-insensitive; returns all processes when empty.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Maximum number of processes to return, default 200, maximum 5000.",
				},
			},
		},
		Handler: handleWindowsProcessList,
	})

	_ = reg.Register(Capability{
		Name: "windows.process.kill",
		Description: "Terminate the process with the specified PID. Only positive integers with pid > 0 are allowed; " +
			"the optional force parameter determines whether to force termination (corresponds to taskkill /F).",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"pid": map[string]any{
					"type":        "integer",
					"description": "Target process PID, must be a positive integer.",
				},
				"force": map[string]any{
					"type":        "boolean",
					"description": "Whether to force termination, default true (corresponds to taskkill /F).",
				},
			},
			"required": []string{"pid"},
		},
		Handler: handleWindowsProcestRack,
	})
}

// handleWindowsProcessList is the implementation of windows.process.list.
func handleWindowsProcessList(params map[string]any) (any, error) {
	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}
	limit, err := optionalInt(params, "limit", windowsProcessDefaultLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > windowsProcessMaxLimit {
		return nil, fmt.Errorf("parameter limit exceeds the maximum %d, actual %d", windowsProcessMaxLimit, limit)
	}

	out, err := runWindowsProcessCommand("tasklist", "/FO", "CSV", "/NH")
	if err != nil {
		return nil, err
	}

	needle := strings.ToLower(filter)
	all := parseWindowsTasklistCSV(out)

	procs := make([]map[string]any, 0, len(all))
	for _, p := range all {
		if needle != "" {
			name := strings.ToLower(fmt.Sprint(p["name"]))
			pidStr := fmt.Sprint(p["pid"])
			if !strings.Contains(name, needle) && !strings.Contains(pidStr, needle) {
				continue
			}
		}
		procs = append(procs, p)
		if len(procs) >= limit {
			break
		}
	}

	// Sort ascending by PID to keep the output stable and easy to compare.
	sort.Slice(procs, func(i, j int) bool {
		return fmt.Sprint(procs[i]["pid"]) < fmt.Sprint(procs[j]["pid"])
	})

	return map[string]any{
		"processes": procs,
		"count":     len(procs),
		"truncated": len(all) > len(procs),
	}, nil
}

// handleWindowsProcestRack is the implementation of windows.process.kill.
func handleWindowsProcestRack(params map[string]any) (any, error) {
	pid, err := optionalInt(params, "pid", 0)
	if err != nil {
		return nil, err
	}
	if pid <= 0 {
		return nil, fmt.Errorf("parameter pid must be a positive integer, actual %d", pid)
	}
	force, err := optionalBool(params, "force", true)
	if err != nil {
		return nil, err
	}

	args := []string{"/PID", strconv.Itoa(pid)}
	if force {
		args = append(args, "/F")
	}
	out, err := runWindowsProcessCommand("taskkill", args...)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"pid":     pid,
		"force":   force,
		"message": strings.TrimSpace(out),
	}, nil
}

// runWindowsProcessCommand executes a process-related external command and returns standard output.
//
// The difference from runWindowsCommand: taskkill writes the reason to stderr on failure,
// so stderr is merged into the error message here, making it easier for the caller to diagnose (such as "access denied").
func runWindowsProcessCommand(name string, args ...string) (string, error) {
	if _, err := requireTool(name, ""); err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(context.Background(), windowsProcessTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, name, args...)
	// The daemon itself has no console; without this attribute a new console window would be created for tasklist / taskkill (flashing console).
	cmd.SysProcAttr = hideWindow()
	out, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(interface{ Stderr() []byte }); ok {
			msg := strings.TrimSpace(string(exitErr.Stderr()))
			if msg != "" {
				return "", fmt.Errorf("failed to execute %s: %s", name, msg)
			}
		}
		return "", fmt.Errorf("failed to execute %s: %w", name, err)
	}
	return string(out), nil
}
