package capability

// This file unit-tests the pure parsing function parseWindowsAppCSV in windows_app_parse.go.
//
// No build tags: the parsing function only depends on the standard library and can run tests directly on Linux,
// so that the correctness of CSV parsing can still be verified without a Windows environment (the local development environment is Linux).

import (
	"testing"
)

// TestParseWindowsAppCSVBasic verifies the basic parsing: header recognition, field mapping, empty-value omission.
func TestParseWindowsAppCSVBasic(t *testing.T) {
	out := "\"DisplayName\",\"DisplayVersion\",\"Publisher\",\"InstallLocation\",\"InstallDate\",\"SystemComponent\"\r\n" +
		"\"Google Chrome\",\"120.0.1\",\"Google LLC\",\"C:\\Program Files\\Google\\Chrome\",\"20240101\",\"\"\r\n" +
		"\"7-Zip\",\"23.01\",\"Igor Pavlov\",\"\",\"\",\"\"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 2 {
		t.Fatalf("expected to parse 2 apps, got %d: %v", len(apps), apps)
	}

	chrome := apps[0]
	if got := chrome["name"]; got != "Google Chrome" {
		t.Errorf("name error: expected %q, got %q", "Google Chrome", got)
	}
	if got := chrome["version"]; got != "120.0.1" {
		t.Errorf("version error: expected %q, got %q", "120.0.1", got)
	}
	if got := chrome["publisher"]; got != "Google LLC" {
		t.Errorf("publisher error: expected %q, got %q", "Google LLC", got)
	}
	if got := chrome["install_location"]; got != `C:\Program Files\Google\Chrome` {
		t.Errorf("install_location error: expected %q, got %q", `C:\Program Files\Google\Chrome`, got)
	}
	if got := chrome["install_date"]; got != "20240101" {
		t.Errorf("install_date error: expected %q, got %q", "20240101", got)
	}

	// Empty fields should be omitted (not written to the map), staying consistent with the old implementation parseWindowsUninstallEntry.
	sevenZip := apps[1]
	if _, ok := sevenZip["install_location"]; ok {
		t.Errorf("an empty install_location should not be written to the map: %v", sevenZip)
	}
	if _, ok := sevenZip["install_date"]; ok {
		t.Errorf("an empty install_date should not be written to the map: %v", sevenZip)
	}
}

// TestParseWindowsAppCSVChineseAndComma verifies non-ASCII and commas inside fields (RFC4180 quote escaping).
//
// App names and publishers often contain commas (such as "Microsoft Corporation, Inc."), which must be correctly restored
// by the CSV quoting rules; this is also the reason for choosing encoding/csv rather than a hand-written split.
func TestParseWindowsAppCSVChineseAndComma(t *testing.T) {
	out := "\"DisplayName\",\"DisplayVersion\",\"Publisher\",\"InstallLocation\",\"InstallDate\",\"SystemComponent\"\r\n" +
		"\"East Fortune Information Co., Ltd.\",\"12.0.2\",\"East Fortune, Inc.\",\"D:\\East Fortune\",\"\",\"\"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 1 {
		t.Fatalf("expected to parse 1 app, got %d: %v", len(apps), apps)
	}
	if got := apps[0]["name"]; got != "East Fortune Information Co., Ltd." {
		t.Errorf("non-ASCII name parsing error: expected %q, got %q", "East Fortune Information Co., Ltd.", got)
	}
	if got := apps[0]["publisher"]; got != "East Fortune, Inc." {
		t.Errorf("publisher with a comma parsing error: expected %q, got %q", "East Fortune, Inc.", got)
	}
}

// TestParseWindowsAppCSVSkipsEmptyNameAndSystemComponent verifies the filtering rules.
//
//   - DisplayName empty → skip (an uninstall entry without a name is meaningless to the user);
//   - SystemComponent true (1 / 0x1 / true / yes) → skip (an internal system component).
func TestParseWindowsAppCSVSkipsEmptyNameAndSystemComponent(t *testing.T) {
	out := "\"DisplayName\",\"DisplayVersion\",\"Publisher\",\"InstallLocation\",\"InstallDate\",\"SystemComponent\"\r\n" +
		"\"\",\"1.0\",\"NoName Corp\",\"\",\"\",\"\"\r\n" +
		"\"Windows Internal\",\"1.0\",\"Microsoft\",\"\",\"\",\"1\"\r\n" +
		"\"Hex Component\",\"1.0\",\"Microsoft\",\"\",\"\",\"0x1\"\r\n" +
		"\"Kept App\",\"1.0\",\"Vendor\",\"\",\"\",\"0\"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 1 {
		t.Fatalf("expected to keep only 1 app, got %d: %v", len(apps), apps)
	}
	if got := apps[0]["name"]; got != "Kept App" {
		t.Errorf("the kept app is wrong: expected %q, got %q", "Kept App", got)
	}
}

