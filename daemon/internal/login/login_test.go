package login

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// TestLoginSuccess login succeeds: verifies the request method/path/body, and parses the token and user info.
func TestLoginSuccess(t *testing.T) {
	var gotMethod, gotPath, gotCT string
	var gotBody map[string]string

	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotPath = r.URL.Path
		gotCT = r.Header.Get("Content-Type")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"data": map[string]any{
				"token": "test-token-abcdefgh",
				"user": map[string]any{
					"user_id":      "u1",
					"username":     "admin",
					"display_name": "Administrator",
					"is_admin":     true,
				},
			},
		})
	}))
	defer gateway.Close()

	result, err := Login(gateway.URL, "admin", "secret")
	if err != nil {
		t.Fatalf("Login failed: %v", err)
	}

	if gotMethod != http.MethodPost {
		t.Errorf("request method = %q, expected POST", gotMethod)
	}
	if gotPath != "/api/auth/login" {
		t.Errorf("request path = %q, expected /api/auth/login", gotPath)
	}
	if !strings.Contains(gotCT, "application/json") {
		t.Errorf("Content-Type = %q, expected to contain application/json", gotCT)
	}
	if gotBody["username"] != "admin" || gotBody["password"] != "secret" {
		t.Errorf("request body = %v, expected username=admin password=secret", gotBody)
	}

	if result.Token != "test-token-abcdefgh" {
		t.Errorf("Token = %q, expected test-token-abcdefgh", result.Token)
	}
	if result.Username != "admin" || result.DisplayName != "Administrator" || !result.IsAdmin {
		t.Errorf("user info parsed incorrectly: %+v", result)
	}
}

// TestLoginRejected when the gateway returns success=false, an error containing error.message should be returned.
func TestLoginRejected(t *testing.T) {
	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success": false,
			"error":   map[string]any{"code": "AUTH_FAILED", "message": "Invalid username or password"},
		})
	}))
	defer gateway.Close()

	_, err := Login(gateway.URL, "admin", "wrong")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "Invalid username or password") {
		t.Fatalf("error message did not pass through the gateway message: %v", err)
	}
}

// TestLoginNonOKStatus when the gateway returns a non-200 status, the error message should contain the status code.
func TestLoginNonOKStatus(t *testing.T) {
	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte("boom"))
	}))
	defer gateway.Close()

	_, err := Login(gateway.URL, "admin", "secret")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Fatalf("error message did not contain the status code 500: %v", err)
	}
}

// TestLoginEmptyToken when the gateway returns success=true but an empty token, it should be treated as an abnormal response.
func TestLoginEmptyToken(t *testing.T) {
	gateway := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"success": true,
			"data":    map[string]any{"token": ""},
		})
	}))
	defer gateway.Close()

	_, err := Login(gateway.URL, "admin", "secret")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "token") {
		t.Fatalf("error message did not mention token: %v", err)
	}
}

// TestLoginParamErrors an empty gateway / empty username / empty password should return an argument error directly (no request sent).
func TestLoginParamErrors(t *testing.T) {
	cases := []struct {
		name     string
		gateway  string
		username string
		password string
		wantMsg  string
	}{
		{"empty gateway", "", "admin", "secret", "the gateway address is empty"},
		{"empty username", "http://127.0.0.1:1", "", "secret", "the username cannot be empty"},
		{"empty password", "http://127.0.0.1:1", "admin", "", "the password cannot be empty"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			_, err := Login(c.gateway, c.username, c.password)
			if err == nil {
				t.Fatal("expected an error, got nil")
			}
			if !strings.Contains(err.Error(), c.wantMsg) {
				t.Fatalf("error message = %v, expected to contain %q", err, c.wantMsg)
			}
		})
	}
}

// TestLoginUnreachable an unreachable gateway should return a request error containing the address.
func TestLoginUnreachable(t *testing.T) {
	// No service listens on port 1, so the connection is guaranteed to fail.
	_, err := Login("http://127.0.0.1:1", "admin", "secret")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "login request failed") {
		t.Fatalf("error message = %v, expected to contain \"login request failed\"", err)
	}
}

