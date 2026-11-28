package buildinfo

import (
	"encoding/json"
	"os"
	"runtime"
	"testing"
	"time"
)

// TestCollectBasicFields verifies Collect fills in the fields related to the runtime environment.
//
// These fields do not depend on the filesystem and should hold stably on any platform.
func TestCollectBasicFields(t *testing.T) {
	info := Collect("v9.9.9-test")

	if info.Version != "v9.9.9-test" {
		t.Errorf("Version = %q, expected %q", info.Version, "v9.9.9-test")
	}
	if info.GoVersion != runtime.Version() {
		t.Errorf("GoVersion = %q, expected %q", info.GoVersion, runtime.Version())
	}
	if info.OS != runtime.GOOS {
		t.Errorf("OS = %q, expected %q", info.OS, runtime.GOOS)
	}
	if info.Arch != runtime.GOARCH {
		t.Errorf("Arch = %q, expected %q", info.Arch, runtime.GOARCH)
	}
}

// TestCollectBuildTimeSource verifies the build time source annotation is valid and the timestamp is consistent with the string.
func TestCollectBuildTimeSource(t *testing.T) {
	info := Collect("test")

	switch info.BuildTimeSource {
	case "exe_mtime", "process_start", "unknown":
		// Valid values.
	default:
		t.Fatalf("BuildTimeSource = %q, unexpected value", info.BuildTimeSource)
	}

	if info.BuildTimeSource == "unknown" {
		// Extreme environment (e.g. go run with /proc unavailable): empty is allowed, but must be self-consistent.
		if info.BuildTime != "" || info.BuildTimeUnix != 0 {
			t.Errorf("with source=unknown, BuildTime/BuildTimeUnix should be empty, got %q/%d",
				info.BuildTime, info.BuildTimeUnix)
		}
		return
	}

	parsed, err := time.Parse(time.RFC3339, info.BuildTime)
	if err != nil {
		t.Fatalf("BuildTime %q cannot be parsed as RFC3339: %v", info.BuildTime, err)
	}
	if parsed.Unix() != info.BuildTimeUnix {
		t.Errorf("BuildTimeUnix(%d) inconsistent with BuildTime(%s -> %d)",
			info.BuildTimeUnix, info.BuildTime, parsed.Unix())
	}

	// Build time should not be later than "now + a little tolerance", nor earlier than year 2000 (clearly abnormal).
	now := time.Now()
	if parsed.After(now.Add(time.Minute)) {
		t.Errorf("BuildTime %s is later than the current time %s", parsed, now)
	}
	if parsed.Before(time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)) {
		t.Errorf("BuildTime %s is earlier than 2000-01-01, clearly abnormal", parsed)
	}
}

// TestAsMapKeys verifies the key set of AsMap output is complete and consistent with the struct fields.
func TestAsMapKeys(t *testing.T) {
	info := Collect("v1.2.3")
	m := info.AsMap()

	wantKeys := []string{
		"version", "build_time", "build_time_unix", "build_time_source",
		"go_version", "os", "arch", "exe_path",
		"exe_mtime", "commit", "commit_time", "vcs_modified",
		"pid", "started_at", "started_at_unix",
	}
	if len(m) != len(wantKeys) {
		t.Errorf("AsMap key count = %d, expected %d (keys=%v)", len(m), len(wantKeys), m)
	}
	for _, k := range wantKeys {
		if _, ok := m[k]; !ok {
			t.Errorf("AsMap is missing key %q", k)
		}
	}

	// Spot-check several values against the struct (to catch a missed spot when fields are replaced wholesale).
	if m["version"] != info.Version {
		t.Errorf("AsMap[version] = %v, expected %q", m["version"], info.Version)
	}
	if m["build_time"] != info.BuildTime {
		t.Errorf("AsMap[build_time] = %v, expected %q", m["build_time"], info.BuildTime)
	}
	if m["build_time_unix"] != info.BuildTimeUnix {
		t.Errorf("AsMap[build_time_unix] = %v, expected %d", m["build_time_unix"], info.BuildTimeUnix)
	}
	if m["build_time_source"] != info.BuildTimeSource {
		t.Errorf("AsMap[build_time_source] = %v, expected %q", m["build_time_source"], info.BuildTimeSource)
	}
	if m["go_version"] != info.GoVersion {
		t.Errorf("AsMap[go_version] = %v, expected %q", m["go_version"], info.GoVersion)
	}
	if m["os"] != info.OS {
		t.Errorf("AsMap[os] = %v, expected %q", m["os"], info.OS)
	}
	if m["arch"] != info.Arch {
		t.Errorf("AsMap[arch] = %v, expected %q", m["arch"], info.Arch)
	}
	if m["exe_path"] != info.ExePath {
		t.Errorf("AsMap[exe_path] = %v, expected %q", m["exe_path"], info.ExePath)
	}
}