// TestParseWindowsAppCSVHeaderMismatch verifies that an empty result is returned when the header does not contain DisplayName.
//
// This prevents treating script error text (such as an exception message) as an app name.
func TestParseWindowsAppCSVHeaderMismatch(t *testing.T) {
	out := "\"Error\",\"Message\"\r\n" +
		"\"SomethingFailed\",\"details\"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 0 {
		t.Errorf("an empty result should be returned when the header does not contain DisplayName, got %v", apps)
	}
}

// TestParseWindowsAppCSVEmpty verifies that both empty input and header-only input return empty.
func TestParseWindowsAppCSVEmpty(t *testing.T) {
	for _, in := range []string{"", "   ", "\r\n"} {
		if apps := parseWindowsAppCSV(in); len(apps) != 0 {
			t.Errorf("input %q should return empty, got %v", in, apps)
		}
	}

	headerOnly := "\"DisplayName\",\"DisplayVersion\"\r\n"
	if apps := parseWindowsAppCSV(headerOnly); len(apps) != 0 {
		t.Errorf("header only should return empty, got %v", apps)
	}
}

// TestParseWindowsAppCSVColumnOrderIndependent verifies that values are taken by column name rather than column order.
//
// Although PowerShell's Select-Object keeps the given order, taking values by name is more robust;
// here the column order is shuffled to confirm it can still be parsed correctly.
func TestParseWindowsAppCSVColumnOrderIndependent(t *testing.T) {
	out := "\"Publisher\",\"DisplayName\",\"SystemComponent\",\"DisplayVersion\"\r\n" +
		"\"Vendor X\",\"Reordered App\",\"\",\"9.9\"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 1 {
		t.Fatalf("expected to parse 1 app, got %d: %v", len(apps), apps)
	}
	if got := apps[0]["name"]; got != "Reordered App" {
		t.Errorf("name error: expected %q, got %q", "Reordered App", got)
	}
	if got := apps[0]["publisher"]; got != "Vendor X" {
		t.Errorf("publisher error: expected %q, got %q", "Vendor X", got)
	}
	if got := apps[0]["version"]; got != "9.9" {
		t.Errorf("version error: expected %q, got %q", "9.9", got)
	}
}

// TestParseWindowsAppCSVTrimsWhitespace verifies that leading/trailing whitespace in fields is removed.
func TestParseWindowsAppCSVTrimsWhitespace(t *testing.T) {
	out := "\"DisplayName\",\"DisplayVersion\"\r\n" +
		"\"  Padded App  \",\"  1.0  \"\r\n"

	apps := parseWindowsAppCSV(out)
	if len(apps) != 1 {
		t.Fatalf("expected to parse 1 app, got %d: %v", len(apps), apps)
	}
	if got := apps[0]["name"]; got != "Padded App" {
		t.Errorf("name whitespace not removed: got %q", got)
	}
	if got := apps[0]["version"]; got != "1.0" {
		t.Errorf("version whitespace not removed: got %q", got)
	}
}

// TestSplitWindowsArgs verifies the argument-string splitting logic when starting.
func TestSplitWindowsArgs(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want []string
	}{
		{"empty string", "", nil},
		{"whitespace only", "   ", nil},
		{"single argument", "notepad", []string{"notepad"}},
		{"multiple arguments", "file1.txt file2.txt", []string{"file1.txt", "file2.txt"}},
		{"collapsed whitespace", "  a   b  c ", []string{"a", "b", "c"}},
		{"quotes not merged", `"a b" c`, []string{`"a`, `b"`, "c"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := splitWindowsArgs(tt.in)
			if len(got) != len(tt.want) {
				t.Fatalf("expected %d arguments %v, got %d %v", len(tt.want), tt.want, len(got), got)
			}
			for i := range got {
				if got[i] != tt.want[i] {
					t.Errorf("argument[%d] error: expected %q, got %q", i, tt.want[i], got[i])
				}
			}
		})
	}
}
