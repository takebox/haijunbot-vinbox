//go:build windows

package capability

import (
	"fmt"
	"sort"
	"strings"
	"sync"
	"syscall"
	"unsafe"
)

// This file implements the Windows platform window control capabilities (windows.window.*).
//
// Design trade-off: unlike the Linux side (linux_gui_linux.go calls the xdotool/wmctrl external commands),
// the Windows side directly calls the Win32 API of user32.dll via syscall. The benefits of doing so are:
//  1. Zero third-party dependencies (only the standard library syscall is used);
//  2. Zero cgo, preserving CGO_ENABLED=0 static linking and cross-compilation capability;
//  3. No dependency on any additional command-line tools installed on the user's machine.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success paths of each capability have not been verified end-to-end.
// The parameter validation and pure parsing logic have been extracted into the build-tag-free windows_gui_parse.go, which can be unit-tested on Linux.

// user32 is the lazy-load handle for user32.dll.
//
// syscall.NewLazyDLL is used rather than golang.org/x/sys/windows in order not to introduce any third-party dependency.
var user32 = syscall.NewLazyDLL("user32.dll")

var (
	procEnumWindows              = user32.NewProc("EnumWindows")
	procIsWindowVisible          = user32.NewProc("IsWindowVisible")
	procIsWindow                 = user32.NewProc("IsWindow")
	procGetWindowTextW           = user32.NewProc("GetWindowTextW")
	procGetWindowTextLengthW     = user32.NewProc("GetWindowTextLengthW")
	procGetWindowThreadProcessID = user32.NewProc("GetWindowThreadProcessId")
	procShowWindow               = user32.NewProc("ShowWindow")
	procSetForegroundWindow      = user32.NewProc("SetForegroundWindow")
	procPostMessageW             = user32.NewProc("PostMessageW")
	procGetWindowRect            = user32.NewProc("GetWindowRect")
	procMoveWindow               = user32.NewProc("MoveWindow")
	procGetForegroundWindow      = user32.NewProc("GetForegroundWindow")
)

// Win32 constants.
const (
	// swRestore corresponds to ShowWindow's SW_RESTORE: activate and restore the window (restore it if minimized).
	swRestore = 9

	// wmClose corresponds to PostMessage's WM_CLOSE: request the window to close (equivalent to the user clicking the close button).
	// Consistent with the Linux side's wmctrl -c semantics, it does not forcibly terminate the process.
	wmClose = 0x0010

	// vkMenu corresponds to the virtual key VK_MENU (i.e., the Alt key).
	// Used for keybd_event to simulate one Alt keypress, bypassing the Windows foreground lock policy (see focusWindow).
	// Note: procKeybdEvent and keyeventfKeyUp are already declared in windows_input_windows.go,
	// so they are reused directly here and not redefined.
	vkMenu = 0x12

	// windowsGUITool is the value of the tool field in the results returned by the capabilities in this file, for alignment with the Linux side.
	windowsGUITool = "user32.dll"
)

// windowsWindowInfo describes a top-level window.
//
// The field order is the JSON serialization order; window_id is represented as a string (such as "0x00010A2C"),
// keeping it consistent with the Linux side where window_id is a string.
type windowsWindowInfo struct {
	WindowID string `json:"window_id"`
	Title    string `json:"title"`
	PID      uint32 `json:"pid"`
	Visible  bool   `json:"visible"`
}

// windowsEnumState is the collection state of one EnumWindows traversal.
//
// Every call to enumerateWindows creates a new instance and passes its key in the
// windowsEnumStates registry through lparam. The reasons for doing so:
//  1. The callback and the caller share the same buffer, but the buffer is "private to each call",
//     so concurrent calls do not interfere with each other;
//  2. If a single package-level shared buffer were used instead, two concurrent calls would clear/append each other's results,
//     and even adding a lock could not fix it (a lock only guarantees mutual exclusion, not isolation of the two calls' data).
//
// The callback function itself is still a package-level variable: callbacks created by syscall.NewCallback have an upper limit
// (about 2000), so they cannot be created on every call.
type windowsEnumState struct {
	results []windowsWindowInfo
}

// windowsEnumStates maps lparam (uintptr) to the state object of this traversal.
//
// The reason for using a registry rather than stuffing the *windowsEnumState pointer directly into lparam: the latter requires
// doing a uintptr → unsafe.Pointer conversion in the callback, which go vet would flag as
// "possible misuse of unsafe.Pointer" (uintptr carries no object lifetime information,
// so the conversion is unsafe). With a registry, an integer is used as the key, completely avoiding that conversion.
//
// Protected by a mutex: the capability may be called concurrently by the gateway.
var (
	windowsEnumStatesMu sync.Mutex
	windowsEnumStates           = make(map[uintptr]*windowsEnumState)
	windowsEnumNextKey  uintptr = 1
)

