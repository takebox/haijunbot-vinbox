//go:build windows

package service

import "syscall"

// Win32 entry points needed to hide the process's own console window.
//
// Loaded dynamically with syscall.NewLazyDLL to avoid introducing a golang.org/x/sys dependency.
var (
	kernel32Console         = syscall.NewLazyDLL("kernel32.dll")
	procGetConsoleWindow    = kernel32Console.NewProc("GetConsoleWindow")
	user32Console           = syscall.NewLazyDLL("user32.dll")
	procShowWindowForDaemon = user32Console.NewProc("ShowWindow")
)

// swHide corresponds to ShowWindow's SW_HIDE: hide the window.
const swHide = 0

// HideSelfConsole hides the current process's console window (if any).
//
// Background: haijunbot-daemon is a console subsystem program (PE Subsystem=CONSOLE). When started interactively by a
// scheduled task, Windows allocates a **visible console window** for it, and a black box stays on the user's desktop.
// This function is called at runDaemon startup to hide that window.
//
// It only hides the window and does not call FreeConsole: the process still holds the console, so standard output/error
// remain valid, and logging via foreground run with redirection (haijunbot-daemon run > log.txt) is unaffected.
//
// When there is no console (e.g. started with DETACHED_PROCESS), GetConsoleWindow returns 0 and the function returns directly.
func HideSelfConsole() {
	hwnd, _, _ := procGetConsoleWindow.Call()
	if hwnd == 0 {
		return
	}
	procShowWindowForDaemon.Call(hwnd, uintptr(swHide))
}
