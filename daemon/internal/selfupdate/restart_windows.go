//go:build windows

package selfupdate

import "haijunbot-daemon/internal/service"

// restartService restarts the daemon via a scheduled task on Windows.
//
// If the service is not installed (e.g. the user runs it in the foreground), Restart returns an error; the caller only logs it,
// which does not affect the fact that "the file has been replaced with the new version".
func restartService() error {
	_, err := service.New().Restart()
	return err
}
