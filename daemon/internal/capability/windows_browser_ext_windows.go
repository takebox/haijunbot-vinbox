//go:build windows

package capability

// registerWindowsBrowserExt registers the browser extension download/update capability for the Windows platform.
//
// The semantics are fully identical to the Linux side (same capability name, same parameters, same return structure); the only difference is the Platform
// field; the actual logic is reused from browser_ext.go / browser_ext_cap.go.
func registerWindowsBrowserExt(reg *Registry) {
	registerBrowserExt(reg, PlatformWindows)
}
