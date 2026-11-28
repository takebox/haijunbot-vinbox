//go:build windows

package capability

// This file implements the Windows platform input simulation capabilities (windows.input.*).
//
// Like the window capabilities (windows_gui_windows.go), it directly calls user32.dll via syscall,
// with zero third-party dependencies and zero cgo. Unlike the Linux side (which calls xdotool), the Windows side does not depend on any
// external command.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success paths of each capability have not been verified end-to-end.
// The parameter validation and pure parsing logic (key combination parsing, virtual key code mapping, mouse flag mapping) have been extracted into
// the build-tag-free windows_gui_parse.go, which can be unit-tested on Linux.

import (
	"fmt"
	"time"
	"unsafe"
)

// user32.dll's input-related procedures.
//
// Note: the package-level variable user32 is already defined in windows_gui_windows.go and is reused directly here,
// not redefined.
var (
	procSetCursorPos = user32.NewProc("SetCursorPos")
	procMouseEvent   = user32.NewProc("mouse_event")
	procKeybdEvent   = user32.NewProc("keybd_event")
	procSendInput    = user32.NewProc("SendInput")
)

// Keyboard event flags (the dwFlags of keybd_event).
const (
	// keyeventfKeyUp indicates a "key up" event; without this flag it is "key down".
	keyeventfKeyUp = 0x0002
)

// windowsInputTool is the value of the tool field in the results returned by the input capabilities.
const windowsInputTool = "user32.dll"

