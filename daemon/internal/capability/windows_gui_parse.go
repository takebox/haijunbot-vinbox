package capability

// This file holds "platform-independent pure logic" among the Windows GUI capabilities, deliberately without the
// //go:build windows tag, so it can be compiled and unit-tested on Linux (the local dev environment is Linux, no Windows runtime).
//
// Only functions that do not depend on any Windows-specific types (syscall handles other than uintptr, etc.) are put here:
//   - parseWindowIDString: window ID string parsing
//   - parseWindowsKeyCombo: key combination string parsing
//   - virtualKeyCode: mapping from key name to virtual key code
//   - mouseButtonFlags: mapping from mouse button name to mouse_event flags
//   - encodePowerShellText: safe encoding of PowerShell text arguments (anti command injection)

import (
	"fmt"
	"strconv"
	"strings"
)

// parseWindowIDString parses a string-form window ID into an unsigned integer.
//
// It supports both the "0x"-prefixed hexadecimal form and the pure decimal form (strconv.ParseUint's base=0
// automatically recognizes the 0x/0X prefix). The caller is responsible for converting the result to an HWND (uintptr).
//
// The reason for putting the pure parsing logic in this file rather than windows_gui_windows.go: this way it can be
// unit-tested directly on Linux, and the Windows side only needs a thin wrapper (see parseWindowID in
// windows_gui_windows.go).
func parseWindowIDString(s string) (uint64, error) {
	trimmed := strings.TrimSpace(s)
	if trimmed == "" {
		return 0, fmt.Errorf("parameter window_id cannot be empty")
	}
	v, err := strconv.ParseUint(trimmed, 0, 64)
	if err != nil {
		return 0, fmt.Errorf("parameter window_id has an invalid format %q, should be a 0x-prefixed hexadecimal or decimal integer", s)
	}
	if v == 0 {
		return 0, fmt.Errorf("parameter window_id cannot be 0")
	}
	return v, nil
}

// windowsModifierNames is the normalized mapping of modifier key aliases.
//
// The keys are lowercase aliases, and the values are the normalized modifier key names (ctrl/alt/shift/win).
// ctrl and control are equivalent; win and super/meta are equivalent (Linux's xdotool uses super,
// while the Windows side habitually calls it win, and both are accepted).
var windowsModifierNames = map[string]string{
	"ctrl":    "ctrl",
	"control": "ctrl",
	"alt":     "alt",
	"shift":   "shift",
	"win":     "win",
	"super":   "win",
	"meta":    "win",
}

// parseWindowsKeyCombo parses a key combination string of the form "modifiers+main key".
//
// Syntax: joined by '+', such as "ctrl+c", "alt+Tab", "ctrl+shift+s", "Return" (no modifier keys).
// Modifier key names are case-insensitive, supporting ctrl/control, alt, shift, win/super/meta.
//
// Returns the normalized modifier key list (in input order, may be empty) and the main key name (preserving the original
// case, with virtualKeyCode doing the case-insensitive matching afterward).
//
// Error cases: empty string, consecutive plus signs (such as "ctrl++c"), starting or ending with a plus sign, unknown
// modifier key, missing main key. Note: '+' itself as the main key (the plus key) is not supported for now and will
// error with "missing main key"; this is a deliberate trade-off — sending the plus key on Windows should go through windows.input.type.
func parseWindowsKeyCombo(keys string) ([]string, string, error) {
	trimmed := strings.TrimSpace(keys)
	if trimmed == "" {
		return nil, "", fmt.Errorf("parameter keys cannot be empty")
	}

	parts := strings.Split(trimmed, "+")
	// Starting/ending with '+' or having an empty segment (consecutive plus signs) is regarded as illegal.
	for _, p := range parts {
		if strings.TrimSpace(p) == "" {
			return nil, "", fmt.Errorf("parameter keys has an invalid format %q, neither side of the plus sign can be empty", keys)
		}
	}

	// The last segment is the main key, and the rest are all modifier keys.
	key := strings.TrimSpace(parts[len(parts)-1])
	modifiers := make([]string, 0, len(parts)-1)
	seen := make(map[string]struct{}, len(parts)-1)
	for _, raw := range parts[:len(parts)-1] {
		name := strings.ToLower(strings.TrimSpace(raw))
		normalized, ok := windowsModifierNames[name]
		if !ok {
			return nil, "", fmt.Errorf("the %q in parameter keys is not a valid modifier key, "+
				"supported: ctrl/control, alt, shift, win/super/meta", raw)
		}
		// Deduplicate: ctrl+ctrl+c counts Ctrl only once.
		if _, dup := seen[normalized]; dup {
			continue
		}
		seen[normalized] = struct{}{}
		modifiers = append(modifiers, normalized)
	}

	if key == "" {
		return nil, "", fmt.Errorf("parameter keys has an invalid format %q, missing the main key", keys)
	}
	return modifiers, key, nil
}

