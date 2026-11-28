//go:build linux

package capability

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

// linuxServiceTimeout is the timeout for a single systemctl call.
const linuxServiceTimeout = 10 * time.Second

// linuxServiceUnitPattern is the legal character set for a systemd unit name.
//
// It is limited to letters, digits, underscore, dot, @, and hyphen, used to prevent the caller from injecting
// extra arguments (such as `--now`, `; rm -rf /`) into the systemctl command line.
var linuxServiceUnitPattern = regexp.MustCompile(`^[A-Za-z0-9_.@-]+$`)

// linuxServiceProxyEnvVars are the proxy-related environment variables that need to be passed through to systemctl.
//
// Consistent with proxyEnvVars in internal/service/systemd_linux.go:
// in scenarios where external network access needs to go through a proxy, systemctl itself does not need a proxy, but passing
// them through avoids unexpected behavior from differences in the user's environment.
var linuxServiceProxyEnvVars = []string{
	"http_proxy", "HTTP_PROXY",
	"https_proxy", "HTTPS_PROXY",
	"no_proxy", "NO_PROXY",
	"ftp_proxy", "FTP_PROXY",
	"socks_proxy", "SOCKS_PROXY",
}

// registerLinuxService registers the Linux systemd user service capabilities.
//
// The daemon itself runs as a systemd user service (WantedBy=default.target),
// so `systemctl --user` is used uniformly here, and system-level services are not involved.
func registerLinuxService(reg *Registry) {
	_ = reg.Register(Capability{
		Name:        "linux.service.list",
		Description: "List the current user's systemd service units (systemctl --user list-units).",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit_type": map[string]any{
					"type":        "string",
					"description": "Unit type, default service; common values: service, socket, timer, target.",
				},
				"all": map[string]any{
					"type":        "boolean",
					"description": "Whether to include inactive units (--all), default false.",
				},
			},
		},
		Handler: handleLinuxServiceList,
	})

	_ = reg.Register(Capability{
		Name:        "linux.service.status",
		Description: "Query the detailed status of the specified systemd user service unit (systemctl --user show).",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Unit name, such as haijunbot-daemon.service; allowed characters: letters, digits, _ . @ -.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleLinuxServiceStatus,
	})

	_ = reg.Register(Capability{
		Name:        "linux.service.start",
		Description: "Start the specified systemd user service unit (systemctl --user start).",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Unit name, such as haijunbot-daemon.service.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleLinuxServiceAction("start"),
	})

	_ = reg.Register(Capability{
		Name:        "linux.service.stop",
		Description: "Stop the specified systemd user service unit (systemctl --user stop).",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Unit name, such as haijunbot-daemon.service.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleLinuxServiceAction("stop"),
	})

	_ = reg.Register(Capability{
		Name:        "linux.service.restart",
		Description: "Restart the specified systemd user service unit (systemctl --user restart).",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"unit": map[string]any{
					"type":        "string",
					"description": "Unit name, such as haijunbot-daemon.service.",
				},
			},
			"required": []string{"unit"},
		},
		Handler: handleLinuxServiceAction("restart"),
	})
}

// handleLinuxServiceList is the implementation of linux.service.list.
func handleLinuxServiceList(params map[string]any) (any, error) {
	unitType, err := optionalString(params, "unit_type")
	if err != nil {
		return nil, err
	}
	if unitType == "" {
		unitType = "service"
	}
	if !linuxServiceUnitPattern.MatchString(unitType) || strings.HasPrefix(unitType, "-") {
		return nil, fmt.Errorf("parameter unit_type contains illegal characters: %q, allowed characters: letters, digits, _ . @ - (and cannot start with -)", unitType)
	}

	all, err := optionalBool(params, "all", false)
	if err != nil {
		return nil, err
	}

	args := []string{"--user", "list-units", "--type=" + unitType, "--no-pager", "--no-legend", "--plain"}
	if all {
		args = append(args, "--all")
	}

	out, err := runSystemctl(args...)
	if err != nil {
		return nil, err
	}

	units := parseSystemctlListUnits(out)
	return map[string]any{
		"units": units,
		"count": len(units),
	}, nil
}

// handleLinuxServiceStatus is the implementation of linux.service.status.
func handleLinuxServiceStatus(params map[string]any) (any, error) {
	unit, err := resolveLinuxServiceUnit(params)
	if err != nil {
		return nil, err
	}

	out, err := runSystemctl("--user", "show", unit, "--no-pager")
	if err != nil {
		return nil, err
	}

	props := parseSystemctlShow(out)
	result := map[string]any{
		"unit":        unit,
		"load":        props["LoadState"],
		"active":      props["ActiveState"],
		"sub":         props["SubState"],
		"description": props["Description"],
		"main_pid":    props["MainPID"],
		"exec_start":  props["ExecStart"],
	}
	return result, nil
}