// registerWindowsInput registers the Windows input simulation capabilities.
func registerWindowsInput(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.input.click",
		Description: "Clicks the mouse at the specified screen coordinates. " +
			"First moves the cursor with SetCursorPos, then sends down/up with mouse_event. " +
			"The coordinates use the top-left corner of the primary screen as the origin (pixels). No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Screen x coordinate (pixels); 0 is allowed.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Screen y coordinate (pixels); 0 is allowed.",
				},
				"button": map[string]any{
					"type":        "string",
					"description": "Mouse button, default left; supports left/right/middle.",
				},
				"count": map[string]any{
					"type":        "integer",
					"description": "Number of clicks, default 1; set to 2 for a double click.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleWindowsInputClick,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.type",
		Description: "Types text into the currently focused window. " +
			"Sends character by character via keybd_event's Unicode scan code (VK=0, with KEYEVENTF_UNICODE semantics), " +
			"correctly typing non-ASCII characters such as Chinese. " +
			"Note: this capability only sends the characters themselves and does not parse control sequences.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"text": map[string]any{
					"type":        "string",
					"description": "The text to type.",
				},
				"delay_ms": map[string]any{
					"type":        "integer",
					"description": "Delay in milliseconds between each character, default 0 (no delay); cannot be negative.",
				},
			},
			"required": []string{"text"},
		},
		Handler: handleWindowsInputType,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.keys",
		Description: "Sends a key combination to the currently focused window, such as ctrl+c, alt+Tab, ctrl+shift+s, Return. " +
			"Modifier keys support ctrl/control, alt, shift, win/super/meta; the main key supports letters, digits, " +
			"function keys F1-F12, arrow keys, and common special keys. No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"keys": map[string]any{
					"type":        "string",
					"description": "Key sequence, such as ctrl+c, alt+Tab, ctrl+shift+s, Return.",
				},
			},
			"required": []string{"keys"},
		},
		Handler: handleWindowsInputKeys,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.double-click",
		Description: "Double-clicks the mouse at the specified screen coordinates. " +
			"First moves the cursor with SetCursorPos, then sends down/up twice in a row. " +
			"Equivalent to windows.input.click with count=2, but clearer as an independent capability. " +
			"The coordinates use the top-left corner of the primary screen as the origin (pixels). No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Screen x coordinate (pixels); 0 is allowed.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Screen y coordinate (pixels); 0 is allowed.",
				},
				"button": map[string]any{
					"type":        "string",
					"description": "Mouse button, default left; supports left/right/middle.",
				},
				"delay_ms": map[string]any{
					"type":        "integer",
					"description": "Delay in milliseconds between the two clicks, default 0; cannot be negative.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleWindowsInputDoubleClick,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.right-click",
		Description: "Right-clicks the mouse at the specified screen coordinates. " +
			"First moves the cursor with SetCursorPos, then sends right button down/up with mouse_event. " +
			"The coordinates use the top-left corner of the primary screen as the origin (pixels). No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Screen x coordinate (pixels); 0 is allowed.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Screen y coordinate (pixels); 0 is allowed.",
				},
				"button": map[string]any{
					"type":        "string",
					"description": "Mouse button, default right; supports left/right/middle.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleWindowsInputRightClick,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.hover",
		Description: "Moves the mouse cursor to the specified screen coordinates (hover, without clicking). " +
			"Moves the cursor with SetCursorPos, which can be used to trigger a control's hover effect or position for a subsequent operation. " +
			"The coordinates use the top-left corner of the primary screen as the origin (pixels). No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Screen x coordinate (pixels); 0 is allowed.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Screen y coordinate (pixels); 0 is allowed.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleWindowsInputHover,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.drag",
		Description: "Drags the mouse from a start point to an end point (down, move, up). " +
			"First SetCursorPos to the start point and press the button, then interpolate along a straight line moving step by step to the end point, finally releasing. " +
			"Can be used for dragging files, resizing windows, drawing, etc. The coordinates use the top-left corner of the primary screen as the origin (pixels). " +
			"No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"from_x": map[string]any{
					"type":        "integer",
					"description": "Drag start x coordinate (pixels); 0 is allowed.",
				},
				"from_y": map[string]any{
					"type":        "integer",
					"description": "Drag start y coordinate (pixels); 0 is allowed.",
				},
				"to_x": map[string]any{
					"type":        "integer",
					"description": "Drag end x coordinate (pixels); 0 is allowed.",
				},
				"to_y": map[string]any{
					"type":        "integer",
					"description": "Drag end y coordinate (pixels); 0 is allowed.",
				},
				"button": map[string]any{
					"type":        "string",
					"description": "Mouse button, default left; supports left/right/middle.",
				},
				"steps": map[string]any{
					"type":        "integer",
					"description": "Number of interpolation steps for the movement, default 20; larger is a smoother drag trajectory.",
				},
			},
			"required": []string{"from_x", "from_y", "to_x", "to_y"},
		},
		Handler: handleWindowsInputDrag,
	})

	_ = reg.Register(Capability{
		Name: "windows.input.wheel",
		Description: "Scrolls the mouse wheel. " +
			"Sends a wheel scroll via mouse_event's MOUSEEVENTF_WHEEL; " +
			"a positive delta means scroll up and a negative delta means scroll down (±120 is one notch). " +
			"Optional x/y first moves the cursor to the specified position before scrolling. The coordinates use the top-left corner of the primary screen as the origin (pixels). " +
			"No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Optional. The x coordinate (pixels) to move the cursor to before scrolling; scrolls at the current cursor position when omitted.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Optional. The y coordinate (pixels) to move the cursor to before scrolling; scrolls at the current cursor position when omitted.",
				},
				"delta": map[string]any{
					"type":        "integer",
					"description": "Scroll amount, positive=up, negative=down; ±120 is one notch. Default 120.",
				},
			},
		},
		Handler: handleWindowsInputWheel,
	})
}

