//go:build linux

package capability

import (
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"
)

// Note: the tests in this file do **not** run start/stop/restart on any real systemd unit;
// they only do parameter validation and read-only queries (list / show) to avoid affecting the currently deployed services.

// TestLinuxServiceUnitValidation verifies the unit name whitelist validation.
func TestLinuxServiceUnitValidation(t *testing.T) {
	valid := []string{
		"haijunbot-daemon.service",
		"dbus.service",
		"foo@bar.service",
		"a_b-c.d",
		"UPPER.SERVICE",
		"123.service",
	}
	for _, u := range valid {
		params := map[string]any{"unit": u}
		got, err := resolveLinuxServiceUnit(params)
		if err != nil {
			t.Errorf("a valid unit %q should not error: %v", u, err)
			continue
		}
		if got != u {
			t.Errorf("resolveLinuxServiceUnit(%q) = %q", u, got)
		}
	}

	// Illegal characters and injection attempts must be rejected.
	invalid := []string{
		"foo; rm -rf /",
		"foo bar.service",
		"foo/bar",
		"foo$(whoami)",
		"foo`id`",
		"foo|bar",
		"foo&bar",
		"foo\nbar",
		"--now",
		"foo.service --now",
		"foo'bar",
		"foo\"bar",
	}
	for _, u := range invalid {
		if _, err := resolveLinuxServiceUnit(map[string]any{"unit": u}); err == nil {
			t.Errorf("an invalid unit %q should report an error", u)
		}
	}
}

// TestLinuxServiceUnitMissing verifies a missing/wrong-type unit parameter.
func TestLinuxServiceUnitMissing(t *testing.T) {
	cases := []map[string]any{
		{},
		{"unit": nil},
		{"unit": 123},
		{"unit": ""},
		{"unit": "   "},
	}
	for i, params := range cases {
		if _, err := resolveLinuxServiceUnit(params); err == nil {
			t.Errorf("case %d should report an error: %v", i, params)
		}
	}
}

// TestLinuxServiceActionParameterValidation verifies the parameter validation paths of each action.
//
// These calls return before executing systemctl when the parameters are invalid, so they do not affect real services.
func TestLinuxServiceActionParameterValidation(t *testing.T) {
	for _, action := range []string{"start", "stop", "restart"} {
		handler := handleLinuxServiceAction(action)

		if _, err := handler(map[string]any{}); err == nil {
			t.Errorf("action=%s missing unit should report an error", action)
		}
		if _, err := handler(map[string]any{"unit": "bad;unit"}); err == nil {
			t.Errorf("action=%s invalid unit should report an error", action)
		}
		if _, err := handler(map[string]any{"unit": 42}); err == nil {
			t.Errorf("action=%s wrong-type unit should report an error", action)
		}
	}
}

// TestLinuxServiceStatusParameterValidation verifies the parameter validation of status.
func TestLinuxServiceStatusParameterValidation(t *testing.T) {
	if _, err := handleLinuxServiceStatus(map[string]any{}); err == nil {
		t.Error("missing unit should report an error")
	}
	if _, err := handleLinuxServiceStatus(map[string]any{"unit": "bad unit"}); err == nil {
		t.Error("an invalid unit should report an error")
	}
}

// TestLinuxServiceListParameterValidation verifies the unit_type validation of list.
func TestLinuxServiceListParameterValidation(t *testing.T) {
	if _, err := handleLinuxServiceList(map[string]any{"unit_type": "bad type"}); err == nil {
		t.Error("an invalid unit_type should report an error")
	}
	if _, err := handleLinuxServiceList(map[string]any{"unit_type": "service;rm"}); err == nil {
		t.Error("a unit_type containing injection characters should report an error")
	}
	if _, err := handleLinuxServiceList(map[string]any{"unit_type": "--all"}); err == nil {
		t.Error("a unit_type starting with - should report an error (it would be parsed as a systemctl option)")
	}
	if _, err := handleLinuxServiceList(map[string]any{"all": "yes"}); err == nil {
		t.Error("a wrong-type all should report an error")
	}
}

// hasUserSystemdInstance detects whether an available systemd user instance exists on this machine.
//
// `systemctl --user list-units` exits non-zero (or produces empty output) when there is no user instance,
// which is used to determine whether the environment prerequisite for actually running list is present.
func hasUserSystemdInstance() bool {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, "systemctl", "--user", "list-units", "--no-pager").Output()
	if err != nil {
		return false
	}
	return len(strings.TrimSpace(string(out))) > 0
}

