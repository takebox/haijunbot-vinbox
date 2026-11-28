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

// newTestServer builds a test service using real HTTP (httptest, not relying on a fixed port).
//
// The Manager's clients point to unreachable addresses and connections fail and enter reconnect, but status queries and
// credential storage behavior are unaffected; at test end DisconnectAll is called uniformly to avoid goroutine leaks.
func newTestServer(t *testing.T) (*httptest.Server, *auth.Store, *wsclient.Manager) {
	t.Helper()
	store := auth.NewStore()
	manager := wsclient.NewManager(wsclient.Options{
		ClientID:          "test-client",
		Version:           "test",
		ReconnectMin:      0,
		ReconnectMax:      0,
		HeartbeatInterval: 0,
	})
	srv := httptest.NewServer(New(store, manager, "1.2.3").Handler())
	t.Cleanup(func() {
		srv.Close()
		manager.DisconnectAll()
	})
	return srv, store, manager
}

// postJSON sends a POST request and returns the status code and the parsed JSON.
func postJSON(t *testing.T, url string, body any) (int, map[string]any) {
	t.Helper()
	var buf bytes.Buffer
	if body != nil {
		if err := json.NewEncoder(&buf).Encode(body); err != nil {
			t.Fatalf("encode body: %v", err)
		}
	}
	resp, err := http.Post(url, "application/json", &buf)
	if err != nil {
		t.Fatalf("post %s: %v", url, err)
	}
	defer resp.Body.Close()
	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode response from %s: %v", url, err)
	}
	return resp.StatusCode, out
}

// getStatus queries /api/status and returns the parsed JSON.
func getStatus(t *testing.T, base string) (int, map[string]any) {
	t.Helper()
	resp, err := http.Get(base + "/api/status")
	if err != nil {
		t.Fatalf("get status: %v", err)
	}
	defer resp.Body.Close()
	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode status: %v", err)
	}
	return resp.StatusCode, out
}

// statusGateways extracts the gateways array from the status response.
func statusGateways(t *testing.T, body map[string]any) []map[string]any {
	t.Helper()
	raw, ok := body["gateways"].([]any)
	if !ok {
		t.Fatalf("gateways field missing or wrong type: %#v", body["gateways"])
	}
	out := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		m, ok := item.(map[string]any)
		if !ok {
			t.Fatalf("gateways element wrong type: %#v", item)
		}
		out = append(out, m)
	}
	return out
}

// TestAuthMultiGatewayCoexist is the core case: two different gateways push credentials successively without displacing each other.
func TestAuthMultiGatewayCoexist(t *testing.T) {
	srv, store, manager := newTestServer(t)

	code, body := postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-a.example.com:8080", Token: "token-aaaaaaaa"})
	if code != http.StatusOK {
		t.Fatalf("first auth status = %d, expected 200; body=%v", code, body)
	}
	if body["success"] != true || body["status"] != "connecting" || body["daemon_version"] != "1.2.3" {
		t.Fatalf("first auth response does not match the contract: %v", body)
	}

	code, body = postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "https://gw-b.example.com", Token: "token-bbbbbbbb"})
	if code != http.StatusOK {
		t.Fatalf("second auth status = %d, expected 200; body=%v", code, body)
	}

	if manager.Count() != 2 {
		t.Fatalf("manager.Count() = %d, expected 2", manager.Count())
	}
	if !store.Has("http://gw-a.example.com:8080") || !store.Has("https://gw-b.example.com") {
		t.Fatalf("both gateways' credentials should exist: %v", store.List())
	}

	code, body = getStatus(t, srv.URL)
	if code != http.StatusOK {
		t.Fatalf("status status = %d, expected 200", code)
	}
	if body["success"] != true || body["daemon_version"] != "1.2.3" {
		t.Fatalf("status top-level fields do not match the contract: %v", body)
	}
	gws := statusGateways(t, body)
	if len(gws) != 2 {
		t.Fatalf("status returned %d gateways, expected 2: %v", len(gws), gws)
	}
	// In gateway lexicographic order: http://gw-a... < https://gw-b...
	if gws[0]["gateway"] != "http://gw-a.example.com:8080" {
		t.Fatalf("first gateway = %v, expected http://gw-a.example.com:8080", gws[0]["gateway"])
	}
	if gws[1]["gateway"] != "https://gw-b.example.com" {
		t.Fatalf("second gateway = %v, expected https://gw-b.example.com", gws[1]["gateway"])
	}
	// Field completeness and types.
	for i, gw := range gws {
		for _, key := range []string{"gateway", "session_id", "connected", "state", "token_valid", "auth_failed"} {
			if _, ok := gw[key]; !ok {
				t.Fatalf("gateway %d is missing field %q: %v", i, key, gw)
			}
		}
		if gw["token_valid"] != true {
			t.Fatalf("gateway %d token_valid = %v, expected true", i, gw["token_valid"])
		}
		if gw["auth_failed"] != false {
			t.Fatalf("gateway %d auth_failed = %v, expected false", i, gw["auth_failed"])
		}
	}
}