// enumWindowsCallback is the callback function of EnumWindows.
//
// Defined as a package-level variable to ensure the Go callback is created only once for the process lifetime.
// lparam is the key of this traversal state in windowsEnumStates; the callback only does data collection,
// not blocking operations. A return value of 1 means continue enumerating, 0 means stop.
var enumWindowsCallback = syscall.NewCallback(func(hwnd uintptr, lparam uintptr) uintptr {
	windowsEnumStatesMu.Lock()
	state := windowsEnumStates[lparam]
	windowsEnumStatesMu.Unlock()
	if state == nil {
		// If the state cannot be found, the caller has reclaimed it; stop enumerating.
		return 0
	}

	// Only collect visible windows.
	if r, _, _ := procIsWindowVisible.Call(hwnd); r == 0 {
		return 1
	}

	title := getWindowText(hwnd)
	// Filter out windows without a title (a large number of system hidden windows and tool windows have empty titles).
	if title == "" {
		return 1
	}

	var pid uint32
	procGetWindowThreadProcessID.Call(hwnd, uintptr(unsafe.Pointer(&pid)))

	state.results = append(state.results, windowsWindowInfo{
		WindowID: formatWindowID(hwnd),
		Title:    title,
		PID:      pid,
		Visible:  true,
	})
	return 1
})

// getWindowText reads the window title.
//
// It gets the length first and then allocates the buffer, avoiding a fixed-length buffer truncating a long title.
// Note: GetWindowTextLengthW may return 0 for some windows, in which case an empty string is returned directly.
func getWindowText(hwnd uintptr) string {
	n, _, _ := procGetWindowTextLengthW.Call(hwnd)
	if n == 0 {
		return ""
	}
	// Reserve 1 UTF-16 unit for the trailing NUL.
	buf := make([]uint16, int(n)+1)
	procGetWindowTextW.Call(
		hwnd,
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(len(buf)),
	)
	return syscall.UTF16ToString(buf)
}

// formatWindowID formats an HWND as a string of the form "0x%08X".
func formatWindowID(hwnd uintptr) string {
	return fmt.Sprintf("0x%08X", hwnd)
}

// enumerateWindows enumerates all visible top-level windows with a title.
//
// The returned results are already sorted by title, ensuring a stable order across multiple calls (EnumWindows itself does not guarantee order).
// Each call uses an independent collection state, so concurrent calls do not interfere with each other.
func enumerateWindows() []windowsWindowInfo {
	state := &windowsEnumState{results: make([]windowsWindowInfo, 0, 64)}

	// Register this traversal state, taking a unique key as lparam.
	windowsEnumStatesMu.Lock()
	key := windowsEnumNextKey
	windowsEnumNextKey++
	windowsEnumStates[key] = state
	windowsEnumStatesMu.Unlock()

	// EnumWindows returns 0 when the traversal ends, at which point LastError is meaningless, so the return value and err are ignored.
	procEnumWindows.Call(enumWindowsCallback, key)

	// Deregister this traversal state to avoid unbounded growth of the registry.
	windowsEnumStatesMu.Lock()
	delete(windowsEnumStates, key)
	windowsEnumStatesMu.Unlock()

	out := make([]windowsWindowInfo, len(state.results))
	copy(out, state.results)

	sort.Slice(out, func(i, j int) bool {
		if out[i].Title != out[j].Title {
			return out[i].Title < out[j].Title
		}
		return out[i].WindowID < out[j].WindowID
	})
	return out
}

// findWindowByTitle finds the first window whose title matches the substring (case-insensitive).
func findWindowByTitle(title string) (windowsWindowInfo, bool) {
	needle := strings.ToLower(title)
	for _, w := range enumerateWindows() {
		if strings.Contains(strings.ToLower(w.Title), needle) {
			return w, true
		}
	}
	return windowsWindowInfo{}, false
}

