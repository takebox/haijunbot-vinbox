package capability

// This file holds the pure script-construction functions of the Windows system configuration capability (windows.config.*).
//
// These functions only depend on the standard library and encodePowerShellText (defined in the untagged
// windows_gui_parse.go) and do not reference any platform-specific types, so they **carry no build tags**:
// this way they can be compiled and unit tested directly on Linux / macOS, so that even without a Windows environment
// it can still be verified that "user input is correctly escaped and that the script has no injection surface".
//
// The accompanying tests are in windows_config_parse_test.go; windows_config_windows.go, which carries the //go:build windows tag,
// is responsible for registering the capability, parsing parameters, and invoking runWindowsPowerShellCommand.
//
// Security convention: any string originating from user input (plan_id, server, bypass, name) is always escaped by
// encodePowerShellText into a single-quoted literal before being concatenated into the script; it is never concatenated directly.

import (
	"fmt"
	"strings"
)

// Theme registry path (a fixed constant, no user input).
const windowsConfigThemePath = `HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize`

// Proxy registry path (a fixed constant, no user input).
const windowsConfigProxyPath = `HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings`

// Remote desktop registry path (a fixed constant, no user input).
const windowsConfigRemoteDesktopPath = `HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server`

// Startup folder (a PowerShell variable, expanded at runtime, no user input).
const windowsConfigStartupDir = `$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup`

// buildWindowsConfigThemeScript constructs the PowerShell script for windows.config.theme.
// mode is dark/light/toggle; an invalid value returns an error.
func buildWindowsConfigThemeScript(mode string) (string, error) {
	switch mode {
	case "dark":
		return "Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name AppsUseLightTheme -Value 0 -Type Dword -Force; " +
			"Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name SystemUsesLightTheme -Value 0 -Type Dword -Force; " +
			"Write-Output 'Theme: dark'", nil
	case "light":
		return "Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name AppsUseLightTheme -Value 1 -Type Dword -Force; " +
			"Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name SystemUsesLightTheme -Value 1 -Type Dword -Force; " +
			"Write-Output 'Theme: light'", nil
	case "toggle":
		return "$p = Get-ItemProperty -Path '" + windowsConfigThemePath + "' -Name AppsUseLightTheme -ErrorAction SilentlyContinue; " +
			"$v = if ($p.AppsUseLightTheme -eq 0) { 1 } else { 0 }; " +
			"Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name AppsUseLightTheme -Value $v -Type Dword -Force; " +
			"Set-ItemProperty -Path '" + windowsConfigThemePath + "' -Name SystemUsesLightTheme -Value $v -Type Dword -Force; " +
			"Write-Output ('Theme: ' + $(if ($v -eq 0) { 'dark' } else { 'light' }))", nil
	default:
		return "", fmt.Errorf("parameter mode does not support %q, allowed values: dark, light, toggle", mode)
	}
}

// buildWindowsConfigPowerPlanScript constructs the PowerShell script for windows.config.power-plan.
// action is list/set; for set, planID is required and escaped by encodePowerShellText.
func buildWindowsConfigPowerPlanScript(action, planID string) (string, error) {
	switch action {
	case "list":
		return "powercfg /list", nil
	case "set":
		if planID == "" {
			return "", fmt.Errorf("the set operation requires the plan_id parameter")
		}
		// plan_id is a GUID; after escaping by encodePowerShellText it is passed to powercfg as an argument.
		return "powercfg /setactive " + encodePowerShellText(planID), nil
	default:
		return "", fmt.Errorf("parameter action does not support %q, allowed values: list, set", action)
	}
}

// buildWindowsConfigProxyScript constructs the PowerShell script for windows.config.proxy.
// action is get/enable/disable/set; for enable/set, server and bypass are escaped.
func buildWindowsConfigProxyScript(action, server, bypass string) (string, error) {
	switch action {
	case "get":
		return "$p = Get-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyEnable -ErrorAction SilentlyContinue; " +
			"$s = (Get-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyServer -ErrorAction SilentlyContinue).ProxyServer; " +
			"Write-Output ('enabled=' + $p.ProxyEnable + '; server=' + $s)", nil
	case "disable":
		return "Set-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyEnable -Value 0 -Type Dword -Force; " +
			"Write-Output 'Proxy disabled'", nil
	case "enable", "set":
		// When server is empty, enable uses the default address; set must provide server.
		if server == "" {
			if action == "set" {
				return "", fmt.Errorf("the set operation requires the server parameter")
			}
			server = "127.0.0.1:7890"
		}
		if bypass == "" {
			bypass = "localhost;127.*;10.*;172.16.*;192.168.*"
		}
		// All user input is escaped by encodePowerShellText to prevent command injection.
		quotedServer := encodePowerShellText(server)
		quotedBypass := encodePowerShellText(bypass)
		return "Set-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyEnable -Value 1 -Type Dword -Force; " +
			"Set-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyServer -Value " + quotedServer + " -Force; " +
			"Set-ItemProperty -Path '" + windowsConfigProxyPath + "' -Name ProxyOverride -Value " + quotedBypass + " -Force -ErrorAction SilentlyContinue; " +
			"Write-Output ('Proxy " + action + ": ' + " + quotedServer + ")", nil
	default:
		return "", fmt.Errorf("parameter action does not support %q, allowed values: get, enable, disable, set", action)
	}
}

