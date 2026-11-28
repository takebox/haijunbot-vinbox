//go:build windows

package capability

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
)

// windowsSystemInfoTimeout is the timeout for calling external commands when collecting system information.
const windowsSystemInfoTimeout = 10 * time.Second

// Note: the hello first frame does not call this file's external-command collection path; instead it calls
// CollectSystemInfoFast (see wsclient/client.go), so there is no need to set a separate short timeout for hello here.
// registerWindowsSystem registers the Windows system information capability.
func registerWindowsSystem(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.system.info",
		Description: "Gets basic system information of the Windows host: hostname, OS version and build number, architecture, " +
			"CPU count, total and available memory, system boot time and uptime, current user, and home directory. " +
			"The OS version and memory information are obtained via PowerShell / wmic; when the commands are unavailable, the corresponding fields are omitted rather than causing an error.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type":       "object",
			"properties": map[string]any{},
		},
		Handler: handleWindowsSystemInfo,
	})
}

// handleWindowsSystemInfo is the implementation of windows.system.info.
func handleWindowsSystemInfo(_ map[string]any) (any, error) {
	return CollectSystemInfo()
}

// CollectSystemInfoFast collects "zero-cost" system information that does not depend on any external commands.
//
// These fields all come from the standard library (os.Hostname / runtime / os/user) and return in milliseconds,
// so they can be safely used for the hello first frame. The external-command fields (OS version, memory, boot time) are
// filled in concurrently by CollectSystemInfo on top of this.
func CollectSystemInfoFast() map[string]any {
	hostname, _ := os.Hostname()

	username := ""
	home := ""
	if u, err := user.Current(); err == nil {
		username = u.Username
		home = u.HomeDir
	}

	return map[string]any{
		"hostname":  hostname,
		"os_name":   "Windows",
		"arch":      runtime.GOARCH,
		"cpu_count": runtime.NumCPU(),
		"user":      username,
		"home":      home,
	}
}

// CollectSystemInfo collects the complete system information of the local machine.
//
// This function serves both the windows.system.info capability and the hello reporting during daemon registration,
// ensuring the fields and values are exactly the same in both places. Each platform provides its implementation in a build-tagged file.
//
// Only fields that can be reliably obtained using the standard library and built-in system commands are used; fields that cannot be obtained are omitted rather than causing an error,
// so that the daemon registration process is not interrupted by a collection failure.
//
// Implementation notes: first take the zero-cost fields (CollectSystemInfoFast), then **concurrently** execute 3 external
// command collections (OS version, memory, boot time). Concurrency is used to reduce the originally serial ≈10s to
// on the order of a single command's duration. Note: the hello first frame must **not** call this function (it waits for external commands);
// it should call CollectSystemInfoFast instead; this function is used by the windows.system.info capability and can tolerate
// longer durations.
func CollectSystemInfo() (map[string]any, error) {
	info := CollectSystemInfoFast()

	// The 3 external command collections are independent of each other; they run concurrently to shorten the total duration.
	var (
		wg sync.WaitGroup

		osName    string
		osVersion string
		osBuild   string

		memTotalKB     int64
		memAvailableKB int64

		bootTime time.Time
		bootOK   bool
	)

	wg.Add(3)
	go func() {
		defer wg.Done()
		osName, osVersion, osBuild = readWindowsOSVersion(windowsSystemInfoTimeout)
	}()
	go func() {
		defer wg.Done()
		memTotalKB, memAvailableKB = readWindowsMemoryKB(windowsSystemInfoTimeout)
	}()
	go func() {
		defer wg.Done()
		bootTime, bootOK = readWindowsBootTime(windowsSystemInfoTimeout)
	}()
	wg.Wait()

	// OS version and build number.
	if osName != "" || osVersion != "" {
		info["os_name"] = osName
		info["os_version"] = osVersion
		if osBuild != "" {
			info["os_build"] = osBuild
		}
	}

	// Total and available memory (KB).
	if memTotalKB > 0 {
		info["mem_total_kb"] = memTotalKB
		info["mem_available_kb"] = memAvailableKB
	}

	// System boot time and uptime.
	if bootOK {
		info["boot_time"] = bootTime.Format(time.RFC3339)
		info["uptime_sec"] = int64(time.Since(bootTime).Seconds())
	}

	return info, nil
}

