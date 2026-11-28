//go:build windows

package capability

// This file implements the Windows platform system configuration capabilities (windows.config.*), with semantics
// aligned with the config command group of haijunbot-windows (hw):
//   - theme: switch the system/app dark/light theme
//   - power-plan: list or switch the power plan
//   - proxy: get/enable/disable/set the system proxy
//   - screen-timeout: get/set the screen-off timeout
//   - remote-desktop: enable/disable/query Remote Desktop
//   - startup: list/enable/disable startup items
//
// Everything operates on the registry or invokes system commands (powercfg, etc.) via PowerShell, with zero third-party dependencies.
// Unlike hw (third-party libraries such as pywinauto), only the system's built-in PowerShell and registry are used here.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success path has not been verified end-to-end.
// The parameter validation and script construction logic have been extracted into the build-tag-free windows_config_parse.go,
// which can be unit-tested on Linux.

import (
	"time"
)

// windowsConfigTimeout is the timeout for a single system configuration operation.
// Commands such as powercfg /query may be a bit slow, so it is relaxed to 30s.
const windowsConfigTimeout = 30 * time.Second

// registerWindowsConfig registers the Windows system configuration capabilities.
func registerWindowsConfig(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.config.theme",
		Description: "Switch the system/app theme (dark/light mode)." +
			"Implemented by modifying the AppsUseLightTheme and SystemUsesLightTheme of the " +
			"Themes\\Personalize registry key under HKCU (0=dark, 1=light). No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"mode": map[string]any{
					"type":        "string",
					"description": "Target mode: dark, light, toggle (invert the current value).",
				},
			},
			"required": []string{"mode"},
		},
		Handler: handleWindowsConfigTheme,
	})

	_ = reg.Register(Capability{
		Name: "windows.config.power-plan",
		Description: "List or switch the Windows power plan." +
			"list uses powercfg /list to list all plans; set uses powercfg /setactive to activate the specified plan." +
			"No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"action": map[string]any{
					"type":        "string",
					"description": "Action: list (list plans) or set (switch plan).",
				},
				"plan_id": map[string]any{
					"type":        "string",
					"description": "Power plan GUID (required for set), such as 381b4222-f694-41f0-9685-ff5bb260df2e.",
				},
			},
			"required": []string{"action"},
		},
		Handler: handleWindowsConfigPowerPlan,
	})

	_ = reg.Register(Capability{
		Name: "windows.config.proxy",
		Description: "Get, enable, disable, or set the Windows system proxy." +
			"Implemented by modifying the Internet Settings registry key under HKCU (ProxyEnable/ProxyServer/ProxyOverride)." +
			"No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"action": map[string]any{
					"type":        "string",
					"description": "Action: get (query), enable, disable, set (set the proxy address).",
				},
				"server": map[string]any{
					"type":        "string",
					"description": "Proxy address, such as 127.0.0.1:7890 (used for enable/set).",
				},
				"bypass": map[string]any{
					"type":        "string",
					"description": "Bypass list, semicolon-separated, such as localhost;127.* (optional for enable/set).",
				},
			},
			"required": []string{"action"},
		},
		Handler: handleWindowsConfigProxy,
	})

	_ = reg.Register(Capability{
		Name: "windows.config.screen-timeout",
		Description: "Get or set the screen-off timeout (current power plan)." +
			"get uses powercfg /query to query VIDEOIDLE; set uses powercfg /change to set the screen-off minutes on AC/battery power." +
			"No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"action": map[string]any{
					"type":        "string",
					"description": "Action: get (query) or set.",
				},
				"minutes": map[string]any{
					"type":        "integer",
					"description": "Screen-off minutes, 0 means never (required for set).",
				},
			},
			"required": []string{"action"},
		},
		Handler: handleWindowsConfigScreenTimeout,
	})

	_ = reg.Register(Capability{
		Name: "windows.config.remote-desktop",
		Description: "Enable, disable, or query Remote Desktop." +
			"Implemented by modifying the fDenyTSConnections of the Terminal Server registry key under HKLM (0=allow, 1=deny)." +
			"Modification requires administrator privileges. No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"action": map[string]any{
					"type":        "string",
					"description": "Action: enable, disable, get (query).",
				},
			},
			"required": []string{"action"},
		},
		Handler: handleWindowsConfigRemoteDesktop,
	})

	_ = reg.Register(Capability{
		Name: "windows.config.startup",
		Description: "List, enable, or disable the current user's startup items." +
			"Operates on the %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup folder, " +
			"renaming files with a .disabled suffix when disabling and restoring them when enabling. No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"action": map[string]any{
					"type":        "string",
					"description": "Action: list, enable, disable.",
				},
				"name": map[string]any{
					"type":        "string",
					"description": "Startup item file name (required for enable/disable), such as myapp.lnk.",
				},
			},
			"required": []string{"action"},
		},
		Handler: handleWindowsConfigStartup,
	})
}

// handleWindowsConfigTheme is the implementation of windows.config.theme.
func handleWindowsConfigTheme(params map[string]any) (any, error) {
	mode, err := requiredString(params, "mode")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigThemeScript(mode)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"mode":   mode,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}

// handleWindowsConfigPowerPlan is the implementation of windows.config.power-plan.
func handleWindowsConfigPowerPlan(params map[string]any) (any, error) {
	action, err := requiredString(params, "action")
	if err != nil {
		return nil, err
	}

	planID, err := optionalString(params, "plan_id")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigPowerPlanScript(action, planID)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"action": action,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}

// handleWindowsConfigProxy is the implementation of windows.config.proxy.
func handleWindowsConfigProxy(params map[string]any) (any, error) {
	action, err := requiredString(params, "action")
	if err != nil {
		return nil, err
	}

	server, err := optionalString(params, "server")
	if err != nil {
		return nil, err
	}
	bypass, err := optionalString(params, "bypass")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigProxyScript(action, server, bypass)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"action": action,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}

// handleWindowsConfigScreenTimeout is the implementation of windows.config.screen-timeout.
func handleWindowsConfigScreenTimeout(params map[string]any) (any, error) {
	action, err := requiredString(params, "action")
	if err != nil {
		return nil, err
	}

	minutes, err := optionalInt(params, "minutes", 0)
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigScreenTimeoutScript(action, minutes)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"action": action,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}

// handleWindowsConfigRemoteDesktop is the implementation of windows.config.remote-desktop.
func handleWindowsConfigRemoteDesktop(params map[string]any) (any, error) {
	action, err := requiredString(params, "action")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigRemoteDesktopScript(action)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"action": action,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}

// handleWindowsConfigStartup is the implementation of windows.config.startup.
func handleWindowsConfigStartup(params map[string]any) (any, error) {
	action, err := requiredString(params, "action")
	if err != nil {
		return nil, err
	}

	name, err := optionalString(params, "name")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsConfigStartupScript(action, name)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsConfigTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"action": action,
		"output": trimWindowsOutput(out),
		"tool":   "powershell",
	}, nil
}
