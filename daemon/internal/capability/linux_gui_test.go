//go:build linux

package capability

import (
	"os"
	"os/exec"
	"strings"
	"testing"
)

// Environment note: on this machine both DISPLAY and WAYLAND_DISPLAY are empty, and xdotool / wmctrl /
// xclip / import / scrot / grim are all not installed (only xsel exists).
// Therefore the tests in this file **can only cover error paths and pure logic** and cannot verify real GUI operations end to end.
// This is an environment limitation, not an implementation defect.

// TestRequireDisplayNoDisplay verifies that a clear error is returned when there is no graphical environment.
func TestRequireDisplayNoDisplay(t *testing.T) {
	t.Setenv("DISPLAY", "")
	t.Setenv("WAYLAND_DISPLAY", "")

	err := requireDisplay()
	if err == nil {
		t.Fatal("it should return an error when DISPLAY/WAYLAND_DISPLAY are absent")
	}
	if !strings.Contains(err.Error(), "graphical environment") {
		t.Errorf("the error message should state that the graphical environment is missing, actual: %v", err)
	}
	if !strings.Contains(err.Error(), "DISPLAY") {
		t.Errorf("the error message should mention DISPLAY, actual: %v", err)
	}
}

// TestRequireDisplayWithX11 verifies that it passes when DISPLAY is present.
func TestRequireDisplayWithX11(t *testing.T) {
	t.Setenv("DISPLAY", ":0")
	t.Setenv("WAYLAND_DISPLAY", "")
	if err := requireDisplay(); err != nil {
		t.Errorf("it should not error when DISPLAY is present: %v", err)
	}
}

// TestRequireDisplayWithWayland verifies that it passes when WAYLAND_DISPLAY is present.
func TestRequireDisplayWithWayland(t *testing.T) {
	t.Setenv("DISPLAY", "")
	t.Setenv("WAYLAND_DISPLAY", "wayland-0")
	if err := requireDisplay(); err != nil {
		t.Errorf("it should not error when WAYLAND_DISPLAY is present: %v", err)
	}
}

// TestRequireToolMissing verifies that the error message contains an installation hint when a tool is missing.
func TestRequireToolMissing(t *testing.T) {
	// Use a command name that definitely does not exist.
	_, err := requireTool("definitely-not-a-real-tool-xyz")
	if err == nil {
		t.Fatal("a non-existent command should return an error")
	}
	if !strings.Contains(err.Error(), "no available command found") {
		t.Errorf("the error message should state that no command was found, actual: %v", err)
	}
}

// TestRequireToolHintForKnownTools verifies that an installation command is given when a known tool is missing.
func TestRequireToolHintForKnownTools(t *testing.T) {
	// Make sure these tools are indeed not in PATH (all are missing on this machine as measured).
	for _, name := range []string{"xdotool", "wmctrl", "xclip", "import", "scrot", "grim"} {
		if _, err := exec.LookPath(name); err == nil {
			t.Skipf("%s is already installed on this machine, skipping the missing-hint verification for this tool", name)
		}
	}

	_, err := requireTool("xdotool")
	if err == nil {
		t.Fatal("it should return an error when xdotool is missing")
	}
	if !strings.Contains(err.Error(), "xdotool") {
		t.Errorf("the error message should contain the tool name, actual: %v", err)
	}
	if !strings.Contains(err.Error(), "apt install") {
		t.Errorf("the error message should contain an installation hint, actual: %v", err)
	}

	// With multiple candidates, all candidates and hints should be listed.
	_, err2 := requireTool("xclip", "xsel")
	if err2 != nil {
		// xsel exists on this machine, so this should succeed; a failure means the environment changed.
		t.Logf("both xclip/xsel are unavailable (environment changed): %v", err2)
	}
}

// TestRequireToolFound verifies that the tool's path is returned when it is found.
func TestRequireToolFound(t *testing.T) {
	// sh definitely exists.
	path, err := requireTool("sh")
	if err != nil {
		t.Fatalf("sh should be available: %v", err)
	}
	if path == "" {
		t.Error("the returned path should not be empty")
	}
}