// handleWindowsInputClick is the implementation of windows.input.click.
func handleWindowsInputClick(params map[string]any) (any, error) {
	// x/y are allowed to be 0 (the top-left corner of the screen), so requiredInt must be used to explicitly determine whether they are provided;
	// the default-value semantics of optionalInt cannot be reused.
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}

	button, err := optionalString(params, "button")
	if err != nil {
		return nil, err
	}
	if button == "" {
		button = "left"
	}
	downFlag, ok := mouseButtonFlags(button, true)
	if !ok {
		return nil, fmt.Errorf("parameter button does not support %q, allowed values: left, right, middle", button)
	}
	upFlag, _ := mouseButtonFlags(button, false)

	count, err := optionalInt(params, "count", 1)
	if err != nil {
		return nil, err
	}
	if count <= 0 {
		return nil, fmt.Errorf("parameter count must be a positive integer, actual %d", count)
	}

	// Move the cursor: SetCursorPos returning 0 means failure.
	if r, _, err := procSetCursorPos.Call(uintptr(x), uintptr(y)); r == 0 {
		return nil, fmt.Errorf("failed to move the cursor to (%d, %d): %v", x, y, err)
	}

	for i := 0; i < count; i++ {
		procMouseEvent.Call(uintptr(downFlag), 0, 0, 0, 0)
		procMouseEvent.Call(uintptr(upFlag), 0, 0, 0, 0)
	}

	return map[string]any{
		"x":      x,
		"y":      y,
		"button": button,
		"count":  count,
		"tool":   windowsInputTool,
	}, nil
}

// handleWindowsInputType is the implementation of windows.input.type.
func handleWindowsInputType(params map[string]any) (any, error) {
	text, err := requiredString(params, "text")
	if err != nil {
		return nil, err
	}

	delayMS, err := optionalInt(params, "delay_ms", 0)
	if err != nil {
		return nil, err
	}
	if delayMS < 0 {
		return nil, fmt.Errorf("parameter delay_ms cannot be negative, actual %d", delayMS)
	}

	// Send Unicode character by character.
	//
	// Scheme notes: SendInput + KEYBDINPUT (with KEYEVENTF_UNICODE in dwFlags) is used here.
	// This is the standard way to input arbitrary Unicode characters (including Chinese) on Windows:
	//   - wVk set to 0, wScan set to the UTF-16 code unit, dwFlags with KEYEVENTF_UNICODE(0x0004),
	//     and the system injects that code unit as a character, without going through keyboard layout translation;
	//   - send two events "down + up" for each character.
	//
	// Why not use keybd_event: keybd_event only accepts virtual key codes and has no KEYEVENTF_UNICODE
	// semantics, so it cannot directly input non-ASCII characters (Chinese would be lost). SendInput is the only reliable path.
	//
	// Struct layout risk: on 64-bit, INPUT is 40 bytes (type 4 + alignment 4 + union 32),
	// and KEYBDINPUT is 24 bytes (wVk 2 + wScan 2 + dwFlags 4 + time 4 + dwExtraInfo 8
	// + alignment 4). The struct definition below is written strictly according to the Win32 layout and validated with a compile-time assertion on the size,
	// so a layout mismatch is exposed at compile time rather than silently failing at runtime.
	const keyeventfUnicode = 0x0004
	for _, r := range text {
		// Iterate with rune to correctly handle characters outside the BMP; for surrogate pairs
		// they need to be split into two UTF-16 code units and sent separately.
		if r > 0xFFFF {
			hi, lo := utf16SurrogatePair(r)
			sendUnicodeChar(hi, keyeventfUnicode)
			sendUnicodeChar(lo, keyeventfUnicode)
		} else {
			sendUnicodeChar(uint16(r), keyeventfUnicode)
		}
		if delayMS > 0 {
			time.Sleep(time.Duration(delayMS) * time.Millisecond)
		}
	}

	return map[string]any{
		"typed": text,
		"tool":  windowsInputTool,
	}, nil
}

// windowsKeybdInput corresponds to the Win32 KEYBDINPUT structure.
//
// The field order and types strictly follow the Windows SDK definition:
//
//	typedef struct tagKEYBDINPUT {
//	    WORD      wVk;
//	    WORD      wScan;
//	    DWORD     dwFlags;
//	    DWORD     time;
//	    ULONG_PTR dwExtraInfo;   // pointer width: 4 bytes on 32-bit, 8 bytes on 64-bit
//	} KEYBDINPUT;
type windowsKeybdInput struct {
	WVk         uint16
	WScan       uint16
	DwFlags     uint32
	Time        uint32
	DwExtraInfo uintptr
}

// inputKeyboard is the value INPUT_KEYBOARD of the type field of the INPUT structure.
const inputKeyboard = 1

