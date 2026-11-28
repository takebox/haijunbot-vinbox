//go:build windows

package capability

import (
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strings"
	"time"
)

// windowsAppDefaultLimit is the maximum number of applications returned by windows.app.list when limit is not specified.
const windowsAppDefaultLimit = 1000

// windowsAppMaxLimit is the maximum allowed value of limit, to prevent returning too much data at once.
const windowsAppMaxLimit = 5000

// windowsAppTimeout is the timeout for executing the registry query.
const windowsAppTimeout = 60 * time.Second

// windowsAppUninstallKeys are the registry paths holding the uninstall information of "installed applications".
//
// It covers three sources: 64-bit programs, 32-bit programs (WOW6432Node), and programs installed by the current user;
// there is no WOW6432Node subkey under the HKCU path, so it is not listed again.
var windowsAppUninstallKeys = []string{
	`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
	`HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
	`HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
}

// registerWindowsApp registers the Windows installed application query capability.
func registerWindowsApp(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.app.list",
		Description: "List the applications installed on Windows. Data comes from registry uninstall entries " +
			"(the Uninstall keys of HKLM/HKCU, including the WOW6432Node 32-bit view), " +
			"read through PowerShell (ensuring Chinese application names and publishers are returned as UTF-8, without garbling due to the system code page). " +
			"Entries with an empty DisplayName and those marked as SystemComponent have been filtered out. " +
			"Note: this capability only covers desktop applications registered in the registry, excluding Microsoft Store (UWP) applications.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by application name or publisher substring, case-insensitive; returns all applications when empty.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Maximum number of applications to return, default 1000, maximum 5000.",
				},
			},
		},
		Handler: handleWindowsAppList,
	})

	_ = reg.Register(Capability{
		Name: "windows.app.start",
		Description: "Start an executable program. " +
			"It launches the process directly via os/exec (without going through a shell, avoiding command injection), " +
			"and the child process runs in a windowless, hidden console (no flashing console window). " +
			"It can optionally wait for the process to exit and return the exit code. No third-party dependencies are required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The path of the executable to start, such as C:\\Windows\\notepad.exe.",
				},
				"args": map[string]any{
					"type":        "string",
					"description": "Optional command-line arguments, split on whitespace and passed to the process; not going through a shell.",
				},
				"wait": map[string]any{
					"type":        "boolean",
					"description": "Whether to wait for the process to exit before returning; default false (returns pid immediately).",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleWindowsAppStart,
	})
}

// handleWindowsAppList is the implementation of windows.app.list.
func handleWindowsAppList(params map[string]any) (any, error) {
	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}
	limit, err := optionalInt(params, "limit", windowsAppDefaultLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > windowsAppMaxLimit {
		return nil, fmt.Errorf("parameter limit exceeds the maximum %d, actual %d", windowsAppMaxLimit, limit)
	}

	apps, err := collectWindowsApps()
	if err != nil {
		return nil, err
	}

	needle := strings.ToLower(filter)
	filtered := make([]map[string]any, 0, len(apps))
	for _, app := range apps {
		if needle != "" {
			name := strings.ToLower(fmt.Sprint(app["name"]))
			publisher := strings.ToLower(fmt.Sprint(app["publisher"]))
			if !strings.Contains(name, needle) && !strings.Contains(publisher, needle) {
				continue
			}
		}
		filtered = append(filtered, app)
		if len(filtered) >= limit {
			break
		}
	}

	return map[string]any{
		"apps":      filtered,
		"count":     len(filtered),
		"total":     len(apps),
		"truncated": len(apps) > len(filtered),
	}, nil
}

// collectWindowsApps aggregates all registry uninstall entries, deduplicates them, and returns them sorted by name.
//
// Performance key: **only start PowerShell once**.
//
// The earlier implementation used N+1 process launches (first enumerate the subkeys of 3 root keys, then run
// reg query separately for each subkey), but a real machine's registry usually has 200~500 uninstall entries, i.e. 200~500
// powershell.exe cold starts, far exceeding the 60s timeout in total — this is the root cause of the
// windows.app.list timeout on real machines. Now it is changed to a single call that exports all uninstall entries under the three root keys as CSV,
// parsed by parseWindowsAppCSV (see windows_app_parse.go).
func collectWindowsApps() ([]map[string]any, error) {
	if _, err := requirePowerShell(); err != nil {
		return nil, err
	}

	script := buildWindowsAppListScript()
	out, err := runWindowsPowerShellCommand(script, windowsAppTimeout)
	if err != nil {
		return nil, err
	}

	apps := parseWindowsAppCSV(out)

	// Deduplicate: same name and same version is regarded as the same application (different root keys/32-64-bit views may register duplicates).
	seen := make(map[string]struct{}, len(apps))
	deduped := make([]map[string]any, 0, len(apps))
	for _, app := range apps {
		name := fmt.Sprint(app["name"])
		dedupKey := strings.ToLower(name) + "\x00" + strings.ToLower(fmt.Sprint(app["version"]))
		if _, exists := seen[dedupKey]; exists {
			continue
		}
		seen[dedupKey] = struct{}{}
		deduped = append(deduped, app)
	}

	sort.Slice(deduped, func(i, j int) bool {
		return strings.ToLower(fmt.Sprint(deduped[i]["name"])) < strings.ToLower(fmt.Sprint(deduped[j]["name"]))
	})
	return deduped, nil
}

// buildWindowsAppListScript constructs the PowerShell script that exports all uninstall entries in one go.
//
// Script behavior:
//   - Traverse the three root keys in windowsAppUninstallKeys (HKLM 64-bit, HKLM WOW6432Node
//     32-bit, HKCU), using Get-ItemProperty to read the uninstall information of each subkey;
//   - Select only the needed fields and normalize them to strings (Get-ItemProperty returns $null for missing fields;
//     here [string] is cast and TrimSpace is applied, ensuring no empty-column misalignment in the CSV);
//   - Output with ConvertTo-Csv -NoTypeInformation, parsed by parseWindowsAppCSV on the Go side.
//
// The key paths are concatenated from the windowsAppUninstallKeys constant in this file and contain no user input;
// but they are still escaped by encodePowerShellText to avoid syntax problems caused by backslashes/quotes.
//
// Note: Get-ItemProperty errors on non-existent keys, so -ErrorAction SilentlyContinue is used to
// silently skip them (for example, HKCU may not have an Uninstall key).
func buildWindowsAppListScript() string {
	parts := make([]string, 0, len(windowsAppUninstallKeys))
	for _, key := range windowsAppUninstallKeys {
		psKey, err := toPowerShellRegistryPath(key)
		if err != nil {
			// A constant key that cannot be converted is a programming error; skip it rather than failing entirely (retaining the other root keys).
			continue
		}
		parts = append(parts, encodePowerShellText(psKey))
	}

	// Write the script using a backtick raw string, avoiding Go-level quote escaping and PowerShell's
	// quote syntax interfering with each other. Select-Object uses a hashtable @{Name=...;Expression={...}}
	// to normalize each field to [string], making the CSV columns stable (missing fields become empty strings rather than $null).
	selectClause := "Select-Object " +
		"@{Name='DisplayName';Expression={[string]$_.DisplayName}}, " +
		"@{Name='DisplayVersion';Expression={[string]$_.DisplayVersion}}, " +
		"@{Name='Publisher';Expression={[string]$_.Publisher}}, " +
		"@{Name='InstallLocation';Expression={[string]$_.InstallLocation}}, " +
		"@{Name='InstallDate';Expression={[string]$_.InstallDate}}, " +
		"@{Name='SystemComponent';Expression={[string]$_.SystemComponent}}"

	return `
$paths = @(` + strings.Join(parts, ", ") + `)
$paths | ForEach-Object {
    Get-ChildItem -Path $_ -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ItemProperty -Path $_.PSPath -ErrorAction SilentlyContinue
    }
} | ` + selectClause + ` | ConvertTo-Csv -NoTypeInformation
`
}

// toPowerShellRegistryPath converts a reg.exe-style root key name into a PowerShell registry path.
//
// reg.exe uses the abbreviations HKLM / HKCU / HKCR / HKU / HKCC, while PowerShell's registry provider
// accepts forms such as HKLM: / HKCU:. Only the prefix is replaced; the rest of the path is preserved as-is.
func toPowerShellRegistryPath(key string) (string, error) {
	prefixes := []struct {
		reg string
		ps  string
	}{
		{`HKLM\`, `HKLM:\`},
		{`HKCU\`, `HKCU:\`},
		{`HKCR\`, `HKCR:\`},
		{`HKU\`, `HKU:\`},
		{`HKCC\`, `HKCC:\`},
	}
	for _, p := range prefixes {
		if strings.HasPrefix(key, p.reg) {
			return p.ps + strings.TrimPrefix(key, p.reg), nil
		}
	}
	return "", fmt.Errorf("unrecognized registry root key: %s", key)
}

// windowsAppStartTool is the value of the tool field in the result returned by windows.app.start.
const windowsAppStartTool = "os/exec"

// handleWindowsAppStart is the implementation of windows.app.start.
func handleWindowsAppStart(params map[string]any) (any, error) {
	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	// Verify that the executable exists; give a clear error when it does not, avoiding an obscure error after exec launches.
	if _, err := os.Stat(path); err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("executable file does not exist: %s", path)
		}
		return nil, fmt.Errorf("cannot access executable file %s: %v", path, err)
	}

	args, err := optionalString(params, "args")
	if err != nil {
		return nil, err
	}
	argList := splitWindowsArgs(args)

	wait, err := optionalBool(params, "wait", false)
	if err != nil {
		return nil, err
	}

	// Launch directly via os/exec, without going through a shell (not calling cmd.exe /c), to avoid command injection.
	cmd := exec.Command(path, argList...)
	// The child process runs in a windowless, hidden console, avoiding a flashing console window when the daemon starts a GUI program.
	cmd.SysProcAttr = hideWindow()

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start %s: %v", path, err)
	}

	result := map[string]any{
		"pid":  cmd.Process.Pid,
		"tool": windowsAppStartTool,
	}

	// Optionally wait for the process to exit and return the exit code.
	if wait {
		err := cmd.Wait()
		exitCode := 0
		if err != nil {
			if exitErr, ok := err.(*exec.ExitError); ok {
				exitCode = exitErr.ExitCode()
			} else {
				return nil, fmt.Errorf("failed to wait for process exit: %v", err)
			}
		}
		result["exit_code"] = exitCode
	}

	return result, nil
}