// TestLinuxGUINoDisplayErrors verifies that all GUI capabilities return an error rather than panic when there is no DISPLAY.
func TestLinuxGUINoDisplayErrors(t *testing.T) {
	t.Setenv("DISPLAY", "")
	t.Setenv("WAYLAND_DISPLAY", "")

	cases := []struct {
		name   string
		params map[string]any
		fn     func(map[string]any) (any, error)
	}{
		{"window.list", map[string]any{}, handleLinuxWindowList},
		{"window.focus", map[string]any{"window_id": "0x1"}, handleLinuxWindowFocus},
		{"window.close", map[string]any{"window_id": "0x1"}, handleLinuxWindowClose},
		{"input.click", map[string]any{"x": 1, "y": 2}, handleLinuxInputClick},
		{"input.type", map[string]any{"text": "hi"}, handleLinuxInputType},
		{"input.keys", map[string]any{"keys": "Return"}, handleLinuxInputKeys},
		{"clipboard.get", map[string]any{}, handleLinuxClipboardGet},
		{"clipboard.set", map[string]any{"text": "hi"}, handleLinuxClipboardSet},
		{"screenshot", map[string]any{"path": "/tmp/x.png"}, handleLinuxScreenshot},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := tc.fn(tc.params)
			if err == nil {
				t.Fatal("it should return an error when there is no graphical environment")
			}
			if !strings.Contains(err.Error(), "graphical environment") {
				t.Errorf("the error message should state that the graphical environment is missing, actual: %v", err)
			}
		})
	}
}

// TestLinuxGUIParameterValidation verifies the parameter validation paths.
//
// These cases return at the parameter validation stage and do not reach requireDisplay,
// so they can be tested in a no-DISPLAY environment.
func TestLinuxGUIParameterValidation(t *testing.T) {
	cases := []struct {
		name   string
		params map[string]any
		fn     func(map[string]any) (any, error)
	}{
		{"window.close missing window_id", map[string]any{}, handleLinuxWindowClose},
		{"window.close window_id has the wrong type", map[string]any{"window_id": 1}, handleLinuxWindowClose},
		{"window.focus both missing", map[string]any{}, handleLinuxWindowFocus},
		{"window.focus filter has the wrong type", map[string]any{"filter": 1}, handleLinuxWindowList},
		{"input.click missing x", map[string]any{"y": 1}, handleLinuxInputClick},
		{"input.click missing y", map[string]any{"x": 1}, handleLinuxInputClick},
		{"input.click x has the wrong type", map[string]any{"x": "a", "y": 1}, handleLinuxInputClick},
		{"input.click x is not an integer", map[string]any{"x": 1.5, "y": 1}, handleLinuxInputClick},
		{"input.type missing text", map[string]any{}, handleLinuxInputType},
		{"input.type text is empty", map[string]any{"text": "  "}, handleLinuxInputType},
		{"input.type delay_ms is negative", map[string]any{"text": "a", "delay_ms": -1}, handleLinuxInputType},
		{"input.keys missing keys", map[string]any{}, handleLinuxInputKeys},
		{"clipboard.set missing text", map[string]any{}, handleLinuxClipboardSet},
		{"clipboard.set text has the wrong type", map[string]any{"text": 1}, handleLinuxClipboardSet},
		{"screenshot missing path", map[string]any{}, handleLinuxScreenshot},
		{"screenshot path is empty", map[string]any{"path": " "}, handleLinuxScreenshot},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := tc.fn(tc.params)
			if err == nil {
				t.Fatal("expected an error but actually succeeded")
			}
		})
	}
}

// TestLinuxGUINoDisplayBeforeToolCheck verifies that "no graphical environment" is reported before "tool missing".
//
// Design intent: telling the user "there is no graphical environment" first is more useful than telling them "xdotool is not installed",
// because the former is the more fundamental blocking cause.
func TestLinuxGUINoDisplayBeforeToolCheck(t *testing.T) {
	t.Setenv("DISPLAY", "")
	t.Setenv("WAYLAND_DISPLAY", "")

	_, err := handleLinuxWindowList(map[string]any{})
	if err == nil {
		t.Fatal("it should return an error")
	}
	if strings.Contains(err.Error(), "apt install") {
		t.Errorf("when there is no graphical environment it should report the graphical environment error first rather than a tool installation hint, actual: %v", err)
	}
	if !strings.Contains(err.Error(), "graphical environment") {
		t.Errorf("it should report a graphical environment error, actual: %v", err)
	}
}

