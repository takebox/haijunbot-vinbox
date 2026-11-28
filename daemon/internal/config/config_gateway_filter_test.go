package config

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

// readFileString reads a file's content as a string, Fatal on failure.
func readFileString(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read the file: %v", err)
	}
	return string(b)
}

// TestUpdateGatewayFilterReplacesInPlace verifies that when these two keys exist they are replaced in place,
// and **the rest of the file (comments and other keys) is preserved**.
func TestUpdateGatewayFilterReplacesInPlace(t *testing.T) {
	path := writeTempConfig(t, strings.Join([]string{
		"# hand-written user comment",
		"listen: 127.0.0.1:17800",
		"gateway_filter_mode: off",
		"gateway_filter_patterns: ",
		"web_listen: 127.0.0.1:17801",
		"",
	}, "\n"))

	if err := UpdateGatewayFilter(path, "whitelist", []string{"a.com:443", "b.com:8443"}); err != nil {
		t.Fatalf("UpdateGatewayFilter failed: %v", err)
	}

	got := readFileString(t, path)
	// The comment and other keys must be preserved.
	if !strings.Contains(got, "# hand-written user comment") {
		t.Fatalf("the comment should be preserved, actual content:\n%s", got)
	}
	if !strings.Contains(got, "listen: 127.0.0.1:17800") {
		t.Fatalf("other keys should be preserved, actual content:\n%s", got)
	}
	if !strings.Contains(got, "web_listen: 127.0.0.1:17801") {
		t.Fatalf("other keys should be preserved, actual content:\n%s", got)
	}
	// The two keys are updated.
	if !strings.Contains(got, "gateway_filter_mode: whitelist") {
		t.Fatalf("mode should be updated, actual content:\n%s", got)
	}
	if !strings.Contains(got, "gateway_filter_patterns: a.com:443,b.com:8443") {
		t.Fatalf("patterns should be updated, actual content:\n%s", got)
	}
	// No duplicate append.
	if strings.Count(got, "gateway_filter_mode:") != 1 {
		t.Fatalf("gateway_filter_mode should appear exactly once, actual content:\n%s", got)
	}
	if strings.Count(got, "gateway_filter_patterns:") != 1 {
		t.Fatalf("gateway_filter_patterns should appear exactly once, actual content:\n%s", got)
	}

	// After persisting, it should be read back correctly by Load.
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.GatewayFilterMode != "whitelist" {
		t.Fatalf("read-back mode should be whitelist, got %q", cfg.GatewayFilterMode)
	}
	if !reflect.DeepEqual(cfg.GatewayFilterPatterns, []string{"a.com:443", "b.com:8443"}) {
		t.Fatalf("read-back patterns mismatch, got %v", cfg.GatewayFilterPatterns)
	}
}

// TestUpdateGatewayFilterAppendsWhenMissing verifies that when the keys are absent they are appended to the file end.
func TestUpdateGatewayFilterAppendsWhenMissing(t *testing.T) {
	path := writeTempConfig(t, "listen: 127.0.0.1:17800\n")

	if err := UpdateGatewayFilter(path, "blacklist", []string{"evil.com:443"}); err != nil {
		t.Fatalf("UpdateGatewayFilter failed: %v", err)
	}

	got := readFileString(t, path)
	if !strings.Contains(got, "listen: 127.0.0.1:17800") {
		t.Fatalf("the original content should be preserved, actual content:\n%s", got)
	}
	if !strings.Contains(got, "gateway_filter_mode: blacklist") {
		t.Fatalf("mode should be appended, actual content:\n%s", got)
	}
	if !strings.Contains(got, "gateway_filter_patterns: evil.com:443") {
		t.Fatalf("patterns should be appended, actual content:\n%s", got)
	}
}

// TestUpdateGatewayFilterCreatesFile verifies the file is created when absent (including parent directories).
func TestUpdateGatewayFilterCreatesFile(t *testing.T) {
	dir := t.TempDir()
	// Deliberately use a non-existent nested directory to verify MkdirAll works.
	path := filepath.Join(dir, "nested", "config.yaml")

	if err := UpdateGatewayFilter(path, "whitelist", []string{"x.com:1"}); err != nil {
		t.Fatalf("UpdateGatewayFilter failed: %v", err)
	}

	got := readFileString(t, path)
	if !strings.Contains(got, "gateway_filter_mode: whitelist") {
		t.Fatalf("the new file should contain mode, actual content:\n%s", got)
	}
	if !strings.Contains(got, "gateway_filter_patterns: x.com:1") {
		t.Fatalf("the new file should contain patterns, actual content:\n%s", got)
	}
}

// TestUpdateGatewayFilterEmptyPatterns verifies an empty list writes an empty value and can be read back as empty.
func TestUpdateGatewayFilterEmptyPatterns(t *testing.T) {
	path := writeTempConfig(t, "gateway_filter_mode: whitelist\ngateway_filter_patterns: a.com:1\n")

	if err := UpdateGatewayFilter(path, "off", nil); err != nil {
		t.Fatalf("UpdateGatewayFilter failed: %v", err)
	}

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.GatewayFilterMode != "off" {
		t.Fatalf("mode should be off, got %q", cfg.GatewayFilterMode)
	}
	if len(cfg.GatewayFilterPatterns) != 0 {
		t.Fatalf("patterns should be empty, got %v", cfg.GatewayFilterPatterns)
	}
}

// TestUpdateGatewayFilterEmptyModeFallsBackOff verifies an empty mode falls back to off (no empty value written).
func TestUpdateGatewayFilterEmptyModeFallsBackOff(t *testing.T) {
	path := writeTempConfig(t, "listen: 127.0.0.1:17800\n")

	if err := UpdateGatewayFilter(path, "  ", nil); err != nil {
		t.Fatalf("UpdateGatewayFilter failed: %v", err)
	}

	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load failed: %v", err)
	}
	if cfg.GatewayFilterMode != "off" {
		t.Fatalf("an empty mode should fall back to off, got %q", cfg.GatewayFilterMode)
	}
}

// TestUpdateGatewayFilterEmptyPath verifies an empty path errors, avoiding a wrongful write to the current directory.
func TestUpdateGatewayFilterEmptyPath(t *testing.T) {
	if err := UpdateGatewayFilter("", "off", nil); err == nil {
		t.Fatal("an empty path should error")
	}
}
