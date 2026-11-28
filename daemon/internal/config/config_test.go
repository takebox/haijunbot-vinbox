package config

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

// writeTempConfig writes a temp config file and returns its path.
func writeTempConfig(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("failed to write the temp config: %v", err)
	}
	return path
}

func TestDefaultGatewayFilter(t *testing.T) {
	cfg := Default()
	if cfg.GatewayFilterMode != "off" {
		t.Fatalf("default mode should be off, got %q", cfg.GatewayFilterMode)
	}
	if len(cfg.GatewayFilterPatterns) != 0 {
		t.Fatalf("the default list should be empty, got %v", cfg.GatewayFilterPatterns)
	}
}

func TestLoadGatewayFilterMode(t *testing.T) {
	path := writeTempConfig(t, "listen: 127.0.0.1:17800\ngateway_filter_mode: whitelist\n")
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.GatewayFilterMode != "whitelist" {
		t.Fatalf("mode = %q, want whitelist", cfg.GatewayFilterMode)
	}
}

func TestLoadGatewayFilterPatterns(t *testing.T) {
	path := writeTempConfig(t,
		"gateway_filter_patterns: \"*.example.com:8000, 192.168.1.5:* ,,  a:1  \"\n")
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	want := []string{"*.example.com:8000", "192.168.1.5:*", "a:1"}
	if !reflect.DeepEqual(cfg.GatewayFilterPatterns, want) {
		t.Fatalf("patterns = %v, want %v", cfg.GatewayFilterPatterns, want)
	}
}

func TestLoadGatewayFilterPatternsEmpty(t *testing.T) {
	path := writeTempConfig(t, "gateway_filter_patterns: \"\"\n")
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if len(cfg.GatewayFilterPatterns) != 0 {
		t.Fatalf("an empty value should yield an empty list, got %v", cfg.GatewayFilterPatterns)
	}
}

func TestValidateGatewayFilterMode(t *testing.T) {
	// Valid values should pass.
	for _, mode := range []string{"off", "whitelist", "blacklist"} {
		cfg := Default()
		cfg.GatewayFilterMode = mode
		if err := cfg.Validate(); err != nil {
			t.Errorf("mode=%q should pass validation, got an error: %v", mode, err)
		}
	}
	// An invalid value should error.
	cfg := Default()
	cfg.GatewayFilterMode = "allow"
	if err := cfg.Validate(); err == nil {
		t.Fatal("an invalid mode should fail validation")
	}
}

func TestValidateEmptyModeFails(t *testing.T) {
	// An empty mode (e.g. omitted when hand-writing the config) should error, avoiding a silent fallback to no restriction.
	cfg := Default()
	cfg.GatewayFilterMode = ""
	if err := cfg.Validate(); err == nil {
		t.Fatal("an empty mode should fail validation")
	}
}
