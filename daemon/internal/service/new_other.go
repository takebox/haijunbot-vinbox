//go:build !linux && !windows

package service

// newPlatformService returns nil on non-Linux / non-Windows platforms, and New falls back to unsupportedService.
func newPlatformService() Service {
	return nil
}
