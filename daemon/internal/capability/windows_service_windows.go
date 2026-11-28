//go:build windows

package capability

// This file implements the Windows platform service management capabilities (windows.service.*), mirroring the 5
// capabilities of the Linux side linux_service_linux.go and keeping the parameters and return structure consistent:
//   - list: unit_type/all → units/count
//   - status: unit → unit/load/active/sub/description/main_pid/exec_start
//   - start/stop/restart: unit → unit/action/ok/output
//
// Differences from Linux:
//   - Linux uses systemctl --user to manage user-level systemd units; Windows has no equivalent concept,
//     so what is managed here is "system services" (Service Control Manager), going through PowerShell's
//     Get-Service / Start-Service / Stop-Service / Restart-Service.
//   - The reason for not using sc.exe: sc.exe output is affected by the console code page, and non-ASCII service names
//     would be garbled; whereas runWindowsPowerShellCommand already uniformly forces the subprocess output to UTF-8 (see
//     windows_encoding.go), so non-ASCII service names can be returned correctly.
//   - "unit" on Windows is the service name (ServiceName), such as Spooler, wuauserv.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success path has not been verified end-to-end.

import (
	"fmt"
	"strings"
	"time"
)

// windowsServiceTimeout is the timeout for a single service query/operation.
//
// Starting/stopping a service may take a while (especially with long dependency chains), so it is relaxed from 10s to 30s.
const windowsServiceTimeout = 30 * time.Second

// registerWindowsService registers the Windows service management capabilities.
func registerWindowsService(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.service.list",
		Description: "List Windows system services (Service Control Manager)." +
			"Data comes from PowerShell Get-Service; non-ASCII service display names can be returned correctly.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by service name or display name substring, case-insensitive; returns all services when empty.",
				},
				"all": map[string]any{
					"type":        "boolean",
					"description": "Whether to include stopped services, default true (Get-Service includes all by default).",
				},
			},
		},
		Handler: handleWindowsServiceList,
	})

	_ = reg.Register(Capability{
		Name:        "windows.service.status",
		Description: "Query the detailed status of the specified Windows service (PowerShell Get-Service).",
		Platform:    PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Service name (ServiceName), such as Spooler, wuauserv; a display name is also accepted.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleWindowsServiceStatus,
	})

	_ = reg.Register(Capability{
		Name:        "windows.service.start",
		Description: "Start the specified Windows service (PowerShell Start-Service).",
		Platform:    PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Service name (ServiceName), such as Spooler.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleWindowsServiceAction("start"),
	})

	_ = reg.Register(Capability{
		Name:        "windows.service.stop",
		Description: "Stop the specified Windows service (PowerShell Stop-Service).",
		Platform:    PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Service name (ServiceName), such as Spooler.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleWindowsServiceAction("stop"),
	})

	_ = reg.Register(Capability{
		Name:        "windows.service.restart",
		Description: "Restart the specified Windows service (PowerShell Restart-Service).",
		Platform:    PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Service name (ServiceName), such as Spooler.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleWindowsServiceAction("restart"),
	})
}

// handleWindowsServiceList is the implementation of windows.service.list.
func handleWindowsServiceList(params map[string]any) (any, error) {
	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}

	// The all parameter exists only to align with the Linux side's parameters: Get-Service itself returns all services
	// (including stopped ones), so it is read but not used; validation is kept so a parameter type error is detected promptly.
	if _, err := optionalBool(params, "all", true); err != nil {
		return nil, err
	}

	// Output with ConvertTo-Csv, avoiding the column-width truncation and localized-header problems of Format-Table.
	script := "Get-Service | Select-Object Name,DisplayName,Status | ConvertTo-Csv -NoTypeInformation"

	out, err := runWindowsPowerShellCommand(script, windowsServiceTimeout)
	if err != nil {
		return nil, err
	}

	units := parseWindowsServiceCSV(out)

	if filter != "" {
		units = filterWindowsServiceUnits(units, filter)
	}

	return map[string]any{
		"units": units,
		"count": len(units),
	}, nil
}

