//go:build windows

package capability

// This file unit-tests the pure functions in windows_script_windows.go that "do not depend on a real Windows runtime environment":
// interpreter resolution, command-line construction, environment variable assembly.
//
// It carries the //go:build windows tag: the object under test only exists under the Windows build.
// On Linux, `GOOS=windows go vet ./...` can be used for compile-time checking; actual execution requires Windows.

import (
	"encoding/base64"
	"strings"
	"testing"
	"unicode/utf16"
)

// TestResolveWindowsScriptInterpreter verifies interpreter whitelist resolution.
func TestResolveWindowsScriptInterpreter(t *testing.T) {
	cases := []struct {
		name    string
		in      map[string]any
		want    string
		wantErr bool
	}{
		{name: "defaults to powershell", in: map[string]any{}, want: "powershell"},
		{name: "explicit powershell", in: map[string]any{"interpreter": "powershell"}, want: "powershell"},
		{name: "case-insensitive", in: map[string]any{"interpreter": "PowerShell.EXE"}, want: "powershell.exe"},
		{name: "pwsh", in: map[string]any{"interpreter": "pwsh"}, want: "pwsh"},
		{name: "cmd", in: map[string]any{"interpreter": "cmd.exe"}, want: "cmd.exe"},
		{name: "not in whitelist errors", in: map[string]any{"interpreter": "/bin/sh"}, wantErr: true},
		{name: "empty string treated as default", in: map[string]any{"interpreter": ""}, want: "powershell"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := resolveWindowsScriptInterpreter(tc.in)
			if tc.wantErr {
				if err == nil {
					t.Errorf("expected an error, got %q", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tc.want {
				t.Errorf("expected %q, got %q", tc.want, got)
			}
		})
	}
}

// TestBuildWindowsScriptCommandPowerShell verifies that PowerShell uses -EncodedCommand.
func TestBuildWindowsScriptCommandPowerShell(t *testing.T) {
	script := "Write-Output 'café test'"
	args, cleanup, err := buildWindowsScriptCommand("powershell", script)
	if err != nil {
		t.Fatalf("failed to construct command: %v", err)
	}
	defer cleanup()

	joined := strings.Join(args, " ")
	if !strings.Contains(joined, "-EncodedCommand") {
		t.Fatalf("PowerShell should use -EncodedCommand, actual args: %v", args)
	}
	if !strings.Contains(joined, "-NoProfile") || !strings.Contains(joined, "-NonInteractive") {
		t.Fatalf("missing -NoProfile/-NonInteractive, actual args: %v", args)
	}

	// Take out the value of -EncodedCommand; after decoding it should contain the original script and the preamble.
	idx := -1
	for i, a := range args {
		if a == "-EncodedCommand" {
			idx = i
			break
		}
	}
	if idx < 0 || idx+1 >= len(args) {
		t.Fatalf("-EncodedCommand value not found, args: %v", args)
	}
	raw, err := base64.StdEncoding.DecodeString(args[idx+1])
	if err != nil {
		t.Fatalf("base64 decoding failed: %v", err)
	}
	// Restore UTF-16LE.
	u16 := make([]uint16, 0, len(raw)/2)
	for i := 0; i+1 < len(raw); i += 2 {
		u16 = append(u16, uint16(raw[i])|uint16(raw[i+1])<<8)
	}
	decoded := string(utf16.Decode(u16))
	if !strings.Contains(decoded, script) {
		t.Errorf("after decoding it should contain the original script, actual: %q", decoded)
	}
	if !strings.Contains(decoded, "OutputEncoding") {
		t.Errorf("after decoding it should contain the encoding preamble, actual: %q", decoded)
	}
}

// TestBuildWindowsScriptCommandCmd verifies that cmd uses a temporary .cmd file.
func TestBuildWindowsScriptCommandCmd(t *testing.T) {
	args, cleanup, err := buildWindowsScriptCommand("cmd", "echo hi")
	if err != nil {
		t.Fatalf("failed to construct command: %v", err)
	}
	defer cleanup()

	if len(args) != 2 || args[0] != "/C" {
		t.Fatalf("cmd args should be [/C <temp file>], actual: %v", args)
	}
	if !strings.HasSuffix(args[1], ".cmd") {
		t.Fatalf("the temp file should end with .cmd, actual: %q", args[1])
	}
}

// TestBuildWindowsScriptCommandUnknown verifies that an unknown interpreter errors.
func TestBuildWindowsScriptCommandUnknown(t *testing.T) {
	if _, _, err := buildWindowsScriptCommand("bash", "echo hi"); err == nil {
		t.Fatal("an unknown interpreter should error")
	}
}

// TestBuildWindowsEnvPairs verifies environment variable assembly.
func TestBuildWindowsEnvPairs(t *testing.T) {
	got := buildWindowsEnvPairs(map[string]string{"A": "1", "B": "2"})
	if len(got) != 2 {
		t.Fatalf("expected 2 entries, actual %v", got)
	}
	// Map order is not fixed, so judge using a set.
	set := map[string]bool{}
	for _, kv := range got {
		set[kv] = true
	}
	if !set["A=1"] || !set["B=2"] {
		t.Fatalf("environment variable assembly error: %v", got)
	}

	// An empty key should be skipped.
	got = buildWindowsEnvPairs(map[string]string{"": "x", "C": "3"})
	if len(got) != 1 || got[0] != "C=3" {
		t.Fatalf("an empty key should be skipped, actual: %v", got)
	}
}
