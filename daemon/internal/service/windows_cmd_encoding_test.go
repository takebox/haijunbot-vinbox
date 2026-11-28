package service

import (
	"encoding/base64"
	"strings"
	"testing"
	"unicode/utf16"
)

// TestQuotePowerShellArg verifies argument escaping: single quotes are added only when whitespace/special characters are present,
// and an inner single quote is written as two consecutive single quotes per PowerShell convention.
func TestQuotePowerShellArg(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{"empty string", "", "''"},
		{"pure ASCII without special characters", "/Create", "/Create"},
		{"contains a space", "C:\\Program Files\\x.exe", "'C:\\Program Files\\x.exe'"},
		{"contains single quotes", "a'b", "'a''b'"},
		{"contains double quotes", `a"b`, `'a"b'`},
		{"contains the cmd metacharacter &", "a&b", "'a&b'"},
		{"contains $", "a$b", "'a$b'"},
		{"contains parentheses", "a(b)", "'a(b)'"},
		{"contains a comma", "a,b", "'a,b'"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := quotePowerShellArg(c.in); got != c.want {
				t.Errorf("quotePowerShellArg(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}

// TestStripPowerShellClixml verifies that CLIXML noise is stripped while the real error text is kept.
// The cases come from the actual output on a real Windows machine when install fails.
func TestStripPowerShellClixml(t *testing.T) {
	// Real-machine output: the CLIXML header + Objs block (a progress record) mixed in before the error text.
	realWorld := "#< CLIXML\n<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\"><Obj S=\"progress\" RefId=\"0\"><TN RefId=\"0\"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN><MS><I64 N=\"SourceId\">1</I64><PR N=\"Record\"><AV>Preparing module for first use.</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj></Objs>\nError: Access denied."
	got := stripPowerShellClixml(realWorld)
	want := "Error: Access denied."
	if got != want {
		t.Errorf("stripPowerShellClixml did not clean up correctly:\n got = %q\nwant = %q", got, want)
	}

	cases := []struct {
		name string
		in   string
		want string
	}{
		{"no CLIXML is returned as-is", "Error: Access denied.", "Error: Access denied."},
		{"CLIXML header only", "#< CLIXML\nError: Access denied.", "Error: Access denied."},
		{"Objs block only", "<Objs Version=\"1.1\"><Obj/></Objs>Error: Access denied.", "Error: Access denied."},
		{"CLIXML after the error", "Error: Access denied.\n#< CLIXML\n<Objs><Obj/></Objs>", "Error: Access denied."},
		{"empty string", "", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := stripPowerShellClixml(c.in); got != c.want {
				t.Errorf("stripPowerShellClixml(%q) = %q, want %q", c.in, got, c.want)
			}
		})
	}
}

// TestBuildPowerShellScriptStructure verifies the script structure: first run the command, then change the encoding, then write out;
// the order must not change (changing the encoding first causes GBK output to be miscoded as UTF-8).
func TestBuildPowerShellScriptStructure(t *testing.T) {
	script := buildPowerShellScript("schtasks", []string{"/Create", "/TN", "HaijunBot-Daemon"})

	idxProgress := strings.Index(script, "$ProgressPreference='SilentlyContinue'")
	idxExec := strings.Index(script, "$out = & schtasks")
	idxCode := strings.Index(script, "$code = $LASTEXITCODE")
	idxSetEnc := strings.Index(script, "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8")
	idxWrite := strings.Index(script, "[Console]::Out.Write($out)")
	idxExit := strings.Index(script, "exit $code")

	if idxProgress < 0 {
		t.Fatalf("the script does not contain the progress-stream-closing fragment: %q", script)
	}
	if idxExec < 0 {
		t.Fatalf("the script does not contain the command-execution fragment: %q", script)
	}
	if idxCode < 0 {
		t.Fatalf("the script does not contain the exit-code-capture fragment: %q", script)
	}
	if idxSetEnc < 0 {
		t.Fatalf("the script does not contain the set-UTF-8-output-encoding fragment: %q", script)
	}
	if idxWrite < 0 {
		t.Fatalf("the script does not contain the write-out fragment: %q", script)
	}
	if idxExit < 0 {
		t.Fatalf("the script does not contain the exit-code-pass-through fragment: %q", script)
	}
	// Key order: close progress stream → execute → capture exit code → change encoding → write out → pass through exit code.
	// $LASTEXITCODE must be captured after execution (otherwise it holds the previous command's exit code);
	// exit must be last (otherwise the following statements never run).
	if !(idxProgress < idxExec && idxExec < idxCode && idxCode < idxSetEnc && idxSetEnc < idxWrite && idxWrite < idxExit) {
		t.Errorf("script fragment order wrong (should be close-progress < execute < capture-exit-code < change-encoding < write-out < pass-through-exit-code): progress=%d exec=%d code=%d setEnc=%d write=%d exit=%d\n%s",
			idxProgress, idxExec, idxCode, idxSetEnc, idxWrite, idxExit, script)
	}
	// stderr is merged, ensuring failure reasons can also be captured.
	if !strings.Contains(script, "2>&1") {
		t.Errorf("the script does not merge stderr: %q", script)
	}
	// Non-ASCII arguments should be wrapped in single quotes.
	script2 := buildPowerShellScript("schtasks", []string{"/TR", "C:\\Program Files\\haijunbot daemon.exe"})
	if !strings.Contains(script2, "'C:\\Program Files\\haijunbot daemon.exe'") {
		t.Errorf("the argument containing spaces was not quoted correctly: %q", script2)
	}
}

// TestEncodePowerShellCommandRoundTrip verifies that the -EncodedCommand encoding can be correctly restored:
// this is the precondition for "non-ASCII characters in the script not being corrupted".
func TestEncodePowerShellCommandRoundTrip(t *testing.T) {
	original := "$out = & schtasks /TN 'café tête' 2>&1"
	encoded := encodePowerShellCommand(original)

	// base64 must be pure ASCII.
	for i := 0; i < len(encoded); i++ {
		if encoded[i] > 0x7F {
			t.Fatalf("base64 contains non-ASCII bytes: %q", encoded)
		}
	}

	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		t.Fatalf("base64 decode failed: %v", err)
	}
	if len(raw)%2 != 0 {
		t.Fatalf("the UTF-16LE byte count should be even, got %d", len(raw))
	}
	units := make([]uint16, 0, len(raw)/2)
	for i := 0; i+1 < len(raw); i += 2 {
		units = append(units, uint16(raw[i])|uint16(raw[i+1])<<8)
	}
	if got := string(utf16.Decode(units)); got != original {
		t.Errorf("mismatch after the round trip:\n got = %q\nwant = %q", got, original)
	}
}
