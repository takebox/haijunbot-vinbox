//go:build windows

package capability

// This file implements the Windows UI automation capabilities (windows.ui.*), with semantics aligned with the
// get-tree / menu commands of haijunbot-windows (hw):
//   - windows.ui.tree: enumerate the control tree of the specified window (using the .NET built-in UIAutomation)
//   - windows.ui.menu: operate a menu item by path (such as "File->Open")
//
// Everything is implemented via PowerShell loading the UIAutomationClient assembly, with zero third-party dependencies.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success path has not been verified end-to-end.
// The script construction and output parsing logic have been extracted into the build-tag-free windows_ui_parse.go, which can be unit-tested on Linux.

import (
	"strings"
	"time"
)

// windowsUITimeout is the timeout for a single UI automation operation.
// UIA traversal of a large window may be slow, so it is relaxed to 30s.
const windowsUITimeout = 30 * time.Second

// registerWindowsUI registers the Windows UI automation capabilities.
func registerWindowsUI(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.ui.tree",
		Description: "Enumerate the control tree of the specified window. " +
			"Uses the .NET built-in UIAutomation to traverse all controls in the window, returning each control's type, name, AutomationId, and rectangle. " +
			"Locate the window via window_id or title; max_depth/max_controls limit the traversal scale. No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match, case-insensitive), used when window_id is not provided.",
				},
				"max_depth": map[string]any{
					"type":        "integer",
					"description": "Maximum traversal depth, default 10.",
				},
				"max_controls": map[string]any{
					"type":        "integer",
					"description": "Maximum number of controls, default 200.",
				},
			},
		},
		Handler: handleWindowsUITree,
	})

	_ = reg.Register(Capability{
		Name: "windows.ui.menu",
		Description: "Operate a window menu item by path (such as 'File->Open'). " +
			"Uses the .NET built-in UIAutomation to find the menu item level by level and trigger Invoke/ExpandCollapse. " +
			"Locate the window via window_id or title. No third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match, case-insensitive), used when window_id is not provided.",
				},
				"path": map[string]any{
					"type":        "string",
					"description": "Menu path, separated by '->', such as 'File->Open'.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleWindowsUIMenu,
	})

	_ = reg.Register(Capability{
		Name: "windows.control.click",
		Description: "Directly click a control within the window by control name or AutomationId (a control-level operation, not relying on screen coordinates). " +
			"Uses the .NET built-in UIAutomation to locate the control and trigger InvokePattern.Invoke or SelectionItemPattern.Select. " +
			"Locate the window via window_id or title, and the control via name/automation_id. No third-party dependencies required. " +
			"Note: Chromium-rendered apps such as CEF/Electron do not expose UIA controls, so this capability is ineffective for them; use screenshot + OCR + coordinate click instead.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match, case-insensitive), used when window_id is not provided.",
				},
				"name": map[string]any{
					"type":        "string",
					"description": "Control name (Name property); provide at least one of name and automation_id.",
				},
				"automation_id": map[string]any{
					"type":        "string",
					"description": "Control AutomationId; provide at least one of automation_id and name.",
				},
			},
		},
		Handler: handleWindowsControlClick,
	})

	_ = reg.Register(Capability{
		Name: "windows.control.set-text",
		Description: "Directly set the text of a control within the window by control name or AutomationId (a control-level operation, not relying on screen coordinates). " +
			"Uses the .NET built-in UIAutomation to locate the control and ValuePattern.SetValue to set the text. " +
			"Locate the window via window_id or title, and the control via name/automation_id. No third-party dependencies required. " +
			"Note: Chromium-rendered apps such as CEF/Electron do not expose UIA controls, so this capability is ineffective for them; use screenshot + OCR + coordinate click instead.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match, case-insensitive), used when window_id is not provided.",
				},
				"name": map[string]any{
					"type":        "string",
					"description": "Control name (Name property); provide at least one of name and automation_id.",
				},
				"automation_id": map[string]any{
					"type":        "string",
					"description": "Control AutomationId; provide at least one of automation_id and name.",
				},
				"text": map[string]any{
					"type":        "string",
					"description": "The text content to set.",
				},
			},
			"required": []string{"text"},
		},
		Handler: handleWindowsControlSetText,
	})
}

