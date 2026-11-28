package capability

import (
	"testing"
)

// This file tests the pure parsing functions in windows_parse.go.
//
// These functions carry no build tags, so they can also be compiled and run on Linux/macOS,
// allowing verification of the correctness of parsing reg.exe / tasklist / PowerShell output even without a Windows environment.

func TestSplitNonEmptyLines(t *testing.T) {
	got := splitNonEmptyLines("a\r\n\r\n  b  \n\nc\n")
	want := []string{"a", "b", "c"}
	if len(got) != len(want) {
		t.Fatalf("line count mismatch: got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("line %d mismatch: got %q, want %q", i, got[i], want[i])
		}
	}
}

func TestFirstNonEmptyLine(t *testing.T) {
	if got := firstNonEmptyLine("\n\n  hello  \nworld"); got != "hello" {
		t.Fatalf("got %q, want %q", got, "hello")
	}
	if got := firstNonEmptyLine("   \n\n"); got != "" {
		t.Fatalf("all-blank lines should return an empty string, got %q", got)
	}
}

func TestSplitCSVLine(t *testing.T) {
	got := splitCSVLine(`"chrome.exe","1234","Console","1","123,456 K"`)
	// The simplified parsing does not handle commas embedded in quotes, so "123,456 K" is split into two pieces.
	if len(got) != 6 {
		t.Fatalf("field count mismatch: got %v", got)
	}
	if got[0] != "chrome.exe" || got[1] != "1234" || got[2] != "Console" || got[4] != "123" {
		t.Fatalf("field parsing mismatch: %v", got)
	}
}

func TestIndexOfFold(t *testing.T) {
	header := []string{"Node", "ProductName", "Version"}
	if got := indexOfFold(header, "productname"); got != 1 {
		t.Fatalf("case-insensitive lookup failed: got %d, want 1", got)
	}
	if got := indexOfFold(header, "DisplayVersion", "Version"); got != 2 {
		t.Fatalf("candidate name matching failed: got %d, want 2", got)
	}
	if got := indexOfFold(header, "Missing"); got != -1 {
		t.Fatalf("a miss should return -1, got %d", got)
	}
}

func TestMinInt(t *testing.T) {
	if got := minInt(3, 7); got != 3 {
		t.Fatalf("got %d, want 3", got)
	}
	if got := minInt(9, 2); got != 2 {
		t.Fatalf("got %d, want 2", got)
	}
}

func TestParseWindowsOSVersionCSV(t *testing.T) {
	// PowerShell ConvertTo-Csv style: the first line is the header, with a column order different from wmic.
	out := "\"Node\",\"ProductName\",\"DisplayVersion\",\"CurrentBuildNumber\"\r\n" +
		"\"PC\",\"Windows 11 Pro\",\"23H2\",\"22631\"\r\n"
	name, version, build := parseWindowsOSVersionCSV(out)
	if name != "Windows 11 Pro" || version != "23H2" || build != "22631" {
		t.Fatalf("parsing result mismatch: name=%q version=%q build=%q", name, version, build)
	}
}

func TestParseWindowsOSVersionCSVEmpty(t *testing.T) {
	name, version, build := parseWindowsOSVersionCSV("")
	if name != "" || version != "" || build != "" {
		t.Fatalf("empty input should return empty strings: %q %q %q", name, version, build)
	}
	// Header only, no data rows.
	name, version, build = parseWindowsOSVersionCSV("\"ProductName\"\r\n")
	if name != "" || version != "" || build != "" {
		t.Fatalf("header only should return empty strings: %q %q %q", name, version, build)
	}
}

func TestParseWindowsTasklistCSV(t *testing.T) {
	out := "\"chrome.exe\",\"1234\",\"Console\",\"1\",\"123,456 K\"\r\n" +
		"\"notepad.exe\",\"5678\",\"Console\",\"1\",\"12,345 K\"\r\n"
	procs := parseWindowsTasklistCSV(out)
	if len(procs) != 2 {
		t.Fatalf("process count mismatch: got %d, want 2", len(procs))
	}
	if procs[0]["name"] != "chrome.exe" {
		t.Fatalf("name mismatch: %v", procs[0]["name"])
	}
	if procs[0]["pid"] != 1234 {
		t.Fatalf("pid should be the int 1234, got %v (%T)", procs[0]["pid"], procs[0]["pid"])
	}
	if procs[0]["session_name"] != "Console" {
		t.Fatalf("session_name mismatch: %v", procs[0]["session_name"])
	}
	if procs[0]["session_id"] != 1 {
		t.Fatalf("session_id should be the int 1, got %v", procs[0]["session_id"])
	}
}

func TestParseWindowsTasklistCSVSkipsInvalid(t *testing.T) {
	// A row with a non-numeric PID should be skipped, and a row with too few fields should also be skipped.
	out := "\"bad.exe\",\"notanumber\",\"Console\",\"1\",\"0 K\"\r\n" +
		"\"short.exe\"\r\n" +
		"\"good.exe\",\"42\",\"Console\",\"1\",\"1 K\"\r\n"
	procs := parseWindowsTasklistCSV(out)
	if len(procs) != 1 {
		t.Fatalf("only 1 valid record should be kept, got %d: %v", len(procs), procs)
	}
	if procs[0]["name"] != "good.exe" || procs[0]["pid"] != 42 {
		t.Fatalf("the kept record mismatch: %v", procs[0])
	}
}

