//go:build windows

package service

import "fmt"

// InstallNotice returns the permission and risk notice before install on Windows (for the CLI to print).
//
// Windows scheduled tasks use /RL HIGHEST (run with the highest privileges), so creating the task itself
// must be done in an **administrator** session; the process run by the task also has admin privileges.
// Both points are stated plainly here so users do not run into an unexplained "access denied" in a normal session.
func InstallNotice() string {
	return `Note: on Windows, install registers the daemon as a scheduled task running with "highest privileges".
  1. Creating a scheduled task requires administrator privileges; run install in a terminal opened with
     "Run as administrator"; otherwise it fails with insufficient privileges (showing "access denied").
  2. The task auto-starts when the user logs in, and the daemon it starts runs with administrator privileges.
  3. Risk: the capabilities the daemon can execute (file read/write, process management, script execution, desktop automation, etc.)
     take effect with administrator privileges; install only on a machine you trust, and keep your login credentials safe.
  4. Uninstall: run uninstall as an administrator to remove the scheduled task and the installed executable.`
}

// StartHint returns the hint for starting the service after install (including the full path of the executable).
//
// Why give the full path: install copies the exe to ~/.haijunbot/bin, which is **not in PATH**,
// so typing `haijunbot-daemon start` directly reports "not recognized as a cmdlet/command". Execution only works
// with the full path. It also notes that subsequent start/stop/status/uninstall should use the exe at that fixed path,
// to stay consistent with the executable the scheduled task points at.
//
// The command uses PowerShell's call operator `&`: when a path contains spaces or is quoted, PowerShell does not treat the
// string after the quotes as an argument (writing `"C:\...\x.exe" start` directly reports an "unexpected token" for start);
// it must be written `& "C:\...\x.exe" start` to execute correctly. This lets users copy and paste directly.
func StartHint() string {
	path, err := InstalledBinaryPath()
	if err != nil {
		path = `%USERPROFILE%\.haijunbot\bin\haijunbot-daemon.exe`
	}
	return fmt.Sprintf("Note: the install directory is not in PATH. Use the following command in PowerShell (note the leading &):\n"+
		"  & \"%s\" start\n"+
		"  For subsequent start/stop/status/uninstall also use the exe at this path.", path)
}
