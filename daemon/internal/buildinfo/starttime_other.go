//go:build !linux && !windows

package buildinfo

import "time"

// processStartTime is not yet supported on non-Linux/Windows platforms (e.g. darwin),
// so it returns ok=false and the caller degrades to BuildTimeSource="unknown".
//
// Why not implement it: darwin needs platform-specific calls like sysctl KERN_PROC_PID,
// while the daemon's production platforms are Windows (user machine SF-PC) and Linux (the gateway host itself);
// darwin only needs to compile. It can be added here later if support is required.
func processStartTime() (time.Time, bool) {
	return time.Time{}, false
}
