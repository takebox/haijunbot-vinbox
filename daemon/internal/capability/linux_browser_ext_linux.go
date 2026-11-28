//go:build linux

package capability

// registerLinuxBrowserExt registers the browser extension download/update capability for the Linux platform.
//
// The semantics are fully identical to the Windows side (same capability name, same parameters, same return structure); the only difference is the Platform
// field; the actual logic is reused from browser_ext.go / browser_ext_cap.go.
func registerLinuxBrowserExt(reg *Registry) {
	registerBrowserExt(reg, PlatformLinux)
}