// TestAuthSameGatewayReplaces verifies that repeated pushes to the same gateway keep only the newest connection, without affecting other gateways.
func TestAuthSameGatewayReplaces(t *testing.T) {
	srv, _, manager := newTestServer(t)

	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-a.example.com:8080", Token: "token-old-old"})
	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-a.example.com:8080", Token: "token-new-new"})
	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-b.example.com:9090", Token: "token-bbbbbbbb"})

	if manager.Count() != 2 {
		t.Fatalf("manager.Count() = %d, expected 2 (only one entry per gateway)", manager.Count())
	}
	_, body := getStatus(t, srv.URL)
	gws := statusGateways(t, body)
	if len(gws) != 2 {
		t.Fatalf("status returned %d gateways, expected 2: %v", len(gws), gws)
	}
}

// TestLogoutSingleGateway verifies that a logout with gateway only clears that gateway; the other remains.
func TestLogoutSingleGateway(t *testing.T) {
	srv, store, manager := newTestServer(t)

	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-a.example.com:8080", Token: "token-aaaaaaaa"})
	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-b.example.com:9090", Token: "token-bbbbbbbb"})

	code, body := postJSON(t, srv.URL+"/api/logout", logoutRequest{Gateway: "http://gw-a.example.com:8080"})
	if code != http.StatusOK || body["success"] != true {
		t.Fatalf("logout response does not match the contract: code=%d body=%v", code, body)
	}

	if store.Has("http://gw-a.example.com:8080") {
		t.Fatalf("gw-a's credentials should have been cleared")
	}
	if !store.Has("http://gw-b.example.com:9090") {
		t.Fatalf("gw-b's credentials should not be cleared")
	}
	if manager.Count() != 1 {
		t.Fatalf("manager.Count() = %d, expected 1", manager.Count())
	}

	_, body = getStatus(t, srv.URL)
	gws := statusGateways(t, body)
	if len(gws) != 1 {
		t.Fatalf("status returned %d gateways, expected 1: %v", len(gws), gws)
	}
	if gws[0]["gateway"] != "http://gw-b.example.com:9090" {
		t.Fatalf("remaining gateway = %v, expected http://gw-b.example.com:9090", gws[0]["gateway"])
	}
}

// TestLogoutAll verifies that a logout without gateway clears all (backward compatible with old semantics).
func TestLogoutAll(t *testing.T) {
	srv, store, manager := newTestServer(t)

	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-a.example.com:8080", Token: "token-aaaaaaaa"})
	postJSON(t, srv.URL+"/api/auth", authRequest{Gateway: "http://gw-b.example.com:9090", Token: "token-bbbbbbbb"})

	// An empty request body should also be accepted.
	code, body := postJSON(t, srv.URL+"/api/logout", nil)
	if code != http.StatusOK || body["success"] != true {
		t.Fatalf("logout response does not match the contract: code=%d body=%v", code, body)
	}

	if len(store.List()) != 0 {
		t.Fatalf("all credentials should be cleared: %v", store.List())
	}
	if manager.Count() != 0 {
		t.Fatalf("manager.Count() = %d, expected 0", manager.Count())
	}

	_, body = getStatus(t, srv.URL)
	gws := statusGateways(t, body)
	if len(gws) != 0 {
		t.Fatalf("status should return 0 gateways: %v", gws)
	}
}

// TestAuthValidation verifies that an empty gateway or token returns 400.
func TestAuthValidation(t *testing.T) {
	srv, _, manager := newTestServer(t)

	cases := []authRequest{
		{Gateway: "", Token: "token-aaaaaaaa"},
		{Gateway: "http://gw-a.example.com:8080", Token: ""},
		{Gateway: "", Token: ""},
	}
	for _, c := range cases {
		code, body := postJSON(t, srv.URL+"/api/auth", c)
		if code != http.StatusBadRequest {
			t.Fatalf("gateway=%q token=%q status = %d, expected 400; body=%v", c.Gateway, c.Token, code, body)
		}
		if body["success"] != false {
			t.Fatalf("failure response success should be false: %v", body)
		}
	}
	if manager.Count() != 0 {
		t.Fatalf("an invalid request should not establish a connection, Count() = %d", manager.Count())
	}
}

