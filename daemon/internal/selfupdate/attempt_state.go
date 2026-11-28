package selfupdate

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Failure backoff ladder: on consecutive failures, the waiting duration is picked by the count; past the last tier, the last tier is kept.
//
// Why it is needed: the auto-update trigger point is each WS handshake (hello → hello_ack). If the update keeps
// failing (download failure, replacement failure, etc.), the daemon version does not change, and the gateway re-sends
// available=true at every handshake, forming a "reconnect means retry" storm. Backoff keeps the retry frequency within a controllable range.
var backoffLadder = []time.Duration{
	1 * time.Minute,
	5 * time.Minute,
	30 * time.Minute,
}

// MaxBackoff is the backoff ceiling (the last tier), for callers and tests to reference.
func MaxBackoff() time.Duration { return backoffLadder[len(backoffLadder)-1] }

// BackoffFor returns the waiting duration after attempts consecutive failures.
//
// attempts <= 0 is treated as no failure (returns 0); beyond the ladder length, the last tier is used.
func BackoffFor(attempts int) time.Duration {
	if attempts <= 0 {
		return 0
	}
	if attempts > len(backoffLadder) {
		attempts = len(backoffLadder)
	}
	return backoffLadder[attempts-1]
}

// AttemptState is the auto-update attempt state, persisted to disk to recognize a "restart loop" across process restarts.
//
// Why it must be persisted (in-memory alone is not enough): the most dangerous failure mode is "replacement succeeded but the new version does not start"—
// after the new process starts the version is still old, and at handshake the gateway again decides an update is needed, so it replaces and restarts again,
// looping endlessly with the daemon never coming up. Only by persisting "which version is being updated to" can the new process
// discover at startup that it "just tried to update to X but is still on the old version", and thus trip the circuit breaker.
//
// Difference from TokenState: this file contains no credentials, only the version and counts, so long-term residency poses no security risk.
type AttemptState struct {
	// TargetVersion is the version number of the most recent update attempt (raw format, may have a v prefix).
	TargetVersion string `json:"target_version"`
	// Attempts is the consecutive failure count for the same target version (cleared on success or when the target changes).
	Attempts int `json:"attempts"`
	// LastAttemptUnix is the time of the most recent attempt (Unix seconds).
	LastAttemptUnix int64 `json:"last_attempt_unix"`
	// LastError is the reason for the most recent failure (for debugging; empty on success).
	LastError string `json:"last_error"`
	// InProgress indicates "replacement has started but success is not yet confirmed". If it is true and the version
	// is unchanged after a process restart, it is judged as a restart loop.
	InProgress bool `json:"in_progress"`
}

// AttemptStatePath returns the attempt state file path: ~/.haijunbot/daemon/update-attempt.json.
//
// In the same directory as TokenStatePath (~/.haijunbot/daemon/), for easy user debugging.
func AttemptStatePath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", "daemon", "update-attempt.json"), nil
}

// SaveAttemptState writes the attempt state to a file (0600).
//
// A write failure returns an error; the caller only logs it and does not block the update flow (worst case is losing the cross-restart circuit breaker).
func SaveAttemptState(state AttemptState) error {
	path, err := AttemptStatePath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("failed to create the state directory: %w", err)
	}
	blob, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to serialize the attempt state: %w", err)
	}
	// Write to a temp file first, then rename, to avoid a half-written file.
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, blob, 0o600); err != nil {
		return fmt.Errorf("failed to write the attempt state temp file: %w", err)
	}
	_ = os.Chmod(tmp, 0o600)
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("failed to save the attempt state: %w", err)
	}
	return nil
}

// LoadAttemptState reads the attempt state; when the file is missing or parsing fails it returns the zero value and false.
func LoadAttemptState() (AttemptState, bool) {
	path, err := AttemptStatePath()
	if err != nil {
		return AttemptState{}, false
	}
	blob, err := os.ReadFile(path)
	if err != nil {
		return AttemptState{}, false
	}
	var state AttemptState
	if err := json.Unmarshal(blob, &state); err != nil {
		return AttemptState{}, false
	}
	return state, true
}

// ClearAttemptState deletes the attempt state file (absence is treated as success; idempotent).
func ClearAttemptState() error {
	path, err := AttemptStatePath()
	if err != nil {
		return err
	}
	if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete the attempt state: %w", err)
	}
	return nil
}