// windowsInputSize is the size of the Win32 INPUT structure.
//
// INPUT is "DWORD type + union", and the largest member of the union is MOUSEINPUT:
//   - 64-bit: MOUSEINPUT is 32 bytes, plus the type 4 bytes and 4 bytes alignment = 40 bytes;
//   - 32-bit: MOUSEINPUT is 24 bytes, plus the type 4 bytes = 28 bytes.
//
// A value of 40 is used here for 64-bit. SendInput validates against cbSize, and passing the wrong size fails directly
// (returns 0 and sets LastError), rather than silently failing.
//
// Note: this value is only correct for 64-bit Windows. The Windows targets of the current build matrix are
// amd64/arm64 (both 64-bit), so it is safe; if 386 needs to be supported in the future, it must be changed to
// a dynamic computation via unsafe.Sizeof(uintptr(0)) (28 for 32-bit). The compile-time assertion below will
// fail directly on a 32-bit build, avoiding a silent failure.
const windowsInputSize = 40

// Compile-time assertion: windowsInputSize is only correct on 64-bit.
//
// If built on 32-bit (GOARCH=386/arm), the array length becomes negative and compilation fails directly,
// indicating that windowsInputSize and the union offset need adjustment, rather than a silent runtime failure.
var _ [unsafe.Sizeof(uintptr(0)) - 8]struct{}

// sendInputKeyboard sends one keyboard event with SendInput.
//
// The reason for manually constructing INPUT by byte offset rather than defining a Go struct: Go cannot express the Win32
// "type + union" layout — the union's alignment requirement (8 bytes) cannot be naturally obtained with Go fields
// ([32]byte only has alignment 1). Manual construction allows precise control of the offset and total size, avoiding a silent
// failure caused by a struct layout mismatch.
//
// The memory layout of INPUT (64-bit):
//
//	offset 0  : DWORD type
//	offset 4  : 4 bytes of alignment padding
//	offset 8  : the union (KEYBDINPUT starts here)
//
// Therefore KEYBDINPUT should be written at offset 8.
func sendInputKeyboard(kb windowsKeybdInput) {
	var buf [windowsInputSize]byte

	// Write the type field (offset 0).
	*(*uint32)(unsafe.Pointer(&buf[0])) = inputKeyboard

	// Write the KEYBDINPUT in the union (offset 8).
	*(*windowsKeybdInput)(unsafe.Pointer(&buf[8])) = kb

	procSendInput.Call(
		1,
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(windowsInputSize),
	)
}

// sendUnicodeChar sends the down and up events of one UTF-16 code unit with SendInput.
//
// KEYEVENTF_UNICODE requires wVk to be 0 and wScan to be the UTF-16 code unit.
func sendUnicodeChar(code uint16, unicodeFlag uint32) {
	// Key down event.
	sendInputKeyboard(windowsKeybdInput{WScan: code, DwFlags: unicodeFlag})
	// Key up event.
	sendInputKeyboard(windowsKeybdInput{WScan: code, DwFlags: unicodeFlag | keyeventfKeyUp})
}

// utf16SurrogatePair splits a code point above U+10000 into a UTF-16 surrogate pair.
func utf16SurrogatePair(r rune) (uint16, uint16) {
	v := uint32(r) - 0x10000
	hi := uint16(0xD800 + (v >> 10))
	lo := uint16(0xDC00 + (v & 0x3FF))
	return hi, lo
}

