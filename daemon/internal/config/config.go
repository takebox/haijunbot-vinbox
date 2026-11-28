// Package config handles the daemon's configuration loading: defaults → config file → command-line arguments.
package config

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Default values.
const (
	DefaultListen            = "127.0.0.1:17800"
	DefaultHeartbeatInterval = 20 // seconds
	DefaultReconnectMin      = 1  // seconds
	DefaultReconnectMax      = 30 // seconds
	// DefaultWebListen is the default listen address of the Web login service.
	//
	// Deliberately binds to 0.0.0.0: this service is meant to be accessed by browsers on **other machines** (a headless
	// host has no browser). It should only be used on a trusted intranet; see the security notes in internal/webui.
	DefaultWebListen = "0.0.0.0:17801"
)

// Config is the daemon's runtime configuration.
type Config struct {
	// Listen is the listen address of the local API; it must bind to the loopback address.
	Listen string
	// Gateway is the default gateway address; can be overridden by values pushed to /api/auth.
	Gateway string
	// WebListen is the listen address of the Web login service (for browsers on other machines).
	//
	// An empty string disables the service; default is 0.0.0.0:17801 (see DefaultWebListen).
	WebListen string
	// GatewayFilterMode is the gateway whitelist/blacklist mode: off / whitelist / blacklist.
	//
	// Default is off (no restriction). It prevents a "logged-in-once" gateway from staying connected after being
	// auto-discovered. This setting should only be changed through the local interface (command line / local browser),
	// see /api/gateway-filter in internal/localapi.
	GatewayFilterMode string
	// GatewayFilterPatterns is the list of whitelist/blacklist match patterns (host:port, supports * and ? wildcards).
	GatewayFilterPatterns []string
	// HeartbeatInterval is the heartbeat interval (seconds), can be overridden by hello_ack.
	HeartbeatInterval int
	// ReconnectMin / ReconnectMax are the lower/upper bounds of the reconnect backoff (seconds).
	ReconnectMin int
	ReconnectMax int
}

// Default returns the built-in default configuration.
func Default() Config {
	return Config{
		Listen:            DefaultListen,
		Gateway:           "",
		WebListen:         DefaultWebListen,
		HeartbeatInterval: DefaultHeartbeatInterval,
		ReconnectMin:      DefaultReconnectMin,
		ReconnectMax:      DefaultReconnectMax,
		// The gateway whitelist/blacklist is off by default (no restriction).
		GatewayFilterMode:     "off",
		GatewayFilterPatterns: nil,
	}
}

// DefaultPath returns the default config file path: ~/.haijunbot/daemon/config.yaml.
func DefaultPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".haijunbot", "daemon", "config.yaml")
}

// Load reads the config file and returns the configuration. A missing file returns the default config without an error.
func Load(path string) (Config, error) {
	cfg := Default()
	if path == "" {
		return cfg, nil
	}
	f, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return cfg, nil
		}
		return cfg, fmt.Errorf("failed to open the config file: %w", err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	lineNo := 0
	for scanner.Scan() {
		lineNo++
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, ":")
		if !ok {
			return cfg, fmt.Errorf("config line %d is malformed (missing ':'): %s", lineNo, line)
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		value = strings.Trim(value, `"'`)
		if err := cfg.set(key, value); err != nil {
			return cfg, fmt.Errorf("config line %d: %w", lineNo, err)
		}
	}
	if err := scanner.Err(); err != nil {
		return cfg, fmt.Errorf("failed to read the config file: %w", err)
	}
	return cfg, nil
}

func (c *Config) set(key, value string) error {
	switch key {
	case "listen":
		c.Listen = value
	case "gateway":
		c.Gateway = value
	case "web_listen":
		// An empty value disables the Web login service, so no non-empty check is done here.
		c.WebListen = value
	case "heartbeat_interval":
		n, err := strconv.Atoi(value)
		if err != nil {
			return fmt.Errorf("heartbeat_interval must be an integer: %q", value)
		}
		c.HeartbeatInterval = n
	case "reconnect_min":
		n, err := strconv.Atoi(value)
		if err != nil {
			return fmt.Errorf("reconnect_min must be an integer: %q", value)
		}
		c.ReconnectMin = n
	case "reconnect_max":
		n, err := strconv.Atoi(value)
		if err != nil {
			return fmt.Errorf("reconnect_max must be an integer: %q", value)
		}
		c.ReconnectMax = n
	case "gateway_filter_mode":
		// Assign directly; validity is uniformly checked by Validate (set only does parsing).
		c.GatewayFilterMode = value
	case "gateway_filter_patterns":
		// Comma-separated list of match patterns; each item is trimmed and empty items are filtered out.
		// An empty value clears the list (combined with mode=off it means no restriction).
		c.GatewayFilterPatterns = splitPatterns(value)
	default:
		return fmt.Errorf("unknown config key: %s", key)
	}
	return nil
}

