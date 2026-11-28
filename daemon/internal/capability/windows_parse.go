package capability

import (
	"strconv"
	"strings"
)

// This file holds the pure parsing functions of the Windows capabilities.
//
// These functions only depend on the standard library and do not reference any platform-specific types, so they **carry no build tags**:
// this way they can be compiled and unit tested directly on Linux / macOS, so that even without a Windows environment
// the correctness of parsing reg.exe / tasklist output can still be verified.
//
// The accompanying tests are in windows_parse_test.go.

// This file also provides several cross-platform small utility functions (splitNonEmptyLines, etc.),
// for use by capability files carrying the //go:build windows tag.

// splitNonEmptyLines splits by line and removes blank lines and leading/trailing whitespace.
func splitNonEmptyLines(s string) []string {
	raw := strings.Split(strings.ReplaceAll(s, "\r\n", "\n"), "\n")
	out := make([]string, 0, len(raw))
	for _, line := range raw {
		line = strings.TrimSpace(line)
		if line != "" {
			out = append(out, line)
		}
	}
	return out
}

// firstNonEmptyLine returns the first non-empty line (with leading/trailing whitespace already removed).
func firstNonEmptyLine(s string) string {
	lines := splitNonEmptyLines(s)
	if len(lines) == 0 {
		return ""
	}
	return lines[0]
}

// splitCSVLine splits a CSV line by comma and removes the quotes and whitespace on both sides of each field.
//
// This does not handle the full CSV semantics of embedded commas (quote-wrapped) within a field: Windows product names,
// version numbers, and build numbers contain no commas, so simplified parsing is sufficient to cover the actual values.
func splitCSVLine(line string) []string {
	parts := strings.Split(line, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		out = append(out, strings.Trim(strings.TrimSpace(p), `"`))
	}
	return out
}

// indexOfFold finds, case-insensitively, the index of the first match among the candidate names; returns -1 when there is no match.
func indexOfFold(header []string, candidates ...string) int {
	for i, h := range header {
		for _, c := range candidates {
			if strings.EqualFold(strings.TrimSpace(h), c) {
				return i
			}
		}
	}
	return -1
}

// minInt returns the smaller of two integers.
func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// parseWindowsOSVersionCSV parses the output of PowerShell ConvertTo-Csv or wmic /format:csv.
//
// The common point of the two outputs is that the first line is the header and subsequent lines are comma-separated values; this function locates fields by header,
// so it is insensitive to column order and can also be compatible with both sources at once.
func parseWindowsOSVersionCSV(out string) (name, version, build string) {
	lines := splitNonEmptyLines(out)
	if len(lines) < 2 {
		return "", "", ""
	}

	header := splitCSVLine(lines[0])
	idxName := indexOfFold(header, "ProductName", "Caption", "Name")
	idxVersion := indexOfFold(header, "DisplayVersion", "Version")
	idxBuild := indexOfFold(header, "CurrentBuildNumber", "BuildNumber")

	for _, line := range lines[1:] {
		fields := splitCSVLine(line)
		if len(fields) == 0 {
			continue
		}
		if idxName >= 0 && idxName < len(fields) && name == "" {
			name = fields[idxName]
		}
		if idxVersion >= 0 && idxVersion < len(fields) && version == "" {
			version = fields[idxVersion]
		}
		if idxBuild >= 0 && idxBuild < len(fields) && build == "" {
			build = fields[idxBuild]
		}
		if name != "" && version != "" && build != "" {
			break
		}
	}
	return name, version, build
}

// parseWindowsTasklistCSV parses the output of tasklist /FO CSV /NH.
//
// Each line looks like: "chrome.exe","1234","Console","1","123,456 K".
// The field order is fixed: image name, PID, session name, session number, memory usage.
func parseWindowsTasklistCSV(out string) []map[string]any {
	lines := splitNonEmptyLines(out)
	procs := make([]map[string]any, 0, len(lines))
	for _, line := range lines {
		fields := splitCSVLine(line)
		if len(fields) < 2 {
			continue
		}
		pid, err := strconv.Atoi(strings.TrimSpace(fields[1]))
		if err != nil {
			continue
		}
		item := map[string]any{
			"name": fields[0],
			"pid":  pid,
		}
		if len(fields) >= 3 {
			item["session_name"] = fields[2]
		}
		if len(fields) >= 4 {
			if sessionID, err := strconv.Atoi(strings.TrimSpace(fields[3])); err == nil {
				item["session_id"] = sessionID
			}
		}
		if len(fields) >= 5 {
			item["mem_usage"] = fields[4]
		}
		procs = append(procs, item)
	}
	return procs
}

