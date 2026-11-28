//go:build windows

package capability

// registerPlatformCapabilities registers capabilities specific to the Windows platform.
//
// Capabilities are split by domain into separate files; this only does the assembly:
//   - windows_system_windows.go: system information
//   - windows_process_windows.go: process listing and process termination
//   - windows_app_windows.go: installed application query
//   - windows_gui_windows.go: window control (list/focus/close)
//   - windows_input_windows.go: input simulation (mouse click/type text/key combination)
//   - windows_clipboard_windows.go: clipboard read/write and screenshot
//   - windows_script_windows.go: script execution
//   - windows_fs_windows.go: filesystem read/write and directory listing
//   - windows_service_windows.go: system service query and start/stop
//   - windows_config_windows.go: system configuration (theme/power plan/proxy/screen timeout/remote desktop/startup)
//   - windows_ui_windows.go: UI automation (control tree enumeration/menu operations)
//   - windows_browser_ext_windows.go: browser extension download and update
//   - windows_common_windows.go: parameter parsing and external command helper functions
func registerPlatformCapabilities(reg *Registry) {
	registerWindowsSystem(reg)
	registerWindowsProcess(reg)
	registerWindowsApp(reg)
	registerWindowsGUI(reg)
	registerWindowsInput(reg)
	registerWindowsClipboard(reg)
	registerWindowsScript(reg)
	registerWindowsFS(reg)
	// Cross-machine direct file transfer (push/pull): logic shared across platforms, only the Platform field differs
	registerTransferRemote(reg, PlatformWindows)
	registerWindowsService(reg)
	registerWindowsConfig(reg)
	registerWindowsUI(reg)
	registerWindowsWait(reg)
	registerWindowsBrowserExt(reg)
	// OCR text recognition: logic shared across platforms (images recognized via the gateway), only the Platform field differs
	registerOcr(reg, PlatformWindows)
}
