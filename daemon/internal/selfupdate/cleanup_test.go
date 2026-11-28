package selfupdate

import (
	"os"
	"path/filepath"
	"testing"

	"haijunbot-daemon/internal/service"
)

// TestCleanupAfterUpdateClearsSettledState verifies that the attempt state is cleared when "the update has fully succeeded".
//
// Scenario: the state records InProgress=true with target version == current running version, meaning the previous update
// took effect; the state should be cleared (otherwise the lingering InProgress would permanently break the circuit when the gateway keeps sending the same version).
func TestCleanupAfterUpdateClearsSettledState(t *testing.T) {
	withTempHome(t)

	if err := SaveAttemptState(AttemptState{
		TargetVersion:   "6.0.1",
		Attempts:        0,
		LastAttemptUnix: NowUnix(),
		InProgress:      true,
	}); err != nil {
		t.Fatalf("failed to write the attempt state: %v", err)
	}

	CleanupAfterUpdate("v6.0.1")

	if _, ok := LoadAttemptState(); ok {
		t.Fatal("the attempt state should be cleared when the update is settled, but the state file still exists")
	}
}

// TestCleanupAfterUpdateKeepsFailedState verifies that failure backoff/circuit-break state is not mistakenly cleared.
//
// Scenario: the target version differs from the current version (the update did not take effect), or InProgress=false
// (a failure record); such states must be kept, otherwise the cross-restart backoff and circuit-break protection are lost.
func TestCleanupAfterUpdateKeepsFailedState(t *testing.T) {
	cases := []struct {
		name    string
		state   AttemptState
		version string
	}{
		{
			name: "target version differs from the current version (the update did not take effect)",
			state: AttemptState{
				TargetVersion:   "6.0.2",
				Attempts:        1,
				LastAttemptUnix: NowUnix(),
				InProgress:      true,
			},
			version: "v6.0.1",
		},
		{
			name: "InProgress=false (failure backoff record)",
			state: AttemptState{
				TargetVersion:   "6.0.1",
				Attempts:        2,
				LastAttemptUnix: NowUnix(),
				LastError:       "download failed",
				InProgress:      false,
			},
			version: "v6.0.1",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			withTempHome(t)
			if err := SaveAttemptState(tc.state); err != nil {
				t.Fatalf("failed to write the attempt state: %v", err)
			}

			CleanupAfterUpdate(tc.version)

			got, ok := LoadAttemptState()
			if !ok {
				t.Fatal("the attempt state must be kept in this scenario, but the file was deleted")
			}
			if got.Attempts != tc.state.Attempts || got.LastError != tc.state.LastError {
				t.Fatalf("state was unexpectedly modified: got=%+v want=%+v", got, tc.state)
			}
		})
	}
}

// TestCleanupAfterUpdateRemovesLeftovers verifies cleaning up the .new / .helper.exe leftover files.
func TestCleanupAfterUpdateRemovesLeftovers(t *testing.T) {
	withTempHome(t)

	target, err := service.InstalledBinaryPath()
	if err != nil {
		t.Fatalf("failed to get the install path: %v", err)
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		t.Fatalf("failed to create the install directory: %v", err)
	}
	leftovers := []string{target + ".new", target + ".helper.exe"}
	for _, p := range leftovers {
		if err := os.WriteFile(p, []byte("stub"), 0o755); err != nil {
			t.Fatalf("failed to create the leftover file %s: %v", p, err)
		}
	}

	CleanupAfterUpdate("v6.0.1")

	for _, p := range leftovers {
		if _, err := os.Stat(p); !os.IsNotExist(err) {
			t.Fatalf("the leftover file %s should have been deleted, stat err=%v", p, err)
		}
	}
}

// TestCleanupAfterUpdateIdempotent verifies that calling with no leftovers does not error (idempotent).
func TestCleanupAfterUpdateIdempotent(t *testing.T) {
	withTempHome(t)
	CleanupAfterUpdate("v6.0.1")
	CleanupAfterUpdate("v6.0.1")
}
