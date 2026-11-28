package wsclient

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"

	"haijunbot-daemon/internal/capability"
)

// testServer starts a local WS server and returns its HTTP address and the upgraded connection channel.
//
// The server only performs a minimal handshake: accepts the haijunbot-daemon subprotocol, then replies hello_ack and waits for the test to drive it.
func startCapabilityTestServer(t *testing.T) (string, <-chan *websocket.Conn) {
	t.Helper()

	upgrader := websocket.Upgrader{
		Subprotocols: []string{"haijunbot-daemon"},
		CheckOrigin:  func(*http.Request) bool { return true },
	}
	connCh := make(chan *websocket.Conn, 1)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/daemon/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			t.Errorf("failed to upgrade WS: %v", err)
			return
		}
		connCh <- conn
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv.URL, connCh
}

// readJSONWithTimeout reads a JSON frame with a timeout.
func readJSONWithTimeout(t *testing.T, conn *websocket.Conn) map[string]any {
	t.Helper()

	type readResult struct {
		data []byte
		err  error
	}
	ch := make(chan readResult, 1)
	go func() {
		_, data, err := conn.ReadMessage()
		ch <- readResult{data: data, err: err}
	}()

	select {
	case r := <-ch:
		if r.err != nil {
			t.Fatalf("failed to read message: %v", r.err)
		}
		var msg map[string]any
		if err := json.Unmarshal(r.data, &msg); err != nil {
			t.Fatalf("failed to parse message: %v (raw %s)", err, string(r.data))
		}
		return msg
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for message")
		return nil
	}
}

// readJSONSkippingSystemInfo reads the next JSON frame, skipping the system_info_update
// that the daemon sends on its own (after the handshake the daemon asynchronously sends the full system info, which may arrive before the test's
// expected message, so it needs to be skipped).
func readJSONSkippingSystemInfo(t *testing.T, conn *websocket.Conn) map[string]any {
	t.Helper()
	for {
		msg := readJSONWithTimeout(t, conn)
		if msg["type"] == "system_info_update" {
			continue
		}
		return msg
	}
}

// waitForConn waits for the server to get the connection.
func waitForConn(t *testing.T, connCh <-chan *websocket.Conn) *websocket.Conn {
	t.Helper()
	select {
	case conn := <-connCh:
		return conn
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for client connection")
		return nil
	}
}

// newEchoRegistry builds a registry with the test.echo capability registered.
func newEchoRegistry(t *testing.T) *capability.Registry {
	t.Helper()

	reg := capability.NewRegistry()
	err := reg.Register(capability.Capability{
		Name:        "test.echo",
		Description: "echo parameters",
		Parameters:  map[string]any{"msg": "string"},
		Handler: func(params map[string]any) (any, error) {
			return map[string]any{"echo": params["msg"]}, nil
		},
	})
	if err != nil {
		t.Fatalf("failed to register test capability: %v", err)
	}
	return reg
}

// TestCapabilityList verifies that the client can respond to capability.list.
func TestCapabilityList(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)

	// First receive hello, reply hello_ack
	hello := readJSONWithTimeout(t, serverConn)
	if hello["type"] != "hello" {
		t.Fatalf("expected the first frame to be hello, got %v", hello["type"])
	}
	if err := serverConn.WriteJSON(map[string]any{
		"type":       "hello_ack",
		"session_id": "test-session",
	}); err != nil {
		t.Fatalf("failed to reply hello_ack: %v", err)
	}

	// Query the capability list
	if err := serverConn.WriteJSON(map[string]any{"type": "capability.list"}); err != nil {
		t.Fatalf("failed to send capability.list: %v", err)
	}
	reply := readJSONSkippingSystemInfo(t, serverConn)

	if reply["type"] != "capability.list.result" {
		t.Fatalf("expected type=capability.list.result, got %v", reply["type"])
	}
	caps, ok := reply["capabilities"].([]any)
	if !ok {
		t.Fatalf("expected capabilities to be an array, got %T", reply["capabilities"])
	}
	// NewRegistry assembles platform capabilities, so assert that test.echo is in the list rather than that the list length is 1.
	var found bool
	for _, raw := range caps {
		item, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		if item["name"] == "test.echo" {
			found = true
		}
	}
	if !found {
		t.Fatalf("the capability list should contain test.echo, got %v", caps)
	}
}

