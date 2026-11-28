package buildinfo

import "time"

// Constants and pure functions for converting between Windows FILETIME and Unix time.
//
// Placed in a file with no build tags so this conversion logic can be unit-tested on Linux as well--
// it once had an overflow bug that only surfaced on real hardware (see the comment on filetimeToTime).

const (
	// windowsEpochToUnixSec is the number of seconds from 1601-01-01 to 1970-01-01.
	windowsEpochToUnixSec = 11644473600
	// filetimeTicksPerSecond is the number of counts per second in FILETIME (units of 100ns, hence 1e7).
	filetimeTicksPerSecond = 10000000
)

// filetimeToTime converts a Windows FILETIME 100ns count (since 1601-01-01 UTC)
// into a time.Time.
//
// Why not use syscall.Filetime.Nanoseconds(): it multiplies the count by 100 to convert to nanoseconds and returns
// an int64, while the current instant in nanoseconds is about 1.34e19, already beyond the int64 upper limit (9.22e18),
// so it necessarily overflows to negative. Real hardware once produced an absurd started_at=1657-09-26 this way.
//
// The correct path is to first compute seconds from the 100ns count (about 1.34e17, well within int64),
// then subtract the epoch offset to get Unix seconds, and convert the remaining count into nanoseconds.
func filetimeToTime(ticks int64) time.Time {
	sec := ticks/filetimeTicksPerSecond - windowsEpochToUnixSec
	nsec := (ticks % filetimeTicksPerSecond) * 100
	return time.Unix(sec, nsec)
}
