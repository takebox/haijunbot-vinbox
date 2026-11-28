//go:build windows

package selfupdate

import "os"

// exitForHelperReplacement immediately terminates the current process on Windows, releasing the executable handle for the helper.
//
// Why it must exit directly instead of calling restartService:
//   - the helper's replacement prerequisite is "the target exe is no longer in use", i.e. this process must exit first;
//   - restartService uses service.Restart (Stop + Start), and Stop depends on a PID file.
//     When the daemon is started by a scheduled task (schtasks /Run), no PID file is written (only service start writes one),
//     so Stop reads a stale PID, wrongly concludes "the service is not running" and does **not kill this process**, while Start launches
//     a new process that fails to grab the listening port (verified on a real machine: bind 127.0.0.1:17800 is in use). As a result this process
//     keeps holding the exe, the helper times out after 60 seconds, the replacement fails, and the update never takes effect.
//   - the restart responsibility is on the helper side anyway (--restart flag, calls restartServiceForHelper after a successful replacement),
//     so the parent process neither needs nor should do the restart.
//
// os.Exit(0) does not run defers (e.g. cleaning up temp directories), but the process is about to be replaced, which is acceptable.
func exitForHelperReplacement() {
	os.Exit(0)
}
