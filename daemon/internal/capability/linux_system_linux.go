//go:build linux

package capability

import (
	"bufio"
	"fmt"
	"os"
	"os/user"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

// registerLinuxSystem registers the Linux system information capability.
func registerLinuxSystem(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "linux.system.info",
		Description: "Get basic system information about the Linux host: hostname, kernel version, distribution, architecture, " +
			"CPU count and model, total and available memory, uptime, current user and home directory.",
		Platform: PlatformLinux,
		Parameters: map[string]any{
			"type":       "object",
			"properties": map[string]any{},
		},
		Handler: handleLinuxSystemInfo,
	})
}

// handleLinuxSystemInfo is the implementation of linux.system.info.
func handleLinuxSystemInfo(_ map[string]any) (any, error) {
	return CollectSystemInfo()
}

// CollectSystemInfoFast collects "zero-cost" system information that does not depend on any external command.
//
// Unlike Windows, all of Linux's system information comes from /proc pseudo-files and the standard library, and reading it is already
// on the order of milliseconds, so here we directly reuse the result of CollectSystemInfo (the fields are fully identical);
// it exists only to keep the same interface as Windows, for use by the hello first frame.
func CollectSystemInfoFast() map[string]any {
	info, _ := CollectSystemInfo()
	if info == nil {
		info = map[string]any{}
	}
	return info
}

// CollectSystemInfo collects information about the local system.
//
// This function serves both the linux.system.info capability and the hello report during daemon registration,
// ensuring that the fields and values in both places are fully identical. Each platform provides its implementation in a file carrying build tags.
func CollectSystemInfo() (map[string]any, error) {
	hostname, _ := os.Hostname()

	kernel := ""
	if raw, err := os.ReadFile("/proc/sys/kernel/osrelease"); err == nil {
		kernel = strings.TrimSpace(string(raw))
	}

	osName, osVersion := readLinuxOSRelease()

	cpuCount := runtime.NumCPU()
	cpuModel := readLinuxCPUModel()

	memTotalKB, memAvailableKB := readLinuxMemInfo()

	var uptimeSec float64
	if raw, err := os.ReadFile("/proc/uptime"); err == nil {
		fields := strings.Fields(string(raw))
		if len(fields) > 0 {
			if v, err := strconv.ParseFloat(fields[0], 64); err == nil {
				uptimeSec = v
			}
		}
	}

	username := ""
	home := ""
	if u, err := user.Current(); err == nil {
		username = u.Username
		home = u.HomeDir
	}

	return map[string]any{
		"hostname":         hostname,
		"kernel":           kernel,
		"os_name":          osName,
		"os_version":       osVersion,
		"arch":             runtime.GOARCH,
		"cpu_count":        cpuCount,
		"cpu_model":        cpuModel,
		"mem_total_kb":     memTotalKB,
		"mem_available_kb": memAvailableKB,
		"uptime_sec":       int64(uptimeSec),
		"user":             username,
		"home":             home,
	}, nil
}

// readLinuxOSRelease parses /etc/os-release and returns the distribution name and version.
func readLinuxOSRelease() (name, version string) {
	f, err := os.Open("/etc/os-release")
	if err != nil {
		return "", ""
	}
	defer f.Close()

	values := map[string]string{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(val), `"'`)
	}

	name = values["NAME"]
	if name == "" {
		name = values["ID"]
	}
	version = values["VERSION_ID"]
	if version == "" {
		version = values["VERSION"]
	}
	return name, version
}

// readLinuxCPUModel reads the first processor model from /proc/cpuinfo.
func readLinuxCPUModel() string {
	f, err := os.Open("/proc/cpuinfo")
	if err != nil {
		return ""
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		key, val, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		if strings.TrimSpace(key) == "model name" {
			return strings.TrimSpace(val)
		}
	}
	return ""
}

// readLinuxMemInfo reads total and available memory (in KB) from /proc/meminfo.
func readLinuxMemInfo() (totalKB, availableKB int64) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, 0
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		key, val, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		fields := strings.Fields(val)
		if len(fields) == 0 {
			continue
		}
		n, err := strconv.ParseInt(fields[0], 10, 64)
		if err != nil {
			continue
		}
		switch strings.TrimSpace(key) {
		case "MemTotal":
			totalKB = n
		case "MemAvailable":
			availableKB = n
		}
	}
	return totalKB, availableKB
}

// linuxPageSizeKB returns the system page size (KB), for reuse by other Linux capabilities.
func linuxPageSizeKB() int64 {
	return int64(syscall.Getpagesize()) / 1024
}

// linuxFormatBytes formats a byte count into a human-readable string.
func linuxFormatBytes(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div, exp := int64(unit), 0
	for m := n / unit; m >= unit; m /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(n)/float64(div), "KMGTPE"[exp])
}
