//go:build windows

package capability

// This file implements the Windows implementation of "open the local browser extension page".
//
// Purpose: after the daemon automatically syncs the browser extension files (overwriting ~/.haijunbot/browser_extension),
// the user needs to go to the browser's extensions page and click "refresh" (if installed) or "load unpacked extension"
// (if not installed) for it to take effect. Previously this could only be done manually by focusing the window -> Ctrl+L -> entering the URL -> Enter;
// this function automates that step.
//
// Browser selection strategy (confirmed by the user):
//   - Edge / Chrome running locally: open each one's own extensions page (the extension may be installed in either);
//   - neither running but installed: start the installed browser and open the extensions page;
//   - neither installed: return an empty list, leaving it to the caller to decide whether to log; not treated as an error.
//
// Implementation points (all via user32.dll syscall, reusing the existing window enumeration/focus and key simulation in
// windows_gui_windows.go and windows_input_windows.go, with zero third-party dependencies and zero cgo):
//   - use tasklist (reusing runWindowsProcessCommand) to determine whether the browser is running. Note that
//     msedgewebview2.exe is the WebView2 runtime rather than the browser itself and must be excluded, otherwise it would be
//     misjudged as "running" when the user has not opened Edge;
//   - use EnumWindows (reusing enumerateWindows) to enumerate top-level windows, locating the target window by "the process name
//     the window belongs to" and "the title suffix";
//   - use keybd_event / SendInput (reusing focusWindow, sendKeyCombo, sendUnicodeText) to
//     simulate Ctrl+L -> URL -> Enter.
//
// Why can't the URL be passed as a command-line argument to the browser exe: edge:// and chrome:// are browser-internal
// schemes, and Edge/Chrome refuse to open such addresses directly from the command line for security reasons; in practice they silently fall back to
// a "new tab" and the extensions page simply does not open (ordinary https URLs work fine).
//
// Why can't key simulation be done directly on the "existing browser window": the user may be using a PWA (installed
// web app) window, which has no address bar, so Ctrl+L is intercepted by the web page itself and the URL gets typed into the page's
// input field (as measured). Therefore it must first locate a "normal browser window" (whose title ends with the browser name,
// such as "… - Microsoft Edge"); if there is none, open a new one with --new-window.
//
// Why not use PowerShell's SendKeys: as measured, SendKeys is ineffective on the target window in this context (a PowerShell
// child process started non-interactively by the daemon), whereas keybd_event/SendInput works. So it was changed to a pure
// Go implementation, also saving one PowerShell process overhead.

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// browserWindowWaitTicks is the number of polling attempts to wait for the browser window to appear, at 500ms intervals.
// A cold-started browser usually shows its main window within 1~3 seconds; 20 attempts (10 seconds) is enough to cover slow scenarios.
const browserWindowWaitTicks = 20

// browserWindowPollInterval is the interval for polling for the window to appear.
const browserWindowPollInterval = 500 * time.Millisecond

// browserFocusSettleDelay is the wait time after focusing the window and before sending keys,
// letting the window finish foreground switching and the address bar become ready.
const browserFocusSettleDelay = 800 * time.Millisecond

// browserKeyDelay is the wait time between keystrokes, to avoid the browser not having time to process them.
const browserKeyDelay = 500 * time.Millisecond

// browserNavigateSettleDelay is the wait time after Enter for the page to load (only used to read the title for troubleshooting).
const browserNavigateSettleDelay = 2 * time.Second

// browserTarget describes an openable browser and its extensions page address.
type browserTarget struct {
	// name is the human-readable name used in logs and return values, such as "Edge".
	name string
	// processName is the process name in tasklist (lowercase), used to determine whether it is running.
	processName string
	// extensionsURL is that browser's extensions page address.
	extensionsURL string
	// windowTitleSuffix is the ending marker of a "normal browser window" title.
	//
	// A normal window title looks like "Extensions - Personal - Microsoft Edge" (ending with "Edge"),
	// whereas a PWA window title is the app name (such as "HaijunBot Web Gateway - HaijunBot AI Assistant"),
	// which does not end with the browser name, so this can be used to exclude PWA windows.
	windowTitleSuffix string
	// installPaths are candidate installation paths, ordered by priority; used for "start when not running".
	installPaths []string
}

