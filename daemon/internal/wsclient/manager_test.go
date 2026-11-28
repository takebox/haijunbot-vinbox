package wsclient

import (
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

// startMultiGatewayTestServer starts a local WS server supporting multi-gateway scenarios.
//
// After each connection upgrade: receive hello -> reply hello_ack (session_id determined by the query parameter) -> keep the connection.
// Returns the HTTP address and a notification channel for "connection established".
func startMultiGatewayTestServer(t *testing.T) (string, <-chan struct{}) {
	t.Helper()

	upgrader := websocket.Upgrader{
		Subprotocols: []string{"haijunbot-daemon"},
		CheckOrigin:  func(*http.Request) bool { return true },
	}
	connCh := make(chan struct{}, 64)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/daemon/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()

		// Receive hello
		if _, _, err := conn.ReadMessage(); err != nil {
			return
		}
		sid := r.URL.Query().Get("sid")
		if sid == "" {
			sid = "sess"
		}
		if err := conn.WriteJSON(map[string]any{
			"type":       "hello_ack",
			"session_id": sid,
		}); err != nil {
			return
		}
		select {
		case connCh <- struct{}{}:
		default:
		}

		// Keep the connection until the peer closes
		for {
			if _, _, err := conn.ReadMessage(); err != nil {
				return
			}
		}
	})

	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv.URL, connCh
}

// waitForGatewayConnected waits for the specified gateway in the Manager to enter the connected state.
func waitForGatewayConnected(t *testing.T, m *Manager, gateway string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		c, ok := m.Get(gateway)
		if ok && c.State() == StateConnected {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for gateway %s to connect (current state %v)", gateway, m.Status())
}

// TestManagerMultiGatewayIsolation verifies that two gateways each connect independently and their states do not affect each other.
func TestManagerMultiGatewayIsolation(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.Connect(gateway, "token-a")
	// Connecting the same gateway again (same host:port -> same GatewayKey) should replace the old connection.
	m.Connect(gateway, "token-b")

	// The two above are the same gateway, so only one should remain.
	if got := m.Count(); got != 1 {
		t.Fatalf("expected only 1 connection after repeated Connect to the same gateway, got %d", got)
	}

	waitForGatewayConnected(t, m, gateway)

	status := m.Status()
	if len(status) != 1 {
		t.Fatalf("expected 1 status, got %d: %+v", len(status), status)
	}
	if !status[0].Connected {
		t.Fatalf("expected connected, got %+v", status[0])
	}
	if status[0].Gateway != gateway {
		t.Fatalf("expected gateway=%s, got %s", gateway, status[0].Gateway)
	}
	if !status[0].TokenValid {
		t.Fatalf("expected token_valid=true, got %+v", status[0])
	}
}

// TestManagerConnectReplacesSameGateway verifies that reconnecting the same gateway keeps only one Client (the old Client is Stopped).
func TestManagerConnectReplacesSameGateway(t *testing.T) {
	gateway, connCh := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.Connect(gateway, "token-1")
	first, ok := m.Get(gateway)
	if !ok {
		t.Fatal("should be able to get the Client after the first Connect")
	}
	select {
	case <-connCh:
	case <-time.After(5 * time.Second):
		t.Fatal("the first connection was not established")
	}

	m.Connect(gateway, "token-2")
	second, ok := m.Get(gateway)
	if !ok {
		t.Fatal("should be able to get the Client after reconnecting")
	}
	if first == second {
		t.Fatal("reconnecting the same gateway should rebuild the Client (different pointer)")
	}
	if got := m.Count(); got != 1 {
		t.Fatalf("expected only 1 connection after reconnecting the same gateway, got %d", got)
	}

	// The old Client must have been Stopped: the state returns to disconnected and it no longer reconnects.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if first.State() == StateDisconnected {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if got := first.State(); got != StateDisconnected {
		t.Fatalf("the old Client should have been Stopped (disconnected), got %s", got)
	}

	waitForGatewayConnected(t, m, gateway)
}

