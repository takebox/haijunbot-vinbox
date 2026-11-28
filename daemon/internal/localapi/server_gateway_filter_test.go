package localapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/wsclient"
)

// newGatewayFilterTestServer starts a test service with the gateway allow/deny list callbacks injected.
//
// In-memory state simulates the list held by the upper layer (main), avoiding dependence on a real config file;
// the returned pointers point to the current mode/patterns, making it easy to assert whether the setter was called.
func newGatewayFilterTestServer(t *testing.T) (*httptest.Server, *string, *[]string) {
	t.Helper()
	store := auth.NewStore()
	manager := wsclient.NewManager(wsclient.Options{
		ClientID:          "test-client",
		Version:           "test",
		ReconnectMin:      0,
		ReconnectMax:      0,
		HeartbeatInterval: 0,
	})
	srv := New(store, manager, "1.2.3")
	mode := "off"
	var patterns []string
	srv.SetGatewayFilter(
		func() (string, []string) { return mode, patterns },
		func(m string, p []string) (string, []string, error) {
			mode, patterns = m, p
			return mode, patterns, nil
		},
	)
	ts := httptest.NewServer(srv.Handler())
	t.Cleanup(func() {
		ts.Close()
		manager.DisconnectAll()
	})
	return ts, &mode, &patterns
}

// gatewayFilterGet sends GET /api/gateway-filter and parses the response.
func gatewayFilterGet(t *testing.T, base string) (int, map[string]any) {
	t.Helper()
	resp, err := http.Get(base + "/api/gateway-filter")
	if err != nil {
		t.Fatalf("get gateway-filter: %v", err)
	}
	defer resp.Body.Close()
	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode gateway-filter response: %v", err)
	}
	return resp.StatusCode, out
}

// TestGatewayFilterGetDefault verifies that GET returns off + an empty array (not null) when unset.
func TestGatewayFilterGetDefault(t *testing.T) {
	ts, _, _ := newGatewayFilterTestServer(t)

	code, out := gatewayFilterGet(t, ts.URL)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %+v", code, out)
	}
	if out["mode"] != "off" {
		t.Fatalf("expected mode=off, got %v", out["mode"])
	}
	patterns, ok := out["patterns"].([]any)
	if !ok {
		t.Fatalf("patterns should be an array, got %T (%v)", out["patterns"], out["patterns"])
	}
	if len(patterns) != 0 {
		t.Fatalf("default patterns should be empty, got %v", patterns)
	}
}

// TestGatewayFilterPostThenGet verifies that after POST updates, GET can read it, and the setter was actually called.
func TestGatewayFilterPostThenGet(t *testing.T) {
	ts, mode, patterns := newGatewayFilterTestServer(t)

	body := map[string]any{
		"mode":     "whitelist",
		"patterns": []string{"example.com:443", "*.internal:8443"},
	}
	code, out := postJSON(t, ts.URL+"/api/gateway-filter", body)
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %+v", code, out)
	}
	if out["mode"] != "whitelist" {
		t.Fatalf("response mode should be whitelist, got %v", out["mode"])
	}
	if *mode != "whitelist" {
		t.Fatalf("the setter should update the in-memory state, got %q", *mode)
	}
	if len(*patterns) != 2 {
		t.Fatalf("the setter should receive 2 patterns, got %v", *patterns)
	}

	// GET again to confirm the read callback returns the updated value.
	code, out = gatewayFilterGet(t, ts.URL)
	if code != http.StatusOK {
		t.Fatalf("GET expected 200, got %d: %+v", code, out)
	}
	if out["mode"] != "whitelist" {
		t.Fatalf("GET mode should be whitelist, got %v", out["mode"])
	}
	got, ok := out["patterns"].([]any)
	if !ok || len(got) != 2 {
		t.Fatalf("GET patterns should have 2 items, got %v", out["patterns"])
	}
}

// TestGatewayFilterPostEmptyPatterns verifies that an empty patterns array is valid (meaning clear the list).
func TestGatewayFilterPostEmptyPatterns(t *testing.T) {
	ts, _, patterns := newGatewayFilterTestServer(t)

	code, out := postJSON(t, ts.URL+"/api/gateway-filter", map[string]any{
		"mode":     "blacklist",
		"patterns": []string{},
	})
	if code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %+v", code, out)
	}
	if len(*patterns) != 0 {
		t.Fatalf("patterns should be cleared, got %v", *patterns)
	}
}

// TestGatewayFilterPostInvalidMode verifies that an invalid mode returns 400 and does not call the setter.
func TestGatewayFilterPostInvalidMode(t *testing.T) {
	ts, mode, _ := newGatewayFilterTestServer(t)

	// Note: ValidMode internally does TrimSpace + lowercase, so "WHITELIST " is considered valid;
	// only truly invalid values are listed here.
	for _, bad := range []string{"", "allow", "deny", "whitelistx", "1"} {
		code, out := postJSON(t, ts.URL+"/api/gateway-filter", map[string]any{
			"mode":     bad,
			"patterns": []string{"a:1"},
		})
		if code != http.StatusBadRequest {
			t.Fatalf("mode=%q expected 400, got %d: %+v", bad, code, out)
		}
	}
	if *mode != "off" {
		t.Fatalf("an invalid mode should not change the in-memory state, got %q", *mode)
	}
}