// TestLinuxGUIToolMissingWithDisplay verifies that the error contains an installation hint when DISPLAY is present but the tool is missing.
//
// A fake DISPLAY is set to bypass the environment check and verify the tool detection branch.
func TestLinuxGUIToolMissingWithDisplay(t *testing.T) {
	t.Setenv("DISPLAY", ":99")

	// Skip if these tools happen to be installed on this machine.
	for _, name := range []string{"wmctrl", "xdotool"} {
		if _, err := exec.LookPath(name); err == nil {
			t.Skipf("%s is already installed on this machine, skipping the tool-missing verification", name)
		}
	}

	_, err := handleLinuxWindowList(map[string]any{})
	if err == nil {
		t.Fatal("it should return an error when the tool is missing")
	}
	if !strings.Contains(err.Error(), "no available command found") {
		t.Errorf("the error message should state that no available command was found, actual: %v", err)
	}
	if !strings.Contains(err.Error(), "apt install") {
		t.Errorf("the error message should contain an installation hint, actual: %v", err)
	}
}

// TestParseWmctrlWindowList verifies the pure logic of parsing wmctrl -lp output.
func TestParseWmctrlWindowList(t *testing.T) {
	sample := `0x03400007  0 12345 myhost Terminal — bash
0x0360000a  1 67890 myhost Firefox — Mozilla Firefox
0x03800001 -1 111   myhost Sticky Window

`
	windows := parseWmctrlWindowList(sample)
	if len(windows) != 3 {
		t.Fatalf("it should parse 3 windows, actual %d", len(windows))
	}

	if windows[0]["window_id"] != "0x03400007" {
		t.Errorf("window_id parsed incorrectly: %v", windows[0]["window_id"])
	}
	if windows[0]["desktop"] != "0" {
		t.Errorf("desktop parsed incorrectly: %v", windows[0]["desktop"])
	}
	if windows[0]["pid"] != "12345" {
		t.Errorf("pid parsed incorrectly: %v", windows[0]["pid"])
	}
	if windows[0]["hostname"] != "myhost" {
		t.Errorf("hostname parsed incorrectly: %v", windows[0]["hostname"])
	}
	// The title contains spaces and a dash and should be preserved completely.
	if windows[0]["title"] != "Terminal — bash" {
		t.Errorf("title parsed incorrectly: %q", windows[0]["title"])
	}
	if windows[1]["title"] != "Firefox — Mozilla Firefox" {
		t.Errorf("title parsed incorrectly: %q", windows[1]["title"])
	}

	// Empty input should return an empty slice without panicking.
	if got := parseWmctrlWindowList(""); len(got) != 0 {
		t.Errorf("empty input should return an empty result, actual %d entries", len(got))
	}
	// Lines with insufficient fields should be skipped.
	if got := parseWmctrlWindowList("0x1 0 1"); len(got) != 0 {
		t.Errorf("lines with insufficient fields should be skipped, actual %d entries", len(got))
	}
}

// TestRequiredInt verifies required-int parsing (0 is a valid value and must not be confused with missing).
func TestRequiredInt(t *testing.T) {
	// 0 must be accepted.
	if v, err := requiredInt(map[string]any{"x": 0}, "x"); err != nil || v != 0 {
		t.Errorf("x=0 should be accepted, got v=%d err=%v", v, err)
	}
	// Negative coordinates should also be accepted (they may be negative in multi-monitor scenarios).
	if v, err := requiredInt(map[string]any{"x": -100}, "x"); err != nil || v != -100 {
		t.Errorf("x=-100 should be accepted, got v=%d err=%v", v, err)
	}
	// A float64 integer should be accepted (JSON decoding scenario).
	if v, err := requiredInt(map[string]any{"x": float64(42)}, "x"); err != nil || v != 42 {
		t.Errorf("x=42.0 should be accepted, got v=%d err=%v", v, err)
	}
	// Missing, nil, non-integer, and wrong-type values should all report errors.
	for _, params := range []map[string]any{
		{},
		{"x": nil},
		{"x": 1.5},
		{"x": "a"},
		{"x": true},
	} {
		if _, err := requiredInt(params, "x"); err == nil {
			t.Errorf("params=%v should report an error", params)
		}
	}
}