// TestManagerConnectWithNameIdempotent verifies that, when neither credentials nor name change and the connection is normal,
// repeated ConnectWithName does not rebuild the connection (the Client pointer is unchanged, no new connection is created).
//
// This is a regression test for "the session id keeps changing": the web page pushes the same credentials multiple times,
// and before the fix each push would drop the old connection and create a new one, so the gateway side kept allocating new session_ids.
func TestManagerConnectWithNameIdempotent(t *testing.T) {
	gateway, connCh := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.ConnectWithName(gateway, "token-x", "SF-PC")
	first, ok := m.Get(gateway)
	if !ok {
		t.Fatal("should be able to get the Client after the first ConnectWithName")
	}
	select {
	case <-connCh:
	case <-time.After(5 * time.Second):
		t.Fatal("the first connection was not established")
	}
	waitForGatewayConnected(t, m, gateway)

	// Repeatedly push exactly the same credentials and name: should hit idempotency and not rebuild.
	for i := 0; i < 3; i++ {
		m.ConnectWithName(gateway, "token-x", "SF-PC")
	}
	again, ok := m.Get(gateway)
	if !ok {
		t.Fatal("should still be able to get the Client after repeated ConnectWithName")
	}
	if first != again {
		t.Fatal("should reuse the same Client when credentials and name are unchanged (same pointer)")
	}
	// No second connection should be established.
	select {
	case <-connCh:
		t.Fatal("the idempotent path should not create a new connection")
	case <-time.After(300 * time.Millisecond):
	}
}

// TestManagerConnectWithNameRebuildsOnChange verifies that the connection is still rebuilt when credentials or name change.
func TestManagerConnectWithNameRebuildsOnChange(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.ConnectWithName(gateway, "token-x", "SF-PC")
	first, _ := m.Get(gateway)
	waitForGatewayConnected(t, m, gateway)

	// token change -> must rebuild.
	m.ConnectWithName(gateway, "token-y", "SF-PC")
	second, _ := m.Get(gateway)
	if first == second {
		t.Fatal("should rebuild the Client when token changes")
	}

	// name change -> must rebuild.
	m.ConnectWithName(gateway, "token-y", "OTHER-PC")
	third, _ := m.Get(gateway)
	if second == third {
		t.Fatal("should rebuild the Client when name changes")
	}
}

// TestManagerConnectWithNameRebuildsWhenDisconnected verifies that when the connection is already disconnected, even if
// credentials and name are unchanged, it still rebuilds (idempotency only covers the "connection still usable" case).
func TestManagerConnectWithNameRebuildsWhenDisconnected(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.ConnectWithName(gateway, "token-x", "SF-PC")
	first, _ := m.Get(gateway)
	waitForGatewayConnected(t, m, gateway)

	// Manually stop the connection to simulate a disconnected state.
	first.Stop()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) && first.State() != StateDisconnected {
		time.Sleep(10 * time.Millisecond)
	}

	m.ConnectWithName(gateway, "token-x", "SF-PC")
	second, _ := m.Get(gateway)
	if first == second {
		t.Fatal("should rebuild the Client when the connection is disconnected")
	}
}
func TestManagerDisconnectOneGateway(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	// httptest provides only one port, so use an unreachable port for the second gateway
	// (the connection fails but the entry exists), to verify that "disconnecting one does not affect the other".
	g1 := gateway
	g2 := "http://127.0.0.1:1"

	m.Connect(g1, "token-1")
	m.Connect(g2, "token-2")
	if got := m.Count(); got != 2 {
		t.Fatalf("expected 2 gateway entries, got %d", got)
	}

	m.Disconnect(g1)
	if got := m.Count(); got != 1 {
		t.Fatalf("expected 1 remaining after disconnecting one gateway, got %d", got)
	}
	if _, ok := m.Get(g1); ok {
		t.Fatal("the disconnected gateway should no longer exist")
	}
	if _, ok := m.Get(g2); !ok {
		t.Fatal("other gateways should not be affected")
	}

	// Disconnecting a nonexistent gateway should be a no-op
	m.Disconnect("http://127.0.0.1:9")
	if got := m.Count(); got != 1 {
		t.Fatalf("disconnecting a nonexistent gateway should not change the count, got %d", got)
	}
}