// readWindowsOSVersion reads the Windows product name, version number, and build number.
//
// The data source is the registry CurrentVersion key (PowerShell Get-ItemProperty);
// on failure it falls back to wmic os. When neither is available, an empty string is returned and the caller omits the fields.
// timeout controls the timeout of a single external command, passed in by the caller per scenario (the capability path is longer,
// the hello path is shorter).
func readWindowsOSVersion(timeout time.Duration) (name, version, build string) {
	// Goes through runWindowsPowerShellCommand: it passes the script via -EncodedCommand and forces UTF-8 output,
	// so ProductName will not be garbled even when localized to Chinese (such as "Windows 10 Pro").
	// Earlier versions used runWindowsCommand to directly concatenate -Command here, which output GBK bytes on Chinese systems
	// and was misinterpreted by Go as UTF-8, so it was changed to uniformly go through the PowerShell executor.
	if out, err := runWindowsPowerShellCommand(
		"(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion') | "+
			"Select-Object ProductName,DisplayVersion,CurrentBuildNumber | ConvertTo-Csv -NoTypeInformation",
		timeout,
	); err == nil {
		name, version, build = parseWindowsOSVersionCSV(out)
		if name != "" || version != "" {
			return name, version, build
		}
	}

	// Fallback: wmic has no UTF-8 output mode, but this branch only takes Caption/Version/BuildNumber,
	// so if Caption is Chinese it may still be garbled; hence it only serves as a last resort when PowerShell is unavailable.
	if out, err := runWindowsCommand(timeout, "wmic", "os", "get", "Caption,Version,BuildNumber", "/format:csv"); err == nil {
		name, version, build = parseWindowsOSVersionCSV(out)
	}
	return name, version, build
}

// readWindowsMemoryKB reads the total and available physical memory (in KB).
//
// Obtained via PowerShell's Get-CimInstance Win32_OperatingSystem; returns 0 on failure.
// timeout controls the timeout of a single external command, passed in by the caller per scenario.
func readWindowsMemoryKB(timeout time.Duration) (totalKB, availableKB int64) {
	// Uniformly goes through runWindowsPowerShellCommand (-EncodedCommand + UTF-8 output),
	// avoiding any encoding-related surprises; this function only reads numbers but stays consistent with other PowerShell calls.
	out, err := runWindowsPowerShellCommand(
		"$os = Get-CimInstance Win32_OperatingSystem; "+
			"'{0},{1}' -f $os.TotalVisibleMemorySize, $os.FreePhysicalMemory",
		timeout,
	)
	if err != nil {
		return 0, 0
	}
	line := firstNonEmptyLine(out)
	if line == "" {
		return 0, 0
	}
	fields := strings.Split(line, ",")
	if len(fields) < 2 {
		return 0, 0
	}
	totalKB, _ = strconv.ParseInt(strings.TrimSpace(fields[0]), 10, 64)
	availableKB, _ = strconv.ParseInt(strings.TrimSpace(fields[1]), 10, 64)
	return totalKB, availableKB
}

// readWindowsBootTime reads the system boot time.
//
// Obtained via PowerShell's Win32_OperatingSystem.LastBootUpTime; ok is false on failure.
// timeout controls the timeout of a single external command, passed in by the caller per scenario.
func readWindowsBootTime(timeout time.Duration) (time.Time, bool) {
	// Uniformly goes through runWindowsPowerShellCommand (-EncodedCommand + UTF-8 output).
	out, err := runWindowsPowerShellCommand(
		"(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('o')",
		timeout,
	)
	if err != nil {
		return time.Time{}, false
	}
	line := firstNonEmptyLine(out)
	if line == "" {
		return time.Time{}, false
	}
	// PowerShell's 'o' format looks like 2026-09-26T13:00:00.0000000+08:00,
	// Go's RFC3339 parsing does not accept 7 fractional digits, so try RFC3339Nano first and then truncate the fraction and retry.
	if t, err := time.Parse(time.RFC3339Nano, line); err == nil {
		return t, true
	}
	if t, err := time.Parse("2006-01-02T15:04:05", line[:minInt(len(line), 19)]); err == nil {
		return t, true
	}
	return time.Time{}, false
}

// runWindowsCommand executes an external command and returns the standard output (UTF-8).
//
// Uniformly with a timeout, to avoid capability calls blocking due to a hung command; returns a clear error when the command does not exist.
// timeout is passed in by the caller, making it easy to choose different limits per scenario (capability call / hello first frame).
//
// Encoding note: this function is called by readWindowsOSVersion / readWindowsMemoryKB /
// readWindowsBootTime, and these three functions only read **pure ASCII numbers and English product names**
// (such as "Microsoft Windows 10 Pro", "26200", "33382940"), not involving Chinese.
// Therefore UTF-8 output is not forced here (wmic does not support it either); interpreting directly as UTF-8 is fine —
// even if the system code page is GBK, ASCII bytes are identical in both encodings and will not be garbled.
//
// If in the future these functions need to read Chinese content, they must be changed to go through PowerShell and reuse
// runWindowsPowerShellCommand (which already guarantees UTF-8 output), or add a
// looksLikeUTF8 check and a clear error here to avoid silently producing U+FFFD.
func runWindowsCommand(timeout time.Duration, name string, args ...string) (string, error) {
	if _, err := requireTool(name, ""); err != nil {
		return "", err
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, name, args...)
	// The daemon itself has no console; without this attribute a new console window (flashing black box) is created for wmic etc.
	cmd.SysProcAttr = hideWindow()
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to execute %s: %w", name, err)
	}
	return string(out), nil
}
