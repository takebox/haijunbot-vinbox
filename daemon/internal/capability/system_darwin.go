//go:build darwin

package capability

import (
	"os"
	"os/user"
	"runtime"
)

// CollectSystemInfoFast collects "zero-cost" system information that does not depend on any external command.
//
// All of macOS's system information comes from the standard library and reading it is already on the order of milliseconds, so here we directly reuse
// the result of CollectSystemInfo (the fields are fully identical); it exists only to keep the same interface as Windows,
// for use by the hello first frame.
func CollectSystemInfoFast() map[string]any {
	info, _ := CollectSystemInfo()
	if info == nil {
		info = map[string]any{}
	}
	return info
}

// CollectSystemInfo collects basic system information about the macOS host.
//
// It only uses fields that can be reliably obtained from the standard library; fields that cannot be obtained are omitted rather than raising an error,
// so that the daemon registration flow is not interrupted by collection failures.
func CollectSystemInfo() (map[string]any, error) {
	hostname, _ := os.Hostname()

	username := ""
	home := ""
	if u, err := user.Current(); err == nil {
		username = u.Username
		home = u.HomeDir
	}

	info := map[string]any{
		"hostname":  hostname,
		"os_name":   "macOS",
		"arch":      runtime.GOARCH,
		"cpu_count": runtime.NumCPU(),
		"user":      username,
		"home":      home,
	}
	return info, nil
}