// TestManagerDisconnectAll verifies that DisconnectAll clears all gateways.
func TestManagerDisconnectAll(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})

	m.Connect(gateway, "token-1")
	m.Connect("http://127.0.0.1:1", "token-2")
	if got := m.Count(); got != 2 {
		t.Fatalf("expected 2 gateway entries, got %d", got)
	}

	first, _ := m.Get(gateway)
	m.DisconnectAll()

	if got := m.Count(); got != 0 {
		t.Fatalf("expected 0 after DisconnectAll, got %d", got)
	}
	if got := len(m.Status()); got != 0 {
		t.Fatalf("Status should be empty after DisconnectAll, got %d", got)
	}
	if _, ok := m.Get(gateway); ok {
		t.Fatal("should no longer be able to get the Client after DisconnectAll")
	}
	if got := first.State(); got != StateDisconnected {
		t.Fatalf("the old Client should be disconnected after DisconnectAll, got %s", got)
	}
}

// TestManagerStatusSortedAndStable verifies that Status is sorted lexicographically by gateway with correct fields.
func TestManagerStatusSortedAndStable(t *testing.T) {
	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	// Use unreachable ports to avoid real network dependencies; only verify entries and ordering.
	m.Connect("http://127.0.0.1:3", "t3")
	m.Connect("http://127.0.0.1:1", "t1")
	m.Connect("http://127.0.0.1:2", "t2")

	status := m.Status()
	if len(status) != 3 {
		t.Fatalf("expected 3 statuses, got %d", len(status))
	}
	// The Gateway field is the normalized address (including the scheme prefix).
	want := []string{"http://127.0.0.1:1", "http://127.0.0.1:2", "http://127.0.0.1:3"}
	for i, s := range status {
		if s.Gateway != want[i] {
			t.Fatalf("entry %d expected gateway=%s, got %s (all %+v)", i, want[i], s.Gateway, status)
		}
		if s.State == "" {
			t.Fatalf("State should not be empty: %+v", s)
		}
		if s.Connected {
			t.Fatalf("an unreachable gateway should not be connected: %+v", s)
		}
	}

	// Calling again should yield the same order (stable)
	again := m.Status()
	for i := range again {
		if again[i].Gateway != status[i].Gateway {
			t.Fatalf("Status order is unstable: %v vs %v", status, again)
		}
	}
}

// TestManagerEmptyInputNoop verifies that empty gateway/token is a no-op.
func TestManagerEmptyInputNoop(t *testing.T) {
	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.Connect("", "token")
	m.Connect("   ", "token")
	m.Connect("http://127.0.0.1:1", "")
	if got := m.Count(); got != 0 {
		t.Fatalf("empty gateway/token should be a no-op, got %d entries", got)
	}

	// Disconnect / Get on an empty gateway should also not panic or create entries
	m.Disconnect("")
	if _, ok := m.Get(""); ok {
		t.Fatal("should not be able to get a Client for an empty gateway")
	}
}

// TestManagerConcurrentAccess verifies that concurrent Connect/Disconnect/Status have no data race.
func TestManagerConcurrentAccess(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	var wg sync.WaitGroup
	stop := make(chan struct{})
	var readers sync.WaitGroup

	// Concurrent Connect/Disconnect on the same gateway
	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < 30; i++ {
			m.Connect(gateway, "token")
			m.Disconnect(gateway)
		}
	}()

	// Concurrent Status / Get / Count
	for i := 0; i < 4; i++ {
		readers.Add(1)
		go func() {
			defer readers.Done()
			for {
				select {
				case <-stop:
					return
				default:
				}
				_ = m.Status()
				_, _ = m.Get(gateway)
				_ = m.Count()
			}
		}()
	}

	// Wait for the writer goroutine to finish, then notify the reader goroutines to exit, and finally wait for the reader goroutines to wrap up.
	wg.Wait()
	close(stop)
	readers.Wait()

	// Should eventually converge normally
	m.DisconnectAll()
	if got := m.Count(); got != 0 {
		t.Fatalf("expected 0 after DisconnectAll, got %d", got)
	}
}

