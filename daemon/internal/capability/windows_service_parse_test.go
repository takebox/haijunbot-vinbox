package capability

// This file unit-tests the pure logic in windows_service_parse.go (CSV parsing, filtering).
//
// These tests **carry no build tags**, so they can be run on Linux — the local development environment is Linux,
// with no Windows runtime environment, which is the main means of verifying the windows.service.* parsing logic.
//
// Note: the actual PowerShell invocation (windows_service_windows.go) carries the //go:build windows
// tag, and its success path cannot be verified end-to-end locally; only compilation under GOOS=windows can be guaranteed.

import (
	"strings"
	"testing"
)

// Simulates the real output of PowerShell `Get-Service | Select Name,DisplayName,Status |
// ConvertTo-Csv -NoTypeInformation`.
const sampleServiceCSV = `"Name","DisplayName","Status"
"Spooler","Print Spooler","Running"
"wuauserv","Windows Update","Stopped"
"W32Time","Windows Time","Running"
"EventLog","Windows Event Log","Running"`

// TestParseWindowsServiceCSV covers the basic parsing.
func TestParseWindowsServiceCSV(t *testing.T) {
	units := parseWindowsServiceCSV(sampleServiceCSV)
	if len(units) != 4 {
		t.Fatalf("expected to parse 4 services, actual %d", len(units))
	}

	if units[0]["unit"] != "Spooler" {
		t.Errorf("the 1st service name expected Spooler, actual %v", units[0]["unit"])
	}
	if units[0]["display_name"] != "Print Spooler" {
		t.Errorf("the 1st display name expected Print Spooler, actual %v", units[0]["display_name"])
	}
	if units[0]["active"] != "Running" {
		t.Errorf("the 1st status expected Running, actual %v", units[0]["active"])
	}
	if units[1]["unit"] != "wuauserv" || units[1]["active"] != "Stopped" {
		t.Errorf("the 2nd service parsing is abnormal: %v", units[1])
	}
}

// TestParseWindowsServiceCSVWithCommaInDisplayName verifies that a display name containing a comma does not misalign.
//
// This is the core reason for choosing CSV rather than a hand-written split.
func TestParseWindowsServiceCSVWithCommaInDisplayName(t *testing.T) {
	csvText := `"Name","DisplayName","Status"
"svc1","Windows Update, Auto Update","Running"`

	units := parseWindowsServiceCSV(csvText)
	if len(units) != 1 {
		t.Fatalf("expected 1 service, actual %d", len(units))
	}
	if units[0]["display_name"] != "Windows Update, Auto Update" {
		t.Fatalf("parsing a display name containing a comma is wrong: %q", units[0]["display_name"])
	}
	if units[0]["active"] != "Running" {
		t.Fatalf("the status column is misaligned, actual %q", units[0]["active"])
	}
}

// TestParseWindowsServiceCSVWithEscapedQuote verifies that a double quote inside a field (escaped as "") is correctly restored.
func TestParseWindowsServiceCSVWithEscapedQuote(t *testing.T) {
	csvText := `"Name","DisplayName","Status"
"svc1","My ""Quoted"" Service","Running"`

	units := parseWindowsServiceCSV(csvText)
	if len(units) != 1 {
		t.Fatalf("expected 1 service, actual %d", len(units))
	}
	if units[0]["display_name"] != `My "Quoted" Service` {
		t.Fatalf("restoring the escaped quote is wrong: %q", units[0]["display_name"])
	}
}

// TestParseWindowsServiceCSVChineseDisplayName verifies that a non-ASCII display name is not corrupted.
func TestParseWindowsServiceCSVChineseDisplayName(t *testing.T) {
	csvText := `"Name","DisplayName","Status"
"TestSvc","Test Service (Chinese)","Running"`

	units := parseWindowsServiceCSV(csvText)
	if len(units) != 1 {
		t.Fatalf("expected 1 service, actual %d", len(units))
	}
	if units[0]["display_name"] != "Test Service (Chinese)" {
		t.Fatalf("parsing the non-ASCII display name is wrong: %q", units[0]["display_name"])
	}
}

// TestParseWindowsServiceCSVEmpty verifies that empty input and header-only input do not panic.
func TestParseWindowsServiceCSVEmpty(t *testing.T) {
	if got := parseWindowsServiceCSV(""); len(got) != 0 {
		t.Errorf("empty input expected 0 entries, actual %d", len(got))
	}
	if got := parseWindowsServiceCSV("   \n  \n"); len(got) != 0 {
		t.Errorf("whitespace-only input expected 0 entries, actual %d", len(got))
	}
	// Header only (no data rows): should produce no entries.
	headerOnly := `"Name","DisplayName","Status"`
	if got := parseWindowsServiceCSV(headerOnly); len(got) != 0 {
		t.Errorf("header only expected 0 entries, actual %d", len(got))
	}
}

