package localapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/capability"
	"haijunbot-daemon/internal/wsclient"
)

// resetAutoInstallBrowserExt resets the package-level switch state.
//
// The switch is a package-level variable in capability and tests would pollute each other, so each case explicitly resets it to
// the default false (off) before starting.
func resetAutoInstallBrowserExt(t *testing.T) {
	t.Helper()
	capability.SetAutoInstallBrowserExt(false)
	if capability.AutoInstallBrowserExt() {
		t.Fatalf("the switch should be false after reset")
	}
}

// getSettings queries /api/settings and returns the status code and the parsed JSON.
func getSettings(t *testing.T, base string) (int, map[string]any) {
	t.Helper()
	resp, err := http.Get(base + "/api/settings")
	if err != nil {
		t.Fatalf("get settings: %v", err)
	}
	defer resp.Body.Close()
	var out map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatalf("decode settings: %v", err)
	}
	return resp.StatusCode, out
}

// TestSettingsDefaultOff verifies the switch is false by default (before any push).
func TestSettingsDefaultOff(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	code, body := getSettings(t, srv.URL)
	if code != http.StatusOK {
		t.Fatalf("GET /api/settings status = %d, expected 200; body=%v", code, body)
	}
	if body["success"] != true {
		t.Fatalf("success should be true: %v", body)
	}
	if body["auto_install_browser_ext"] != false {
		t.Fatalf("default auto_install_browser_ext should be false, got %v", body["auto_install_browser_ext"])
	}
}

// TestSettingsPostThenGet verifies that after turning the switch on, GET reads true; after turning it off, it reads false.
func TestSettingsPostThenGet(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	// Turn on
	code, body := postJSON(t, srv.URL+"/api/settings", map[string]any{"auto_install_browser_ext": true})
	if code != http.StatusOK {
		t.Fatalf("POST /api/settings status = %d, expected 200; body=%v", code, body)
	}
	if body["success"] != true || body["auto_install_browser_ext"] != true {
		t.Fatalf("POST response does not match the contract: %v", body)
	}
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("the capability switch should be true after POST")
	}

	code, body = getSettings(t, srv.URL)
	if code != http.StatusOK || body["auto_install_browser_ext"] != true {
		t.Fatalf("GET should return true: code=%d body=%v", code, body)
	}

	// Turn off
	code, body = postJSON(t, srv.URL+"/api/settings", map[string]any{"auto_install_browser_ext": false})
	if code != http.StatusOK || body["auto_install_browser_ext"] != false {
		t.Fatalf("turn-off response does not match the contract: code=%d body=%v", code, body)
	}
	if capability.AutoInstallBrowserExt() {
		t.Fatalf("the capability switch should be false after turning off")
	}
}

// TestSettingsPostMissingField verifies that a missing field returns 400 and does not change the switch value.
func TestSettingsPostMissingField(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	// First turn it on, to verify that a request with a missing field does not change it.
	postJSON(t, srv.URL+"/api/settings", map[string]any{"auto_install_browser_ext": true})

	code, body := postJSON(t, srv.URL+"/api/settings", map[string]any{})
	if code != http.StatusBadRequest {
		t.Fatalf("missing-field status = %d, expected 400; body=%v", code, body)
	}
	if body["success"] != false {
		t.Fatalf("failure response success should be false: %v", body)
	}
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("a request with a missing field should not change the switch (should still be true)")
	}
}

// TestSettingsInvalidJSON verifies that invalid JSON returns 400.
func TestSettingsInvalidJSON(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	resp, err := http.Post(srv.URL+"/api/settings", "application/json", bytes.NewBufferString("{not json"))
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("status = %d, expected 400", resp.StatusCode)
	}
}

// TestSettingsMethodNotAllowed verifies that a non-GET/POST method returns 405.
func TestSettingsMethodNotAllowed(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	req, err := http.NewRequest(http.MethodDelete, srv.URL+"/api/settings", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("delete settings: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusMethodNotAllowed {
		t.Fatalf("DELETE /api/settings status = %d, expected 405", resp.StatusCode)
	}
}

// TestAuthCarriesAutoInstallSwitch verifies that /api/auth carrying the field updates the switch synchronously.
func TestAuthCarriesAutoInstallSwitch(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	enabled := true
	code, body := postJSON(t, srv.URL+"/api/auth", authRequest{
		Gateway:               "http://gw-a.example.com:8080",
		Token:                 "token-aaaaaaaa",
		AutoInstallBrowserExt: &enabled,
	})
	if code != http.StatusOK {
		t.Fatalf("auth status = %d, expected 200; body=%v", code, body)
	}
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("after /api/auth carries true, the switch should be true")
	}

	// The turn-off direction works too (distinguishing nil from explicit false).
	disabled := false
	postJSON(t, srv.URL+"/api/auth", authRequest{
		Gateway:               "http://gw-a.example.com:8080",
		Token:                 "token-aaaaaaaa",
		AutoInstallBrowserExt: &disabled,
	})
	if capability.AutoInstallBrowserExt() {
		t.Fatalf("after /api/auth carries false, the switch should be false")
	}
}