// TestLinuxServiceListReal verifies on a real machine that list returns a result.
//
// Prerequisite: an available systemd user instance exists on this machine (`systemctl --user` responds normally).
// On CI runners the systemctl binary exists but there is no user instance, so list-units returns empty,
// in which case it is skipped rather than failed—the assertion verifies the ability to "parse real output", not the environment itself.
func TestLinuxServiceListReal(t *testing.T) {
	if _, err := exec.LookPath("systemctl"); err != nil {
		t.Skip("no systemctl on this machine, skipping")
	}
	if !hasUserSystemdInstance() {
		t.Skip("no systemd user instance on this machine (systemctl --user unavailable), skipping")
	}

	res, err := handleLinuxServiceList(map[string]any{})
	if err != nil {
		t.Fatalf("failed to list services: %v", err)
	}
	m := res.(map[string]any)
	count := m["count"].(int)
	if count == 0 {
		// An available systemd user instance exists on the CI runner (systemctl --user responds),
		// but there are no active user units, so list-units returns 0 entries.
		// The assertion verifies the ability to "parse real output", not the environment itself, so it is skipped rather than failed.
		t.Skip("no active units under the systemd user instance on this machine, skipping")
	}

	units := m["units"].([]map[string]any)
	for _, u := range units {
		if u["unit"].(string) == "" {
			t.Error("there is an entry with an empty unit name")
		}
		if u["load"].(string) == "" {
			t.Errorf("entry %v is missing load", u["unit"])
		}
		if u["active"].(string) == "" {
			t.Errorf("entry %v is missing active", u["unit"])
		}
		if u["sub"].(string) == "" {
			t.Errorf("entry %v is missing sub", u["unit"])
		}
	}

	// haijunbot-master.service is known to exist on this machine; verify that parsing correctly preserves spaces in the description.
	found := false
	for _, u := range units {
		if u["unit"].(string) == "haijunbot-master.service" {
			found = true
			if desc, _ := u["description"].(string); desc == "" {
				t.Error("the description of haijunbot-master.service should not be empty")
			}
		}
	}
	if !found {
		t.Log("hint: haijunbot-master.service was not found in the list (environment difference, not treated as a failure)")
	}
}

// TestLinuxServiceStatusReal verifies status queries on a real machine.
//
// Only a read-only query on dbus.service is done (a mandatory unit for the user session; the query will not modify it).
// Prerequisite: an available systemd user instance exists on this machine. On CI runners the systemctl binary exists
// but there is no user instance, so `systemctl --user show` exits non-zero, in which case it is skipped rather than failed
// —the assertion verifies the ability to "parse real output", not the environment itself.
func TestLinuxServiceStatusReal(t *testing.T) {
	if _, err := exec.LookPath("systemctl"); err != nil {
		t.Skip("no systemctl on this machine, skipping")
	}
	if !hasUserSystemdInstance() {
		t.Skip("no systemd user instance on this machine (systemctl --user unavailable), skipping")
	}

	res, err := handleLinuxServiceStatus(map[string]any{"unit": "dbus.service"})
	if err != nil {
		t.Fatalf("failed to query status: %v", err)
	}
	m := res.(map[string]any)
	if m["unit"].(string) != "dbus.service" {
		t.Errorf("unit should be dbus.service, actual %v", m["unit"])
	}
	if m["load"].(string) == "" {
		t.Error("load should not be empty")
	}
	if m["active"].(string) == "" {
		t.Error("active should not be empty")
	}
	if m["sub"].(string) == "" {
		t.Error("sub should not be empty")
	}
}

// TestLinuxServiceStatusNonexistent verifies the behavior when querying a non-existent unit.
func TestLinuxServiceStatusNonexistent(t *testing.T) {
	if _, err := exec.LookPath("systemctl"); err != nil {
		t.Skip("no systemctl on this machine, skipping")
	}

	// systemctl show usually still returns 0 for a non-existent unit and outputs an inactive state,
	// so here it only requires "no panic and either a result or a clear error".
	res, err := handleLinuxServiceStatus(map[string]any{"unit": "definitely-not-exist-xyz.service"})
	if err != nil {
		if !strings.Contains(err.Error(), "systemctl") && !strings.Contains(err.Error(), "failed") {
			t.Errorf("the error message is not clear enough: %v", err)
		}
		return
	}
	m := res.(map[string]any)
	if m["unit"].(string) != "definitely-not-exist-xyz.service" {
		t.Errorf("the unit field should echo the requested value, actual %v", m["unit"])
	}
}

