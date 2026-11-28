//go:build linux

package capability

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"testing"
	"time"
)

// TestLinuxProcessRegistered verifies that the process capabilities are registered and the platform is correct.
func TestLinuxProcessRegistered(t *testing.T) {
	r := NewRegistry()
	for _, name := range []string{"linux.process.list", "linux.process.kill"} {
		c, ok := r.Get(name)
		if !ok {
			t.Fatalf("%s should be registered", name)
		}
		if c.Platform != PlatformLinux {
			t.Fatalf("the platform of %s should be linux, actual %q", name, c.Platform)
		}
		if c.Description == "" {
			t.Fatalf("the Description of %s should not be empty", name)
		}
		if len(c.Parameters) == 0 {
			t.Fatalf("the Parameters of %s should not be empty", name)
		}
	}
}

// TestLinuxProcessListReturnsSelf verifies that the process list contains at least the current test process.
func TestLinuxProcessListReturnsSelf(t *testing.T) {
	r := NewRegistry()
	res := r.Execute("linux.process.list", map[string]any{"limit": 5000})
	if !res.Success {
		t.Fatalf("execution failed: %s", res.Error)
	}
	data, ok := res.Data.(map[string]any)
	if !ok {
		t.Fatalf("the return type should be map[string]any, actual %T", res.Data)
	}
	procs, ok := data["processes"].([]map[string]any)
	if !ok {
		t.Fatalf("the type of processes should be []map[string]any, actual %T", data["processes"])
	}
	if len(procs) == 0 {
		t.Fatal("the process list should not be empty")
	}

	self := os.Getpid()
	found := false
	for _, p := range procs {
		if p["pid"] == self {
			found = true
			// The fields of the process itself should have values.
			if p["comm"] == "" {
				t.Error("the comm of the process itself should not be empty")
			}
			if p["cmdline"] == "" {
				t.Error("the cmdline of the process itself should not be empty")
			}
			if p["state"] == "" {
				t.Error("the state of the process itself should not be empty")
			}
			if p["ppid"] == 0 {
				t.Error("the ppid of the process itself should not be 0")
			}
		}
	}
	if !found {
		t.Fatalf("the process list should contain the current process pid=%d", self)
	}
}

// TestLinuxProcessListFilter verifies the filtering and limit behavior.
func TestLinuxProcessListFilter(t *testing.T) {
	r := NewRegistry()

	// Filter by the current test binary name; it should match itself.
	self, err := os.Executable()
	if err != nil {
		t.Skipf("cannot get the path of the executable itself: %v", err)
	}
	base := self[strings.LastIndex(self, "/")+1:]

	res := r.Execute("linux.process.list", map[string]any{"filter": base})
	if !res.Success {
		t.Fatalf("execution failed: %s", res.Error)
	}
	data := res.Data.(map[string]any)
	procs := data["processes"].([]map[string]any)
	if len(procs) == 0 {
		t.Fatalf("filtering by %q should match at least the process itself", base)
	}
	for _, p := range procs {
		comm := strings.ToLower(p["comm"].(string))
		cmdline := strings.ToLower(p["cmdline"].(string))
		if !strings.Contains(comm, strings.ToLower(base)) && !strings.Contains(cmdline, strings.ToLower(base)) {
			t.Errorf("the filter result should not contain a non-matching process: comm=%q cmdline=%q", comm, cmdline)
		}
	}

	// With limit=1 it should return only 1 entry and set truncated.
	res = r.Execute("linux.process.list", map[string]any{"limit": 1})
	if !res.Success {
		t.Fatalf("execution failed: %s", res.Error)
	}
	data = res.Data.(map[string]any)
	procs = data["processes"].([]map[string]any)
	if len(procs) != 1 {
		t.Fatalf("with limit=1 it should return 1 entry, actual %d", len(procs))
	}
	if data["truncated"] != true {
		t.Error("with limit=1 and more than 1 process on the system, truncated should be true")
	}
}

// TestLinuxProcessListParamErrors covers the parameter validation error paths.
func TestLinuxProcessListParamErrors(t *testing.T) {
	r := NewRegistry()
	cases := []struct {
		name   string
		params map[string]any
	}{
		{"limit is 0", map[string]any{"limit": 0}},
		{"limit is negative", map[string]any{"limit": -1}},
		{"limit exceeds the upper bound", map[string]any{"limit": 999999}},
		{"limit has the wrong type", map[string]any{"limit": "abc"}},
		{"filter has the wrong type", map[string]any{"filter": 123}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := r.Execute("linux.process.list", tc.params)
			if res.Success {
				t.Fatalf("it should fail but actually succeeded: %+v", res.Data)
			}
			if res.Error == "" {
				t.Fatal("the error message should not be empty")
			}
		})
	}
}