// TestAuthWithoutSwitchKeepsValue verifies that omitting the field (nil) keeps the original value, for compatibility with old frontends.
func TestAuthWithoutSwitchKeepsValue(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	// First set it to true.
	enabled := true
	postJSON(t, srv.URL+"/api/auth", authRequest{
		Gateway:               "http://gw-a.example.com:8080",
		Token:                 "token-aaaaaaaa",
		AutoInstallBrowserExt: &enabled,
	})
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("precondition failed: the switch should be true")
	}

	// An old frontend does not carry the field; the switch should not be changed back to false.
	postJSON(t, srv.URL+"/api/auth", authRequest{
		Gateway: "http://gw-b.example.com:9090",
		Token:   "token-bbbbbbbb",
	})
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("/api/auth without the field should not change the switch (should still be true)")
	}
}

// TestAutoInstallBrowserExtConcurrent verifies that concurrent read/write of the switch does not trigger a data race (with -race).
func TestAutoInstallBrowserExtConcurrent(t *testing.T) {
	resetAutoInstallBrowserExt(t)

	done := make(chan struct{})
	// Writer goroutine
	go func() {
		for i := 0; i < 1000; i++ {
			capability.SetAutoInstallBrowserExt(i%2 == 0)
		}
		close(done)
	}()
	// Reader goroutine
	for i := 0; i < 1000; i++ {
		_ = capability.AutoInstallBrowserExt()
	}
	<-done
}

// TestBrowserExtEnabledCallbackOnTransition verifies the callback is triggered when the switch changes from off to on;
// setting true repeatedly (no transition) or setting false does not trigger it.
//
// Regression background: the daemon checks the switch only once at hello_ack, while the frontend push of the switch usually arrives after
// hello_ack, causing the user's already-enabled switch to still be judged as "off" and the sync to be skipped. The fix is to call back the upper layer
// to do one supplementary sync check when the switch transitions false→true; this case locks in that triggering semantics.
func TestBrowserExtEnabledCallbackOnTransition(t *testing.T) {
	resetAutoInstallBrowserExt(t)

	store := auth.NewStore()
	manager := wsclient.NewManager(wsclient.Options{
		ClientID:          "test-client",
		Version:           "test",
		ReconnectMin:      0,
		ReconnectMax:      0,
		HeartbeatInterval: 0,
	})
	api := New(store, manager, "1.2.3")
	var calls int
	api.SetOnBrowserExtEnabled(func() { calls++ })
	srv := httptest.NewServer(api.Handler())
	t.Cleanup(func() {
		srv.Close()
		manager.DisconnectAll()
	})

	enabled := true
	// First turn-on: a false→true transition occurs, callback once.
	postJSON(t, srv.URL+"/api/auth", authRequest{
		Gateway:               "http://gw-a.example.com:8080",
		Token:                 "token-aaaaaaaa",
		AutoInstallBrowserExt: &enabled,
	})
	if calls != 1 {
		t.Fatalf("the first turn-on should trigger 1 callback, got %d", calls)
	}

	// Set true again: no transition, no trigger.
	postJSON(t, srv.URL+"/api/settings", settingsRequest{AutoInstallBrowserExt: &enabled})
	if calls != 1 {
		t.Fatalf("setting true repeatedly should not trigger the callback, got %d", calls)
	}

	// Set false: no trigger.
	disabled := false
	postJSON(t, srv.URL+"/api/settings", settingsRequest{AutoInstallBrowserExt: &disabled})
	if calls != 1 {
		t.Fatalf("setting false should not trigger the callback, got %d", calls)
	}

	// Turn on again: another transition, callback increments to 2.
	postJSON(t, srv.URL+"/api/settings", settingsRequest{AutoInstallBrowserExt: &enabled})
	if calls != 2 {
		t.Fatalf("turning the switch on again should trigger the 2nd callback, got %d", calls)
	}
}

// TestBrowserExtEnabledCallbackNilSafe verifies that a switch transition does not panic when no callback is injected.
func TestBrowserExtEnabledCallbackNilSafe(t *testing.T) {
	resetAutoInstallBrowserExt(t)
	srv, _, _ := newTestServer(t)

	enabled := true
	code, body := postJSON(t, srv.URL+"/api/settings", settingsRequest{AutoInstallBrowserExt: &enabled})
	if code != http.StatusOK {
		t.Fatalf("settings status = %d, expected 200; body=%v", code, body)
	}
	if !capability.AutoInstallBrowserExt() {
		t.Fatalf("the switch should be true")
	}
}