// TestParseSystemctlListUnits verifies the pure logic of parsing list-units output.
func TestParseSystemctlListUnits(t *testing.T) {
	sample := `UNIT                     LOAD   ACTIVE SUB     DESCRIPTION
dbus.service             loaded active running D-Bus User Message Bus
gpg-agent.service        loaded active running GnuPG cryptographic agent
foo.service              loaded failed failed  Some Failing Service

Legend: LOAD   → Reflects whether the unit definition was properly loaded.
0 loaded units listed.
`
	units := parseSystemctlListUnits(sample)
	if len(units) != 3 {
		t.Fatalf("it should parse 3 units, actual %d", len(units))
	}

	if units[0]["unit"] != "dbus.service" {
		t.Errorf("the first unit should be dbus.service, actual %v", units[0]["unit"])
	}
	if units[0]["load"] != "loaded" {
		t.Errorf("load should be loaded, actual %v", units[0]["load"])
	}
	if units[0]["active"] != "active" {
		t.Errorf("active should be active, actual %v", units[0]["active"])
	}
	if units[0]["sub"] != "running" {
		t.Errorf("sub should be running, actual %v", units[0]["sub"])
	}
	// The description contains spaces and should be preserved completely.
	if units[0]["description"] != "D-Bus User Message Bus" {
		t.Errorf("description parsed incorrectly: %q", units[0]["description"])
	}

	// The header and the Legend/summary lines should be skipped.
	for _, u := range units {
		name := u["unit"].(string)
		if strings.HasPrefix(name, "UNIT") || strings.HasPrefix(name, "Legend") {
			t.Errorf("the header or a legend line should not be included: %s", name)
		}
	}
}

// TestParseSystemctlShow verifies the pure logic of parsing show output.
func TestParseSystemctlShow(t *testing.T) {
	sample := `Type=notify
LoadState=loaded
ActiveState=active
SubState=running
Description=D-Bus User Message Bus
MainPID=1234
ExecStart={ path=/usr/bin/dbus-daemon ; argv[]=/usr/bin/dbus-daemon --session ; ignore_errors=no }
`
	props := parseSystemctlShow(sample)
	expect := map[string]string{
		"Type":        "notify",
		"LoadState":   "loaded",
		"ActiveState": "active",
		"SubState":    "running",
		"Description": "D-Bus User Message Bus",
		"MainPID":     "1234",
	}
	for k, want := range expect {
		if got := props[k]; got != want {
			t.Errorf("props[%q] = %q, want %q", k, got, want)
		}
	}
	// When a value contains =, the complete value should be preserved (split only on the first =).
	if !strings.Contains(props["ExecStart"], "ignore_errors=no") {
		t.Errorf("ExecStart should preserve the complete value containing =, actual %q", props["ExecStart"])
	}

	// Blank lines and lines without = should be ignored without panicking.
	props2 := parseSystemctlShow("\n\nno-equals-here\n\n")
	if len(props2) != 0 {
		t.Errorf("invalid lines should be ignored, actual parsed %v", props2)
	}
}

// TestLinuxServiceCapabilitiesRegistered verifies that all 5 capabilities are registered.
func TestLinuxServiceCapabilitiesRegistered(t *testing.T) {
	reg := NewRegistry()
	names := []string{
		"linux.service.list",
		"linux.service.status",
		"linux.service.start",
		"linux.service.stop",
		"linux.service.restart",
	}
	for _, name := range names {
		cap, ok := reg.Get(name)
		if !ok {
			t.Fatalf("capability %s is not registered", name)
		}
		if cap.Platform != PlatformLinux {
			t.Errorf("the platform of capability %s should be linux, actual %s", name, cap.Platform)
		}
		if strings.TrimSpace(cap.Description) == "" {
			t.Errorf("capability %s is missing Description", name)
		}
		if cap.Parameters == nil {
			t.Errorf("capability %s is missing Parameters", name)
		}
		if cap.Handler == nil {
			t.Errorf("capability %s is missing Handler", name)
		}
	}
}

// TestCollectLinuxServiceProxyEnv verifies proxy environment variable collection.
func TestCollectLinuxServiceProxyEnv(t *testing.T) {
	t.Setenv("http_proxy", "http://127.0.0.1:7890")
	t.Setenv("HTTPS_PROXY", "http://127.0.0.1:7891")
	t.Setenv("no_proxy", "")

	got := collectLinuxServiceProxyEnv()
	joined := strings.Join(got, " ")
	if !strings.Contains(joined, "http_proxy=http://127.0.0.1:7890") {
		t.Errorf("it should contain http_proxy, actual %v", got)
	}
	if !strings.Contains(joined, "HTTPS_PROXY=http://127.0.0.1:7891") {
		t.Errorf("it should contain HTTPS_PROXY, actual %v", got)
	}
	if strings.Contains(joined, "no_proxy=") {
		t.Errorf("empty-valued variables should not be collected, actual %v", got)
	}
}