// registerWindowsGUI registers the Windows window control capabilities.
func registerWindowsGUI(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.window.list",
		Description: "Lists the top-level windows on the Windows desktop. " +
			"Enumerated via user32.dll's EnumWindows, only returning visible windows with a title " +
			"(system hidden windows and tool windows with empty titles are filtered out). " +
			"No external commands or third-party dependencies required.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by window title substring, case-insensitive; when empty, all windows are returned.",
				},
			},
		},
		Handler: handleWindowsWindowList,
	})

	_ = reg.Register(Capability{
		Name: "windows.window.focus",
		Description: "Activates (focuses) the specified window. Locates the window via window_id or title; " +
			"first ShowWindow(SW_RESTORE) to restore (if minimized), then SetForegroundWindow to bring it to the front. " +
			"Note: Windows restricts foreground window switching; if the target process is not in the foreground and the system refuses to bring it forward, " +
			"the focused field in the returned result will faithfully reflect whether it actually succeeded.",
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
			},
		},
		Handler: handleWindowsWindowFocus,
	})

	_ = reg.Register(Capability{
		Name: "windows.window.close",
		Description: "Closes the specified window. Sends a WM_CLOSE message via PostMessage, " +
			"equivalent to the user clicking the window close button; the target program decides whether to exit " +
			"(it does not forcibly terminate the process). Consistent with the Linux side's wmctrl -c semantics.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x00010A2C or decimal.",
				},
			},
			"required": []string{"window_id"},
		},
		Handler: handleWindowsWindowClose,
	})

	_ = reg.Register(Capability{
		Name: "windows.window.get-pos",
		Description: "Gets the position and size of a window. " +
			"Reads the window's screen coordinates (top-left x/y and width/height) via GetWindowRect. " +
			"Locates the window via window_id or title. No external commands or third-party dependencies required.",
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
			},
		},
		Handler: handleWindowsWindowGetPos,
	})

	_ = reg.Register(Capability{
		Name: "windows.window.move",
		Description: "Moves a window to the specified screen coordinates. " +
			"Moves the window's top-left corner to the specified x/y via MoveWindow, optionally resizing with width/height. " +
			"Locates the window via window_id or title. No external commands or third-party dependencies required.",
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
				"x": map[string]any{
					"type":        "integer",
					"description": "Target top-left x coordinate (pixels); 0 is allowed.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Target top-left y coordinate (pixels); 0 is allowed.",
				},
				"width": map[string]any{
					"type":        "integer",
					"description": "Optional. Target width (pixels); keeps the original width when omitted.",
				},
				"height": map[string]any{
					"type":        "integer",
					"description": "Optional. Target height (pixels); keeps the original height when omitted.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleWindowsWindowMove,
	})

	_ = reg.Register(Capability{
		Name: "windows.window.resize",
		Description: "Resizes a window. " +
			"Adjusts the window to the specified width/height via MoveWindow, optionally moving the position with x/y. " +
			"Locates the window via window_id or title. No external commands or third-party dependencies required.",
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
				"width": map[string]any{
					"type":        "integer",
					"description": "Target width (pixels), must be a positive integer.",
				},
				"height": map[string]any{
					"type":        "integer",
					"description": "Target height (pixels), must be a positive integer.",
				},
				"x": map[string]any{
					"type":        "integer",
					"description": "Optional. Target top-left x coordinate (pixels); keeps the original position when omitted.",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Optional. Target top-left y coordinate (pixels); keeps the original position when omitted.",
				},
			},
			"required": []string{"width", "height"},
		},
		Handler: handleWindowsWindowResize,
	})
}

// handleWindowsWindowList is the implementation of windows.window.list.
func handleWindowsWindowList(params map[string]any) (any, error) {
	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}

	windows := enumerateWindows()

	if filter != "" {
		needle := strings.ToLower(filter)
		filtered := make([]windowsWindowInfo, 0, len(windows))
		for _, w := range windows {
			if strings.Contains(strings.ToLower(w.Title), needle) {
				filtered = append(filtered, w)
			}
		}
		windows = filtered
	}

	return map[string]any{
		"windows": windows,
		"count":   len(windows),
		"tool":    windowsGUITool,
	}, nil
}

// handleWindowsWindowFocus is the implementation of windows.window.focus.
func handleWindowsWindowFocus(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	if windowID == "" && title == "" {
		return nil, fmt.Errorf("at least one of the parameters window_id and title must be provided")
	}

	var hwnd uintptr
	var resolvedTitle string

	if windowID != "" {
		hwnd, err = parseWindowID(windowID)
		if err != nil {
			return nil, err
		}
		if r, _, _ := procIsWindow.Call(hwnd); r == 0 {
			return nil, fmt.Errorf("window %s does not exist or has been closed", windowID)
		}
		resolvedTitle = getWindowText(hwnd)
	} else {
		info, ok := findWindowByTitle(title)
		if !ok {
			return nil, fmt.Errorf("no window with a title matching %q was found", title)
		}
		hwnd, err = parseWindowID(info.WindowID)
		if err != nil {
			return nil, err
		}
		resolvedTitle = info.Title
	}

	// SW_RESTORE: restore the window if it is minimized; no side effect on normal windows.
	procShowWindow.Call(hwnd, swRestore)

	// Foreground switching is restricted by the Windows foreground lock policy; focusWindow first tries directly,
	// and after a failure simulates one Alt keypress to gain foreground eligibility and retries (see that function's comment for details).
	focused := focusWindow(hwnd)

	return map[string]any{
		"window_id": formatWindowID(hwnd),
		"title":     resolvedTitle,
		"focused":   focused,
		"tool":      windowsGUITool,
	}, nil
}

