//go:build windows

package service

import "syscall"

// Windows process creation flags (to avoid introducing a golang.org/x/sys dependency).
const (
	// detachedProcess makes the child process not inherit the current console.
	detachedProcess = 0x00000008
	// createNewProcessGroup gives the child process an independent process group.
	createNewProcessGroup = 0x00000200
	// createNoWindow keeps a console program from creating a new console window.
	//
	// The daemon runs as a detached process (no console); when starting console programs such as powershell / schtasks
	// without this flag, Windows creates a new console window for the child process (showing as a flashing black box).
	createNoWindow = 0x08000000
)

// hideWindowProcAttr returns the startup attribute that keeps the child process from popping up a console window.
func hideWindowProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{CreationFlags: createNoWindow}
}

// detachedProcAttr returns the startup attribute that detaches the child process from the current console.
//
// CREATE_NO_WINDOW is carried at the same time: the daemon is a console program; with only DETACHED_PROCESS and without
// this flag, Windows creates a new console window for the detached daemon (the user sees a flashing black box).
func detachedProcAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: detachedProcess | createNewProcessGroup | createNoWindow,
	}
}
