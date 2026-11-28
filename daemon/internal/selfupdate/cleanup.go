package selfupdate

import (
	"log"
	"os"

	"haijunbot-daemon/internal/service"
)

// CleanupAfterUpdate cleans up the intermediate artifacts left behind by the previous auto-update when the new process starts.
//
// Why it must be done at **new process startup** (not when the update flow ends):
//   - On Windows, the update goes through the helper path, and the parent process calls os.Exit(0) immediately after
//     starting the helper (see exitForHelperReplacement in updater.go), so the parent process never reaches any
//     "cleanup" code;
//   - the helper also exits after the replacement, and it runs on <target>.helper.exe itself; Windows does not allow
//     deleting a running executable, so the helper cannot even delete itself.
//
// Therefore, the only safe time to clean up is "when the new daemon process starts after the replacement and service restart"--
// at that point the helper has exited and the old process has exited, so neither leftover file is in use.
//
// Cleanup contents:
//  1. The attempt state file (~/.haijunbot/daemon/update-attempt.json): if the recorded target version matches the current
//     running version and state is InProgress, the update has fully succeeded, so that state is cleared. Otherwise it is kept
//     (failure backoff/circuit-breaker info must survive restarts).
//  2. The <target>.new and <target>.helper.exe leftovers in the same directory as the target executable.
//
// Any step failure is only logged and never affects normal daemon startup.
func CleanupAfterUpdate(currentVersion string) {
	clearSettledAttemptState(currentVersion)
	removeUpdateLeftovers()
}

// clearSettledAttemptState clears the attempt state when the update has fully succeeded.
//
// Judgment condition: the target version recorded in the state == the current running version, and InProgress is true.
// Why it is needed: if not cleared after success, InProgress would linger forever; although the next time the gateway
// sends a new version the target version change auto-releases the circuit breaker (see ShouldSkipUpdate), if the gateway
// keeps sending the same version, the lingering InProgress would keep the daemon permanently broken and recovery would
// require manual file deletion. Clearing it here removes that fragility.
func clearSettledAttemptState(currentVersion string) {
	state, ok := LoadAttemptState()
	if !ok {
		return
	}
	if !state.InProgress || !SameVersion(state.TargetVersion, currentVersion) {
		// Not the "just updated successfully" scenario: it may be a failure backoff/circuit-break record that must be kept.
		return
	}
	if err := ClearAttemptState(); err != nil {
		log.Printf("[selfupdate] failed to clear the completed update attempt state (does not affect running): %v", err)
		return
	}
	log.Printf("[selfupdate] auto-update confirmed effective (%s), update attempt state cleared", currentVersion)
}

// removeUpdateLeftovers deletes the update leftover files in the same directory as the target executable.
//
// A missing file is treated as normal (idempotent); a delete failure is only logged -- e.g. when the user manually made the file read-only.
func removeUpdateLeftovers() {
	target, err := service.InstalledBinaryPath()
	if err != nil {
		return
	}
	for _, path := range []string{target + ".new", target + ".helper.exe"} {
		if err := os.Remove(path); err != nil {
			if !os.IsNotExist(err) {
				log.Printf("[selfupdate] failed to clean up update leftover files (can be removed manually) %s: %v", path, err)
			}
			continue
		}
		log.Printf("[selfupdate] cleaned up update leftover file: %s", path)
	}
}