// NormalizeVersion normalizes a version: trim whitespace + strip a leading v/V.
//
// Why it is needed: the gateway version comes from haijunbot.__version__ (e.g. "6.0.0", no v prefix),
// while the daemon version is build-injected (e.g. "v5.0.5", with v). Without normalization, "actually the same version
// judged as different" occurs → an endless download-restart loop.
func NormalizeVersion(value string) string {
	v := strings.TrimSpace(value)
	for len(v) > 0 && (v[0] == 'v' || v[0] == 'V') {
		v = v[1:]
	}
	return v
}

// SameVersion determines whether two version numbers are the same (compared after normalization; case- and leading-v-insensitive).
func SameVersion(a, b string) bool {
	return NormalizeVersion(a) == NormalizeVersion(b)
}

// ShouldSkipUpdate determines whether this auto-update should be skipped (centralized duplicate-prevention decision).
//
// Arguments:
//   - state: the persisted attempt state;
//   - currentVersion: the current daemon version (e.g. "v5.0.5");
//   - targetVersion: the latest version issued by the gateway this time (e.g. "6.0.0");
//   - now: current time (Unix seconds), for test injection.
//
// Returns (skip, reason): when skip is true the update should be skipped; reason is the reason (for logs).
//
// Decision order:
//  1. Circuit break: the last attempt "started replacement" but after a restart the version is still old (and the target version matches this one)
//     → judged as a restart loop, skip, to avoid endless restarts;
//  2. Circuit-break recovery: if this target version differs from the circuit-break record's target version (the gateway issued a new version)
//     → clear the circuit break, allow the attempt;
//  3. Same-version failure no-retry + backoff: the previously failed target version matches this one, and still within the backoff window
//     → skip; once the window has passed, allow retry (Attempts keeps accumulating).
func ShouldSkipUpdate(state AttemptState, currentVersion, targetVersion string, now int64) (bool, string) {
	if !SameVersion(state.TargetVersion, targetVersion) {
		// Target version changed: whether the last outcome was a circuit break or a failure, treat it as a new opportunity and allow the attempt.
		return false, ""
	}
	if state.InProgress {
		// Replacement started last time but still on the old version → the new version did not start (or the replacement did not take effect), trip the breaker.
		return true, fmt.Sprintf("restart loop detected: last time it tried to update to %s but the current version is still %s; auto-update has been circuit-broken (recovers automatically once the gateway publishes a new version)",
			targetVersion, currentVersion)
	}
	if state.Attempts > 0 {
		wait := BackoffFor(state.Attempts)
		elapsed := now - state.LastAttemptUnix
		if elapsed < int64(wait/time.Second) {
			return true, fmt.Sprintf("update to %s failed last time (%dth time, reason: %s); backing off (about %d seconds left)",
				targetVersion, state.Attempts, state.LastError, int64(wait/time.Second)-elapsed)
		}
	}
	return false, ""
}

// RetryAfter returns how long to wait before the next retry; returns 0 when no wait is needed (or retry is not allowed).
//
// Why it is needed: ShouldSkipUpdate is only called at the "trigger point" (WS handshake receiving hello_ack).
// But when the connection is stable there is only ping/pong heartbeat, which does not produce hello_ack; and when the frontend re-pushes identical credentials,
// ConnectWithName skips rebuilding the connection due to idempotency (see wsclient/manager.go), which likewise produces no
// hello_ack. The result is that once the backoff window expires, no event wakes the check, and the update stalls forever.
// The caller schedules a timer based on this return value, achieving "auto retry when backoff expires", no longer relying on external handshake events.
//
// The returns of 0 in different situations need differentiated handling by the caller:
//   - target version changed / no failure record: should attempt immediately;
//   - circuit-broken state (InProgress and target version unchanged): must not retry, otherwise it falls into a restart loop.
//
// Therefore the caller should first use ShouldSkipUpdate to decide "whether to skip", and only when skipping use this function to get the wait
// duration; if it returns 0, it is the circuit-broken state and no retry may be scheduled.
func RetryAfter(state AttemptState, currentVersion, targetVersion string, now int64) time.Duration {
	if !SameVersion(state.TargetVersion, targetVersion) {
		// Target version changed: treat it as a new opportunity, no wait needed.
		return 0
	}
	if state.InProgress {
		// Circuit-broken state: recovery only happens when the gateway publishes a new version; no retry is scheduled here.
		return 0
	}
	if state.Attempts > 0 {
		wait := BackoffFor(state.Attempts)
		elapsed := now - state.LastAttemptUnix
		if remaining := wait - time.Duration(elapsed)*time.Second; remaining > 0 {
			return remaining
		}
	}
	return 0
}
