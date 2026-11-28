//go:build windows

package buildinfo

import (
	"syscall"
	"time"
)

// processStartTime obtains the creation time of the current process via GetProcessTimes.
//
// Uses only the standard library syscall (kernel32!GetProcessTimes), without introducing golang.org/x/sys.
// Returns ok=false on failure.
func processStartTime() (time.Time, bool) {
	handle, err := syscall.GetCurrentProcess()
	if err != nil {
		return time.Time{}, false
	}

	var creation, exit, kernel, user syscall.Filetime
	err = syscall.GetProcessTimes(handle, &creation, &exit, &kernel, &user)
	if err != nil {
		return time.Time{}, false
	}

	// FILETIME is an unsigned 64-bit count in units of 100 nanoseconds since 1601-01-01 UTC.
	// The conversion logic is factored into filetimeToTime in filetime.go (no build tags, unit-testable on Linux),
	// which explains in detail why creation.Nanoseconds() cannot be used (it overflows int64).
	ticks := int64(creation.HighDateTime)<<32 | int64(creation.LowDateTime)
	return filetimeToTime(ticks), true
}