// TestAsMapJSONRoundTrip verifies the AsMap result can be JSON serialized (a hello message requirement).
func TestAsMapJSONRoundTrip(t *testing.T) {
	m := Collect("v1.0.0").AsMap()
	if _, err := json.Marshal(m); err != nil {
		t.Fatalf("AsMap result cannot be JSON serialized: %v", err)
	}
}

// TestCollectPIDAndStartedAt verifies the process ID and start time are collected.
//
// These two fields distinguish "the same exe restarted multiple times" and are key evidence for troubleshooting deployments.
func TestCollectPIDAndStartedAt(t *testing.T) {
	info := Collect("v1.0.0")

	if info.PID <= 0 {
		t.Errorf("PID = %d, expected a positive number", info.PID)
	}
	if info.PID != os.Getpid() {
		t.Errorf("PID = %d, expected %d", info.PID, os.Getpid())
	}

	// On Linux processStartTime goes through /proc and should be available; on darwin it degrades to an empty string.
	if info.StartedAt != "" {
		parsed, err := time.Parse(time.RFC3339, info.StartedAt)
		if err != nil {
			t.Fatalf("StartedAt %q is not valid RFC3339: %v", info.StartedAt, err)
		}
		if parsed.After(time.Now().Add(time.Minute)) {
			t.Errorf("StartedAt %s is later than the current time, clearly abnormal", parsed)
		}
		if info.StartedAtUnix != parsed.Unix() {
			t.Errorf("StartedAtUnix = %d, inconsistent with StartedAt(%d)", info.StartedAtUnix, parsed.Unix())
		}
	}
}

// TestExeMTimeMatchesBuildTime verifies exe_mtime and build_time share the same source.
//
// Both come from the exe's mtime, differing only in field name (exe_mtime has more straightforward semantics).
// If BuildTimeSource is not exe_mtime (exe info unavailable), both should be empty.
func TestExeMTimeMatchesBuildTime(t *testing.T) {
	info := Collect("v1.0.0")

	if info.BuildTimeSource == "exe_mtime" {
		if info.ExeMTime == "" {
			t.Error("with source=exe_mtime, ExeMTime should not be empty")
		}
		if info.ExeMTime != info.BuildTime {
			t.Errorf("ExeMTime = %q, expected to equal BuildTime(%q)", info.ExeMTime, info.BuildTime)
		}
	} else if info.ExeMTime != "" {
		t.Errorf("with source=%s, ExeMTime expected to be empty, got %q", info.BuildTimeSource, info.ExeMTime)
	}
}

// TestCollectVCSInfoDoesNotPanic verifies VCS info collection degrades gracefully without build info.
//
// A go test binary usually carries vcs info, but it may be absent with -buildvcs=false or under go run.
// This test only requires no panic and valid field formats; it does not assume the vcs info always exists.
func TestCollectVCSInfoDoesNotPanic(t *testing.T) {
	info := Collect("v1.0.0")

	if info.Commit != "" && len(info.Commit) > 12 {
		t.Errorf("Commit = %q, expected the short form (no more than 12 chars)", info.Commit)
	}
	if info.CommitTime != "" {
		if _, err := time.Parse(time.RFC3339, info.CommitTime); err != nil {
			t.Errorf("CommitTime %q is not valid RFC3339: %v", info.CommitTime, err)
		}
	}
}
