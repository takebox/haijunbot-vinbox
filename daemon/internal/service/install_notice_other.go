//go:build !windows

package service

// InstallNotice needs no extra notice on non-Windows platforms (Linux uses the systemd user service
// and needs no admin privileges); returns an empty string.
func InstallNotice() string {
	return ""
}

// StartHint returns an empty string on non-Windows platforms (Linux is managed via systemctl and needs no full path).
func StartHint() string {
	return ""
}
