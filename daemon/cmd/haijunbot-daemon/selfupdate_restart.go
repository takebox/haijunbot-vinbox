package main

import "haijunbot-daemon/internal/service"

// restartServiceForHelper is called by the update helper after the replacement completes, to restart the daemon service.
//
// It has the same semantics as restartService inside the selfupdate package, but lives here in the cmd package,
// directly reusing service.Service's Restart implementation (Windows scheduled task / Linux systemd).
func restartServiceForHelper() error {
	_, err := service.New().Restart()
	return err
}
