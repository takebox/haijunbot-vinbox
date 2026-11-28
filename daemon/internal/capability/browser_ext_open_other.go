//go:build !windows

package capability

// openBrowserExtensionsPage is a no-op implementation on non-Windows platforms.
//
// Why it is needed: automatically opening the browser extensions page is only implemented on Windows (using PowerShell's
// Start-Process). This no-op implementation lets the caller (the auto-sync path in main.go) call it unconditionally
// across platforms, without needing platform branches in the upper layer.
//
// Returns an empty list without error: non-Windows platforms do not provide this capability, and the caller can simply skip it on that basis.
func OpenBrowserExtensionsPage() ([]string, error) {
	return nil, nil
}
