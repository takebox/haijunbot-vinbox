package capability

import (
	"strings"
	"testing"
)

func TestParseWindowsUIMenuPath(t *testing.T) {
	cases := []struct {
		path string
		want []string
	}{
		{"File->Open", []string{"File", "Open"}},
		{"Edit->Copy", []string{"Edit", "Copy"}},
		{"Help", []string{"Help"}},
		{"  File  ->  Open  ", []string{"File", "Open"}},
		{"File->Edit->Preferences->General", []string{"File", "Edit", "Preferences", "General"}},
	}
	for _, c := range cases {
		got, err := parseWindowsUIMenuPath(c.path)
		if err != nil {
			t.Fatalf("path=%q unexpected error: %v", c.path, err)
		}
		if len(got) != len(c.want) {
			t.Errorf("path=%q segment count error: got %v, want %v", c.path, got, c.want)
			continue
		}
		for i := range got {
			if got[i] != c.want[i] {
				t.Errorf("path=%q segment %d error: got %q, want %q", c.path, i, got[i], c.want[i])
			}
		}
	}

	// Error cases.
	if _, err := parseWindowsUIMenuPath(""); err == nil {
		t.Error("an empty path should return an error")
	}
	if _, err := parseWindowsUIMenuPath("File->"); err == nil {
		t.Error("a path ending with -> should return an error")
	}
	if _, err := parseWindowsUIMenuPath("->File"); err == nil {
		t.Error("a path starting with -> should return an error")
	}
}

func TestBuildWindowsUITreeScript(t *testing.T) {
	// window_id location.
	script, err := buildWindowsUITreeScript("0x00010A2C", "", 5, 100)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, want := range []string{
		"UIAutomationClient",
		"UIAutomationTypes",
		"FromHandle([IntPtr]0x00010A2C)",
		"function Walk",
		"FindAll([System.Windows.Automation.TreeScope]::Children",
	} {
		if !strings.Contains(script, want) {
			t.Errorf("tree script is missing %q: %s", want, script)
		}
	}
	// The depth/count limits should be written into the script.
	if !strings.Contains(script, "if ($script:count -ge 100)") {
		t.Errorf("tree script is missing the maxControls limit: %s", script)
	}
	if !strings.Contains(script, "if ($depth -ge 5)") {
		t.Errorf("tree script is missing the maxDepth limit: %s", script)
	}

	// title location: title must be escaped, never concatenated raw.
	title := "Notepad'; Remove-Item -Recurse C:\\ -Force; '"
	script, err = buildWindowsUITreeScript("", title, 0, 0)
	if err != nil {
		t.Fatalf("title location unexpected error: %v", err)
	}
	if !strings.Contains(script, encodePowerShellText(title)) {
		t.Errorf("tree title was not correctly escaped: %s", script)
	}
	assertNoRawInput(t, script, title)

	// Both missing errors.
	if _, err := buildWindowsUITreeScript("", "", 0, 0); err == nil {
		t.Error("both window_id and title missing should return an error")
	}
}

func TestParseWindowsUITreeText(t *testing.T) {
	out := "0|ControlType.Window|Main Window|main|0|0|800|600\r\n" +
		"1|ControlType.MenuBar|Menu|menuBar|0|0|800|30\r\n" +
		"2|ControlType.MenuItem|File|fileMenu|10|5|50|20\r\n" +
		"ERROR:no-window\r\n" +
		"garbage-line\r\n"
	controls := parseWindowsUITreeText(out)
	if len(controls) != 3 {
		t.Fatalf("parsed control count error: got %d, want 3", len(controls))
	}
	first := controls[0]
	if first["depth"] != "0" || first["type"] != "ControlType.Window" || first["name"] != "Main Window" {
		t.Errorf("first control parsing error: %v", first)
	}
	rect, ok := first["rect"].(map[string]any)
	if !ok {
		t.Fatalf("rect type error: %T", first["rect"])
	}
	if rect["x"] != "0" || rect["width"] != "800" {
		t.Errorf("rect parsing error: %v", rect)
	}
	// The ERROR and garbage lines are skipped.
	for _, c := range controls {
		if c["name"] == "ERROR:no-window" {
			t.Errorf("the ERROR line should not be parsed as a control: %v", c)
		}
	}

	// Empty output returns an empty list.
	if got := parseWindowsUITreeText(""); len(got) != 0 {
		t.Errorf("empty output should return an empty list: %v", got)
	}
}

