//go:build !windows

package service

// HideSelfConsole is a no-op on non-Windows platforms.
//
// Only on Windows, when a scheduled task starts a console program interactively, is a visible console window allocated;
// Linux / macOS have no such problem.
func HideSelfConsole() {}