// TestCapabilityCallSuccess verifies that the client can execute a registered capability.
func TestCapabilityCallSuccess(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	readJSONWithTimeout(t, serverConn) // hello
	if err := serverConn.WriteJSON(map[string]any{
		"type":       "hello_ack",
		"session_id": "test-session",
	}); err != nil {
		t.Fatalf("failed to reply hello_ack: %v", err)
	}

	// Call the capability
	if err := serverConn.WriteJSON(map[string]any{
		"type":   "capability.call",
		"id":     "c1",
		"name":   "test.echo",
		"params": map[string]any{"msg": "hi"},
	}); err != nil {
		t.Fatalf("failed to send capability.call: %v", err)
	}
	reply := readJSONSkippingSystemInfo(t, serverConn)

	if reply["type"] != "capability.call.result" {
		t.Fatalf("expected type=capability.call.result, got %v", reply["type"])
	}
	if reply["id"] != "c1" {
		t.Fatalf("expected id=c1, got %v", reply["id"])
	}
	if reply["success"] != true {
		t.Fatalf("expected success=true, got %v (error=%v)", reply["success"], reply["error"])
	}
	data, ok := reply["data"].(map[string]any)
	if !ok {
		t.Fatalf("expected data to be an object, got %T", reply["data"])
	}
	if data["echo"] != "hi" {
		t.Fatalf("expected data.echo=hi, got %v", data["echo"])
	}
}

// TestCapabilityCallUnknown verifies that calling an unregistered capability returns a clear error.
func TestCapabilityCallUnknown(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	readJSONWithTimeout(t, serverConn) // hello
	if err := serverConn.WriteJSON(map[string]any{
		"type":       "hello_ack",
		"session_id": "test-session",
	}); err != nil {
		t.Fatalf("failed to reply hello_ack: %v", err)
	}

	if err := serverConn.WriteJSON(map[string]any{
		"type": "capability.call",
		"id":   "c2",
		"name": "no.such",
	}); err != nil {
		t.Fatalf("failed to send capability.call: %v", err)
	}
	reply := readJSONSkippingSystemInfo(t, serverConn)

	if reply["type"] != "capability.call.result" {
		t.Fatalf("expected type=capability.call.result, got %v", reply["type"])
	}
	if reply["id"] != "c2" {
		t.Fatalf("expected id=c2, got %v", reply["id"])
	}
	if reply["success"] != false {
		t.Fatalf("expected success=false, got %v", reply["success"])
	}
	errMsg, _ := reply["error"].(string)
	if !strings.Contains(errMsg, "unknown capability") {
		t.Fatalf("expected error to contain unknown capability, got %q", errMsg)
	}
}

// TestHelloCarriesCapabilities verifies that the handshake frame hello directly carries the capability list.
//
// Background: the gateway's /api/daemon/sessions only reads capabilities from the session cache, which is
// populated by hello or runtime queries. If hello does not carry capabilities, the capability list is empty when the session is first established.
func TestHelloCarriesCapabilities(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	hello := readJSONWithTimeout(t, serverConn)
	if hello["type"] != "hello" {
		t.Fatalf("expected the first frame to be hello, got %v", hello["type"])
	}
	caps, ok := hello["capabilities"].([]any)
	if !ok {
		t.Fatalf("expected hello to carry a capabilities array, got %T", hello["capabilities"])
	}
	var found bool
	for _, raw := range caps {
		if item, ok := raw.(map[string]any); ok && item["name"] == "test.echo" {
			found = true
		}
	}
	if !found {
		t.Fatalf("hello.capabilities should contain test.echo, got %v", caps)
	}
}

// TestHelloCarriesBuildInfo verifies that the handshake frame hello carries build info (build time, etc.).
//
// Requirement: the info reported by the daemon must include the build time, so the gateway can determine "which version is running and when it was built".
// The build time comes from the exe's mtime (see internal/buildinfo); here only check that the field exists and the format is self-consistent.
func TestHelloCarriesBuildInfo(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "v9.9.9-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	hello := readJSONWithTimeout(t, serverConn)
	if hello["type"] != "hello" {
		t.Fatalf("expected the first frame to be hello, got %v", hello["type"])
	}

	bi, ok := hello["build_info"].(map[string]any)
	if !ok {
		t.Fatalf("expected hello to carry a build_info object, got %T", hello["build_info"])
	}

	// The version should match Options.Version.
	if bi["version"] != "v9.9.9-test" {
		t.Errorf("build_info.version = %v, expected v9.9.9-test", bi["version"])
	}
	// The platform fields should be non-empty (running locally, so they can always be collected).
	if bi["os"] == "" || bi["os"] == nil {
		t.Errorf("build_info.os should not be empty, got %v", bi["os"])
	}
	if bi["arch"] == "" || bi["arch"] == nil {
		t.Errorf("build_info.arch should not be empty, got %v", bi["arch"])
	}
	if bi["go_version"] == "" || bi["go_version"] == nil {
		t.Errorf("build_info.go_version should not be empty, got %v", bi["go_version"])
	}
	// The source label must be one of the known values.
	src, _ := bi["build_time_source"].(string)
	switch src {
	case "exe_mtime", "process_start", "unknown":
	default:
		t.Errorf("build_info.build_time_source = %q, unexpected value", src)
	}
}