// browserTargets is the list of browsers that support automatically opening the extensions page.
//
// The order is the priority: only used for the startup choice when "none are running" (take the first installed one in order).
var browserTargets = []browserTarget{
	{
		name:              "Edge",
		processName:       "msedge.exe",
		extensionsURL:     "edge://extensions",
		windowTitleSuffix: "Edge",
		installPaths: []string{
			`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
			`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
		},
	},
	{
		name:              "Chrome",
		processName:       "chrome.exe",
		extensionsURL:     "chrome://extensions",
		windowTitleSuffix: "Chrome",
		installPaths: []string{
			`C:\Program Files\Google\Chrome\Application\chrome.exe`,
			`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`,
		},
	},
}

// OpenBrowserExtensionsPage opens the local browser's extensions page and returns the list of opened browser names.
//
// The selection logic is in the file header comment. The return value is used for logs and test assertions; the caller should not treat
// "an empty list" as an error (it may simply mean no supported browser is installed on this machine).
func OpenBrowserExtensionsPage() ([]string, error) {
	running, err := runningBrowserProcessNames()
	if err != nil {
		// A process enumeration failure is not fatal: fall back to "start by installation status", still opening the extensions page as much as possible.
		running = map[string]bool{}
	}

	var opened []string
	var lastErr error

	// First round: open the extensions page for every "running" browser (open all of them, confirmed by the user).
	// The browser is already running, so no cold start is needed; if it only has PWA windows, it will open a --new-window itself.
	for _, t := range browserTargets {
		if !running[t.processName] {
			continue
		}
		if err := openExtensionsPage(t, ""); err != nil {
			lastErr = err
			continue
		}
		opened = append(opened, t.name)
	}
	if len(opened) > 0 {
		return opened, nil
	}

	// Second round: none are running, so cold-start the first "installed" browser and open the extensions page.
	for _, t := range browserTargets {
		exe, ok := firstExistingPath(t.installPaths)
		if !ok {
			continue
		}
		if err := openExtensionsPage(t, exe); err != nil {
			lastErr = err
			continue
		}
		opened = append(opened, t.name)
		// Start only one: when no browser is open on this machine, opening too many windows is more of a disturbance to the user.
		break
	}
	if len(opened) > 0 {
		return opened, nil
	}

	if lastErr != nil {
		return nil, lastErr
	}
	// No supported browser is installed on this machine: not an error, leaving it to the caller to decide whether to log.
	return nil, nil
}

// openExtensionsPage opens the specified browser's extensions page.
//
// A non-empty exePath means the browser is not running (or is running but a new normal window is needed), used for --new-window;
// when empty, it is resolved from the installed paths or from a running process.
func openExtensionsPage(t browserTarget, exePath string) error {
	hwnd, err := ensureBrowserContentWindow(t, exePath)
	if err != nil {
		return fmt.Errorf("failed to open the %s extensions page: %w", t.name, err)
	}

	// Focus the window (reusing the same implementation as windows.window.focus).
	if !focusWindow(hwnd) {
		return fmt.Errorf("failed to focus the %s window", t.name)
	}
	time.Sleep(browserFocusSettleDelay)

	// Ctrl+L focuses the address bar -> type the extensions page URL -> Enter.
	if err := sendKeyCombo("ctrl+l"); err != nil {
		return fmt.Errorf("failed to send Ctrl+L: %w", err)
	}
	time.Sleep(browserKeyDelay)
	sendUnicodeText(t.extensionsURL)
	time.Sleep(browserKeyDelay)
	if err := sendKeyCombo("Return"); err != nil {
		return fmt.Errorf("failed to send Enter: %w", err)
	}

	// Wait for the page to load before reading the title, only for logging/troubleshooting.
	time.Sleep(browserNavigateSettleDelay)
	_ = getWindowText(hwnd)
	return nil
}