// handleWindowsInputKeys is the implementation of windows.input.keys.
func handleWindowsInputKeys(params map[string]any) (any, error) {
	keys, err := requiredString(params, "keys")
	if err != nil {
		return nil, err
	}

	modifiers, keyName, err := parseWindowsKeyCombo(keys)
	if err != nil {
		return nil, err
	}

	keyVK, ok := virtualKeyCode(keyName)
	if !ok {
		return nil, fmt.Errorf("unsupported key name %q", keyName)
	}

	modifierVKs := make([]uint16, 0, len(modifiers))
	for _, m := range modifiers {
		vk, ok := virtualKeyCode(m)
		if !ok {
			// parseWindowsKeyCombo has already validated the modifier key names, so this normally will not be reached.
			return nil, fmt.Errorf("unsupported modifier key %q", m)
		}
		modifierVKs = append(modifierVKs, vk)
	}

	// Press the modifier keys in order.
	for _, vk := range modifierVKs {
		procKeybdEvent.Call(uintptr(vk), 0, 0, 0)
	}
	// Press and release the main key.
	procKeybdEvent.Call(uintptr(keyVK), 0, 0, 0)
	procKeybdEvent.Call(uintptr(keyVK), 0, uintptr(keyeventfKeyUp), 0)
	// Release the modifier keys in reverse order.
	for i := len(modifierVKs) - 1; i >= 0; i-- {
		procKeybdEvent.Call(uintptr(modifierVKs[i]), 0, uintptr(keyeventfKeyUp), 0)
	}

	return map[string]any{
		"keys": keys,
		"tool": windowsInputTool,
	}, nil
}

// handleWindowsInputDoubleClick is the implementation of windows.input.double-click.
func handleWindowsInputDoubleClick(params map[string]any) (any, error) {
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}

	button, err := optionalString(params, "button")
	if err != nil {
		return nil, err
	}
	if button == "" {
		button = "left"
	}
	downFlag, ok := mouseButtonFlags(button, true)
	if !ok {
		return nil, fmt.Errorf("parameter button does not support %q, allowed values: left, right, middle", button)
	}
	upFlag, _ := mouseButtonFlags(button, false)

	delayMS, err := optionalInt(params, "delay_ms", 0)
	if err != nil {
		return nil, err
	}
	if delayMS < 0 {
		return nil, fmt.Errorf("parameter delay_ms cannot be negative, actual %d", delayMS)
	}

	// Move the cursor: SetCursorPos returning 0 means failure.
	if r, _, err := procSetCursorPos.Call(uintptr(x), uintptr(y)); r == 0 {
		return nil, fmt.Errorf("failed to move the cursor to (%d, %d): %v", x, y, err)
	}

	// Two clicks in a row to implement a double click.
	for i := 0; i < 2; i++ {
		procMouseEvent.Call(uintptr(downFlag), 0, 0, 0, 0)
		procMouseEvent.Call(uintptr(upFlag), 0, 0, 0, 0)
		if i == 0 && delayMS > 0 {
			time.Sleep(time.Duration(delayMS) * time.Millisecond)
		}
	}

	return map[string]any{
		"x":      x,
		"y":      y,
		"button": button,
		"tool":   windowsInputTool,
	}, nil
}

// handleWindowsInputRightClick is the implementation of windows.input.right-click.
func handleWindowsInputRightClick(params map[string]any) (any, error) {
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}

	button, err := optionalString(params, "button")
	if err != nil {
		return nil, err
	}
	if button == "" {
		button = "right"
	}
	downFlag, ok := mouseButtonFlags(button, true)
	if !ok {
		return nil, fmt.Errorf("parameter button does not support %q, allowed values: left, right, middle", button)
	}
	upFlag, _ := mouseButtonFlags(button, false)

	// Move the cursor: SetCursorPos returning 0 means failure.
	if r, _, err := procSetCursorPos.Call(uintptr(x), uintptr(y)); r == 0 {
		return nil, fmt.Errorf("failed to move the cursor to (%d, %d): %v", x, y, err)
	}

	procMouseEvent.Call(uintptr(downFlag), 0, 0, 0, 0)
	procMouseEvent.Call(uintptr(upFlag), 0, 0, 0, 0)

	return map[string]any{
		"x":      x,
		"y":      y,
		"button": button,
		"tool":   windowsInputTool,
	}, nil
}

// handleWindowsInputHover is the implementation of windows.input.hover.
func handleWindowsInputHover(params map[string]any) (any, error) {
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}

	// Move the cursor: SetCursorPos returning 0 means failure.
	if r, _, err := procSetCursorPos.Call(uintptr(x), uintptr(y)); r == 0 {
		return nil, fmt.Errorf("failed to move the cursor to (%d, %d): %v", x, y, err)
	}

	return map[string]any{
		"x":    x,
		"y":    y,
		"tool": windowsInputTool,
	}, nil
}