// TestPushAuthSuccess push succeeds: verifies it hits /api/auth and the body contains gateway/token/name.
func TestPushAuthSuccess(t *testing.T) {
	var gotMethod, gotPath string
	var gotBody map[string]string

	daemon := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotMethod = r.Method
		gotPath = r.URL.Path
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true})
	}))
	defer daemon.Close()

	// httptest.Server.URL is shaped like http://127.0.0.1:PORT; PushAuth needs host:port.
	listen := strings.TrimPrefix(daemon.URL, "http://")
	if err := PushAuth(listen, "http://gateway.example", "tok-123456", "my-pc"); err != nil {
		t.Fatalf("PushAuth failed: %v", err)
	}

	if gotMethod != http.MethodPost {
		t.Errorf("request method = %q, expected POST", gotMethod)
	}
	if gotPath != "/api/auth" {
		t.Errorf("request path = %q, expected /api/auth", gotPath)
	}
	if gotBody["gateway"] != "http://gateway.example" ||
		gotBody["token"] != "tok-123456" ||
		gotBody["name"] != "my-pc" {
		t.Errorf("request body = %v, expected correct gateway/token/name", gotBody)
	}
}

// TestPushAuthDaemonDown when the local daemon is not running, a readable hint should be given.
func TestPushAuthDaemonDown(t *testing.T) {
	err := PushAuth("127.0.0.1:1", "http://gateway.example", "tok-123456", "")
	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "local background service is not running") {
		t.Fatalf("error message = %v, expected to contain \"local background service is not running\"", err)
	}
}

// TestPushAuthParamErrors an empty listen / empty gateway / empty token should return an argument error directly.
func TestPushAuthParamErrors(t *testing.T) {
	cases := []struct {
		name    string
		listen  string
		gateway string
		token   string
		wantMsg string
	}{
		{"empty listen", "", "http://g", "t", "the local service listen address is empty"},
		{"empty gateway", "127.0.0.1:1", "", "t", "the gateway address is empty"},
		{"empty token", "127.0.0.1:1", "http://g", "", "the token is empty"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := PushAuth(c.listen, c.gateway, c.token, "")
			if err == nil {
				t.Fatal("expected an error, got nil")
			}
			if !strings.Contains(err.Error(), c.wantMsg) {
				t.Fatalf("error message = %v, expected to contain %q", err, c.wantMsg)
			}
		})
	}
}

// TestNormalizeGateway normalization: strips surrounding whitespace and trailing slashes, without adding a protocol prefix.
func TestNormalizeGateway(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"  http://a:1/  ", "http://a:1"},
		{"http://a:1", "http://a:1"},
		{"http://a:1///", "http://a:1"},
		{"", ""},
		{"   ", ""},
		// ws/wss are preserved as-is: the daemon side can recognize them when pushing credentials, they must not be broken here.
		{"ws://a:1", "ws://a:1"},
		{"wss://a:1/", "wss://a:1"},
	}
	for _, c := range cases {
		if got := NormalizeGateway(c.in); got != c.want {
			t.Errorf("NormalizeGateway(%q) = %q, expected %q", c.in, got, c.want)
		}
	}
}

// TestHTTPGateway the login endpoint has HTTP semantics; ws/wss must be mapped to http/https,
// otherwise http.Client reports "unsupported protocol scheme ws".
func TestHTTPGateway(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"ws://a:1", "http://a:1"},
		{"wss://a:1", "https://a:1"},
		{"WS://A:1", "http://A:1"},
		{"WSS://A:1", "https://A:1"},
		{"http://a:1", "http://a:1"},
		{"https://a:1", "https://a:1"},
		{"", ""},
	}
	for _, c := range cases {
		if got := HTTPGateway(c.in); got != c.want {
			t.Errorf("HTTPGateway(%q) = %q, expected %q", c.in, got, c.want)
		}
	}
}

// TestMaskToken masking: short tokens are fully masked, long tokens keep the first and last 4 characters.
func TestMaskToken(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"", "***"},
		{"short", "***"},
		{"12345678", "***"},
		{"123456789", "1234...6789"},
	}
	for _, c := range cases {
		if got := MaskToken(c.in); got != c.want {
			t.Errorf("MaskToken(%q) = %q, expected %q", c.in, got, c.want)
		}
	}
}
