//go:build linux

package capability

import (
	"os"
	"strings"
	"testing"
	"time"
)

// execLinuxScript is a test helper: it executes linux.script.exec through the registry and asserts success.
func execLinuxScript(t *testing.T, params map[string]any) map[string]any {
	t.Helper()
	r := NewRegistry()
	res := r.Execute("linux.script.exec", params)
	if !res.Success {
		t.Fatalf("execution failed: %s", res.Error)
	}
	data, ok := res.Data.(map[string]any)
	if !ok {
		t.Fatalf("the return type should be map[string]any, actual %T", res.Data)
	}
	return data
}

// TestLinuxScriptRegistered verifies that the capability is registered and the platform is correct.
func TestLinuxScriptRegistered(t *testing.T) {
	r := NewRegistry()
	c, ok := r.Get("linux.script.exec")
	if !ok {
		t.Fatal("linux.script.exec should be registered")
	}
	if c.Platform != PlatformLinux {
		t.Fatalf("the platform should be linux, actual %q", c.Platform)
	}
	if c.Description == "" {
		t.Fatal("Description should not be empty")
	}
	if len(c.Parameters) == 0 {
		t.Fatal("Parameters should not be empty")
	}
	// It should appear in the Linux platform list.
	found := false
	for _, cap := range r.ListForPlatform(PlatformLinux) {
		if cap.Name == "linux.script.exec" {
			found = true
		}
	}
	if !found {
		t.Fatal("linux.script.exec should appear in the Linux platform capability list")
	}
}

// TestLinuxScriptMissingParam covers missing parameters and type errors.
func TestLinuxScriptMissingParam(t *testing.T) {
	r := NewRegistry()

	cases := []struct {
		name   string
		params map[string]any
		want   string
	}{
		{"no parameters at all", nil, "missing required parameter script"},
		{"script is nil", map[string]any{"script": nil}, "missing required parameter script"},
		{"script is an empty string", map[string]any{"script": ""}, "cannot be empty"},
		{"script is whitespace", map[string]any{"script": "   "}, "cannot be empty"},
		{"script has the wrong type", map[string]any{"script": 123}, "must be a string"},
		{"timeout_ms has the wrong type", map[string]any{"script": "echo hi", "timeout_ms": "abc"}, "must be an integer"},
		{"timeout_ms is 0", map[string]any{"script": "echo hi", "timeout_ms": 0}, "must be a positive integer"},
		{"timeout_ms is negative", map[string]any{"script": "echo hi", "timeout_ms": -1}, "must be a positive integer"},
		{"cwd has the wrong type", map[string]any{"script": "echo hi", "cwd": 1}, "cwd must be a string"},
		{"env has the wrong type", map[string]any{"script": "echo hi", "env": "not-a-map"}, "env must be an object"},
		{"env value has the wrong type", map[string]any{"script": "echo hi", "env": map[string]any{"A": 1}}, "env.A must be a string"},
		{"stdin has the wrong type", map[string]any{"script": "echo hi", "stdin": 1}, "stdin must be a string"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := r.Execute("linux.script.exec", tc.params)
			if res.Success {
				t.Fatalf("it should fail but actually succeeded: %+v", res.Data)
			}
			if !strings.Contains(res.Error, tc.want) {
				t.Fatalf("the error message should contain %q, actual %q", tc.want, res.Error)
			}
		})
	}
}

// TestLinuxScriptInterpreterWhitelist covers interpreter whitelist validation.
func TestLinuxScriptInterpreterWhitelist(t *testing.T) {
	r := NewRegistry()

	// An illegal interpreter must be rejected.
	illegal := []string{
		"/bin/rm",
		"rm",
		"/usr/bin/python3",
		"/bin/sh -c",   // with argument injection
		"sh; rm -rf /", // command concatenation injection
		"../../bin/sh",
		"",
	}
	for _, interp := range illegal {
		if interp == "" {
			continue // an empty string means the default is used, which is a legal case
		}
		res := r.Execute("linux.script.exec", map[string]any{
			"script":      "echo hi",
			"interpreter": interp,
		})
		if res.Success {
			t.Fatalf("the illegal interpreter %q should be rejected", interp)
		}
		if !strings.Contains(res.Error, "not in the whitelist") {
			t.Fatalf("the error message for the illegal interpreter %q should mention the whitelist, actual %q", interp, res.Error)
		}
	}

	// Interpreters within the whitelist should be available (using the existence-checked /bin/sh and /bin/bash).
	for _, interp := range []string{"/bin/sh", "/bin/bash"} {
		res := r.Execute("linux.script.exec", map[string]any{
			"script":      "echo ok",
			"interpreter": interp,
		})
		if !res.Success {
			t.Fatalf("the whitelisted interpreter %q should be available, actual error: %s", interp, res.Error)
		}
	}

	// When interpreter is not passed, it defaults to /bin/sh.
	data := execLinuxScript(t, map[string]any{"script": "echo default-interp"})
	if got := strings.TrimSpace(data["stdout"].(string)); got != "default-interp" {
		t.Fatalf("the default interpreter should execute successfully, actual stdout=%q", got)
	}
}

// TestLinuxScriptEcho covers normal execution: stdout / exit_code / duration.
func TestLinuxScriptEcho(t *testing.T) {
	data := execLinuxScript(t, map[string]any{"script": "echo hello-haijunbot"})

	if got := strings.TrimSpace(data["stdout"].(string)); got != "hello-haijunbot" {
		t.Fatalf("stdout should be hello-haijunbot, actual %q", got)
	}
	if got := data["exit_code"].(int); got != 0 {
		t.Fatalf("exit_code should be 0, actual %d", got)
	}
	if data["timed_out"].(bool) {
		t.Fatal("it should not time out")
	}
	if got := data["duration_ms"].(int64); got < 0 {
		t.Fatalf("duration_ms should not be negative, actual %d", got)
	}
	if got := data["stderr"].(string); got != "" {
		t.Fatalf("stderr should be empty, actual %q", got)
	}
}

