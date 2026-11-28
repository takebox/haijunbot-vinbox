package selfupdate

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// withTempHome points HOME at a temp directory and returns a cleanup function.
//
// The attempt state file path is determined by os.UserHomeDir(); tests must isolate HOME,
// otherwise they would pollute ~/.haijunbot/daemon/update-attempt.json on the developer's machine.
func withTempHome(t *testing.T) {
	t.Helper()
	old := os.Getenv("HOME")
	dir := t.TempDir()
	if err := os.Setenv("HOME", dir); err != nil {
		t.Fatalf("failed to set HOME: %v", err)
	}
	t.Cleanup(func() { _ = os.Setenv("HOME", old) })
}

func TestNormalizeVersion(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{"v5.0.5", "5.0.5"},
		{"V6.0.0", "6.0.0"},
		{"6.0.0", "6.0.0"},
		{"  v1.2.3  ", "1.2.3"},
		{"", ""},
		{"vv1.0.0", "1.0.0"},
	}
	for _, c := range cases {
		if got := NormalizeVersion(c.in); got != c.want {
			t.Errorf("NormalizeVersion(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestSameVersion(t *testing.T) {
	if !SameVersion("v6.0.0", "6.0.0") {
		t.Error("v6.0.0 and 6.0.0 should be treated as the same version")
	}
	if !SameVersion(" 6.0.0 ", "V6.0.0") {
		t.Error("whitespace and case differences should be treated as the same version")
	}
	if SameVersion("6.0.0", "6.0.1") {
		t.Error("6.0.0 and 6.0.1 should not be treated as the same version")
	}
}

func TestBackoffFor(t *testing.T) {
	cases := []struct {
		attempts int
		want     time.Duration
	}{
		{0, 0},
		{-1, 0},
		{1, time.Minute},
		{2, 5 * time.Minute},
		{3, 30 * time.Minute},
		{4, 30 * time.Minute},
		{100, 30 * time.Minute},
	}
	for _, c := range cases {
		if got := BackoffFor(c.attempts); got != c.want {
			t.Errorf("BackoffFor(%d) = %v, want %v", c.attempts, got, c.want)
		}
	}
	if MaxBackoff() != 30*time.Minute {
		t.Errorf("MaxBackoff() = %v, want 30m", MaxBackoff())
	}
}

func TestAttemptStateSaveLoadClear(t *testing.T) {
	withTempHome(t)

	// Does not exist initially.
	if _, ok := LoadAttemptState(); ok {
		t.Fatal("the attempt state should not exist initially")
	}

	want := AttemptState{
		TargetVersion:   "v6.0.0",
		Attempts:        2,
		LastAttemptUnix: 1700000000,
		LastError:       "download failed",
		InProgress:      true,
	}
	if err := SaveAttemptState(want); err != nil {
		t.Fatalf("failed to save the attempt state: %v", err)
	}

	path, err := AttemptStatePath()
	if err != nil {
		t.Fatalf("failed to get the path: %v", err)
	}
	if filepath.Base(path) != "update-attempt.json" {
		t.Errorf("file name = %s, want update-attempt.json", filepath.Base(path))
	}
	// Permission should be 0600.
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat failed: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("permission = %o, want 600", perm)
	}

	got, ok := LoadAttemptState()
	if !ok {
		t.Fatal("the attempt state should be readable")
	}
	if got != want {
		t.Errorf("read back = %+v, want %+v", got, want)
	}

	// After clearing it should not be readable, and repeated clearing is idempotent.
	if err := ClearAttemptState(); err != nil {
		t.Fatalf("failed to clear: %v", err)
	}
	if _, ok := LoadAttemptState(); ok {
		t.Error("should not read the attempt state after clearing")
	}
	if err := ClearAttemptState(); err != nil {
		t.Errorf("repeated clearing should be idempotent, got %v", err)
	}
}

func TestLoadAttemptStateCorrupt(t *testing.T) {
	withTempHome(t)
	path, err := AttemptStatePath()
	if err != nil {
		t.Fatalf("failed to get the path: %v", err)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		t.Fatalf("failed to create the directory: %v", err)
	}
	if err := os.WriteFile(path, []byte("{not valid json"), 0o600); err != nil {
		t.Fatalf("failed to write the corrupt file: %v", err)
	}
	if _, ok := LoadAttemptState(); ok {
		t.Error("a corrupt file should not be parsed successfully")
	}
}

func TestShouldSkipUpdate(t *testing.T) {
	const now = int64(1700000000)

	t.Run("no state means no skip", func(t *testing.T) {
		skip, _ := ShouldSkipUpdate(AttemptState{}, "v5.0.5", "6.0.0", now)
		if skip {
			t.Error("should not skip with no historical state")
		}
	})

	t.Run("same-version failure skips within the backoff window", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 10, // backoff 1min, only 10s elapsed
			LastError:       "download failed",
		}
		skip, reason := ShouldSkipUpdate(state, "v5.0.5", "6.0.0", now)
		if !skip {
			t.Error("should skip within the backoff window")
		}
		if reason == "" {
			t.Error("a reason should be given when skipping")
		}
	})

	t.Run("same-version failure retries after the backoff window", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 61, // more than 1min
			LastError:       "download failed",
		}
		skip, _ := ShouldSkipUpdate(state, "v5.0.5", "6.0.0", now)
		if skip {
			t.Error("a retry should be allowed after the backoff window")
		}
	})

	t.Run("backoff time increases with repeated failures", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        2,
			LastAttemptUnix: now - 61, // 2nd backoff 5min, only 61s elapsed
			LastError:       "download failed",
		}
		skip, _ := ShouldSkipUpdate(state, "v5.0.5", "6.0.0", now)
		if !skip {
			t.Error("2nd failure backs off 5min, still should skip after 61s")
		}
	})

	t.Run("a target version change allows retry", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        3,
			LastAttemptUnix: now - 1,
			LastError:       "download failed",
		}
		skip, _ := ShouldSkipUpdate(state, "v5.0.5", "6.0.1", now)
		if skip {
			t.Error("a target version change should allow attempting")
		}
	})

	t.Run("InProgress with unchanged version breaks the circuit", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 99999,
			InProgress:      true,
		}
		skip, reason := ShouldSkipUpdate(state, "v5.0.5", "6.0.0", now)
		if !skip {
			t.Error("a restart loop should break the circuit")
		}
		if reason == "" {
			t.Error("a reason should be given when the circuit breaks")
		}
	})

	t.Run("recovery after the circuit breaks once the gateway sends a new version", func(t *testing.T) {
		state := AttemptState{
			TargetVersion: "6.0.0",
			InProgress:    true,
		}
		skip, _ := ShouldSkipUpdate(state, "v5.0.5", "6.0.1", now)
		if skip {
			t.Error("a new version from the gateway should recover the attempt")
		}
	})

	t.Run("circuit-break judgment is unaffected by the version v prefix", func(t *testing.T) {
		state := AttemptState{TargetVersion: "v6.0.0", InProgress: true}
		skip, _ := ShouldSkipUpdate(state, "v5.0.5", "6.0.0", now)
		if !skip {
			t.Error("v6.0.0 and 6.0.0 should be treated as the same target, still broken")
		}
	})
}