// TestAuthInvalidJSON verifies that invalid JSON returns 400.
func TestAuthInvalidJSON(t *testing.T) {
	srv, _, _ := newTestServer(t)

	resp, err := http.Post(srv.URL+"/api/auth", "application/json", bytes.NewBufferString("{not json"))
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, expected 400", resp.StatusCode)
	}
}

// TestMethodNotAllowed verifies that a wrong method returns 405.
func TestMethodNotAllowed(t *testing.T) {
	srv, _, _ := newTestServer(t)

	// GET /api/auth
	resp, err := http.Get(srv.URL + "/api/auth")
	if err != nil {
		t.Fatalf("get auth: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("GET /api/auth status = %d, expected 405", resp.StatusCode)
	}

	// POST /api/status
	code, _ := postJSON(t, srv.URL+"/api/status", nil)
	if code != http.StatusMethodNotAllowed {
		t.Fatalf("POST /api/status status = %d, expected 405", code)
	}

	// GET /api/logout
	resp, err = http.Get(srv.URL + "/api/logout")
	if err != nil {
		t.Fatalf("get logout: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("GET /api/logout status = %d, expected 405", resp.StatusCode)
	}
}

// TestStatusContentType verifies the response Content-Type and structure contract.
func TestStatusContentType(t *testing.T) {
	srv, _, _ := newTestServer(t)

	resp, err := http.Get(srv.URL + "/api/status")
	if err != nil {
		t.Fatalf("get status: %v", err)
	}
	defer resp.Body.Close()
	if ct := resp.Header.Get("Content-Type"); ct != "application/json; charset=utf-8" {
		t.Fatalf("Content-Type = %q", ct)
	}
	var body map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if _, ok := body["gateways"].([]any); !ok {
		t.Fatalf("gateways should be an array: %#v", body["gateways"])
	}
	if body["daemon_version"] != "1.2.3" {
		t.Fatalf("daemon_version = %v", body["daemon_version"])
	}
}

// TestCORSPreflight verifies that a preflight request (OPTIONS) must return CORS headers and not enter business logic.
//
// Scenario: a web page deployed at https://hjb-ai.cn does a cross-origin POST to http://127.0.0.1:17800;
// the browser first sends an OPTIONS preflight; without CORS headers it is blocked outright.
func TestCORSPreflight(t *testing.T) {
	srv, _, _ := newTestServer(t)

	req, err := http.NewRequest(http.MethodOptions, srv.URL+"/api/auth", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Origin", "https://hjb-ai.cn")
	req.Header.Set("Access-Control-Request-Method", "POST")
	req.Header.Set("Access-Control-Request-Headers", "content-type")
	req.Header.Set("Access-Control-Request-Private-Network", "true")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("preflight: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("preflight status = %d, expected 204", resp.StatusCode)
	}
	checks := map[string]string{
		"Access-Control-Allow-Origin":          "*",
		"Access-Control-Allow-Methods":         "GET, POST, OPTIONS",
		"Access-Control-Allow-Headers":         "Content-Type",
		"Access-Control-Allow-Private-Network": "true",
	}
	for k, want := range checks {
		if got := resp.Header.Get(k); got != want {
			t.Fatalf("%s = %q, expected %q", k, got, want)
		}
	}
}

// TestCORSActualResponse verifies that actual requests (including error responses) also carry CORS headers,
// otherwise the browser cannot read the status code and response body.
func TestCORSActualResponse(t *testing.T) {
	srv, _, _ := newTestServer(t)

	// Success path: GET /api/status
	resp, err := http.Get(srv.URL + "/api/status")
	if err != nil {
		t.Fatalf("get status: %v", err)
	}
	resp.Body.Close()
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "*" {
		t.Fatalf("status response Allow-Origin = %q, expected *", got)
	}

	// Error path: GET /api/auth → 405, must also carry CORS headers.
	resp, err = http.Get(srv.URL + "/api/auth")
	if err != nil {
		t.Fatalf("get auth: %v", err)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("GET /api/auth status = %d, expected 405", resp.StatusCode)
	}
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "*" {
		t.Fatalf("405 response Allow-Origin = %q, expected *", got)
	}
}
