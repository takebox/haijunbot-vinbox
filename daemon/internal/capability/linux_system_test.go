//go:build linux

package capability

import (
	"os"
	"strings"
	"testing"
)

// TestLinuxSystemRegistered verifies that the system information capability is registered and the platform is correct.
func TestLinuxSystemRegistered(t *testing.T) {
	r := NewRegistry()
	c, ok := r.Get("linux.system.info")
	if !ok {
		t.Fatal("linux.system.info should be registered")
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
}

// TestLinuxSystemInfoFields verifies on a real machine that each field is non-empty and of the correct type.
func TestLinuxSystemInfoFields(t *testing.T) {
	r := NewRegistry()
	res := r.Execute("linux.system.info", map[string]any{})
	if !res.Success {
		t.Fatalf("execution failed: %s", res.Error)
	}
	data, ok := res.Data.(map[string]any)
	if !ok {
		t.Fatalf("the return type should be map[string]any, actual %T", res.Data)
	}

	// String fields should be non-empty.
	for _, key := range []string{"hostname", "kernel", "os_name", "arch", "cpu_model", "user", "home"} {
		v, ok := data[key]
		if !ok {
			t.Errorf("missing field %s", key)
			continue
		}
		s, ok := v.(string)
		if !ok {
			t.Errorf("field %s should be a string, actual %T", key, v)
			continue
		}
		if strings.TrimSpace(s) == "" {
			t.Errorf("field %s should not be empty", key)
		}
	}

	// Numeric fields should be positive.
	if v, ok := data["cpu_count"].(int); !ok || v <= 0 {
		t.Errorf("cpu_count should be a positive integer, actual %v (%T)", data["cpu_count"], data["cpu_count"])
	}
	if v, ok := data["mem_total_kb"].(int64); !ok || v <= 0 {
		t.Errorf("mem_total_kb should be a positive integer, actual %v (%T)", data["mem_total_kb"], data["mem_total_kb"])
	}
	if v, ok := data["mem_available_kb"].(int64); !ok || v < 0 {
		t.Errorf("mem_available_kb should be a non-negative integer, actual %v (%T)", data["mem_available_kb"], data["mem_available_kb"])
	}
	if v, ok := data["uptime_sec"].(int64); !ok || v <= 0 {
		t.Errorf("uptime_sec should be a positive integer, actual %v (%T)", data["uptime_sec"], data["uptime_sec"])
	}

	// Available memory should not exceed total memory.
	total := data["mem_total_kb"].(int64)
	avail := data["mem_available_kb"].(int64)
	if avail > total {
		t.Errorf("mem_available_kb (%d) should not be greater than mem_total_kb (%d)", avail, total)
	}

	// hostname should be consistent with os.Hostname.
	wantHost, err := os.Hostname()
	if err == nil && data["hostname"] != wantHost {
		t.Errorf("hostname should be %q, actual %q", wantHost, data["hostname"])
	}
}

// TestReadLinuxOSRelease verifies the parsing of /etc/os-release.
func TestReadLinuxOSRelease(t *testing.T) {
	name, version := readLinuxOSRelease()
	if name == "" {
		t.Fatal("the distribution name should not be empty (/etc/os-release should exist on this machine)")
	}
	if version == "" {
		t.Log("warning: could not parse the distribution version number (fields may differ across distributions)")
	}
	t.Logf("parse result: name=%q version=%q", name, version)
}

// TestReadLinuxMemInfo verifies the parsing of /proc/meminfo.
func TestReadLinuxMemInfo(t *testing.T) {
	total, avail := readLinuxMemInfo()
	if total <= 0 {
		t.Fatalf("MemTotal should be positive, actual %d", total)
	}
	if avail < 0 {
		t.Fatalf("MemAvailable should be non-negative, actual %d", avail)
	}
	if avail > total {
		t.Fatalf("MemAvailable (%d) should not be greater than MemTotal (%d)", avail, total)
	}
}

// TestLinuxFormatBytes covers the byte formatting helper function.
func TestLinuxFormatBytes(t *testing.T) {
	cases := []struct {
		in   int64
		want string
	}{
		{0, "0 B"},
		{512, "512 B"},
		{1024, "1.0 KB"},
		{1536, "1.5 KB"},
		{1024 * 1024, "1.0 MB"},
		{1024 * 1024 * 1024, "1.0 GB"},
	}
	for _, tc := range cases {
		if got := linuxFormatBytes(tc.in); got != tc.want {
			t.Errorf("linuxFormatBytes(%d) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

// TestLinuxPageSizeKB verifies that the page size is positive.
func TestLinuxPageSizeKB(t *testing.T) {
	if got := linuxPageSizeKB(); got <= 0 {
		t.Fatalf("the page size should be positive, actual %d", got)
	}
}