// parseWindowsRegSubKeys parses the output of reg query <key> and extracts the subkey names.
//
// The output looks like (the first line is the path of the queried key itself, and each subsequent line is a full subkey path):
//
//	HKEY_LOCAL_MACHINE\SOFTWARE\...\Uninstall
//	    HKEY_LOCAL_MACHINE\SOFTWARE\...\Uninstall\{GUID}
//	    HKEY_LOCAL_MACHINE\SOFTWARE\...\Uninstall\AppName
//
// This function takes the part after the last backslash of each line as the subkey name.
func parseWindowsRegSubKeys(out string) []string {
	lines := splitNonEmptyLines(out)
	if len(lines) == 0 {
		return nil
	}
	// The first line is the path of the queried key itself; skip it.
	subKeys := make([]string, 0, len(lines)-1)
	for _, line := range lines[1:] {
		if idx := strings.LastIndex(line, `\`); idx >= 0 && idx+1 < len(line) {
			subKeys = append(subKeys, line[idx+1:])
		}
	}
	return subKeys
}

// parseWindowsUninstallEntry parses the reg query output of a single uninstall entry and returns the application information.
//
// The output looks like:
//
//	HKEY_LOCAL_MACHINE\...\Uninstall\{GUID}
//	    DisplayName    REG_SZ    Google Chrome
//	    DisplayVersion    REG_SZ    120.0.1
//	    Publisher    REG_SZ    Google LLC
//	    SystemComponent    REG_DWORD    0x1
//
// Returning nil means the entry should be skipped: DisplayName is missing, or SystemComponent is 1.
func parseWindowsUninstallEntry(out string) map[string]any {
	values := parseWindowsRegValues(out)
	if len(values) == 0 {
		return nil
	}

	name := strings.TrimSpace(values["DisplayName"])
	if name == "" {
		return nil
	}
	// SystemComponent=1 means this is an internal system component and is not listed as a user-visible application.
	if isWindowsRegTrue(values["SystemComponent"]) {
		return nil
	}

	app := map[string]any{
		"name": name,
	}
	if v := strings.TrimSpace(values["DisplayVersion"]); v != "" {
		app["version"] = v
	}
	if v := strings.TrimSpace(values["Publisher"]); v != "" {
		app["publisher"] = v
	}
	if v := strings.TrimSpace(values["InstallLocation"]); v != "" {
		app["install_location"] = v
	}
	if v := strings.TrimSpace(values["InstallDate"]); v != "" {
		app["install_date"] = v
	}
	return app
}

// parseWindowsRegValues parses the output of reg query <key> into a "value name → value content" map.
//
// Each line has the format:    <name>    <type>    <data>
// The name and data are separated by several spaces, and the type is REG_SZ / REG_DWORD / REG_EXPAND_SZ, etc.
// The first line (the key path itself) contains no type marker and is naturally skipped.
func parseWindowsRegValues(out string) map[string]string {
	values := make(map[string]string)
	for _, line := range splitNonEmptyLines(out) {
		fields := strings.Fields(line)
		if len(fields) < 3 {
			continue
		}
		// Find the position of the type marker field; before it is the value name and after it is the data.
		typeIdx := -1
		for i, f := range fields {
			if strings.HasPrefix(f, "REG_") {
				typeIdx = i
				break
			}
		}
		if typeIdx <= 0 || typeIdx+1 >= len(fields) {
			continue
		}
		name := strings.Join(fields[:typeIdx], " ")
		data := strings.Join(fields[typeIdx+1:], " ")
		values[name] = data
	}
	return values
}

// isWindowsRegTrue determines whether a registry value represents "true".
//
// The 1 of REG_DWORD appears in the output as 0x1, while REG_SZ is simply "1".
func isWindowsRegTrue(raw string) bool {
	v := strings.ToLower(strings.TrimSpace(raw))
	return v == "1" || v == "0x1" || v == "true" || v == "yes"
}
