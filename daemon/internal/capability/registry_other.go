//go:build !linux && !windows

package capability

// registerPlatformCapabilities registers capabilities specific to other platforms (such as darwin).
//
// This round only implements the framework and registers no actual capabilities; platform-specific capabilities will be registered here later.
func registerPlatformCapabilities(reg *Registry) {
	_ = reg
}