func TestRetryAfter(t *testing.T) {
	const now = int64(1700000000)

	t.Run("no state means no wait needed", func(t *testing.T) {
		if got := RetryAfter(AttemptState{}, "v5.0.5", "6.0.0", now); got != 0 {
			t.Errorf("RetryAfter = %v, want 0", got)
		}
	})

	t.Run("a target version change means no wait needed", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        3,
			LastAttemptUnix: now - 1,
		}
		if got := RetryAfter(state, "v5.0.5", "6.0.1", now); got != 0 {
			t.Errorf("RetryAfter = %v, want 0 on target change", got)
		}
	})

	t.Run("circuit-break state returns 0 meaning no retry", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 1,
			InProgress:      true,
		}
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != 0 {
			t.Errorf("RetryAfter = %v, want 0 in circuit-break state", got)
		}
	})

	t.Run("returns the remaining time within the backoff window", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 10, // backoff 1min, 10s elapsed
		}
		want := 50 * time.Second
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != want {
			t.Errorf("RetryAfter = %v, want %v", got, want)
		}
	})

	t.Run("returns 0 after the backoff window", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 61,
		}
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != 0 {
			t.Errorf("RetryAfter = %v, want 0 after backoff", got)
		}
	})

	t.Run("2nd failure computed with the 5min tier", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        2,
			LastAttemptUnix: now - 61,
		}
		want := 5*time.Minute - 61*time.Second
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != want {
			t.Errorf("RetryAfter = %v, want %v", got, want)
		}
	})

	t.Run("beyond the ladder caps at 30min", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "6.0.0",
			Attempts:        100,
			LastAttemptUnix: now - 10,
		}
		want := 30*time.Minute - 10*time.Second
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != want {
			t.Errorf("RetryAfter = %v, want %v", got, want)
		}
	})

	t.Run("the version v prefix does not affect judgment", func(t *testing.T) {
		state := AttemptState{
			TargetVersion:   "v6.0.0",
			Attempts:        1,
			LastAttemptUnix: now - 10,
		}
		if got := RetryAfter(state, "v5.0.5", "6.0.0", now); got != 50*time.Second {
			t.Errorf("RetryAfter = %v, want 50s", got)
		}
	})
}
