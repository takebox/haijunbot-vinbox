package capability

import (
	"strings"
	"testing"
)

// Assert that no unescaped injection risk appears in the script: user input should not be concatenated into the script as a bare string.
// All user input must be escaped by encodePowerShellText into a single-quoted literal.
func assertNoRawInput(t *testing.T, script, input string) {
	t.Helper()
	if input == "" {
		return
	}
	if strings.Contains(script, input) && !strings.Contains(script, encodePowerShellText(input)) {
		t.Errorf("script contains unescaped user input %q: %s", input, script)
	}
}

func TestBuildWindowsConfigThemeScript(t *testing.T) {
	cases := []struct {
		mode string
		want string // substring the script is expected to contain
	}{
		{"dark", "AppsUseLightTheme -Value 0"},
		{"light", "AppsUseLightTheme -Value 1"},
		{"toggle", "$v = if ($p.AppsUseLightTheme -eq 0)"},
	}
	for _, c := range cases {
		script, err := buildWindowsConfigThemeScript(c.mode)
		if err != nil {
			t.Fatalf("mode=%q unexpected error: %v", c.mode, err)
		}
		if !strings.Contains(script, c.want) {
			t.Errorf("mode=%q script is missing %q, actual: %s", c.mode, c.want, script)
		}
	}

	if _, err := buildWindowsConfigThemeScript("invalid"); err == nil {
		t.Error("an invalid mode should return an error")
	}
}

func TestBuildWindowsConfigPowerPlanScript(t *testing.T) {
	// list does not need plan_id.
	script, err := buildWindowsConfigPowerPlanScript("list", "")
	if err != nil {
		t.Fatalf("list unexpected error: %v", err)
	}
	if !strings.Contains(script, "powercfg /list") {
		t.Errorf("list script is missing powercfg /list: %s", script)
	}

	// set needs plan_id, and it is escaped.
	planID := "381b4222-f694-41f0-9685-ff5bb260df2e"
	script, err = buildWindowsConfigPowerPlanScript("set", planID)
	if err != nil {
		t.Fatalf("set unexpected error: %v", err)
	}
	if !strings.Contains(script, "powercfg /setactive "+encodePowerShellText(planID)) {
		t.Errorf("set script did not correctly escape plan_id: %s", script)
	}
	assertNoRawInput(t, script, planID)

	// set missing plan_id errors.
	if _, err := buildWindowsConfigPowerPlanScript("set", ""); err == nil {
		t.Error("set missing plan_id should return an error")
	}

	// invalid action.
	if _, err := buildWindowsConfigPowerPlanScript("bogus", ""); err == nil {
		t.Error("an invalid action should return an error")
	}
}

func TestBuildWindowsConfigProxyScript(t *testing.T) {
	// get.
	script, err := buildWindowsConfigProxyScript("get", "", "")
	if err != nil {
		t.Fatalf("get unexpected error: %v", err)
	}
	if !strings.Contains(script, "ProxyEnable") {
		t.Errorf("get script is missing ProxyEnable: %s", script)
	}

	// disable.
	script, err = buildWindowsConfigProxyScript("disable", "", "")
	if err != nil {
		t.Fatalf("disable unexpected error: %v", err)
	}
	if !strings.Contains(script, "ProxyEnable -Value 0") {
		t.Errorf("disable script did not set ProxyEnable=0: %s", script)
	}

	// enable default address.
	script, err = buildWindowsConfigProxyScript("enable", "", "")
	if err != nil {
		t.Fatalf("enable unexpected error: %v", err)
	}
	if !strings.Contains(script, encodePowerShellText("127.0.0.1:7890")) {
		t.Errorf("enable script is missing the default proxy address: %s", script)
	}

	// set needs server, and server/bypass are escaped (including a single-quote injection attempt).
	server := "127.0.0.1:7890'; Remove-Item -Recurse C:\\ -Force; '"
	bypass := "localhost;192.168.*"
	script, err = buildWindowsConfigProxyScript("set", server, bypass)
	if err != nil {
		t.Fatalf("set unexpected error: %v", err)
	}
	if !strings.Contains(script, encodePowerShellText(server)) {
		t.Errorf("set script did not correctly escape server: %s", script)
	}
	if !strings.Contains(script, encodePowerShellText(bypass)) {
		t.Errorf("set script did not correctly escape bypass: %s", script)
	}
	assertNoRawInput(t, script, server)
	assertNoRawInput(t, script, bypass)

	// set missing server errors.
	if _, err := buildWindowsConfigProxyScript("set", "", ""); err == nil {
		t.Error("set missing server should return an error")
	}

	// invalid action.
	if _, err := buildWindowsConfigProxyScript("bogus", "", ""); err == nil {
		t.Error("an invalid action should return an error")
	}
}