// splitPatterns splits a comma-separated pattern list into a slice, trimming each item and filtering out empty items.
func splitPatterns(value string) []string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	parts := strings.Split(value, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if v := strings.TrimSpace(p); v != "" {
			out = append(out, v)
		}
	}
	return out
}

// Validate validates the configuration's validity.
func (c Config) Validate() error {
	if c.Listen == "" {
		return fmt.Errorf("listen cannot be empty")
	}
	if !isLoopback(c.Listen) {
		return fmt.Errorf("listen must bind to a loopback address (127.0.0.1 / localhost / [::1]), currently %q", c.Listen)
	}
	if c.HeartbeatInterval <= 0 {
		return fmt.Errorf("heartbeat_interval must be positive, currently %d", c.HeartbeatInterval)
	}
	if c.ReconnectMin <= 0 || c.ReconnectMax < c.ReconnectMin {
		return fmt.Errorf("invalid reconnect backoff range: min=%d max=%d", c.ReconnectMin, c.ReconnectMax)
	}
	// The whitelist/blacklist mode must be one of the three valid values; an invalid value fails startup,
	// instead of silently becoming "no restriction" and making the user believe the list is effective.
	switch c.GatewayFilterMode {
	case "off", "whitelist", "blacklist":
	default:
		return fmt.Errorf("gateway_filter_mode must be one of off / whitelist / blacklist, currently %q", c.GatewayFilterMode)
	}
	return nil
}

// UpdateGatewayFilter writes the gateway whitelist/blacklist back to the config file.
//
// Design trade-off: **only rewrite these two key lines, keeping the rest of the file (including comments and other
// keys)** rather than rewriting everything--a full rewrite would lose the user's hand-written comments and key order.
//
// Behavior:
//   - creates the file when it does not exist (including the necessary parent directories);
//   - in-place replaces an existing gateway_filter_mode / gateway_filter_patterns line;
//   - appends to the end of the file when absent;
//   - writes an empty value when patterns is empty (gateway_filter_patterns: ).
//
// The write uses "same-directory temp file + atomic rename", avoiding a corrupt config file from a crash mid-write.
func UpdateGatewayFilter(path, mode string, patterns []string) error {
	if strings.TrimSpace(path) == "" {
		return fmt.Errorf("the config file path is empty")
	}
	mode = strings.TrimSpace(mode)
	if mode == "" {
		mode = "off"
	}
	patternsLine := "gateway_filter_patterns: " + strings.Join(patterns, ",")

	// Read the existing content (a missing file is treated as an empty file).
	var lines []string
	raw, err := os.ReadFile(path)
	if err != nil {
		if !os.IsNotExist(err) {
			return fmt.Errorf("failed to read the config file: %w", err)
		}
	} else {
		lines = strings.Split(strings.TrimRight(string(raw), "\n"), "\n")
		if len(lines) == 1 && lines[0] == "" {
			lines = nil
		}
	}

	// Replace or append these two keys in place; use the done* flags to avoid duplicate appends.
	modeDone, patternsDone := false, false
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "gateway_filter_mode:") {
			lines[i] = "gateway_filter_mode: " + mode
			modeDone = true
		} else if strings.HasPrefix(trimmed, "gateway_filter_patterns:") {
			lines[i] = patternsLine
			patternsDone = true
		}
	}
	if !modeDone {
		lines = append(lines, "gateway_filter_mode: "+mode)
	}
	if !patternsDone {
		lines = append(lines, patternsLine)
	}

	content := strings.Join(lines, "\n") + "\n"
	if err := writeFileAtomic(path, []byte(content), 0o600); err != nil {
		return fmt.Errorf("failed to write the config file: %w", err)
	}
	return nil
}

// writeFileAtomic writes a file atomically via "same-directory temp file + rename".
//
// The same directory guarantees the rename stays within one filesystem (a cross-device rename would fail);
// the temp file uses 0600 permissions so the config content (which may contain gateway addresses) is not readable by other users.
func writeFileAtomic(path string, data []byte, perm os.FileMode) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".config-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer func() {
		// On the success path the file no longer exists after the rename, so a Remove failure can be ignored;
		// on the failure path it cleans up the temp file.
		_ = os.Remove(tmpName)
	}()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Chmod(perm); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}

// isLoopback determines whether the listen address binds to the loopback.
func isLoopback(listen string) bool {
	host := listen
	if h, _, err := splitHostPort(listen); err == nil {
		host = h
	}
	host = strings.Trim(host, "[]")
	switch host {
	case "127.0.0.1", "localhost", "::1":
		return true
	}
	return strings.HasPrefix(host, "127.")
}

func splitHostPort(addr string) (string, string, error) {
	idx := strings.LastIndex(addr, ":")
	if idx < 0 {
		return "", "", fmt.Errorf("no port")
	}
	return addr[:idx], addr[idx+1:], nil
}