// ensureBrowserContentWindow returns the handle of a "normal browser window".
//
// It prefers to reuse an existing normal window (whose title ends with windowTitleSuffix and which belongs to that browser process);
// if there is none (for example, the user only has PWA windows open), it opens a new one with --new-window and waits for it to appear.
func ensureBrowserContentWindow(t browserTarget, exePath string) (uintptr, error) {
	browserPIDs := browserProcessIDs(t.processName)

	if hwnd, ok := findContentWindow(t, browserPIDs); ok {
		return hwnd, nil
	}

	// A new normal window is needed: first resolve the executable path.
	exe := exePath
	if exe == "" {
		exe = runningProcessPath(t.processName)
	}
	if exe == "" {
		if p, ok := firstExistingPath(t.installPaths); ok {
			exe = p
		}
	}
	if exe == "" {
		return 0, fmt.Errorf("the %s executable was not found", t.name)
	}

	before := windowIDsOfPIDs(browserPIDs)
	cmd := exec.Command(exe, "--new-window")
	cmd.SysProcAttr = hideWindow()
	if err := cmd.Start(); err != nil {
		return 0, fmt.Errorf("failed to start %s: %w", t.name, err)
	}
	// Do not wait for the process to exit (the browser forwards the command to an existing instance and returns immediately).
	go func() { _ = cmd.Wait() }()

	for i := 0; i < browserWindowWaitTicks; i++ {
		time.Sleep(browserWindowPollInterval)
		// The set of processes may change (the new window is created by an existing instance), so take it again.
		pids := browserProcessIDs(t.processName)
		if hwnd, ok := findNewContentWindow(t, pids, before); ok {
			return hwnd, nil
		}
	}
	return 0, fmt.Errorf("timed out waiting for the %s normal window", t.name)
}

// findContentWindow finds the first "normal browser window" among the windows of the given process set.
func findContentWindow(t browserTarget, pids map[uint32]bool) (uintptr, bool) {
	for _, w := range enumerateWindows() {
		if !pids[w.PID] {
			continue
		}
		if isContentWindowTitle(t, w.Title) {
			if hwnd, err := parseWindowID(w.WindowID); err == nil {
				return hwnd, true
			}
		}
	}
	return 0, false
}

// findNewContentWindow finds a new normal browser window "not in before".
func findNewContentWindow(t browserTarget, pids map[uint32]bool, before map[uintptr]bool) (uintptr, bool) {
	for _, w := range enumerateWindows() {
		if !pids[w.PID] {
			continue
		}
		if !isContentWindowTitle(t, w.Title) {
			continue
		}
		hwnd, err := parseWindowID(w.WindowID)
		if err != nil {
			continue
		}
		if before[hwnd] {
			continue
		}
		return hwnd, true
	}
	return 0, false
}

// isContentWindowTitle determines whether a window title belongs to a "normal browser window".
//
// A normal window title ends with the browser name (such as "… - Microsoft Edge"); a PWA window title is the app name and
// will not match. Suffix matching is used rather than full matching: in Edge's window title there is a zero-width space
// (U+200B, an anti-counterfeiting marker) between "Microsoft Edge", so a full string match would fail.
func isContentWindowTitle(t browserTarget, title string) bool {
	return strings.HasSuffix(title, t.windowTitleSuffix)
}

// windowIDsOfPIDs returns the set of handles of all currently visible windows of the given process set.
func windowIDsOfPIDs(pids map[uint32]bool) map[uintptr]bool {
	result := map[uintptr]bool{}
	for _, w := range enumerateWindows() {
		if !pids[w.PID] {
			continue
		}
		if hwnd, err := parseWindowID(w.WindowID); err == nil {
			result[hwnd] = true
		}
	}
	return result
}

// browserProcessIDs returns the set of PIDs corresponding to the specified browser process name (such as "msedge.exe").
//
// The data comes from tasklist (the same source as runningBrowserProcessNames).
func browserProcessIDs(processName string) map[uint32]bool {
	result := map[uint32]bool{}
	out, err := runWindowsProcessCommand("tasklist", "/FO", "CSV", "/NH")
	if err != nil {
		return result
	}
	want := strings.ToLower(strings.TrimSpace(processName))
	for _, p := range parseWindowsTasklistCSV(out) {
		name := strings.ToLower(strings.TrimSpace(fmt.Sprint(p["name"])))
		if name != want {
			continue
		}
		pid, ok := p["pid"].(int)
		if !ok {
			continue
		}
		result[uint32(pid)] = true
	}
	return result
}

