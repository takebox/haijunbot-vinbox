//go:build linux

package service

// newPlatformService returns the systemd user service implementation on Linux.
func newPlatformService() Service {
	return &systemdService{}
}