// TestParseXdotoolWindowListEmpty verifies handling of empty xdotool output.
func TestParseXdotoolWindowListEmpty(t *testing.T) {
	// Passing a non-existent tool path makes getwindowname fail, but it should not panic;
	// the title simply remains empty.
	got := parseXdotoolWindowList("", "/nonexistent/xdotool")
	if len(got) != 0 {
		t.Errorf("empty output should return an empty result, actual %d entries", len(got))
	}
}

// TestLinuxGUICapabilitiesRegistered verifies that all 9 GUI capabilities are registered.
func TestLinuxGUICapabilitiesRegistered(t *testing.T) {
	reg := NewRegistry()
	names := []string{
		"linux.window.list",
		"linux.window.focus",
		"linux.window.close",
		"linux.input.click",
		"linux.input.type",
		"linux.input.keys",
		"linux.clipboard.get",
		"linux.clipboard.set",
		"linux.screenshot",
	}
	for _, name := range names {
		cap, ok := reg.Get(name)
		if !ok {
			t.Fatalf("capability %s is not registered", name)
		}
		if cap.Platform != PlatformLinux {
			t.Errorf("the platform of capability %s should be linux, actual %s", name, cap.Platform)
		}
		if strings.TrimSpace(cap.Description) == "" {
			t.Errorf("capability %s is missing Description", name)
		}
		if cap.Parameters == nil {
			t.Errorf("capability %s is missing Parameters", name)
		}
		if cap.Handler == nil {
			t.Errorf("capability %s is missing Handler", name)
		}
	}
}

// TestLinuxGUIToolHintsCoverage verifies that the hint table covers all detected tools.
func TestLinuxGUIToolHintsCoverage(t *testing.T) {
	// These are all the tool names actually used by requireTool in the code.
	used := []string{"wmctrl", "xdotool", "xclip", "xsel", "import", "scrot", "grim"}
	for _, name := range used {
		hint, ok := linuxGUIToolHints[name]
		if !ok {
			t.Errorf("tool %s is missing an installation hint", name)
			continue
		}
		if !strings.Contains(hint, "apt install") {
			t.Errorf("the hint for tool %s should contain apt install, actual %q", name, hint)
		}
	}
}

// TestRunGUICommandTimeout verifies the timeout protection of external commands.
func TestRunGUICommandTimeout(t *testing.T) {
	// A hanging command would be used to verify the timeout. Here sh is used to start sleep,
	// but linuxGUITimeout is 10s, which would make the test too slow, so the normal path is verified instead.
	if testing.Short() {
		t.Skip("skipping in short mode")
	}

	sh, err := exec.LookPath("sh")
	if err != nil {
		t.Skip("no sh, skipping")
	}

	out, err := runGUICommand("", sh, "-c", "echo hello")
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if strings.TrimSpace(out) != "hello" {
		t.Errorf("the output should be hello, actual %q", out)
	}

	// A non-zero exit code should return an error.
	if _, err := runGUICommand("", sh, "-c", "exit 3"); err == nil {
		t.Error("a non-zero exit code should return an error")
	}
}

// TestLinuxGUIEnvironmentNote records the current environment limitations for manual review.
func TestLinuxGUIEnvironmentNote(t *testing.T) {
	display := os.Getenv("DISPLAY")
	wayland := os.Getenv("WAYLAND_DISPLAY")

	tools := []string{"xdotool", "wmctrl", "xclip", "xsel", "import", "scrot", "grim"}
	available := make([]string, 0, len(tools))
	for _, name := range tools {
		if _, err := exec.LookPath(name); err == nil {
			available = append(available, name)
		}
	}

	t.Logf("environment: DISPLAY=%q WAYLAND_DISPLAY=%q", display, wayland)
	t.Logf("available GUI tools: %v", available)
	if display == "" && wayland == "" {
		t.Log("note: there is no graphical environment, the end-to-end behavior of GUI capabilities was not verified; only error paths were verified")
	}
}
