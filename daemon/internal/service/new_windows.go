//go:build windows

package service

// newPlatformService returns the scheduled task implementation on Windows.
func newPlatformService() Service {
	return &taskService{}
}
