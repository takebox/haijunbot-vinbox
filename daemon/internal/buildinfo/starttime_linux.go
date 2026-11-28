//go:build linux

package buildinfo

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// processStartTime derives the process start time from the 22nd field of /proc/self/stat
// (starttime, in jiffies).
//
// This field is the number of clock ticks elapsed since the process started, which must be divided by the system
// clock frequency (USER_HZ) to convert to seconds. On Linux USER_HZ is always 100 (a POSIX convention, and the Go
// runtime also assumes this), so 100 is used directly here to avoid introducing a sysconf call.
//
// Returns ok=false on failure.
func processStartTime() (time.Time, bool) {
	data, err := os.ReadFile("/proc/self/stat")
	if err != nil {
		return time.Time{}, false
	}

	content := string(data)
	// The process name may contain spaces and be wrapped in parentheses (e.g. "(my proc)"), so split from after the last ')'.
	idx := strings.LastIndexByte(content, ')')
	if idx < 0 || idx+2 >= len(content) {
		return time.Time{}, false
	}
	fields := strings.Fields(content[idx+2:])
	// After the split, fields[0] corresponds to the 3rd field of stat (state);
	// starttime is the 22nd field, so its index is 22-3 = 19.
	const starttimeIndex = 19
	if len(fields) <= starttimeIndex {
		return time.Time{}, false
	}

	jiffies, err := strconv.ParseInt(fields[starttimeIndex], 10, 64)
	if err != nil {
		return time.Time{}, false
	}

	// System boot time + the seconds the process has been running = the process start instant.
	bootTime, ok := systemBootTime()
	if !ok {
		return time.Time{}, false
	}

	const userHZ = 100
	start := bootTime.Add(time.Duration(jiffies/userHZ) * time.Second)
	return start, true
}

// systemBootTime reads the btime line of /proc/stat (the system boot Unix timestamp).
func systemBootTime() (time.Time, bool) {
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return time.Time{}, false
	}
	for _, line := range strings.Split(string(data), "\n") {
		if !strings.HasPrefix(line, "btime ") {
			continue
		}
		sec, err := strconv.ParseInt(strings.TrimSpace(strings.TrimPrefix(line, "btime ")), 10, 64)
		if err != nil {
			return time.Time{}, false
		}
		return time.Unix(sec, 0), true
	}
	return time.Time{}, false
}
