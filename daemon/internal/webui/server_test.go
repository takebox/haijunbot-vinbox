package webui

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/wsclient"
)

// newTestServer constructs a webui.Server bound to the given gateway address.
//
// manager uses a zero-value Manager: this test only verifies "credentials written to store", not
// real connections (connections are covered by wsclient's own tests). ConnectWithName is a safe
// no-op for unknown gateways.
func newTestServer(t *testing.T, gateway string) (*Server, *auth.Store) {
	t.Helper()
	store := auth.NewStore()
	manager := wsclient.NewManager(wsclient.Options{})
	return New(store, manager, "test-version"), store
}

// postJSON sends a JSON POST request to the handler.
func postJSON(t *testing.T, h http.Handler, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// TestIndexReturnsLoginPage: GET / should return HTML containing the key form elements.
func TestIndexReturnsLoginPage(t *testing.T) {
	srv, _ := newTestServer(t, "")
	h := srv.Handler()

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("GET / status code = %d, want 200", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); !strings.Contains(ct, "text/html") {
		t.Fatalf("Content-Type = %q, want to contain text/html", ct)
	}
	body := rec.Body.String()
	for _, want := range []string{"<form", "username", "password", "gateway", "/api/login"} {
		if !strings.Contains(body, want) {
			t.Errorf("login page missing key content %q", want)
		}
	}
}

// TestLoginSuccess: a successful login should write credentials and return success=true.
func TestLoginSuccess(t *testing.T) {
	// Mock gateway: returns a successful response.
	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/auth/login" {
			http.NotFound(w, r)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"data": map[string]any{
				"token": "test-token-abcdefgh",
				"user": map[string]any{
					"user_id":      "u1",
					"username":     "admin",
					"display_name": "admin",
					"is_admin":     true,
				},
			},
		})
	}))
	defer gateway.Close()

	srv, store := newTestServer(t, gateway.URL)
	h := srv.Handler()

	rec := postJSON(t, h, "/api/login",
		`{"gateway":"`+gateway.URL+`","username":"admin","password":"secret"}`)

	if rec.Code != http.StatusOK {
		t.Fatalf("status code = %d, want 200; body=%s", rec.Code, rec.Body.String())
	}
	var resp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if resp["success"] != true {
		t.Fatalf("success = %v, want true", resp["success"])
	}
	// Credentials should have been written to store.
	creds, err := store.Get(gateway.URL)
	if err != nil {
		t.Fatalf("store.Get failed: %v", err)
	}
	if creds.Token != "test-token-abcdefgh" {
		t.Fatalf("token in store = %q, want test-token-abcdefgh", creds.Token)
	}
}

// TestLoginWrongPassword: when the gateway rejects, it should return 400 and pass through the error message.
func TestLoginWrongPassword(t *testing.T) {
	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success": false,
			"error":   map[string]any{"code": "AUTH_FAILED", "message": "Invalid username or password"},
		})
	}))
	defer gateway.Close()

	srv, store := newTestServer(t, gateway.URL)
	rec := postJSON(t, srv.Handler(), "/api/login",
		`{"gateway":"`+gateway.URL+`","username":"admin","password":"wrong"}`)

	if rec.Code != http.StatusBadRequest {
			t.Fatalf("status code = %d, want 400; body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "Invalid username or password") {
		t.Fatalf("response did not pass through gateway error message: %s", rec.Body.String())
	}
	// A failed login should not write credentials.
	if store.Has(gateway.URL) {
		t.Fatalf("credentials were written despite a failed login")
	}
}

// TestLoginMissingParams: missing required parameters should return 400.
func TestLoginMissingParams(t *testing.T) {
	srv, _ := newTestServer(t, "")
	h := srv.Handler()

	cases := []struct {
		name string
		body string
	}{
		{"missing gateway", `{"username":"admin","password":"x"}`},
		{"missing username", `{"gateway":"http://x","password":"x"}`},
		{"missing password", `{"gateway":"http://x","username":"admin"}`},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rec := postJSON(t, h, "/api/login", c.body)
			if rec.Code != http.StatusBadRequest {
		t.Fatalf("status code = %d, want 400; body=%s", rec.Code, rec.Body.String())
			}
		})
	}
}

// TestLoginInvalidJSON: invalid JSON should return 400.
func TestLoginInvalidJSON(t *testing.T) {
	srv, _ := newTestServer(t, "")
	rec := postJSON(t, srv.Handler(), "/api/login", "{not json")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status code = %d, want 400", rec.Code)
	}
}

// TestLoginMethodNotAllowed: GET /api/login should return 405.
func TestLoginMethodNotAllowed(t *testing.T) {
	srv, _ := newTestServer(t, "")
	req := httptest.NewRequest(http.MethodGet, "/api/login", nil)
	rec := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status code = %d, want 405", rec.Code)
	}
}

// TestIndexUnknownPathNotFound: non-root paths should 404.
func TestIndexUnknownPathNotFound(t *testing.T) {
	srv, _ := newTestServer(t, "")
	req := httptest.NewRequest(http.MethodGet, "/whatever", nil)
	rec := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status code = %d, want 404", rec.Code)
	}
}
