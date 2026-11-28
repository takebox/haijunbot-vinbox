//go:build linux

package capability

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
)

// linuxProcessDefaultLimit is the maximum number of processes returned by linux.process.list when limit is not specified.
const linuxProcessDefaultLimit = 200

// linuxProcessMaxLimit is the maximum allowed value of limit, to prevent returning too much data at once.
const linuxProcessMaxLimit = 5000

// linuxProcessSignalWhitelist is the whitelist of signals that may be sent.
//
// Using a whitelist rather than directly parsing the string passed in by the caller avoids accidents
// when passing the parameter through to syscall.Kill (for example, a pid of 0 / negative would affect the entire process group or all processes).
var linuxProcessSignalWhitelist = map[string]syscall.Signal{
	"TERM": syscall.SIGTERM,
	"KILL": syscall.SIGKILL,
	"INT":  syscall.SIGINT,
	"HUP":  syscall.SIGHUP,
	"QUIT": syscall.SIGQUIT,
	"USR1": syscall.SIGUSR1,
	"USR2": syscall.SIGUSR2,
	"STOP": syscall.SIGSTOP,
	"CONT": syscall.SIGCONT,
	"15":   syscall.SIGTERM,
	"9":    syscall.SIGKILL,
	"2":    syscall.SIGINT,
	"1":    syscall.SIGHUP,
}

// registerLinuxProcess registers the Linux process management capability.
func registerLinuxProcess(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "linux.process.list",
		Description: "List the current processes on the Linux system, filterable by name or command-line substring. " +
			"Data is read directly from /proc, without depending on the ps command; processes that cannot be read due to permissions are skipped.",
		Platform: PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by process name (comm) or command line (cmdline) substring, case-insensitive; returns all processes when empty.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Maximum number of processes to return, default 200, maximum 5000.",
				},
			},
		},
		Handler: handleLinuxProcessList,
	})

	_ = reg.Register(Capability{
		Name: "linux.process.kill",
		Description: "Send a signal to the specified process, default SIGTERM. " +
			"Only positive integers with pid > 0 are allowed, and the signal must be in the whitelist (TERM/KILL/INT/HUP/QUIT/USR1/USR2/STOP/CONT or 15/9/2/1).",
		Platform: PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"pid": map[string]any{
					"type":        "integer",
					"description": "Target process PID, must be a positive integer.",
				},
				"signal": map[string]any{
					"type":        "string",
					"description": "Signal name or number, default TERM; allowed: TERM, KILL, INT, HUP, QUIT, USR1, USR2, STOP, CONT, 15, 9, 2, 1.",
				},
			},
			"required": []string{"pid"},
		},
		Handler: handleLinuxProcestRack,
	})
}

// handleLinuxProcessList is the implementation of linux.process.list.
func handleLinuxProcessList(params map[string]any) (any, error) {
	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}
	limit, err := optionalInt(params, "limit", linuxProcessDefaultLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > linuxProcessMaxLimit {
		return nil, fmt.Errorf("parameter limit exceeds the maximum %d, actual %d", linuxProcessMaxLimit, limit)
	}

	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil, fmt.Errorf("failed to read /proc: %w", err)
	}

	needle := strings.ToLower(filter)
	procs := make([]map[string]any, 0, 64)
	truncated := false

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(entry.Name())
		if err != nil {
			// Non-numeric directories (such as /proc/self, /proc/sys) are skipped directly.
			continue
		}

		info, err := readLinuxProcessInfo(pid)
		if err != nil {
			// The process may have exited, or the current user lacks permission to read it; skipping is enough.
			continue
		}

		if needle != "" {
			comm := strings.ToLower(info.comm)
			cmdline := strings.ToLower(info.cmdline)
			if !strings.Contains(comm, needle) && !strings.Contains(cmdline, needle) {
				continue
			}
		}

		if len(procs) >= limit {
			truncated = true
			break
		}

		procs = append(procs, map[string]any{
			"pid":        info.pid,
			"ppid":       info.ppid,
			"comm":       info.comm,
			"cmdline":    info.cmdline,
			"state":      info.state,
			"rss_kb":     info.rssKB,
			"start_time": info.startTime,
		})
	}

	// Sort ascending by PID to keep the output stable (ReadDir is already ordered, but an explicit sort after filtering is clearer).
	sort.Slice(procs, func(i, j int) bool {
		return procs[i]["pid"].(int) < procs[j]["pid"].(int)
	})

	return map[string]any{
		"processes": procs,
		"count":     len(procs),
		"truncated": truncated,
	}, nil
}

// linuxProcessInfo is the process information parsed from /proc.
type linuxProcessInfo struct {
	pid       int
	ppid      int
	comm      string
	cmdline   string
	state     string
	rssKB     int64
	startTime int64
}