func TestParseWindowsRegSubKeys(t *testing.T) {
	out := "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\r\n" +
		"    HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{GUID-1}\r\n" +
		"    HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\AppName\r\n"
	keys := parseWindowsRegSubKeys(out)
	if len(keys) != 2 {
		t.Fatalf("subkey count mismatch: got %d, want 2: %v", len(keys), keys)
	}
	if keys[0] != "{GUID-1}" || keys[1] != "AppName" {
		t.Fatalf("subkey name mismatch: %v", keys)
	}
}

func TestParseWindowsRegValues(t *testing.T) {
	out := "HKEY_LOCAL_MACHINE\\SOFTWARE\\...\\Uninstall\\{GUID}\r\n" +
		"    DisplayName    REG_SZ    Google Chrome\r\n" +
		"    DisplayVersion    REG_SZ    120.0.1\r\n" +
		"    SystemComponent    REG_DWORD    0x1\r\n"
	values := parseWindowsRegValues(out)
	if values["DisplayName"] != "Google Chrome" {
		t.Fatalf("DisplayName mismatch: %q", values["DisplayName"])
	}
	if values["DisplayVersion"] != "120.0.1" {
		t.Fatalf("DisplayVersion mismatch: %q", values["DisplayVersion"])
	}
	if values["SystemComponent"] != "0x1" {
		t.Fatalf("SystemComponent mismatch: %q", values["SystemComponent"])
	}
}

func TestParseWindowsRegValuesMultiWordName(t *testing.T) {
	// When the value name itself contains spaces, it should be preserved in full (the name and type are separated by multiple spaces).
	out := "    Install Location    REG_SZ    C:\\Program Files\\App\r\n"
	values := parseWindowsRegValues(out)
	if values["Install Location"] != "C:\\Program Files\\App" {
		t.Fatalf("multi-word value name parsing mismatch: %v", values)
	}
}

func TestParseWindowsUninstallEntry(t *testing.T) {
	out := "HKEY_LOCAL_MACHINE\\SOFTWARE\\...\\Uninstall\\{GUID}\r\n" +
		"    DisplayName    REG_SZ    Google Chrome\r\n" +
		"    DisplayVersion    REG_SZ    120.0.1\r\n" +
		"    Publisher    REG_SZ    Google LLC\r\n" +
		"    InstallLocation    REG_SZ    C:\\Program Files\\Google\\Chrome\r\n" +
		"    InstallDate    REG_SZ    20240101\r\n"
	app := parseWindowsUninstallEntry(out)
	if app == nil {
		t.Fatal("a valid application should be parsed, got nil")
	}
	if app["name"] != "Google Chrome" {
		t.Fatalf("name mismatch: %v", app["name"])
	}
	if app["version"] != "120.0.1" {
		t.Fatalf("version mismatch: %v", app["version"])
	}
	if app["publisher"] != "Google LLC" {
		t.Fatalf("publisher mismatch: %v", app["publisher"])
	}
	if app["install_location"] != "C:\\Program Files\\Google\\Chrome" {
		t.Fatalf("install_location mismatch: %v", app["install_location"])
	}
	if app["install_date"] != "20240101" {
		t.Fatalf("install_date mismatch: %v", app["install_date"])
	}
}

func TestParseWindowsUninstallEntrySkips(t *testing.T) {
	// Missing DisplayName should be skipped.
	noName := "    DisplayVersion    REG_SZ    1.0\r\n"
	if app := parseWindowsUninstallEntry(noName); app != nil {
		t.Fatalf("missing DisplayName should return nil, got %v", app)
	}

	// SystemComponent=1 should be skipped.
	sysComp := "    DisplayName    REG_SZ    Some Component\r\n" +
		"    SystemComponent    REG_DWORD    0x1\r\n"
	if app := parseWindowsUninstallEntry(sysComp); app != nil {
		t.Fatalf("SystemComponent=1 should return nil, got %v", app)
	}
}

func TestParseWindowsUninstallEntryOmitsEmptyFields(t *testing.T) {
	// When there is only DisplayName, the other fields should not appear in the result.
	out := "    DisplayName    REG_SZ    Minimal App\r\n"
	app := parseWindowsUninstallEntry(out)
	if app == nil {
		t.Fatal("a valid application should be parsed")
	}
	if _, ok := app["version"]; ok {
		t.Fatalf("an empty version should not be written to the result: %v", app)
	}
	if _, ok := app["publisher"]; ok {
		t.Fatalf("an empty publisher should not be written to the result: %v", app)
	}
}

func TestIsWindowsRegTrue(t *testing.T) {
	for _, raw := range []string{"1", "0x1", "true", "TRUE", "yes", " 1 "} {
		if !isWindowsRegTrue(raw) {
			t.Fatalf("%q should be judged as true", raw)
		}
	}
	for _, raw := range []string{"0", "0x0", "false", "no", ""} {
		if isWindowsRegTrue(raw) {
			t.Fatalf("%q should be judged as false", raw)
		}
	}
}