// TestManagerGatewayAwareCallbacks verifies that the Manager injects the gateway context into callbacks.
//
// Each gateway's Client callbacks should carry that gateway's own address and not cross over.
func TestManagerGatewayAwareCallbacks(t *testing.T) {
	g1, connCh1 := startMultiGatewayTestServer(t)
	g2, connCh2 := startMultiGatewayTestServer(t)
	var mu sync.Mutex
	states := map[string][]string{}
	sessions := map[string]string{}
	authErrs := map[string]int{}

	m := NewManagerWithOptions(ManagerOptions{
		Options: Options{
			ClientID: "test-callbacks",
			Version:  "test",
		},
		OnGatewayStateChange: func(gateway, state string) {
			mu.Lock()
			states[gateway] = append(states[gateway], state)
			mu.Unlock()
		},
		OnGatewaySession: func(gateway, sessionID string) {
			mu.Lock()
			sessions[gateway] = sessionID
			mu.Unlock()
		},
		OnGatewayAuthError: func(gateway string, code int, reason string) {
			mu.Lock()
			authErrs[gateway] = code
			mu.Unlock()
		},
	})
	defer m.DisconnectAll()

	// g1/g2 are the full gateway addresses returned by startMultiGatewayTestServer (including http://),
	// two different httptest service ports -> two different GatewayKeys.
	m.Connect(g1, "token-1")
	m.Connect(g2, "token-2")

	// Wait for both connections to be established.
	for i, ch := range []<-chan struct{}{connCh1, connCh2} {
		select {
		case <-ch:
		case <-time.After(3 * time.Second):
			t.Fatalf("timed out waiting for connection %d to be established", i+1)
		}
	}
	// Wait for the hello_ack callbacks to land.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		mu.Lock()
		n := len(sessions)
		mu.Unlock()
		if n == 2 {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}

	mu.Lock()
	defer mu.Unlock()
	if len(sessions) != 2 {
		t.Fatalf("there should be session callbacks for two gateways, got %v", sessions)
	}
	// The gateway in the callback must be the normalized full address.
	if _, ok := sessions[g1]; !ok {
		t.Fatalf("missing session callback for gateway %s, got %v", g1, sessions)
	}
	if _, ok := sessions[g2]; !ok {
		t.Fatalf("missing session callback for gateway %s, got %v", g2, sessions)
	}
	// State callbacks should likewise be recorded separately per gateway.
	if len(states[g1]) == 0 || len(states[g2]) == 0 {
		t.Fatalf("both gateways should have state callbacks, got %v", states)
	}
	// No authentication failure occurred.
	if len(authErrs) != 0 {
		t.Fatalf("there should be no authentication failure callbacks, got %v", authErrs)
	}
}

// TestManagerAuthErrorCallbackCarriesGateway verifies that the authentication failure callback carries the correct gateway.
//
// Scenario: one gateway returns 401 (authentication failure), the other connects normally;
// the callback must target only the failed gateway and must not affect the other gateway's connection.
func TestManagerAuthErrorCallbackCarriesGateway(t *testing.T) {
	// Start a server that returns 401 on the handshake, simulating authentication failure.
	bad := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
	}))
	defer bad.Close()

	good, connCh := startMultiGatewayTestServer(t)

	var mu sync.Mutex
	failed := map[string]int{}

	m := NewManagerWithOptions(ManagerOptions{
		Options: Options{ClientID: "test-auth-err", Version: "test"},
		OnGatewayAuthError: func(gateway string, code int, reason string) {
			mu.Lock()
			failed[gateway] = code
			mu.Unlock()
		},
	})
	defer m.DisconnectAll()

	m.Connect(bad.URL, "bad-token")
	m.Connect(good, "good-token")

	// The normal gateway should be able to connect.
	select {
	case <-connCh:
	case <-time.After(3 * time.Second):
		t.Fatal("the normal gateway should establish a connection")
	}
	// The failed gateway should trigger the authentication failure callback.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		mu.Lock()
		n := len(failed)
		mu.Unlock()
		if n > 0 {
			break
		}
		time.Sleep(20 * time.Millisecond)
	}

	mu.Lock()
	defer mu.Unlock()
	if len(failed) != 1 {
		t.Fatalf("only one gateway should fail authentication, got %v", failed)
	}
	if code, ok := failed[bad.URL]; !ok || code != http.StatusUnauthorized {
		t.Fatalf("the authentication failure callback should carry gateway %s and 401, got %v", bad.URL, failed)
	}
	// The other gateway is unaffected and still in the manager.
	if _, ok := m.Get(good); !ok {
		t.Fatal("the normal gateway should not be removed because another gateway failed authentication")
	}
	if got := m.Count(); got != 2 {
		t.Fatalf("there should still be two gateway entries, got %d", got)
	}
}
