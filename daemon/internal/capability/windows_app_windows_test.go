//go:build windows

package capability

// This file unit-tests the correctness of the "application list script construction" in windows_app_windows.go.
//
// It carries the //go:build windows tag: buildWindowsAppListScript depends on untagged functions such as
// encodePowerShellText, but the object under test itself only exists under the Windows build, so the test needs the same tag.
// On Linux, `GOOS=windows go vet ./...` can be used for compile-time checking.
//
// The tests for the parsing layer parseWindowsAppCSV are in the untagged windows_app_parse_test.go,
// because it is a pure function and can be run directly on Linux.

import (
	"strings"
	"testing"
)

// TestToPowerShellRegistryPath verifies the root key prefix conversion.
func TestToPowerShellRegistryPath(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		want    string
		wantErr bool
	}{
		{
			name: "HKLM uninstall key",
			in:   `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
			want: `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
		},
		{
			name: "WOW6432Node 32-bit view",
			in:   `HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
			want: `HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
		},
		{
			name: "HKCU current user",
			in:   `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
			want: `HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
		},
		{
			name:    "unknown root key errors",
			in:      `HKEY_BOGUS\SOFTWARE\Foo`,
			wantErr: true,
		},
		{
			name:    "empty string errors",
			in:      "",
			wantErr: true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := toPowerShellRegistryPath(tc.in)
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
				t.Errorf("conversion error:\n  input %q\n  expected %q\n  got %q", tc.in, tc.want, got)
			}
		})
	}
}

// TestBuildWindowsAppListScriptContainsRequiredPieces verifies that the generated script contains all required fragments.
//
// Key verification points:
//   - All three root keys are converted to PowerShell paths and listed as literals (to prevent missing the 32-bit view or HKCU);
//   - It uses Get-ChildItem + Get-ItemProperty to traverse (not launching a process per key);
//   - It uses a Select-Object hashtable to normalize the fields to [string] (ensuring stable CSV columns);
//   - It ends with ConvertTo-Csv -NoTypeInformation.
func TestBuildWindowsAppListScriptContainsRequiredPieces(t *testing.T) {
	script := buildWindowsAppListScript()

	required := []string{
		// PowerShell literals for the three root keys.
		`'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'`,
		`'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'`,
		`'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'`,
		// Traversal and reading.
		"Get-ChildItem",
		"Get-ItemProperty",
		// Normalize fields to strings.
		"Select-Object",
		"[string]$_.DisplayName",
		"[string]$_.DisplayVersion",
		"[string]$_.Publisher",
		"[string]$_.InstallLocation",
		"[string]$_.InstallDate",
		"[string]$_.SystemComponent",
		// Output format.
		"ConvertTo-Csv -NoTypeInformation",
	}
	for _, r := range required {
		if !strings.Contains(script, r) {
			t.Errorf("script is missing required fragment %q:\n%s", r, script)
		}
	}

	// There should be no sign of syntax errors caused by leftover Go raw-string delimiter backticks:
	// if the concatenation is wrong, two consecutive backticks would appear.
	if strings.Contains(script, "``") {
		t.Errorf("script contains consecutive backticks, indicating a concatenation error:\n%s", script)
	}
}