// focusWindow brings the window to the foreground and returns whether it actually succeeded.
//
// Why "simulate one Alt keypress" is needed
// ==============================
// Windows has a foreground lock policy: only the **process that currently owns the foreground**, or
// a process that "has recently received user input", can successfully call SetForegroundWindow. The daemon runs in the
// background, and a direct call would be silently rejected by the system — on real hardware, SetForegroundWindow returns False
// and the foreground window does not change (GetForegroundWindow is still the original window).
//
// The standard bypass is to first use keybd_event to simulate one keypress (here the Alt down + up),
// giving this process "recent user input" eligibility, after which SetForegroundWindow succeeds.
// On real hardware: after adding this step, setfg=True and GetForegroundWindow confirms the foreground has switched.
// (Control experiment: without simulating the keypress, setfg=False; AttachThreadInput followed by the call is also still False.)
//
// The reason for choosing Alt: Alt pressed and released alone produces no character input and does not trigger a menu (a menu requires
// Alt+letter), so the side effect is minimal; and it does not pollute the clipboard or input method state.
//
// Note: simulating a keypress has a slight global side effect (it briefly changes the keyboard modifier key state), so it is only used
// after the first attempt fails, to avoid unnecessary interference.
func focusWindow(hwnd uintptr) bool {
	// First try directly: if this process already has foreground eligibility (e.g., the user just interacted with the daemon), no keypress simulation is needed.
	if r, _, _ := procSetForegroundWindow.Call(hwnd); r != 0 {
		return true
	}

	// Simulate one Alt down + up, gain foreground eligibility, and retry.
	procKeybdEvent.Call(vkMenu, 0, 0, 0)
	procKeybdEvent.Call(vkMenu, 0, keyeventfKeyUp, 0)

	r, _, _ := procSetForegroundWindow.Call(hwnd)
	return r != 0
}

// handleWindowsWindowClose is the implementation of windows.window.close.
func handleWindowsWindowClose(params map[string]any) (any, error) {
	windowID, err := requiredString(params, "window_id")
	if err != nil {
		return nil, err
	}

	hwnd, err := parseWindowID(windowID)
	if err != nil {
		return nil, err
	}
	if r, _, _ := procIsWindow.Call(hwnd); r == 0 {
		return nil, fmt.Errorf("window %s does not exist or has been closed", windowID)
	}

	title := getWindowText(hwnd)

	// PostMessage delivers WM_CLOSE asynchronously, without blocking to wait for the window to finish processing.
	r, _, err := procPostMessageW.Call(hwnd, wmClose, 0, 0)
	if r == 0 {
		if err != nil && err != syscall.Errno(0) {
			return nil, fmt.Errorf("failed to send WM_CLOSE to window %s: %v", windowID, err)
		}
		return nil, fmt.Errorf("failed to send WM_CLOSE to window %s", windowID)
	}

	return map[string]any{
		"window_id": formatWindowID(hwnd),
		"title":     title,
		"closed":    true,
		"tool":      windowsGUITool,
	}, nil
}

// parseWindowID parses a string-form window ID into an HWND.
//
// The pure parsing logic is implemented in parseWindowIDString in windows_gui_parse.go (no build tag,
// unit-testable on Linux); this function is only a thin wrapper down to uintptr.
func parseWindowID(s string) (uintptr, error) {
	v, err := parseWindowIDString(s)
	if err != nil {
		return 0, err
	}
	return uintptr(v), nil
}

// windowsRect corresponds to the Win32 RECT structure (the output of GetWindowRect).
type windowsRect struct {
	Left   int32
	Top    int32
	Right  int32
	Bottom int32
}

