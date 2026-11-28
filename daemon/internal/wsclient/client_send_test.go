package wsclient

import (
	"testing"
	"time"
)

// waitUntilConnected polls until the client enters the connected state (ws field ready).
// Used to avoid the race where "hello_ack has been sent but the client has not yet written the connection to the field".
func waitUntilConnected(t *testing.T, c *Client) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if c.State() == StateConnected {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("timed out waiting for the client to enter the connected state")
}

// TestSendNotConnected checks: when no connection is established, Send returns an error and does not panic.
// The auto-update flow may report progress when the connection is already closed (especially during the restarting stage),
// in which case it must fail safely rather than crash.
func TestSendNotConnected(t *testing.T) {
	c := New(Options{Gateway: "http://127.0.0.1:1", Token: "t"})
	if err := c.Send(map[string]any{"type": "daemon.update.status"}); err == nil {
		t.Fatal("Send should return an error when not connected")
	}
}

// TestSendFrame checks: when connected, Send sends the whole JSON frame to the peer.
func TestSendFrame(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	// First frame hello, reply hello_ack to make the client enter the connected state.
	if hello := readJSONWithTimeout(t, serverConn); hello["type"] != "hello" {
		t.Fatalf("expected the first frame to be hello, got %v", hello["type"])
	}
	if err := serverConn.WriteJSON(map[string]any{
		"type":       "hello_ack",
		"session_id": "test-session",
	}); err != nil {
		t.Fatalf("failed to reply hello_ack: %v", err)
	}

	// Wait until the client truly establishes the connection (ws field ready) before sending, to avoid the race.
	waitUntilConnected(t, client)

	if err := client.Send(map[string]any{
		"type":    "daemon.update.status",
		"state":   "downloading",
		"version": "v2.0.0",
	}); err != nil {
		t.Fatalf("Send failed: %v", err)
	}

	msg := readJSONSkippingSystemInfo(t, serverConn)
	if msg["type"] != "daemon.update.status" {
		t.Fatalf("expected type=daemon.update.status, got %v", msg["type"])
	}
	if msg["state"] != "downloading" || msg["version"] != "v2.0.0" {
		t.Fatalf("frame content mismatch: %v", msg)
	}
}
