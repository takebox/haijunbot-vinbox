// Package buildinfo provides the daemon's build information (build time, Go version, target platform, etc.).
//
// Design trade-off: the build time uses the **executable file's own modification time (mtime)** instead of being
// injected via -ldflags "-X ...". Reasons:
//   - injection breaks reproducible builds (building the same source twice yields different binaries);
//   - the user explicitly confirmed "it's fine" to use the mtime approach;
//   - in most scenarios mtime equals the time the exe was built/replaced, sufficient to characterize "when this version was built".
//
// Limitation (stated honestly): if the mtime gets reset after the exe is copied/unpacked (e.g. by some archiving
// tools), the reported time will be inaccurate. In that case the process start time can be used as an approximation.
package buildinfo

import (
	"os"
	"runtime"
	"runtime/debug"
	"time"
)

// Info is the daemon's build/runtime environment information.
type Info struct {
	// Version is the daemon version (provided by the main package via -ldflags or a default value).
	Version string `json:"version"`
	// BuildTime is the inferred build time (exe mtime), in RFC3339 format; empty string when unknown.
	BuildTime string `json:"build_time"`
	// BuildTimeUnix is the Unix-second timestamp of BuildTime; 0 when unknown.
	BuildTimeUnix int64 `json:"build_time_unix"`
	// BuildTimeSource describes the source of BuildTime, for troubleshooting (e.g. "exe_mtime", "process_start", "unknown").
	BuildTimeSource string `json:"build_time_source"`
	// GoVersion is the Go version used to compile this binary.
	GoVersion string `json:"go_version"`
	// OS is the target operating system (e.g. windows, linux, darwin).
	OS string `json:"os"`
	// Arch is the target architecture (e.g. amd64, arm64).
	Arch string `json:"arch"`
	// ExePath is the absolute path of the current executable; empty string when it cannot be obtained.
	ExePath string `json:"exe_path"`
	// ExeMTime is the executable file's modification time (RFC3339), i.e. the commonly called "build time";
	// it shares the same source as BuildTime, and the field name is kept separately for more intuitive caller semantics.
	ExeMTime string `json:"exe_mtime"`
	// Commit is the VCS revision at build time (git commit), shortened (first 12 characters); empty string when unknown.
	Commit string `json:"commit"`
	// CommitTime is the VCS commit time at build time (RFC3339); empty string when unknown.
	CommitTime string `json:"commit_time"`
	// VCSModified indicates whether the workspace had uncommitted changes at build time; false when the info is unavailable.
	VCSModified bool `json:"vcs_modified"`
	// PID is the current daemon process ID, to distinguish different instances after restarts.
	PID int `json:"pid"`
	// StartedAt is the process start time (RFC3339); empty string when it cannot be obtained.
	StartedAt string `json:"started_at"`
	// StartedAtUnix is the Unix-second timestamp of StartedAt; 0 when unknown.
	StartedAtUnix int64 `json:"started_at_unix"`
}

// Collect gathers the current process's build information.
//
// version is passed by the caller (the version variable in the main package).
// This function never returns an error: any collection failure degrades to an empty value, ensuring the hello message can always be sent.
func Collect(version string) Info {
	info := Info{
		Version:         version,
		GoVersion:       runtime.Version(),
		OS:              runtime.GOOS,
		Arch:            runtime.GOARCH,
		BuildTimeSource: "unknown",
		PID:             os.Getpid(),
	}

	exePath, err := os.Executable()
	if err == nil {
		info.ExePath = exePath

		if fi, statErr := os.Stat(exePath); statErr == nil {
			info.BuildTime = fi.ModTime().UTC().Format(time.RFC3339)
			info.BuildTimeUnix = fi.ModTime().Unix()
			info.BuildTimeSource = "exe_mtime"
			// exe_mtime shares the same source as build_time, with more straightforward semantics for direct display.
			info.ExeMTime = info.BuildTime
		}
	}

	// Fallback: when the exe mtime is unavailable, use the process start time as an approximation (at least giving "roughly when this version ran").
	if info.BuildTimeSource == "unknown" {
		if start, ok := processStartTime(); ok {
			info.BuildTime = start.UTC().Format(time.RFC3339)
			info.BuildTimeUnix = start.Unix()
			info.BuildTimeSource = "process_start"
		}
	}

	// Process start time: collected independently whether or not the exe mtime is available,
	// to distinguish the scenario where "the same exe has been restarted multiple times".
	if start, ok := processStartTime(); ok {
		info.StartedAt = start.UTC().Format(time.RFC3339)
		info.StartedAtUnix = start.Unix()
	}

	// VCS info comes from the build info embedded by Go at build time.
	// When not built with go build (e.g. go run), or when built with -buildvcs=false,
	// ReadBuildInfo may return nil or lack the vcs settings, in which case those fields keep zero values.
	collectVCSInfo(&info)

	return info
}

// collectVCSInfo extracts VCS revision info from runtime/debug.ReadBuildInfo.
//
// This info is embedded automatically by the Go toolchain at build time (no ldflags needed), so reproducible builds are not broken.
// Any missing item is silently skipped, guaranteeing the function never panics or errors.
func collectVCSInfo(info *Info) {
	bi, ok := debug.ReadBuildInfo()
	if !ok || bi == nil {
		return
	}
	for _, setting := range bi.Settings {
		switch setting.Key {
		case "vcs.revision":
			rev := setting.Value
			// Take the short form: the full git hash is 40 characters; the first 12 are sufficient to distinguish and easy to read.
			const shortLen = 12
			if len(rev) > shortLen {
				rev = rev[:shortLen]
			}
			info.Commit = rev
		case "vcs.time":
			// vcs.time is in RFC3339 format (e.g. 2026-09-26T07:30:00Z), reported as-is.
			info.CommitTime = setting.Value
		case "vcs.modified":
			info.VCSModified = setting.Value == "true"
		}
	}
}

// AsMap converts Info into a map, for embedding into the hello message (parsed as a JSON object on the gateway side).
func (i Info) AsMap() map[string]any {
	return map[string]any{
		"version":           i.Version,
		"build_time":        i.BuildTime,
		"build_time_unix":   i.BuildTimeUnix,
		"build_time_source": i.BuildTimeSource,
		"go_version":        i.GoVersion,
		"os":                i.OS,
		"arch":              i.Arch,
		"exe_path":          i.ExePath,
		"exe_mtime":         i.ExeMTime,
		"commit":            i.Commit,
		"commit_time":       i.CommitTime,
		"vcs_modified":      i.VCSModified,
		"pid":               i.PID,
		"started_at":        i.StartedAt,
		"started_at_unix":   i.StartedAtUnix,
	}
}
