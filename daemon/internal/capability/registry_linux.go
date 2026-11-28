//go:build linux

package capability

// registerPlatformCapabilities registers capabilities specific to the Linux platform.
//
// Capabilities are split by domain into separate files; this only does the assembly:
//   - linux_script_linux.go: script execution
//   - linux_process_linux.go: process listing and signals
//   - linux_system_linux.go: system information
//   - linux_fs_linux.go: filesystem read/write and directory listing
//   - linux_service_linux.go: systemd user service management
//   - linux_gui_linux.go: window/input/clipboard/screenshot (depends on external commands)
//   - linux_browser_ext_linux.go: browser extension download and update
func registerPlatformCapabilities(reg *Registry) {
	registerLinuxScript(reg)
	registerLinuxProcess(reg)
	registerLinuxSystem(reg)
	registerLinuxFS(reg)
	// Cross-machine direct file transfer (push/pull): logic shared across platforms, only the Platform field differs
	registerTransferRemote(reg, PlatformLinux)
	registerLinuxService(reg)
	registerLinuxGUI(reg)
	registerLinuxBrowserExt(reg)
	// OCR text recognition: logic shared across platforms (images recognized via the gateway), only the Platform field differs
	registerOcr(reg, PlatformLinux)
}
