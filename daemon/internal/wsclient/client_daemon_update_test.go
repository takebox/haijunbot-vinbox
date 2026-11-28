package wsclient

import "testing"

// TestHandleMessage_DaemonUpdate checks: when hello_ack carries daemon_update, OnDaemonUpdate is triggered,
// and session_id and the original map are passed through correctly.
func TestHandleMessage_DaemonUpdate(t *testing.T) {
	var gotSID string
	var gotInfo map[string]any
	c := &Client{opts: Options{
		OnDaemonUpdate: func(sessionID string, info map[string]any) {
			gotSID = sessionID
			gotInfo = info
		},
	}}

	info := map[string]any{"available": true, "latest_version": "v2.0.0"}
	c.handleMessage(nil, map[string]any{
		"type":          "hello_ack",
		"session_id":    "sid-123",
		"daemon_update": info,
	})

	if gotSID != "sid-123" {
		t.Fatalf("session_id not passed through: %q", gotSID)
	}
	if gotInfo == nil || gotInfo["latest_version"] != "v2.0.0" {
		t.Fatalf("daemon_update not passed through: %v", gotInfo)
	}
}

// TestHandleMessage_DaemonUpdateMissing checks: when hello_ack does not carry daemon_update, no callback is made.
func TestHandleMessage_DaemonUpdateMissing(t *testing.T) {
	called := false
	c := &Client{opts: Options{
		OnDaemonUpdate: func(string, map[string]any) { called = true },
	}}
	c.handleMessage(nil, map[string]any{
		"type":       "hello_ack",
		"session_id": "sid-123",
	})
	if called {
		t.Fatal("no callback should occur when daemon_update is not carried")
	}
}

// TestHandleMessage_DaemonUpdateWrongType checks: when daemon_update has the wrong type, no callback and no panic.
func TestHandleMessage_DaemonUpdateWrongType(t *testing.T) {
	called := false
	c := &Client{opts: Options{
		OnDaemonUpdate: func(string, map[string]any) { called = true },
	}}
	c.handleMessage(nil, map[string]any{
		"type":          "hello_ack",
		"session_id":    "sid-123",
		"daemon_update": "not-an-object",
	})
	if called {
		t.Fatal("no callback should occur when the type is wrong")
	}
}

// TestHandleMessage_DaemonUpdateNilCallback checks: receiving daemon_update when no callback is set does not panic.
func TestHandleMessage_DaemonUpdateNilCallback(t *testing.T) {
	c := &Client{opts: Options{}}
	c.handleMessage(nil, map[string]any{
		"type":          "hello_ack",
		"session_id":    "sid-123",
		"daemon_update": map[string]any{"available": true},
	})
}