// readLinuxProcessInfo reads the information of a single process.
//
// Data sources:
//   - /proc/<pid>/stat: pid, ppid, comm, state, rss, starttime
//   - /proc/<pid>/cmdline: the full command line (NUL-separated)
func readLinuxProcessInfo(pid int) (*linuxProcessInfo, error) {
	statPath := filepath.Join("/proc", strconv.Itoa(pid), "stat")
	raw, err := os.ReadFile(statPath)
	if err != nil {
		return nil, err
	}

	info, err := parseLinuxProcStat(string(raw))
	if err != nil {
		return nil, err
	}
	info.pid = pid

	// cmdline may be empty for zombie processes or kernel threads; in that case fall back to comm.
	cmdlinePath := filepath.Join("/proc", strconv.Itoa(pid), "cmdline")
	if cmdRaw, err := os.ReadFile(cmdlinePath); err == nil {
		parts := strings.Split(strings.TrimRight(string(cmdRaw), "\x00"), "\x00")
		nonEmpty := make([]string, 0, len(parts))
		for _, p := range parts {
			if p != "" {
				nonEmpty = append(nonEmpty, p)
			}
		}
		info.cmdline = strings.Join(nonEmpty, " ")
	}
	if info.cmdline == "" {
		info.cmdline = "[" + info.comm + "]"
	}

	return info, nil
}

// parseLinuxProcStat parses the content of /proc/<pid>/stat.
//
// The format is: pid (comm) state ppid ... where comm may contain spaces and parentheses,
// so it cannot simply be split on spaces; it must be cut at the last ')'.
func parseLinuxProcStat(raw string) (*linuxProcessInfo, error) {
	open := strings.Index(raw, "(")
	closeIdx := strings.LastIndex(raw, ")")
	if open < 0 || closeIdx < 0 || closeIdx < open {
		return nil, fmt.Errorf("failed to parse stat content: %q", raw)
	}

	comm := raw[open+1 : closeIdx]
	rest := strings.Fields(strings.TrimSpace(raw[closeIdx+1:]))
	// rest is, in order: state ppid pgrp session tty_nr tpgid flags minflt cminflt
	// majflt cmajflt utime stime cutime cstime priority nice num_threads itrealvalue starttime ...
	if len(rest) < 20 {
		return nil, fmt.Errorf("not enough stat fields, actual %d", len(rest))
	}

	ppid, err := strconv.Atoi(rest[1])
	if err != nil {
		return nil, fmt.Errorf("failed to parse ppid: %w", err)
	}
	// rest[21] is rss (in pages); when there are not enough fields it tolerates 0.
	var rssPages int64
	if len(rest) > 21 {
		if v, err := strconv.ParseInt(rest[21], 10, 64); err == nil {
			rssPages = v
		}
	}
	var startTime int64
	if len(rest) > 19 {
		if v, err := strconv.ParseInt(rest[19], 10, 64); err == nil {
			startTime = v
		}
	}

	return &linuxProcessInfo{
		ppid:      ppid,
		comm:      comm,
		state:     rest[0],
		rssKB:     rssPages * int64(os.Getpagesize()) / 1024,
		startTime: startTime,
	}, nil
}

// handleLinuxProcestRack is the implementation of linux.process.kill.
func handleLinuxProcestRack(params map[string]any) (any, error) {
	pid, err := optionalInt(params, "pid", 0)
	if err != nil {
		return nil, err
	}
	if pid == 0 {
		if _, ok := params["pid"]; !ok {
			return nil, fmt.Errorf("missing required parameter pid")
		}
	}
	// pid <= 0 must be rejected: kill(0) affects the entire process group, and kill(-1) affects all processes.
	if pid <= 0 {
		return nil, fmt.Errorf("parameter pid must be a positive integer, actual %d", pid)
	}

	signalName, err := optionalString(params, "signal")
	if err != nil {
		return nil, err
	}
	if signalName == "" {
		signalName = "TERM"
	}
	sig, ok := linuxProcessSignalWhitelist[strings.ToUpper(signalName)]
	if !ok {
		return nil, fmt.Errorf("parameter signal is not in the whitelist: %q, allowed values: TERM, KILL, INT, HUP, QUIT, USR1, USR2, STOP, CONT, 15, 9, 2, 1", signalName)
	}

	if err := syscall.Kill(pid, sig); err != nil {
		return nil, fmt.Errorf("failed to send signal %s to process %d: %w", pid, strings.ToUpper(signalName), err)
	}

	return map[string]any{
		"pid":    pid,
		"signal": strings.ToUpper(signalName),
		"killed": true,
	}, nil
}