// buildWindowsConfigScreenTimeoutScript constructs the script for windows.config.screen-timeout.
// action is get/set; for set, minutes is an integer (>=0) formatted directly, with no injection surface.
func buildWindowsConfigScreenTimeoutScript(action string, minutes int) (string, error) {
	switch action {
	case "get":
		return "powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE", nil
	case "set":
		if minutes < 0 {
			return "", fmt.Errorf("parameter minutes cannot be negative, actual %d", minutes)
		}
		return fmt.Sprintf("powercfg /change monitor-timeout-ac %d; powercfg /change monitor-timeout-dc %d", minutes, minutes), nil
	default:
		return "", fmt.Errorf("parameter action does not support %q, allowed values: get, set", action)
	}
}

// buildWindowsConfigRemoteDesktopScript constructs the script for windows.config.remote-desktop.
// action is enable/disable/get.
func buildWindowsConfigRemoteDesktopScript(action string) (string, error) {
	switch action {
	case "get":
		return "$v = (Get-ItemProperty -Path '" + windowsConfigRemoteDesktopPath + "' -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections; " +
			"Write-Output ('fDenyTSConnections=' + $v)", nil
	case "enable":
		return "Set-ItemProperty -Path '" + windowsConfigRemoteDesktopPath + "' -Name fDenyTSConnections -Value 0 -Force; " +
			"Write-Output 'Remote Desktop enabled (may need admin)'", nil
	case "disable":
		return "Set-ItemProperty -Path '" + windowsConfigRemoteDesktopPath + "' -Name fDenyTSConnections -Value 1 -Force; " +
			"Write-Output 'Remote Desktop disabled (may need admin)'", nil
	default:
		return "", fmt.Errorf("parameter action does not support %q, allowed values: enable, disable, get", action)
	}
}

// buildWindowsConfigStartupScript constructs the script for windows.config.startup.
// action is list/enable/disable; for enable/disable, name is required and escaped.
func buildWindowsConfigStartupScript(action, name string) (string, error) {
	switch action {
	case "list":
		return "Get-ChildItem -Path '" + windowsConfigStartupDir + "' -ErrorAction SilentlyContinue | " +
			"ForEach-Object { Write-Output ($_.Name + ' | ' + $_.Target) }", nil
	case "enable", "disable":
		if name == "" {
			return "", fmt.Errorf("the %s operation requires the name parameter", action)
		}
		// name is a file name; after escaping by encodePowerShellText it becomes part of the path.
		quotedName := encodePowerShellText(name)
		if action == "disable" {
			return "$p = Join-Path '" + windowsConfigStartupDir + "' " + quotedName + "; " +
				"if (Test-Path $p) { Rename-Item $p ($p + '.disabled') -Force; Write-Output ('Disabled: ' + " + quotedName + ") } " +
				"else { Write-Error ('Not found: ' + " + quotedName + ") }", nil
		}
		return "$p = Join-Path '" + windowsConfigStartupDir + "' " + quotedName + "; " +
			"$disabled = $p + '.disabled'; " +
			"if (Test-Path $disabled) { Rename-Item $disabled $p -Force; Write-Output ('Enabled: ' + " + quotedName + ") } " +
			"elseif (Test-Path $p) { Write-Output ('Already enabled: ' + " + quotedName + ") } " +
			"else { Write-Error ('Not found: ' + " + quotedName + ") }", nil
	default:
		return "", fmt.Errorf("parameter action does not support %q, allowed values: list, enable, disable", action)
	}
}

// trimWindowsOutput removes leading/trailing whitespace from PowerShell output.
func trimWindowsOutput(out string) string {
	return strings.TrimSpace(out)
}