// TestGatewayFilterPostInvalidJSON verifies that a request body that is not valid JSON returns 400.
func TestGatewayFilterPostInvalidJSON(t *testing.T) {
	ts, _, _ := newGatewayFilterTestServer(t)

	resp, err := http.Post(ts.URL+"/api/gateway-filter", "application/json",
		bytes.NewBufferString("{not json"))
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", resp.StatusCode)
	}
}

// TestGatewayFilterMethodNotAllowed verifies that an unsupported method returns 405.
func TestGatewayFilterMethodNotAllowed(t *testing.T) {
	ts, _, _ := newGatewayFilterTestServer(t)

	req, err := http.NewRequest(http.MethodDelete, ts.URL+"/api/gateway-filter", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405, got %d", resp.StatusCode)
	}
}

// TestGatewayFilterNotInjected verifies that POST returns 501 when the setter is not injected,
// avoiding "looks successful but did not take effect".
func TestGatewayFilterNotInjected(t *testing.T) {
	store := auth.NewStore()
	manager := wsclient.NewManager(wsclient.Options{ClientID: "c", Version: "v"})
	srv := New(store, manager, "1.2.3")
	ts := httptest.NewServer(srv.Handler())
	t.Cleanup(func() {
		ts.Close()
		manager.DisconnectAll()
	})

	code, out := postJSON(t, ts.URL+"/api/gateway-filter", map[string]any{
		"mode": "off",
	})
	if code != http.StatusNotImplemented {
		t.Fatalf("should return 501 when the setter is not injected, got %d: %+v", code, out)
	}
}

// TestIsLoopbackRequest covers source determination: only loopback is recognized, and X-Forwarded-For is not trusted.
func TestIsLoopbackRequest(t *testing.T) {
	cases := []struct {
		name       string
		remoteAddr string
		xff        string
		want       bool
	}{
		{"ipv4 loopback", "127.0.0.1:12345", "", true},
		{"ipv4 loopback range", "127.8.8.8:1", "", true},
		{"ipv6 loopback", "[::1]:12345", "", true},
		{"localhost", "localhost:12345", "", true},
		{"public IPv4", "8.8.8.8:12345", "", false},
		{"private IPv4", "192.168.1.10:12345", "", false},
		{"loopback without port", "127.0.0.1", "", true},
		{"empty", "", "", false},
		{"forged XFF must not pass", "8.8.8.8:12345", "127.0.0.1", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/api/gateway-filter", nil)
			req.RemoteAddr = tc.remoteAddr
			if tc.xff != "" {
				req.Header.Set("X-Forwarded-For", tc.xff)
			}
			if got := isLoopbackRequest(req); got != tc.want {
				t.Fatalf("isLoopbackRequest(remote=%q, xff=%q) = %v, expected %v",
					tc.remoteAddr, tc.xff, got, tc.want)
			}
		})
	}
}

// TestGatewayFilterRejectsNonLoopback verifies that non-loopback sources always get 403 (both GET and POST are blocked).
//
// Calls the handler directly (bypassing httptest.Server's real TCP) so RemoteAddr can be forged.
func TestGatewayFilterRejectsNonLoopback(t *testing.T) {
	srv := New(auth.NewStore(), wsclient.NewManager(wsclient.Options{ClientID: "c", Version: "v"}), "1.2.3")
	srv.SetGatewayFilter(
		func() (string, []string) { return "off", nil },
		func(m string, p []string) (string, []string, error) { return m, p, nil },
	)

	for _, method := range []string{http.MethodGet, http.MethodPost} {
		req := httptest.NewRequest(method, "/api/gateway-filter", nil)
		req.RemoteAddr = "203.0.113.7:5555"
		rec := httptest.NewRecorder()
		srv.handleGatewayFilter(rec, req)
		if rec.Code != http.StatusForbidden {
			t.Fatalf("%s non-loopback source expected 403, got %d", method, rec.Code)
		}
	}
}

// TestGatewayFilterAllowsLoopback verifies that a loopback source can read/write normally (handler called directly).
func TestGatewayFilterAllowsLoopback(t *testing.T) {
	srv := New(auth.NewStore(), wsclient.NewManager(wsclient.Options{ClientID: "c", Version: "v"}), "1.2.3")
	srv.SetGatewayFilter(
		func() (string, []string) { return "off", nil },
		func(m string, p []string) (string, []string, error) { return m, p, nil },
	)

	req := httptest.NewRequest(http.MethodGet, "/api/gateway-filter", nil)
	req.RemoteAddr = "127.0.0.1:5555"
	rec := httptest.NewRecorder()
	srv.handleGatewayFilter(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("loopback source expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
}
