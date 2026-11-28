package capability

// This file holds the pure parsing functions of the Windows application list capability (windows.app.list).
//
// These functions only depend on the standard library and do not reference any platform-specific types, so they **carry no build tags**:
// this way they can be compiled and unit tested directly on Linux / macOS, so that even without a Windows environment
// the correctness of parsing PowerShell output can still be verified (the local development environment is Linux).
//
// The accompanying tests are in windows_app_parse_test.go; windows_app_windows.go, which carries the //go:build windows tag,
// is responsible for registering the capability and invoking PowerShell.
//
// Why it was changed from "per-key reg query" to "a single CSV"
// ============================================================
// The earlier implementation used N+1 PowerShell launches: first enumerate the subkeys of 3 Uninstall root keys,
// then launch powershell.exe separately for **each subkey** to read its values. A real machine's registry usually has
// 200~500 uninstall entries, i.e. 200~500 process cold starts (about 0.5~1s each), far exceeding the
// 60s timeout in total — this is exactly the root cause of the windows.app.list timeout on real machines.
//
// Now it is changed to **one** PowerShell call that exports all uninstall entries under the three root keys as CSV in one go,
// parsed on the Go side. The number of process launches drops from N+1 to 1, and the time drops from minutes to seconds.
//
// The reason for choosing CSV is consistent with the service capability: ConvertTo-Csv -NoTypeInformation outputs a stable
// comma-separated format, and commas/quotes inside fields are escaped per RFC4180 (application names and publishers often contain commas,
// such as "Microsoft Corporation, Inc."), which hand-written splitting would misalign.

import (
	"strings"
)

// splitWindowsArgs splits the launch parameter string into a parameter list.
//
// Purpose: windows.app.start needs to pass the user-provided args string to os/exec to launch a process.
// Here strings.Fields is used to split on whitespace, **without going through a shell**, so no command injection
// occurs (unlike concatenating directly into a command line for cmd.exe to parse). When args is empty it returns nil.
//
// Note: this function does not do quote parsing (e.g. "a b" is not merged into a single parameter). If a single
// parameter with spaces must be supported, a more complete parser should be used; for launching applications, splitting
// on whitespace already satisfies the vast majority of scenarios and avoids the injection surface that quote parsing brings.
func splitWindowsArgs(args string) []string {
	trimmed := strings.TrimSpace(args)
	if trimmed == "" {
		return nil
	}
	return strings.Fields(trimmed)
}

// parseWindowsAppCSV parses the output of `Get-ItemProperty ... | Select ... |
// ConvertTo-Csv -NoTypeInformation` and returns the list of application entries.
//
// Expected columns (order-insensitive, values taken by header name):
//
//	DisplayName, DisplayVersion, Publisher, InstallLocation, InstallDate, SystemComponent
//
// The filtering rules are consistent with parseWindowsUninstallEntry:
//   - DisplayName empty → skip;
//   - SystemComponent true → skip (internal system component, not a user-visible application).
//
// The returned map field names are fully identical to the old implementation (name/version/publisher/install_location/
// install_date), so that the upper-layer handleWindowsAppList and existing tests need no changes.
func parseWindowsAppCSV(out string) []map[string]any {
	rows := parseCSVRows(out)
	if len(rows) < 2 {
		return nil
	}

	header := rows[0]
	// Build a "column name → index" map to avoid depending on column order (PowerShell's Select-Object
	// keeps the given order, but looking up by name is more robust).
	index := make(map[string]int, len(header))
	for i, name := range header {
		index[strings.ToLower(strings.TrimSpace(name))] = i
	}

	// If the header does not contain DisplayName, the output is not the expected application list (e.g. script error text),
	// so return empty directly and let the upper layer present count=0, rather than treating the error text as an application name.
	if _, ok := index["displayname"]; !ok {
		return nil
	}

	apps := make([]map[string]any, 0, len(rows)-1)
	for _, row := range rows[1:] {
		cell := func(key string) string {
			i, ok := index[key]
			if !ok || i >= len(row) {
				return ""
			}
			return strings.TrimSpace(row[i])
		}

		name := cell("displayname")
		if name == "" {
			continue
		}
		if isWindowsRegTrue(cell("systemcomponent")) {
			continue
		}

		app := map[string]any{
			"name": name,
		}
		if v := cell("displayversion"); v != "" {
			app["version"] = v
		}
		if v := cell("publisher"); v != "" {
			app["publisher"] = v
		}
		if v := cell("installlocation"); v != "" {
			app["install_location"] = v
		}
		if v := cell("installdate"); v != "" {
			app["install_date"] = v
		}
		apps = append(apps, app)
	}

	return apps
}
