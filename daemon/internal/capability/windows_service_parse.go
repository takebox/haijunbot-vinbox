package capability

// This file holds the pure parsing functions of the Windows service capability (windows.service.*).
//
// These functions only depend on the standard library and do not reference any platform-specific types, so they **carry no build tags**:
// this way they can be compiled and unit tested directly on Linux / macOS, so that even without a Windows environment
// the correctness of parsing PowerShell CSV output can still be verified.
//
// The accompanying tests are in windows_service_parse_test.go; windows_service_windows.go, which carries the //go:build windows tag,
// is responsible for registering the capability and invoking PowerShell.
//
// Why CSV is used instead of Format-Table:
//   - Format-Table truncates columns according to the console width, and the header is localized with the system language, making parsing fragile.
//   - ConvertTo-Csv -NoTypeInformation outputs a stable comma-separated format, with the first line being the header and
//     subsequent lines being data rows, with quotes escaped per the RFC4180 rules (a " inside a field is written as "").

import (
	"encoding/csv"
	"strings"
)

// parseWindowsServiceCSV parses the output of `Get-Service | Select Name,DisplayName,Status |
// ConvertTo-Csv -NoTypeInformation` and returns the list of service entries.
//
// Each row is converted into fields aligned with parseSystemctlListUnits on the Linux side:
// unit (Name), description (DisplayName), active (Status).
// In addition, display_name is attached for the caller to use directly.
func parseWindowsServiceCSV(out string) []map[string]any {
	rows := parseCSVRows(out)
	units := make([]map[string]any, 0, len(rows))

	// The first line of ConvertTo-Csv -NoTypeInformation is the header (Name,DisplayName,Status),
	// which must be skipped; otherwise an extra fake service named "Name" would appear.
	if len(rows) > 0 && isWindowsServiceListHeader(rows[0]) {
		rows = rows[1:]
	}

	for _, row := range rows {
		// Expected columns: Name,DisplayName,Status
		if len(row) < 3 {
			continue
		}
		name := strings.TrimSpace(row[0])
		if name == "" {
			continue
		}
		units = append(units, map[string]any{
			"unit":         name,
			"display_name": strings.TrimSpace(row[1]),
			"description":  strings.TrimSpace(row[1]),
			"active":       strings.TrimSpace(row[2]),
			"load":         "",
			"sub":          "",
		})
	}

	return units
}

// isWindowsServiceListHeader determines whether a line is the header of the service list CSV.
//
// The criterion: the first column equals "Name" and the second column equals "DisplayName" (case-insensitive),
// avoiding misjudging a service that happens to be named Name as the header.
func isWindowsServiceListHeader(row []string) bool {
	if len(row) < 2 {
		return false
	}
	return strings.EqualFold(strings.TrimSpace(row[0]), "Name") &&
		strings.EqualFold(strings.TrimSpace(row[1]), "DisplayName")
}

// parseWindowsServiceStatusCSV parses the service detail CSV and returns the
// column-name → value mapping of the "first data row".
//
// Expected columns: Name,DisplayName,State,StartMode,ProcessId,PathName,Status
func parseWindowsServiceStatusCSV(out string) map[string]string {
	rows := parseCSVRows(out)
	if len(rows) < 2 {
		return map[string]string{}
	}

	header := rows[0]
	values := rows[1]

	props := make(map[string]string, len(header))
	for i, key := range header {
		key = strings.TrimSpace(key)
		if key == "" {
			continue
		}
		if i < len(values) {
			props[key] = strings.TrimSpace(values[i])
		} else {
			props[key] = ""
		}
	}
	return props
}

// filterWindowsServiceUnits filters service entries by the filter substring (case-insensitive),
// with the match range being unit (service name) and display_name (display name).
func filterWindowsServiceUnits(units []map[string]any, filter string) []map[string]any {
	needle := strings.ToLower(strings.TrimSpace(filter))
	if needle == "" {
		return units
	}

	out := make([]map[string]any, 0, len(units))
	for _, u := range units {
		name := strings.ToLower(asString(u["unit"]))
		display := strings.ToLower(asString(u["display_name"]))
		if strings.Contains(name, needle) || strings.Contains(display, needle) {
			out = append(out, u)
		}
	}
	return out
}

// parseCSVRows parses text into a two-dimensional string table using encoding/csv.
//
// The reason for using the standard library csv rather than a hand-written split: a service display name may contain a comma (such as
// "Windows Update, auto-update"), which a hand-written split would misalign; csv correctly
// handles quote wrapping and "" escaping per RFC4180.
//
// On parse failure it returns the portion already parsed (as tolerant as possible) rather than an error — because this is
// the scenario of "parsing external command output", where it is better to have a few fewer entries than to fail entirely.
func parseCSVRows(out string) [][]string {
	// Normalize newlines: PowerShell outputs CRLF on Windows, and the end may carry \r.
	// It must be normalized first, otherwise encoding/csv treats the trailing \r as part of a new record,
	// producing extra blank lines (this once caused CRLF input to parse into 2 entries instead of 1).
	normalized := strings.ReplaceAll(out, "\r\n", "\n")
	normalized = strings.ReplaceAll(normalized, "\r", "\n")

	trimmed := strings.TrimSpace(normalized)
	if trimmed == "" {
		return nil
	}

	reader := csv.NewReader(strings.NewReader(trimmed))
	// Allow inconsistent field counts (PowerShell occasionally outputs extra columns).
	reader.FieldsPerRecord = -1
	reader.LazyQuotes = true

	records, err := reader.ReadAll()
	if err != nil {
		// Tolerance: try to parse line by line.
		return parseCSVRowsFallback(trimmed)
	}

	rows := make([][]string, 0, len(records))
	for _, rec := range records {
		if len(rec) == 0 {
			continue
		}
		// Skip blank records (lines where all fields are whitespace).
		if isBlankCSVRecord(rec) {
			continue
		}
		rows = append(rows, rec)
	}
	return rows
}

// isBlankCSVRecord determines whether a CSV record consists entirely of blank fields.
func isBlankCSVRecord(rec []string) bool {
	for _, f := range rec {
		if strings.TrimSpace(f) != "" {
			return false
		}
	}
	return true
}

// parseCSVRowsFallback tries to parse line by line when csv parsing fails entirely.
func parseCSVRowsFallback(text string) [][]string {
	rows := make([][]string, 0, 16)
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		reader := csv.NewReader(strings.NewReader(line))
		reader.FieldsPerRecord = -1
		reader.LazyQuotes = true
		rec, err := reader.Read()
		if err != nil || len(rec) == 0 {
			continue
		}
		rows = append(rows, rec)
	}
	return rows
}

// asString safely converts an interface value to a string (returns an empty string for non-strings).
func asString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
