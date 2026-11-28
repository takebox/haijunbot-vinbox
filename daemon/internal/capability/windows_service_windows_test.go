//go:build windows

package capability

// This file unit-tests the pure functions in windows_service_windows.go that "do not depend on a real Windows runtime environment":
// the service name validation validateWindowsServiceName.
//
// It is placed separately in a file carrying the //go:build windows tag because validateWindowsServiceName
// is defined in windows_service_windows.go (which also carries the windows tag) and is invisible on Linux,
// so the test must carry the same tag in order to participate in the Windows build together with the target function.
//
// Verification method: CGO_ENABLED=0 GOOS=windows go test -c compiles successfully (the .exe cannot be run locally).

import "testing"

// TestValidateWindowsServiceName covers various values of the service name whitelist validation.
func TestValidateWindowsServiceName(t *testing.T) {
	valid := []string{
		"Spooler",
		"wuauserv",
		"W32Time",
		"EventLog",
		"my-service",
		"my.service",
		"svc@host",
		"my_service",
		"Print Spooler",     // contains a space
		"Print Backend Processor", // former Chinese name
		"Windows Update zh", // mixed Chinese-English with a space
	}

	for _, name := range valid {
		if err := validateWindowsServiceName(name); err != nil {
			t.Errorf("expected %q to be valid, actual error: %v", name, err)
		}
	}

	invalid := []struct {
		name string
		desc string
	}{
		{"", "empty string"},
		{"   ", "pure whitespace"},
		{"-Name", "starts with - (would be treated as an option)"},
		{"-", "single hyphen"},
		{"svc;rm", "contains a semicolon (command injection attempt)"},
		{"svc|whoami", "contains a pipe character"},
		{"svc&calc", "contains an ampersand"},
		{"svc$(whoami)", "contains a subexpression"},
		{"svc`n", "contains a backtick"},
		{"svc'quote", "contains a single quote"},
		{`svc"quote`, "contains a double quote"},
		{"svc/path", "contains a slash"},
		{"svc\\path", "contains a backslash"},
	}

	for _, tc := range invalid {
		if err := validateWindowsServiceName(tc.name); err == nil {
			t.Errorf("expected %q (%s) to be invalid, but it passed validation", tc.name, tc.desc)
		}
	}
}

// TestValidateWindowsServiceNameTrimsSpace verifies that leading/trailing whitespace is ignored and the result is still judged correctly.
func TestValidateWindowsServiceNameTrimsSpace(t *testing.T) {
	// Leading/trailing spaces should be trimmed before validation, so " Spooler " is valid.
	if err := validateWindowsServiceName(" Spooler "); err != nil {
		t.Errorf("a service name with leading/trailing spaces should be valid, actual error: %v", err)
	}
	// But " -x " starts with - after trimming, so it should be rejected.
	if err := validateWindowsServiceName(" -x "); err == nil {
		t.Error("a service name starting with - after trimming should be rejected, but it passed")
	}
}
