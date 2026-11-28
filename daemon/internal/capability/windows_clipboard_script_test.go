package capability

import (
	"strings"
	"testing"
)

// TestBuildWindowsClipboardSetScriptContainsRetry verifies that the script indeed has a retry loop.
//
// This is a fix driven by real-machine measurement: when the Windows clipboard is occupied by another process, Set-Clipboard throws
// ExternalException, a single call fails, and in the worst case it took 9 retries to succeed.
func TestBuildWindowsClipboardSetScriptContainsRetry(t *testing.T) {
	script := buildWindowsClipboardSetScript("'hello'")

	for _, want := range []string{"for ($i = 0;", "try {", "catch {", "Start-Sleep", "Set-Clipboard -Value 'hello'"} {
		if !strings.Contains(script, want) {
			t.Errorf("script is missing %q:\n%s", want, script)
		}
	}
	// The attempt count and interval must come from the constants, to avoid the script drifting from the constants.
	if !strings.Contains(script, "20") {
		t.Errorf("script does not use the retry attempt count constant value:\n%s", script)
	}
	if !strings.Contains(script, "100") {
		t.Errorf("script does not use the retry interval constant value:\n%s", script)
	}
}

// TestBuildWindowsClipboardSetScriptFailsLoudly verifies that after retries are exhausted it fails with a non-zero exit code
// rather than silently succeeding (otherwise the caller would mistakenly believe the clipboard was written).
func TestBuildWindowsClipboardSetScriptFailsLoudly(t *testing.T) {
	script := buildWindowsClipboardSetScript("'x'")

	if !strings.Contains(script, "exit 1") {
		t.Errorf("after retries are exhausted it should exit 1 rather than return silently:\n%s", script)
	}
	if !strings.Contains(script, "Write-Error") {
		t.Errorf("after retries are exhausted it should write an error message:\n%s", script)
	}
}

// TestBuildWindowsClipboardSetScriptInjectionSafety verifies that the text literal is embedded verbatim,
// and the script construction itself performs no escaping (escaping is handled by encodePowerShellText).
// This confirms that a literal containing quotes/semicolons does not break the script structure — i.e. the function only concatenates strings.
func TestBuildWindowsClipboardSetScriptInjectionSafety(t *testing.T) {
	// encodePowerShellText doubles internal single quotes; this simulates its output.
	literal := "'it''s; Remove-Item C:\\ -Recurse'"
	script := buildWindowsClipboardSetScript(literal)

	if !strings.Contains(script, literal) {
		t.Errorf("the literal should be embedded verbatim (escaping is handled by encodePowerShellText):\n%s", script)
	}
	// The literal appears after Set-Clipboard -Value.
	idx := strings.Index(script, "Set-Clipboard -Value ")
	if idx < 0 || !strings.HasPrefix(script[idx+len("Set-Clipboard -Value "):], literal) {
		t.Errorf("the literal does not immediately follow Set-Clipboard -Value:\n%s", script)
	}
}

// TestBuildWindowsClipboardSetScriptEmptyLiteral verifies that an empty string literal (clearing the clipboard)
// can also construct the script normally.
func TestBuildWindowsClipboardSetScriptEmptyLiteral(t *testing.T) {
	script := buildWindowsClipboardSetScript("''")
	if !strings.Contains(script, "Set-Clipboard -Value ''") {
		t.Errorf("the empty literal should be embedded normally:\n%s", script)
	}
}