// handleWindowsUITree is the implementation of windows.ui.tree.
func handleWindowsUITree(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	maxDepth, err := optionalInt(params, "max_depth", uiTreeMaxDepthDefault)
	if err != nil {
		return nil, err
	}
	maxControls, err := optionalInt(params, "max_controls", uiTreeMaxControlsDefault)
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsUITreeScript(windowID, title, maxDepth, maxControls)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsUITimeout)
	if err != nil {
		return nil, err
	}

	controls := parseWindowsUITreeText(out)
	return map[string]any{
		"window_id": windowID,
		"title":     title,
		"count":     len(controls),
		"controls":  controls,
		"tool":      "powershell",
	}, nil
}

// handleWindowsUIMenu is the implementation of windows.ui.menu.
func handleWindowsUIMenu(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsUIMenuScript(windowID, title, path)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsUITimeout)
	if err != nil {
		return nil, err
	}

	result := map[string]any{
		"window_id": windowID,
		"title":     title,
		"path":      path,
		"output":    trimWindowsOutput(out),
		"tool":      "powershell",
	}
	// If the script output has the ERROR: prefix, the menu item was not found or could not be triggered; return an error.
	if msg := trimWindowsOutput(out); len(msg) > 6 && msg[:6] == "ERROR:" {
		return nil, &windowsUIMenuError{msg: msg[6:]}
	}
	return result, nil
}

// windowsUIMenuError represents a menu operation failure (such as the menu item not being found, no available pattern).
type windowsUIMenuError struct {
	msg string
}

func (e *windowsUIMenuError) Error() string {
	return "menu operation failed: " + e.msg
}

// handleWindowsControlClick is the implementation of windows.control.click.
func handleWindowsControlClick(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	name, err := optionalString(params, "name")
	if err != nil {
		return nil, err
	}
	automationID, err := optionalString(params, "automation_id")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsControlClickScript(windowID, title, name, automationID)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsUITimeout)
	if err != nil {
		return nil, err
	}

	result := map[string]any{
		"window_id":     windowID,
		"title":         title,
		"name":          name,
		"automation_id": automationID,
		"output":        trimWindowsOutput(out),
		"tool":          "powershell",
	}
	msg := trimWindowsOutput(out)
	if len(msg) > 6 && msg[:6] == "ERROR:" {
		return nil, &windowsControlError{msg: msg[6:]}
	}
	// Record the pattern actually triggered (invoked/selected).
	if strings.HasPrefix(msg, "OK:invoked") {
		result["clicked"] = "invoked"
	} else if strings.HasPrefix(msg, "OK:selected") {
		result["clicked"] = "selected"
	}
	return result, nil
}

// handleWindowsControlSetText is the implementation of windows.control.set-text.
func handleWindowsControlSetText(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	name, err := optionalString(params, "name")
	if err != nil {
		return nil, err
	}
	automationID, err := optionalString(params, "automation_id")
	if err != nil {
		return nil, err
	}
	text, err := requiredString(params, "text")
	if err != nil {
		return nil, err
	}

	script, err := buildWindowsControlSetTextScript(windowID, title, name, automationID, text)
	if err != nil {
		return nil, err
	}

	out, err := runWindowsPowerShellCommand(script, windowsUITimeout)
	if err != nil {
		return nil, err
	}

	result := map[string]any{
		"window_id":     windowID,
		"title":         title,
		"name":          name,
		"automation_id": automationID,
		"text":          text,
		"output":        trimWindowsOutput(out),
		"tool":          "powershell",
	}
	msg := trimWindowsOutput(out)
	if len(msg) > 6 && msg[:6] == "ERROR:" {
		return nil, &windowsControlError{msg: msg[6:]}
	}
	result["text_set"] = true
	return result, nil
}

// windowsControlError represents a control operation failure (control not found, no available pattern, etc.).
type windowsControlError struct {
	msg string
}

func (e *windowsControlError) Error() string {
	return "control operation failed: " + e.msg
}