// TestLinuxScriptStderrAndExitCode covers a non-zero exit code and stderr passthrough.
func TestLinuxScriptStderrAndExitCode(t *testing.T) {
	data := execLinuxScript(t, map[string]any{
		"script": "echo oops >&2; exit 3",
	})

	if got := data["exit_code"].(int); got != 3 {
		t.Fatalf("exit_code should be 3, actual %d", got)
	}
	if got := strings.TrimSpace(data["stderr"].(string)); got != "oops" {
		t.Fatalf("stderr should be oops, actual %q", got)
	}
	if data["timed_out"].(bool) {
		t.Fatal("it should not time out")
	}
}

// TestLinuxScriptEnvAndCwd covers the effect of the env and cwd parameters.
func TestLinuxScriptEnvAndCwd(t *testing.T) {
	dir := t.TempDir()

	data := execLinuxScript(t, map[string]any{
		"script": "echo $HAIJUNBOT_TEST_VAR; pwd",
		"cwd":    dir,
		"env":    map[string]string{"HAIJUNBOT_TEST_VAR": "env-works"},
	})

	lines := strings.Split(strings.TrimSpace(data["stdout"].(string)), "\n")
	if len(lines) != 2 {
		t.Fatalf("expected 2 lines of output, actual %q", data["stdout"])
	}
	if lines[0] != "env-works" {
		t.Fatalf("env did not take effect, the first line should be env-works, actual %q", lines[0])
	}
	// t.TempDir may be a /var symbolic link on macOS; on Linux a direct comparison is fine.
	if lines[1] != dir {
		t.Fatalf("cwd did not take effect, want %q, actual %q", dir, lines[1])
	}
}

// TestLinuxScriptStdin covers the stdin parameter.
func TestLinuxScriptStdin(t *testing.T) {
	data := execLinuxScript(t, map[string]any{
		"script": "cat",
		"stdin":  "from-stdin",
	})
	if got := strings.TrimSpace(data["stdout"].(string)); got != "from-stdin" {
		t.Fatalf("stdin was not passed through, stdout should be from-stdin, actual %q", got)
	}
}

// TestLinuxScriptTimeout covers timeout: sleep 5 + timeout 500ms should time out with a non-zero exit code.
func TestLinuxScriptTimeout(t *testing.T) {
	start := time.Now()
	data := execLinuxScript(t, map[string]any{
		"script":     "sleep 5; echo should-not-print",
		"timeout_ms": 500,
	})
	elapsed := time.Since(start)

	if !data["timed_out"].(bool) {
		t.Fatal("it should be marked as timed out")
	}
	if got := data["exit_code"].(int); got == 0 {
		t.Fatalf("the exit_code on timeout should not be 0, actual %d", got)
	}
	if strings.Contains(data["stdout"].(string), "should-not-print") {
		t.Fatal("subsequent content should not be output after a timeout")
	}
	// It must return promptly after the timeout and must not actually wait the full 5 seconds.
	if elapsed > 4*time.Second {
		t.Fatalf("timeout control did not take effect, actual elapsed %v", elapsed)
	}
}

// TestLinuxScriptTimeoutKillsProcessGroup verifies that a timeout terminates the entire process group (including child processes).
func TestLinuxScriptTimeoutKillsProcessGroup(t *testing.T) {
	dir := t.TempDir()
	marker := dir + "/child-alive"

	// The parent script starts a child process in the background that writes a marker file, then sleeps for a long time itself.
	// If only the parent process is killed without killing the process group, the child will survive and write the marker file.
	script := "sh -c 'sleep 2; touch " + marker + "' & sleep 30"

	data := execLinuxScript(t, map[string]any{
		"script":     script,
		"timeout_ms": 500,
	})
	if !data["timed_out"].(bool) {
		t.Fatal("it should time out")
	}

	// Wait beyond the time the child was scheduled to write the marker, confirming that it was terminated as well.
	time.Sleep(2500 * time.Millisecond)
	if _, err := os.Stat(marker); err == nil {
		t.Fatal("the child process was not terminated: the marker file was created, which means the process group was not cleaned up")
	}
}

// TestLinuxScriptOutputTruncation verifies that overly long output is truncated and the truncated flag is set.
func TestLinuxScriptOutputTruncation(t *testing.T) {
	// Generate about 2MB of output, exceeding the 1MB limit.
	data := execLinuxScript(t, map[string]any{
		"script": "head -c 2097152 /dev/zero | tr '\\0' 'a'",
	})

	if !data["truncated"].(bool) {
		t.Fatal("overly long output should set truncated=true")
	}
	if got := len(data["stdout"].(string)); got != linuxScriptMaxOutputBytes {
		t.Fatalf("stdout should be truncated to %d bytes, actual %d", linuxScriptMaxOutputBytes, got)
	}
}

// TestLinuxScriptTimeoutUpperBound verifies the timeout_ms upper bound validation.
func TestLinuxScriptTimeoutUpperBound(t *testing.T) {
	r := NewRegistry()
	res := r.Execute("linux.script.exec", map[string]any{
		"script":     "echo hi",
		"timeout_ms": linuxScriptMaxTimeoutMS + 1,
	})
	if res.Success {
		t.Fatal("a timeout_ms exceeding the upper bound should be rejected")
	}
	if !strings.Contains(res.Error, "exceeds the maximum") {
		t.Fatalf("the error message should mention exceeding the maximum, actual %q", res.Error)
	}
}