// TestLinuxProcestRackParamErrors covers the dangerous parameter rejection logic of kill.
func TestLinuxProcestRackParamErrors(t *testing.T) {
	r := NewRegistry()
	cases := []struct {
		name   string
		params map[string]any
	}{
		{"missing pid", map[string]any{}},
		{"pid is 0", map[string]any{"pid": 0}},
		{"pid is negative", map[string]any{"pid": -1}},
		{"pid has the wrong type", map[string]any{"pid": "abc"}},
		{"signal is invalid", map[string]any{"pid": 1, "signal": "SIGFOO"}},
		{"signal has the wrong type", map[string]any{"pid": 1, "signal": 9}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := r.Execute("linux.process.kill", tc.params)
			if res.Success {
				t.Fatalf("it should fail but actually succeeded: %+v", res.Data)
			}
			if res.Error == "" {
				t.Fatal("the error message should not be empty")
			}
		})
	}
}

// TestLinuxProcestRackRealChild verifies on a real machine: send SIGTERM to a child process spawned by itself.
func TestLinuxProcestRackRealChild(t *testing.T) {
	cmd := exec.Command("/bin/sleep", "30")
	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start the child process: %v", err)
	}
	pid := cmd.Process.Pid
	defer func() {
		// Fallback cleanup to avoid leaving an orphan process when the test fails.
		_ = syscall.Kill(pid, syscall.SIGKILL)
		_, _ = cmd.Process.Wait()
	}()

	r := NewRegistry()
	res := r.Execute("linux.process.kill", map[string]any{"pid": pid, "signal": "TERM"})
	if !res.Success {
		t.Fatalf("failed to send SIGTERM: %s", res.Error)
	}
	data := res.Data.(map[string]any)
	if data["pid"] != pid {
		t.Errorf("the returned pid should be %d, actual %v", pid, data["pid"])
	}
	if data["signal"] != "TERM" {
		t.Errorf("the returned signal should be TERM, actual %v", data["signal"])
	}
	if data["killed"] != true {
		t.Errorf("killed should be true, actual %v", data["killed"])
	}

	// Wait for the child process to actually exit.
	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	select {
	case <-done:
		// Exited normally (terminated by signal).
	case <-time.After(5 * time.Second):
		t.Fatal("the child process did not exit within 5 seconds after receiving SIGTERM")
	}
}

// TestLinuxProcestRackNonexistent verifies that a clear error is returned for a non-existent process.
func TestLinuxProcestRackNonexistent(t *testing.T) {
	r := NewRegistry()
	// Find a PID that is almost impossible to exist: first start a child process to get a PID, then use that PID after killing it.
	cmd := exec.Command("/bin/sleep", "1")
	if err := cmd.Start(); err != nil {
		t.Fatalf("failed to start the child process: %v", err)
	}
	pid := cmd.Process.Pid
	_ = cmd.Process.Kill()
	_, _ = cmd.Process.Wait()

	// Wait for the process to be fully reaped.
	time.Sleep(200 * time.Millisecond)

	res := r.Execute("linux.process.kill", map[string]any{"pid": pid, "signal": "TERM"})
	if res.Success {
		t.Skipf("PID %d has been reused, skipping (not treated as a failure)", pid)
	}
	if !strings.Contains(res.Error, fmt.Sprintf("%d", pid)) {
		t.Errorf("the error message should contain the pid, actual: %s", res.Error)
	}
}

// TestParseLinuxProcStat covers the parsing of /proc/<pid>/stat, including boundary cases where comm contains spaces and parentheses.
func TestParseLinuxProcStat(t *testing.T) {
	cases := []struct {
		name      string
		raw       string
		wantComm  string
		wantPPID  int
		wantState string
		wantErr   bool
	}{
		{
			name:      "ordinary process",
			raw:       "1234 (bash) S 1000 1234 1234 0 -1 4194304 100 0 0 0 1 2 0 0 20 0 1 0 5000 1000000 200",
			wantComm:  "bash",
			wantPPID:  1000,
			wantState: "S",
		},
		{
			name:      "comm contains spaces and parentheses",
			raw:       "42 (my (weird) proc) R 1 42 42 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 7000 0 5",
			wantComm:  "my (weird) proc",
			wantPPID:  1,
			wantState: "R",
		},
		{
			name:    "insufficient fields",
			raw:     "1 (x) S 0",
			wantErr: true,
		},
		{
			name:    "missing parentheses",
			raw:     "garbage",
			wantErr: true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			info, err := parseLinuxProcStat(tc.raw)
			if tc.wantErr {
				if err == nil {
					t.Fatal("it should return an error")
				}
				return
			}
			if err != nil {
				t.Fatalf("it should not return an error: %v", err)
			}
			if info.comm != tc.wantComm {
				t.Errorf("comm should be %q, actual %q", tc.wantComm, info.comm)
			}
			if info.ppid != tc.wantPPID {
				t.Errorf("ppid should be %d, actual %d", tc.wantPPID, info.ppid)
			}
			if info.state != tc.wantState {
				t.Errorf("state should be %q, actual %q", tc.wantState, info.state)
			}
		})
	}
}