// TestSlowCapabilityCallDoesNotBlockList verifies that a time-consuming capability does not block a subsequent capability.list.
//
// This is the core regression test for this fix: before the fix, handleCapabilityCall executed synchronously in the read loop,
// and a sleeping capability would occupy the read loop, causing a subsequently arriving capability.list to go unanswered
// (manifesting on the gateway side as a query timeout and an empty capability list). After the fix, execution is in a separate goroutine,
// so list queries should get an immediate response.
func TestSlowCapabilityCallDoesNotBlockList(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := capability.NewRegistry()
	if err := reg.Register(capability.Capability{
		Name:        "test.slow",
		Description: "deliberately slow test capability",
		Handler: func(params map[string]any) (any, error) {
			time.Sleep(2 * time.Second)
			return map[string]any{"done": true}, nil
		},
	}); err != nil {
		t.Fatalf("failed to register test.slow: %v", err)
	}

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)
	readJSONWithTimeout(t, serverConn) // hello
	if err := serverConn.WriteJSON(map[string]any{
		"type":       "hello_ack",
		"session_id": "test-session",
	}); err != nil {
		t.Fatalf("failed to reply hello_ack: %v", err)
	}

	// Trigger a capability call that takes 2 seconds, but **do not wait** for its result.
	if err := serverConn.WriteJSON(map[string]any{
		"type": "capability.call",
		"id":   "slow1",
		"name": "test.slow",
	}); err != nil {
		t.Fatalf("failed to send capability.call: %v", err)
	}

	// Immediately query the capability list: the result must arrive within 1 second (far less than slow's 2 seconds).
	// If the fix is ineffective, the read loop is occupied by slow and this times out.
	if err := serverConn.WriteJSON(map[string]any{"type": "capability.list"}); err != nil {
		t.Fatalf("failed to send capability.list: %v", err)
	}

	type readResult struct {
		msg map[string]any
		err error
	}
	ch := make(chan readResult, 1)
	go func() {
		_, data, err := serverConn.ReadMessage()
		if err != nil {
			ch <- readResult{err: err}
			return
		}
		var m map[string]any
		if err := json.Unmarshal(data, &m); err != nil {
			ch <- readResult{err: err}
			return
		}
		ch <- readResult{msg: m}
	}()

	// Wait for capability.list.result within 1 second, skipping the system_info_update
	// that the daemon sends on its own (sent asynchronously, may arrive first).
	deadline := time.After(1 * time.Second)
	for {
		select {
		case r := <-ch:
			if r.err != nil {
				t.Fatalf("failed to read message: %v", r.err)
			}
			if r.msg["type"] == "system_info_update" {
				// Skip and keep waiting for the target message.
				ch = make(chan readResult, 1)
				go func() {
					_, data, err := serverConn.ReadMessage()
					if err != nil {
						ch <- readResult{err: err}
						return
					}
					var m map[string]any
					if err := json.Unmarshal(data, &m); err != nil {
						ch <- readResult{err: err}
						return
					}
					ch <- readResult{msg: m}
				}()
				continue
			}
			if r.msg["type"] != "capability.list.result" {
				t.Fatalf("expected to receive capability.list.result first, got %v", r.msg["type"])
			}
			return
		case <-deadline:
			t.Fatal("capability.list got no response within 1 second: the time-consuming capability blocked the read loop")
		}
	}
}

// TestHelloSystemInfoFastAndUpdate verifies that the first hello frame carries only the "fast version" system info,
// and that system_info_update (full system info) is sent asynchronously after the handshake.
//
// Background: collecting full system info on Windows requires launching PowerShell (seconds); if it were awaited synchronously in hello,
// it would hit the gateway's first-frame timeout (10s) and be disconnected with close(4400), manifesting as repeated reconnects. So hello carries only
// zero-cost fields, and the full info is sent afterwards.
func TestHelloSystemInfoFastAndUpdate(t *testing.T) {
	gateway, connCh := startCapabilityTestServer(t)
	reg := newEchoRegistry(t)

	client := New(Options{
		Gateway:  gateway,
		Token:    "test-token",
		ClientID: "test-daemon",
		Version:  "0.0.0-test",
		Registry: reg,
	})
	client.Start()
	defer client.Stop()

	serverConn := waitForConn(t, connCh)

	// The first frame must be hello and carry system_info (fast version).
	hello := readJSONWithTimeout(t, serverConn)
	if hello["type"] != "hello" {
		t.Fatalf("expected the first frame to be hello, got %v", hello["type"])
	}
	if _, ok := hello["system_info"].(map[string]any); !ok {
		t.Fatalf("expected hello to carry a system_info object, got %T", hello["system_info"])
	}

	// Afterwards system_info_update should be received (the full system info send).
	// Other messages may arrive first (if any); loop here to skip non-target messages.
	deadline := time.After(5 * time.Second)
	for {
		select {
		case <-deadline:
			t.Fatal("did not receive system_info_update within 5 seconds")
		default:
		}
		msg := readJSONWithTimeout(t, serverConn)
		if msg["type"] == "system_info_update" {
			if _, ok := msg["system_info"].(map[string]any); !ok {
				t.Fatalf("system_info_update's system_info should be an object, got %T", msg["system_info"])
			}
			return
		}
	}
}