func TestBuildWindowsConfigScreenTimeoutScript(t *testing.T) {
	// get.
	script, err := buildWindowsConfigScreenTimeoutScript("get", 0)
	if err != nil {
		t.Fatalf("get unexpected error: %v", err)
	}
	if !strings.Contains(script, "powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE") {
		t.Errorf("get script error: %s", script)
	}

	// set normal.
	script, err = buildWindowsConfigScreenTimeoutScript("set", 10)
	if err != nil {
		t.Fatalf("set unexpected error: %v", err)
	}
	if !strings.Contains(script, "monitor-timeout-ac 10") || !strings.Contains(script, "monitor-timeout-dc 10") {
		t.Errorf("set script error: %s", script)
	}

	// set negative errors.
	if _, err := buildWindowsConfigScreenTimeoutScript("set", -1); err == nil {
		t.Error("set with negative minutes should return an error")
	}

	// invalid action.
	if _, err := buildWindowsConfigScreenTimeoutScript("bogus", 0); err == nil {
		t.Error("an invalid action should return an error")
	}
}

func TestBuildWindowsConfigRemoteDesktopScript(t *testing.T) {
	// get.
	script, err := buildWindowsConfigRemoteDesktopScript("get")
	if err != nil {
		t.Fatalf("get unexpected error: %v", err)
	}
	if !strings.Contains(script, "fDenyTSConnections") {
		t.Errorf("get script error: %s", script)
	}

	// enable sets 0.
	script, err = buildWindowsConfigRemoteDesktopScript("enable")
	if err != nil {
		t.Fatalf("enable unexpected error: %v", err)
	}
	if !strings.Contains(script, "fDenyTSConnections -Value 0") {
		t.Errorf("enable script error: %s", script)
	}

	// disable sets 1.
	script, err = buildWindowsConfigRemoteDesktopScript("disable")
	if err != nil {
		t.Fatalf("disable unexpected error: %v", err)
	}
	if !strings.Contains(script, "fDenyTSConnections -Value 1") {
		t.Errorf("disable script error: %s", script)
	}

	// invalid action.
	if _, err := buildWindowsConfigRemoteDesktopScript("bogus"); err == nil {
		t.Error("an invalid action should return an error")
	}
}

func TestBuildWindowsConfigStartupScript(t *testing.T) {
	// list.
	script, err := buildWindowsConfigStartupScript("list", "")
	if err != nil {
		t.Fatalf("list unexpected error: %v", err)
	}
	if !strings.Contains(script, "Get-ChildItem") {
		t.Errorf("list script error: %s", script)
	}

	// disable needs name and it is escaped (including an injection attempt).
	name := "myapp.lnk'; Remove-Item -Recurse C:\\ -Force; '"
	script, err = buildWindowsConfigStartupScript("disable", name)
	if err != nil {
		t.Fatalf("disable unexpected error: %v", err)
	}
	if !strings.Contains(script, encodePowerShellText(name)) {
		t.Errorf("disable script did not correctly escape name: %s", script)
	}
	assertNoRawInput(t, script, name)

	// enable needs name.
	script, err = buildWindowsConfigStartupScript("enable", "myapp.lnk")
	if err != nil {
		t.Fatalf("enable unexpected error: %v", err)
	}
	if !strings.Contains(script, ".disabled") {
		t.Errorf("enable script should handle .disabled restoration: %s", script)
	}

	// missing name errors.
	if _, err := buildWindowsConfigStartupScript("disable", ""); err == nil {
		t.Error("disable missing name should return an error")
	}

	// invalid action.
	if _, err := buildWindowsConfigStartupScript("bogus", ""); err == nil {
		t.Error("an invalid action should return an error")
	}
}

func TestTrimWindowsOutput(t *testing.T) {
	if got := trimWindowsOutput("  hello  \r\n"); got != "hello" {
		t.Errorf("trimWindowsOutput result error: %q", got)
	}
	if got := trimWindowsOutput(""); got != "" {
		t.Errorf("trimWindowsOutput on an empty string should return empty: %q", got)
	}
}