// TestParseWindowsServiceStatusCSV covers detail parsing (column name → value mapping).
func TestParseWindowsServiceStatusCSV(t *testing.T) {
	// Note: a backtick raw string is used here, so the \\ inside is literally two backslash characters,
	// consistent with the unescaped backslash paths in PowerShell CSV (CSV does not escape backslashes).
	csvText := `"Name","DisplayName","State","StartMode","ProcessId","PathName","Status"
"Spooler","Print Spooler","Running","Auto","1234","C:\WINDOWS\System32\spoolsv.exe","OK"`

	props := parseWindowsServiceStatusCSV(csvText)
	if len(props) == 0 {
		t.Fatal("expected to parse properties, actual empty")
	}

	want := map[string]string{
		"Name":        "Spooler",
		"DisplayName": "Print Spooler",
		"State":       "Running",
		"StartMode":   "Auto",
		"ProcessId":   "1234",
		"PathName":    `C:\WINDOWS\System32\spoolsv.exe`,
		"Status":      "OK",
	}
	for k, v := range want {
		if props[k] != v {
			t.Errorf("property %s expected %q, actual %q", k, v, props[k])
		}
	}
}

// TestParseWindowsServiceStatusCSVInsufficient verifies that an insufficient data row returns an empty map.
func TestParseWindowsServiceStatusCSVInsufficient(t *testing.T) {
	// Header only, no data rows.
	headerOnly := `"Name","DisplayName","State"`
	if got := parseWindowsServiceStatusCSV(headerOnly); len(got) != 0 {
		t.Errorf("header only expected an empty map, actual %v", got)
	}
	if got := parseWindowsServiceStatusCSV(""); len(got) != 0 {
		t.Errorf("empty input expected an empty map, actual %v", got)
	}
}

// TestFilterWindowsServiceUnits covers filtering by service name / display name (case-insensitive).
func TestFilterWindowsServiceUnits(t *testing.T) {
	units := parseWindowsServiceCSV(sampleServiceCSV)

	cases := []struct {
		name   string
		filter string
		want   int
	}{
		{"empty filter returns all", "", 4},
		{"exact substring by service name", "Spooler", 1},
		{"case-insensitive by service name", "spooler", 1},
		{"match by display name", "Windows Update", 1},
		{"partial match by display name", "Windows", 3}, // Windows Update / Windows Time / Windows Event Log
		{"no match returns empty", "nonexistent-service-xyz", 0},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := filterWindowsServiceUnits(units, tc.filter)
			if len(got) != tc.want {
				t.Fatalf("filtering %q expected %d entries, actual %d", tc.filter, tc.want, len(got))
			}
		})
	}
}

// TestFilterWindowsServiceUnitsByChineseDisplayName verifies that a non-ASCII display name can be filtered.
func TestFilterWindowsServiceUnitsByChineseDisplayName(t *testing.T) {
	csvText := `"Name","DisplayName","Status"
"svc1","Print Spooler","Running"
"svc2","Windows Update","Stopped"`

	units := parseWindowsServiceCSV(csvText)
	got := filterWindowsServiceUnits(units, "Print")
	if len(got) != 1 {
		t.Fatalf("filtering by the display name expected 1 entry, actual %d", len(got))
	}
	if got[0]["unit"] != "svc1" {
		t.Fatalf("filtering result is wrong: %v", got[0])
	}
}

// TestParseWindowsServiceCSVSkipsMalformedRows verifies that rows with too few columns are skipped without panicking.
func TestParseWindowsServiceCSVSkipsMalformedRows(t *testing.T) {
	csvText := `"Name","DisplayName","Status"
"OnlyName"
"Good","Good Display","Running"`

	units := parseWindowsServiceCSV(csvText)
	// Only "Good" is complete ("OnlyName" has too few columns and is skipped).
	if len(units) != 1 {
		t.Fatalf("expected 1 valid service, actual %d: %v", len(units), units)
	}
	if units[0]["unit"] != "Good" {
		t.Fatalf("parsing the valid service is wrong: %v", units[0])
	}
}

// TestParseWindowsServiceCSVCRLF verifies that CRLF line endings (Windows output) can also be parsed.
func TestParseWindowsServiceCSVCRLF(t *testing.T) {
	csvText := "\"Name\",\"DisplayName\",\"Status\"\r\n\"Spooler\",\"Print Spooler\",\"Running\"\r\n"

	units := parseWindowsServiceCSV(csvText)
	if len(units) != 1 {
		t.Fatalf("CRLF input expected 1 entry, actual %d", len(units))
	}
	if units[0]["unit"] != "Spooler" {
		t.Fatalf("CRLF parsing is wrong: %v", units[0])
	}
	if strings.Contains(units[0]["active"].(string), "\r") {
		t.Fatalf("the status value retains \\r: %q", units[0]["active"])
	}
}
