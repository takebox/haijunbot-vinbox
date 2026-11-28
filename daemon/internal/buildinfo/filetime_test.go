package buildinfo

import (
	"testing"
	"time"
)

// TestFiletimeToTimeKnownValue verifies the conversion against a FILETIME count reported from real hardware.
//
// Background: a real machine once reported started_at=1657-09-26T15:34:09Z (started_at_unix=-9854036751),
// an absurd value. The root cause was using syscall.Filetime.Nanoseconds()--it multiplies the 100ns count by 100
// to convert to nanoseconds and returns an int64, while the current instant in nanoseconds is about 1.34e19 >
// int64 upper limit 9.22e18, so it necessarily overflows. This case locks in the correct behavior after the fix.
func TestFiletimeToTimeKnownValue(t *testing.T) {
	// Reverse-engineered from the real machine report: the wrong value -9854036751 plus the epoch offset yields the correct Unix seconds.
	const wantUnixSec = 1790436849 // 2026-09-26T15:34:09Z
	ticks := (int64(wantUnixSec) + windowsEpochToUnixSec) * filetimeTicksPerSecond

	got := filetimeToTime(ticks)

	if got.Unix() != wantUnixSec {
		t.Fatalf("filetimeToTime(%d).Unix() = %d, expected %d", ticks, got.Unix(), wantUnixSec)
	}
	if got.UTC().Format(time.RFC3339) != "2026-09-26T15:34:09Z" {
		t.Fatalf("formatted result = %q, expected %q", got.UTC().Format(time.RFC3339), "2026-09-26T15:34:09Z")
	}
	if got.Unix() < 0 {
		t.Fatalf("the Unix timestamp is negative (%d), which means an int64 overflow occurred", got.Unix())
	}
}

// TestFiletimeToTimeNoOverflow confirms the conversion near the current instant does not overflow to negative.
//
// This is precisely the criterion of the original bug: before the fix, the int64 overflow made the result fall back to around 1601 (negative timestamps).
func TestFiletimeToTimeNoOverflow(t *testing.T) {
	// Cover 2020-01-01 through 2100-01-01, ensuring the whole range is positive and monotonically increasing.
	start := time.Date(2020, 1, 1, 0, 0, 0, 0, time.UTC).Unix()
	end := time.Date(2100, 1, 1, 0, 0, 0, 0, time.UTC).Unix()

	var prev int64 = -1
	for sec := start; sec <= end; sec += 86400 * 365 {
		ticks := (sec + windowsEpochToUnixSec) * filetimeTicksPerSecond
		got := filetimeToTime(ticks).Unix()
		if got != sec {
			t.Fatalf("filetimeToTime round-trip mismatch at %d: got %d", sec, got)
		}
		if got <= prev {
			t.Fatalf("timestamps are not monotonically increasing: %d then %d", prev, got)
		}
		prev = got
	}
}

// TestFiletimeToTimeSubSecond confirms the sub-second part (the 100ns count remainder) converts correctly.
func TestFiletimeToTimeSubSecond(t *testing.T) {
	const baseSec = 1790436849
	// Add 0.5 seconds = 5,000,000 100ns counts.
	ticks := (int64(baseSec)+windowsEpochToUnixSec)*filetimeTicksPerSecond + 5000000

	got := filetimeToTime(ticks)

	if got.Unix() != baseSec {
		t.Fatalf("seconds part = %d, expected %d", got.Unix(), baseSec)
	}
	if got.Nanosecond() != 500000000 {
		t.Fatalf("nanoseconds part = %d, expected 500000000", got.Nanosecond())
	}
}