// handleWindowsServiceStatus is the implementation of windows.service.status.
func handleWindowsServiceStatus(params map[string]any) (any, error) {
	unit, err := resolveWindowsServiceUnit(params)
	if err != nil {
		return nil, err
	}

	// Using Get-CimInstance Win32_Service can get more fields (start type, process ID, path, etc.), closer to the information volume of systemctl show than Get-Service.
	//
	// Key: -Filter expects a **WQL predicate**, and the string value must be **wrapped in single quotes**,
	// like Name='Spooler'. Real-machine measurement shows both wrong forms lead to an "invalid query HRESULT 0x80041017"
	// or no matching instances, so that **all service names report "service not found"**:
	//   - passing a bare string 'Spooler' (early implementation) → not a predicate;
	//   - passing 'Name=' + 'Spooler' → produces Name=Spooler, with the value missing quotes.
	//
	// So here the quoted predicate is explicitly constructed on the PowerShell side: first single-quote-escape unit
	// (encodePowerShellText writes an internal ' as ''), then concatenate it into the WQL single quotes.
	// Since WQL and PowerShell have different single-quote escaping rules, this is done in two steps:
	//   1. On the Go side, convert unit into a PowerShell single-quoted literal (used to construct the query string);
	//   2. Wrap another layer of WQL single quotes inside the query string.
	//
	// In addition, per the description's promise to support display names: first match exactly by Name, and if not found,
	// match by DisplayName.
	quoted := encodePowerShellText(unit)
	script := fmt.Sprintf(
		"$name = %s; "+
			"$s = Get-CimInstance Win32_Service -Filter (\"Name='\" + $name + \"'\"); "+
			"if ($null -eq $s) { $s = Get-CimInstance Win32_Service -Filter (\"DisplayName='\" + $name + \"'\") }; "+
			"if ($null -eq $s) { Write-Output 'NOT_FOUND'; exit 0 }; "+
			"$s | Select-Object Name,DisplayName,State,StartMode,ProcessId,PathName,Status | ConvertTo-Csv -NoTypeInformation",
		quoted,
	)

	out, err := runWindowsPowerShellCommand(script, windowsServiceTimeout)
	if err != nil {
		return nil, err
	}

	trimmed := strings.TrimSpace(out)
	if trimmed == "" || strings.Contains(trimmed, "NOT_FOUND") {
		return nil, fmt.Errorf("service not found %q", unit)
	}

	props := parseWindowsServiceStatusCSV(out)
	if len(props) == 0 {
		return nil, fmt.Errorf("service not found %q", unit)
	}

	return map[string]any{
		"unit":        unit,
		"load":        props["StartMode"],
		"active":      props["State"],
		"sub":         props["Status"],
		"description": props["DisplayName"],
		"main_pid":    props["ProcessId"],
		"exec_start":  props["PathName"],
	}, nil
}

// handleWindowsServiceAction generates the implementation of start / stop / restart.
func handleWindowsServiceAction(action string) func(map[string]any) (any, error) {
	return func(params map[string]any) (any, error) {
		unit, err := resolveWindowsServiceUnit(params)
		if err != nil {
			return nil, err
		}

		// Map the action name to a PowerShell cmdlet. The action name is fixedly passed in internally by this function
		// and does not accept external input, so there is no injection risk.
		var cmdlet string
		switch action {
		case "start":
			cmdlet = "Start-Service"
		case "stop":
			cmdlet = "Stop-Service"
		case "restart":
			cmdlet = "Restart-Service"
		default:
			return nil, fmt.Errorf("unsupported service action: %q", action)
		}

		script := fmt.Sprintf(
			"$ErrorActionPreference = 'Stop'; "+
				"try { %s -Name %s; Write-Output 'OK' } catch { Write-Output ('ERR: ' + $_.Exception.Message) }",
			cmdlet,
			encodePowerShellText(unit),
		)

		out, err := runWindowsPowerShellCommand(script, windowsServiceTimeout)
		if err != nil {
			return nil, err
		}

		trimmed := strings.TrimSpace(out)
		if strings.HasPrefix(trimmed, "ERR:") {
			return nil, fmt.Errorf("executing %s service %q failed: %s", action, unit, strings.TrimPrefix(trimmed, "ERR: "))
		}

		return map[string]any{
			"unit":   unit,
			"action": action,
			"ok":     true,
			"output": trimmed,
		}, nil
	}
}

// resolveWindowsServiceUnit parses and validates the unit (service name) parameter.
func resolveWindowsServiceUnit(params map[string]any) (string, error) {
	unit, err := requiredString(params, "unit")
	if err != nil {
		return "", err
	}
	if err := validateWindowsServiceName(unit); err != nil {
		return "", err
	}
	return unit, nil
}

// validateWindowsServiceName validates the legality of the service name.
//
// The characters allowed in a Windows service name (ServiceName) are broader than a Linux unit (it may contain spaces,
// non-ASCII text, etc.), but for safety a whitelist validation is still done here: letters, digits, underscore, dot, @,
// hyphen, space, and non-ASCII visible characters (covering non-ASCII service names).
//
// It also rejects names starting with "-", avoiding being treated by PowerShell as a parameter (such as an extra switch
// injected after -Name). The actual injection protection is borne by encodePowerShellText's single-quote escaping;
// this is only the first line of defense for "failing early".
func validateWindowsServiceName(name string) error {
	trimmed := strings.TrimSpace(name)
	if trimmed == "" {
		return fmt.Errorf("parameter unit cannot be empty")
	}
	if strings.HasPrefix(trimmed, "-") {
		return fmt.Errorf("parameter unit cannot start with - (would be parsed as a command option): %q", name)
	}
	for _, r := range trimmed {
		switch {
		case r >= 'a' && r <= 'z':
		case r >= 'A' && r <= 'Z':
		case r >= '0' && r <= '9':
		case r == '_' || r == '.' || r == '@' || r == '-' || r == ' ':
		case r > 0x7f:
			// Non-ASCII visible characters (such as non-ASCII service names) are allowed.
		default:
			return fmt.Errorf("parameter unit contains illegal character %q, allowed: letters, digits, _ . @ - space, and non-ASCII characters", string(r))
		}
	}
	return nil
}