// windowsSpecialKeys is the mapping from special key names to virtual key codes.
//
// The keys are lowercase key names (including common aliases), and the values are the corresponding Win32 virtual key
// codes (VK_*). Single letters and single digits are not in this table and are handled separately by virtualKeyCode.
var windowsSpecialKeys = map[string]uint16{
	// Editing and whitespace
	"return":    0x0D, // VK_RETURN
	"enter":     0x0D,
	"tab":       0x09, // VK_TAB
	"esc":       0x1B, // VK_ESCAPE
	"escape":    0x1B,
	"space":     0x20, // VK_SPACE
	"backspace": 0x08, // VK_BACK
	"delete":    0x2E, // VK_DELETE
	"del":       0x2E,
	"insert":    0x2D, // VK_INSERT
	"ins":       0x2D,

	// Navigation
	"home":     0x24, // VK_HOME
	"end":      0x23, // VK_END
	"pageup":   0x21, // VK_PRIOR
	"prior":    0x21,
	"pagedown": 0x22, // VK_NEXT
	"next":     0x22,
	"left":     0x25, // VK_LEFT
	"up":       0x26, // VK_UP
	"right":    0x27, // VK_RIGHT
	"down":     0x28, // VK_DOWN

	// The modifier keys themselves may also appear as the main key name (such as "win", "ctrl").
	// The aliases are filled in here to ensure that the modifier key name normalized by parseWindowsKeyCombo
	// can be mapped correctly by virtualKeyCode — otherwise a combination like "ctrl+super+Tab"
	// would fail when looking up the main key code.
	"ctrl":    0x11, // VK_CONTROL
	"control": 0x11,
	"alt":     0x12, // VK_MENU
	"shift":   0x10, // VK_SHIFT
	"win":     0x5B, // VK_LWIN
	"super":   0x5B,
	"meta":    0x5B,
}

// windowsFunctionKeyBase is the virtual key code of F1; F1-F12 increase in sequence.
const windowsFunctionKeyBase = 0x70 // VK_F1

// virtualKeyCode maps a key name to a Win32 virtual key code.
//
// Case-insensitive. Supports:
//   - single letters a-z (VK codes 0x41-0x5A)
//   - single digits 0-9 (VK codes 0x30-0x39)
//   - special keys (see windowsSpecialKeys)
//   - function keys F1-F12 (VK codes 0x70-0x7B)
//
// An unknown key name returns ok=false, and the caller decides how to report the error.
func virtualKeyCode(name string) (uint16, bool) {
	n := strings.ToLower(strings.TrimSpace(name))
	if n == "" {
		return 0, false
	}

	// Single letter: a-z → 0x41-0x5A.
	if len(n) == 1 {
		c := n[0]
		switch {
		case c >= 'a' && c <= 'z':
			return uint16(c - 'a' + 0x41), true
		case c >= '0' && c <= '9':
			return uint16(c - '0' + 0x30), true
		}
	}

	// Function keys F1-F12.
	if len(n) >= 2 && n[0] == 'f' {
		if num, err := strconv.Atoi(n[1:]); err == nil && num >= 1 && num <= 12 {
			return uint16(windowsFunctionKeyBase + num - 1), true
		}
	}

	if vk, ok := windowsSpecialKeys[n]; ok {
		return vk, true
	}
	return 0, false
}

// mouseButtonFlags returns the mouse_event flags corresponding to the specified mouse button when "pressed" or "released".
//
// button supports left/right/middle (case-insensitive); down being true means pressed.
// An unknown button name returns 0 and false.
func mouseButtonFlags(button string, down bool) (uint32, bool) {
	switch strings.ToLower(strings.TrimSpace(button)) {
	case "left":
		if down {
			return 0x0002, true // MOUSEEVENTF_LEFTDOWN
		}
		return 0x0004, true // MOUSEEVENTF_LEFTUP
	case "right":
		if down {
			return 0x0008, true // MOUSEEVENTF_RIGHTDOWN
		}
		return 0x0010, true // MOUSEEVENTF_RIGHTUP
	case "middle":
		if down {
			return 0x0020, true // MOUSEEVENTF_MIDDLEDOWN
		}
		return 0x0040, true // MOUSEEVENTF_MIDDLEUP
	default:
		return 0, false
	}
}

// encodePowerShellText encodes arbitrary text into a form that can be safely embedded in a PowerShell command.
//
// Purpose: windows.clipboard.set needs to pass user-provided text to PowerShell's
// Set-Clipboard. **The text must never be concatenated directly into the command string** (quotes, $, ;, backticks,
// newlines, etc. can all cause command injection).
//
// Method: return a single-quoted PowerShell literal, and escape single quotes in the text into "two consecutive single
// quotes" per PowerShell rules. A PowerShell single-quoted string is a "literal", so $, backticks, semicolons, etc.
// inside are not interpreted, making this a safe encoding that does not change the content.
//
// Note: the caller still needs to pass this literal as a whole to the -Command parameter, and must not wrap it again in double quotes.
func encodePowerShellText(text string) string {
	return "'" + strings.ReplaceAll(text, "'", "''") + "'"
}