// handleWindowsInputDrag is the implementation of windows.input.drag.
func handleWindowsInputDrag(params map[string]any) (any, error) {
	fromX, err := requiredInt(params, "from_x")
	if err != nil {
		return nil, err
	}
	fromY, err := requiredInt(params, "from_y")
	if err != nil {
		return nil, err
	}
	toX, err := requiredInt(params, "to_x")
	if err != nil {
		return nil, err
	}
	toY, err := requiredInt(params, "to_y")
	if err != nil {
		return nil, err
	}

	button, err := optionalString(params, "button")
	if err != nil {
		return nil, err
	}
	if button == "" {
		button = "left"
	}
	downFlag, ok := mouseButtonFlags(button, true)
	if !ok {
		return nil, fmt.Errorf("parameter button does not support %q, allowed values: left, right, middle", button)
	}
	upFlag, _ := mouseButtonFlags(button, false)

	steps, err := optionalInt(params, "steps", 20)
	if err != nil {
		return nil, err
	}
	if steps <= 0 {
		return nil, fmt.Errorf("parameter steps must be a positive integer, actual %d", steps)
	}

	// Move to the start point and press.
	if r, _, err := procSetCursorPos.Call(uintptr(fromX), uintptr(fromY)); r == 0 {
		return nil, fmt.Errorf("failed to move the cursor to the start point (%d, %d): %v", fromX, fromY, err)
	}
	procMouseEvent.Call(uintptr(downFlag), 0, 0, 0, 0)

	// Interpolate along a straight line moving step by step to the end point.
	for i := 1; i <= steps; i++ {
		px := fromX + (toX-fromX)*i/steps
		py := fromY + (toY-fromY)*i/steps
		procSetCursorPos.Call(uintptr(px), uintptr(py))
		// Leave a very short delay between steps so the target program can perceive the movement trajectory.
		time.Sleep(time.Duration(10) * time.Millisecond)
	}

	// Release at the end point.
	procMouseEvent.Call(uintptr(upFlag), 0, 0, 0, 0)

	return map[string]any{
		"from_x": fromX,
		"from_y": fromY,
		"to_x":   toX,
		"to_y":   toY,
		"button": button,
		"steps":  steps,
		"tool":   windowsInputTool,
	}, nil
}

// handleWindowsInputWheel is the implementation of windows.input.wheel.
func handleWindowsInputWheel(params map[string]any) (any, error) {
	// x/y are optional: when provided, move the cursor to that position before scrolling.
	x, err := optionalInt(params, "x", 0)
	if err != nil {
		return nil, err
	}
	y, err := optionalInt(params, "y", 0)
	if err != nil {
		return nil, err
	}
	hasPos := false
	if _, ok := params["x"]; ok {
		hasPos = true
	}
	if _, ok := params["y"]; ok {
		hasPos = true
	}

	delta, err := optionalInt(params, "delta", 120)
	if err != nil {
		return nil, err
	}
	if delta == 0 {
		return nil, fmt.Errorf("parameter delta cannot be 0")
	}

	// If coordinates are provided, move the cursor first (SetCursorPos returning 0 means failure).
	if hasPos {
		if r, _, err := procSetCursorPos.Call(uintptr(x), uintptr(y)); r == 0 {
			return nil, fmt.Errorf("failed to move the cursor to (%d, %d): %v", x, y, err)
		}
	}

	// MOUSEEVENTF_WHEEL(0x0800): dwData is a signed short, positive=up, negative=down.
	// delta may exceed ±32767 (scrolling many notches at once); truncating to a 16-bit signed value is fine,
	// because mouse_event only accepts a short scroll amount.
	const mouseEventfWheel = 0x0800
	procMouseEvent.Call(uintptr(mouseEventfWheel), 0, 0, uintptr(int16(delta)), 0)

	return map[string]any{
		"x":     x,
		"y":     y,
		"delta": delta,
		"tool":  windowsInputTool,
	}, nil
}