// resolveWindowHandle resolves a window handle from window_id or title.
//
// It reuses the location logic of focus/close: window_id takes priority (directly verified for existence),
// otherwise look up by title substring. Returns the resolved HWND and the window title.
func resolveWindowHandle(windowID, title string) (uintptr, string, error) {
	if windowID == "" && title == "" {
		return 0, "", fmt.Errorf("at least one of the parameters window_id and title must be provided")
	}

	var hwnd uintptr
	var resolvedTitle string
	var err error

	if windowID != "" {
		hwnd, err = parseWindowID(windowID)
		if err != nil {
			return 0, "", err
		}
		if r, _, _ := procIsWindow.Call(hwnd); r == 0 {
			return 0, "", fmt.Errorf("window %s does not exist or has been closed", windowID)
		}
		resolvedTitle = getWindowText(hwnd)
	} else {
		info, ok := findWindowByTitle(title)
		if !ok {
			return 0, "", fmt.Errorf("no window with a title matching %q was found", title)
		}
		hwnd, err = parseWindowID(info.WindowID)
		if err != nil {
			return 0, "", err
		}
		resolvedTitle = info.Title
	}

	return hwnd, resolvedTitle, nil
}

// handleWindowsWindowGetPos is the implementation of windows.window.get-pos.
func handleWindowsWindowGetPos(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}

	hwnd, resolvedTitle, err := resolveWindowHandle(windowID, title)
	if err != nil {
		return nil, err
	}

	var rect windowsRect
	if r, _, _ := procGetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&rect))); r == 0 {
		return nil, fmt.Errorf("failed to get the position of window %s", formatWindowID(hwnd))
	}

	return map[string]any{
		"window_id": formatWindowID(hwnd),
		"title":     resolvedTitle,
		"x":         int(rect.Left),
		"y":         int(rect.Top),
		"width":     int(rect.Right - rect.Left),
		"height":    int(rect.Bottom - rect.Top),
		"tool":      windowsGUITool,
	}, nil
}

// handleWindowsWindowMove is the implementation of windows.window.move.
func handleWindowsWindowMove(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}
	width, err := optionalInt(params, "width", 0)
	if err != nil {
		return nil, err
	}
	height, err := optionalInt(params, "height", 0)
	if err != nil {
		return nil, err
	}

	hwnd, resolvedTitle, err := resolveWindowHandle(windowID, title)
	if err != nil {
		return nil, err
	}

	// Keep the original size when width/height are not provided (read the current rect).
	if width <= 0 || height <= 0 {
		var rect windowsRect
		if r, _, _ := procGetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&rect))); r == 0 {
			return nil, fmt.Errorf("failed to get the position of window %s", formatWindowID(hwnd))
		}
		if width <= 0 {
			width = int(rect.Right - rect.Left)
		}
		if height <= 0 {
			height = int(rect.Bottom - rect.Top)
		}
	}

	// MoveWindow(hWnd, x, y, nWidth, nHeight, bRepaint).
	if r, _, _ := procMoveWindow.Call(hwnd, uintptr(x), uintptr(y), uintptr(width), uintptr(height), 1); r == 0 {
		return nil, fmt.Errorf("failed to move window %s", formatWindowID(hwnd))
	}

	return map[string]any{
		"window_id": formatWindowID(hwnd),
		"title":     resolvedTitle,
		"x":         x,
		"y":         y,
		"width":     width,
		"height":    height,
		"moved":     true,
		"tool":      windowsGUITool,
	}, nil
}

// handleWindowsWindowResize is the implementation of windows.window.resize.
func handleWindowsWindowResize(params map[string]any) (any, error) {
	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	width, err := requiredInt(params, "width")
	if err != nil {
		return nil, err
	}
	height, err := requiredInt(params, "height")
	if err != nil {
		return nil, err
	}
	if width <= 0 || height <= 0 {
		return nil, fmt.Errorf("the parameters width and height must be positive integers, actual %d x %d", width, height)
	}
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

	hwnd, resolvedTitle, err := resolveWindowHandle(windowID, title)
	if err != nil {
		return nil, err
	}

	// Keep the original position when x/y are not provided (read the current rect).
	if !hasPos {
		var rect windowsRect
		if r, _, _ := procGetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&rect))); r == 0 {
			return nil, fmt.Errorf("failed to get the position of window %s", formatWindowID(hwnd))
		}
		x = int(rect.Left)
		y = int(rect.Top)
	}

	if r, _, _ := procMoveWindow.Call(hwnd, uintptr(x), uintptr(y), uintptr(width), uintptr(height), 1); r == 0 {
		return nil, fmt.Errorf("failed to resize window %s", formatWindowID(hwnd))
	}

	return map[string]any{
		"window_id": formatWindowID(hwnd),
		"title":     resolvedTitle,
		"x":         x,
		"y":         y,
		"width":     width,
		"height":    height,
		"resized":   true,
		"tool":      windowsGUITool,
	}, nil
}
