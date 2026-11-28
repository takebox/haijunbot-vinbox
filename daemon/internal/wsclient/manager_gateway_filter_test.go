package wsclient

import (
	"testing"
	"time"
)

// TestManagerAllowGatewayBlocksConnect verifies that when AllowGateway returns false,
// ConnectWithName skips directly and does not create any Client.
//
// This is the final interception point on the daemon side for the "gateway allow/deny list": even if upper layers (page push,
// autoDiscover, etc.) push in a gateway not on the list, no connection is actually made.
func TestManagerAllowGatewayBlocksConnect(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	m := NewManagerWithOptions(ManagerOptions{
		Options: Options{ClientID: "test-daemon", Version: "0.0.0-test"},
		// Reject all.
		AllowGateway: func(string) bool { return false },
	})
	defer m.DisconnectAll()

	m.Connect(gateway, "token-a")

	if got := m.Count(); got != 0 {
		t.Fatalf("a blocked gateway should not create a connection, got Count=%d", got)
	}
	if status := m.Status(); len(status) != 0 {
		t.Fatalf("a blocked gateway should not appear in the status, got %+v", status)
	}
	// Wait a little longer to confirm no async connection was created (the block happens before connecting, so it should always be 0).
	time.Sleep(50 * time.Millisecond)
	if got := m.Count(); got != 0 {
		t.Fatalf("a blocked gateway should still not create a connection after a delay, got Count=%d", got)
	}
}

// TestManagerAllowGatewayNilAllows verifies that a nil AllowGateway imposes no restriction (default behavior unchanged).
func TestManagerAllowGatewayNilAllows(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	// Explicitly do not set AllowGateway (nil).
	m := NewManager(Options{ClientID: "test-daemon", Version: "0.0.0-test"})
	defer m.DisconnectAll()

	m.Connect(gateway, "token-a")
	waitForGatewayConnected(t, m, gateway)

	if got := m.Count(); got != 1 {
		t.Fatalf("a nil AllowGateway should not restrict connections, got Count=%d", got)
	}
}

// TestManagerAllowGatewaySelective verifies that AllowGateway is evaluated per gateway:
// allowed ones connect, rejected ones do not, without affecting each other.
func TestManagerAllowGatewaySelective(t *testing.T) {
	allowed, _ := startMultiGatewayTestServer(t)
	blocked, _ := startMultiGatewayTestServer(t)

	m := NewManagerWithOptions(ManagerOptions{
		Options: Options{ClientID: "test-daemon", Version: "0.0.0-test"},
		AllowGateway: func(gateway string) bool {
			return gateway == allowed
		},
	})
	defer m.DisconnectAll()

	m.Connect(allowed, "token-a")
	m.Connect(blocked, "token-b")

	waitForGatewayConnected(t, m, allowed)

	if _, ok := m.Get(blocked); ok {
		t.Fatalf("a rejected gateway %s should not have a Client", blocked)
	}
	if got := m.Count(); got != 1 {
		t.Fatalf("there should be only 1 connection, got %d", got)
	}
}

// TestManagerAllowGatewayKeepsExistingConnection verifies "only blocks new connections, does not actively drop old ones":
// First connect while unrestricted, then change that gateway to rejected; a further Connect should not drop the existing connection.
//
// Note: ConnectWithName's block happens before locking, so it does not touch the existing Client when it returns;
// here we confirm the old connection is still alive by calling Connect again (not Disconnect).
func TestManagerAllowGatewayKeepsExistingConnection(t *testing.T) {
	gateway, _ := startMultiGatewayTestServer(t)

	allow := true
	m := NewManagerWithOptions(ManagerOptions{
		Options:      Options{ClientID: "test-daemon", Version: "0.0.0-test"},
		AllowGateway: func(string) bool { return allow },
	})
	defer m.DisconnectAll()

	// First allow and connect.
	m.Connect(gateway, "token-a")
	waitForGatewayConnected(t, m, gateway)

	// Then change to reject; the next Connect should be blocked, but the existing connection is unaffected.
	allow = false
	m.Connect(gateway, "token-a")

	c, ok := m.Get(gateway)
	if !ok {
		t.Fatalf("an existing connection should not be removed due to a list change")
	}
	if got := c.State(); got != StateConnected {
		t.Fatalf("an existing connection should remain connected, got %s", got)
	}
	if got := m.Count(); got != 1 {
		t.Fatalf("there should still be only 1 connection, got %d", got)
	}
}