// handleLinuxServiceAction generates the implementation of start / stop / restart.
func handleLinuxServiceAction(action string) func(map[string]any) (any, error) {
	return func(params map[string]any) (any, error) {
		unit, err := resolveLinuxServiceUnit(params)
		if err != nil {
			return nil, err
		}

		out, err := runSystemctl("--user", action, unit)
		if err != nil {
			return nil, err
		}

		return map[string]any{
			"unit":   unit,
			"action": action,
			"ok":     true,
			"output": strings.TrimSpace(out),
		}, nil
	}
}

// resolveLinuxServiceUnit parses and validates the unit parameter.
func resolveLinuxServiceUnit(params map[string]any) (string, error) {
	unit, err := requiredString(params, "unit")
	if err != nil {
		return "", err
	}
	if err := validateLinuxServiceUnitName(unit); err != nil {
		return "", err
	}
	return unit, nil
}

// validateLinuxServiceUnitName validates the legality of the unit name.
//
// Besides the character-set whitelist, names starting with "-" must also be rejected:
// such names would be treated by systemctl as command-line options (such as --now, --all),
// thereby bypassing the "unit name" semantics and turning into argument injection.
func validateLinuxServiceUnitName(name string) error {
	if strings.HasPrefix(name, "-") {
		return fmt.Errorf("parameter unit cannot start with - (would be parsed as a systemctl option): %q", name)
	}
	if !linuxServiceUnitPattern.MatchString(name) {
		return fmt.Errorf("parameter unit contains illegal characters: %q, allowed characters: letters, digits, _ . @ -", name)
	}
	return nil
}

// runSystemctl runs the systemctl command and returns standard output.
//
// It uniformly applies a timeout and proxy environment variable pass-through; if systemctl does not exist, a clear error is given.
func runSystemctl(args ...string) (string, error) {
	bin, err := exec.LookPath("systemctl")
	if err != nil {
		return "", fmt.Errorf("systemctl not found; the current system may not use systemd: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), linuxServiceTimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, bin, args...)
	cmd.Env = append(os.Environ(), collectLinuxServiceProxyEnv()...)

	out, err := cmd.Output()
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("executing systemctl %s timed out (%s)", strings.Join(args, " "), linuxServiceTimeout)
		}
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			stderr := strings.TrimSpace(string(exitErr.Stderr))
			if stderr != "" {
				return "", fmt.Errorf("executing systemctl %s failed: %s", strings.Join(args, " "), stderr)
			}
		}
		return "", fmt.Errorf("executing systemctl %s failed: %w", strings.Join(args, " "), err)
	}

	return string(out), nil
}

// collectLinuxServiceProxyEnv collects the proxy variables already set in the current environment.
func collectLinuxServiceProxyEnv() []string {
	out := make([]string, 0, len(linuxServiceProxyEnvVars))
	for _, name := range linuxServiceProxyEnvVars {
		if v := os.Getenv(name); v != "" {
			out = append(out, name+"="+v)
		}
	}
	return out
}

// parseSystemctlListUnits parses the output lines of `systemctl list-units`.
//
// Each line looks like:
//
//	haijunbot-daemon.service loaded active running HaijunBot Daemon
//
// Here description may contain spaces, so after splitting the first 4 fields, the rest is taken as the description.
func parseSystemctlListUnits(out string) []map[string]any {
	units := make([]map[string]any, 0, 16)
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		// Skip the header and summary lines.
		if strings.HasPrefix(line, "UNIT") || strings.HasPrefix(line, "LOAD") ||
			strings.HasPrefix(line, "Legend:") || strings.HasPrefix(line, "0 loaded") {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}

		entry := map[string]any{
			"unit":   fields[0],
			"load":   fields[1],
			"active": fields[2],
			"sub":    fields[3],
		}
		if len(fields) > 4 {
			entry["description"] = strings.Join(fields[4:], " ")
		} else {
			entry["description"] = ""
		}
		units = append(units, entry)
	}
	return units
}

// parseSystemctlShow parses the key=value output of `systemctl show`.
func parseSystemctlShow(out string) map[string]string {
	props := make(map[string]string, 32)
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		idx := strings.IndexByte(line, '=')
		if idx <= 0 {
			continue
		}
		props[line[:idx]] = line[idx+1:]
	}
	return props
}