func TestBuildWindowsUIMenuScript(t *testing.T) {
	// window_id + path.
	script, err := buildWindowsUIMenuScript("0x00010A2C", "", "File->Open")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, want := range []string{
		"UIAutomationClient",
		"File",
		"Open",
		"InvokePattern",
		"ExpandCollapsePattern",
	} {
		if !strings.Contains(script, want) {
			t.Errorf("menu script is missing %q: %s", want, script)
		}
	}
	// Intermediate segments should Expand, and the last segment should Invoke.
	if !strings.Contains(script, "Expand()") {
		t.Errorf("menu script is missing Expand: %s", script)
	}
	if !strings.Contains(script, "$p.Invoke()") {
		t.Errorf("menu script is missing Invoke: %s", script)
	}

	// title + a path segment containing an injection attempt.
	title := "App'; Remove-Item -Recurse C:\\ -Force; '"
	path := "File'; Remove-Item -Recurse C:\\ -Force; '->Open"
	script, err = buildWindowsUIMenuScript("", title, path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// title and every path segment should be escaped.
	if !strings.Contains(script, encodePowerShellText(title)) {
		t.Errorf("menu title not escaped: %s", script)
	}
	assertNoRawInput(t, script, title)
	for _, seg := range []string{"File'; Remove-Item -Recurse C:\\ -Force; '", "Open"} {
		assertNoRawInput(t, script, seg)
	}

	// Invalid path errors.
	if _, err := buildWindowsUIMenuScript("0x1", "", "File->"); err == nil {
		t.Error("an invalid path should return an error")
	}
	// Both missing errors.
	if _, err := buildWindowsUIMenuScript("", "", "File->Open"); err == nil {
		t.Error("both window_id and title missing should return an error")
	}
}

func TestBuildWindowsControlFindPrefix(t *testing.T) {
	// window_id + name location.
	prefix, err := buildWindowsControlFindPrefix("0x00010A2C", "", "Save", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, want := range []string{
		"UIAutomationClient",
		"FromHandle([IntPtr]0x00010A2C)",
		"NameProperty",
		"FindFirst([System.Windows.Automation.TreeScope]::Descendants",
		encodePowerShellText("Save"),
	} {
		if !strings.Contains(prefix, want) {
			t.Errorf("find prefix is missing %q: %s", want, prefix)
		}
	}

	// automation_id location: AutomationIdProperty should be used.
	prefix, err = buildWindowsControlFindPrefix("0x1", "", "", "btnSave")
	if err != nil {
		t.Fatalf("automation_id location unexpected error: %v", err)
	}
	if !strings.Contains(prefix, "AutomationIdProperty") {
		t.Errorf("automation_id location should use AutomationIdProperty: %s", prefix)
	}
	if !strings.Contains(prefix, encodePowerShellText("btnSave")) {
		t.Errorf("automation_id not escaped: %s", prefix)
	}

	// title + an injection-attempt name must be escaped.
	title := "App'; Remove-Item -Recurse C:\\ -Force; '"
	name := "Save'; Remove-Item -Recurse C:\\ -Force; '"
	prefix, err = buildWindowsControlFindPrefix("", title, name, "")
	if err != nil {
		t.Fatalf("title location unexpected error: %v", err)
	}
	assertNoRawInput(t, prefix, title)
	assertNoRawInput(t, prefix, name)

	// Missing parameters errors.
	if _, err := buildWindowsControlFindPrefix("", "", "x", ""); err == nil {
		t.Error("both window_id and title missing should return an error")
	}
	if _, err := buildWindowsControlFindPrefix("0x1", "", "", ""); err == nil {
		t.Error("both name and automation_id missing should return an error")
	}
}

func TestBuildWindowsControlClickScript(t *testing.T) {
	script, err := buildWindowsControlClickScript("0x00010A2C", "", "Save", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, want := range []string{
		"InvokePattern",
		"$p.Invoke()",
		"SelectionItemPattern",
		"$s.Select()",
	} {
		if !strings.Contains(script, want) {
			t.Errorf("click script is missing %q: %s", want, script)
		}
	}
}

func TestBuildWindowsControlSetTextScript(t *testing.T) {
	script, err := buildWindowsControlSetTextScript("0x00010A2C", "", "", "txtName", "John")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, want := range []string{
		"ValuePattern",
		"$v.SetValue(",
		encodePowerShellText("John"),
	} {
		if !strings.Contains(script, want) {
			t.Errorf("set-text script is missing %q: %s", want, script)
		}
	}

	// text containing an injection attempt must be escaped.
	evil := "'; Remove-Item -Recurse C:\\ -Force; '"
	script, err = buildWindowsControlSetTextScript("0x1", "", "", "txt", evil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	assertNoRawInput(t, script, evil)
}