// runningProcessPath returns the executable path of the specified running process; it returns an empty string when it cannot be obtained.
//
// It uses PowerShell's Get-Process to get Path: the Go standard library has no interface to get a path across processes,
// while the daemon runs with administrator privileges and can read the Path of other processes.
func runningProcessPath(processName string) string {
	// Remove the .exe suffix: Get-Process's -Name uses the name without the suffix.
	name := strings.TrimSuffix(processName, ".exe")
	script := "$p=Get-Process -Name " + encodePowerShellText(name) +
		" -ErrorAction SilentlyContinue | Select-Object -First 1; if($p){ Write-Output $p.Path }"
	out, err := runWindowsPowerShellCommand(script, 15*time.Second)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(out)
}

// runningBrowserProcessNames returns the set of running browser process names (lowercase).
//
// The data comes from tasklist (the same source as windows.process.list). Note the exclusion of
// msedgewebview2.exe: it is the WebView2 runtime, loaded by many desktop programs (including some of this project's dependencies),
// but it does not mean the user has opened Edge.
func runningBrowserProcessNames() (map[string]bool, error) {
	out, err := runWindowsProcessCommand("tasklist", "/FO", "CSV", "/NH")
	if err != nil {
		return nil, err
	}

	result := map[string]bool{}
	for _, p := range parseWindowsTasklistCSV(out) {
		name := strings.ToLower(strings.TrimSpace(fmt.Sprint(p["name"])))
		if name == "" {
			continue
		}
		// Exclude the WebView2 runtime to avoid misjudging that Edge is running.
		if name == "msedgewebview2.exe" {
			continue
		}
		result[name] = true
	}
	return result, nil
}

// firstExistingPath returns the first existing file among the candidate paths; when none exist it returns ("", false).
func firstExistingPath(paths []string) (string, bool) {
	for _, p := range paths {
		if info, err := os.Stat(p); err == nil && !info.IsDir() {
			return p, true
		}
	}
	return "", false
}

// sendKeyCombo sends a key combination (such as "ctrl+l", "Return").
//
// It reuses the parsing and sending logic of windows.input.keys (parseWindowsKeyCombo + virtualKeyCode
// + keybd_event) to ensure consistent behavior.
func sendKeyCombo(keys string) error {
	modifiers, keyName, err := parseWindowsKeyCombo(keys)
	if err != nil {
		return err
	}
	keyVK, ok := virtualKeyCode(keyName)
	if !ok {
		return fmt.Errorf("unsupported key name %q", keyName)
	}
	modifierVKs := make([]uint16, 0, len(modifiers))
	for _, m := range modifiers {
		vk, ok := virtualKeyCode(m)
		if !ok {
			return fmt.Errorf("unsupported modifier key %q", m)
		}
		modifierVKs = append(modifierVKs, vk)
	}

	for _, vk := range modifierVKs {
		procKeybdEvent.Call(uintptr(vk), 0, 0, 0)
	}
	procKeybdEvent.Call(uintptr(keyVK), 0, 0, 0)
	procKeybdEvent.Call(uintptr(keyVK), 0, uintptr(keyeventfKeyUp), 0)
	for i := len(modifierVKs) - 1; i >= 0; i-- {
		procKeybdEvent.Call(uintptr(modifierVKs[i]), 0, uintptr(keyeventfKeyUp), 0)
	}
	return nil
}

// sendUnicodeText sends text character by character (including non-ASCII).
//
// It reuses the SendInput + KEYEVENTF_UNICODE implementation of windows.input.type.
func sendUnicodeText(text string) {
	const keyeventfUnicode = 0x0004
	for _, r := range text {
		if r > 0xFFFF {
			hi, lo := utf16SurrogatePair(r)
			sendUnicodeChar(hi, keyeventfUnicode)
			sendUnicodeChar(lo, keyeventfUnicode)
		} else {
			sendUnicodeChar(uint16(r), keyeventfUnicode)
		}
	}
}
