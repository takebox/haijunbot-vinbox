package wsclient

import (
	"log"
	"sort"
	"sync"

	"haijunbot-daemon/internal/auth"
)

// GatewayStatus is a snapshot of a single gateway's connection state.
type GatewayStatus struct {
	// Gateway is the normalized gateway address (same as the extension's normalizeGateway).
	Gateway string `json:"gateway"`
	// SessionID is the current session ID (empty when not connected).
	SessionID string `json:"session_id"`
	// Connected indicates whether it is currently connected.
	Connected bool `json:"connected"`
	// State is the connection state (connecting/connected/disconnected).
	State string `json:"state"`
	// TokenValid indicates whether the gateway's Token is still valid (false after authentication failure).
	TokenValid bool `json:"token_valid"`
	// AuthFailed indicates whether the gateway stopped reconnecting due to authentication failure.
	AuthFailed bool `json:"auth_failed"`
}

// ManagerOptions is the configuration of the multi-gateway connection manager.
//
// It separates "shared configuration" from "callbacks that need gateway awareness":
//   - Shared configuration (ClientID/Version/Registry/HeartbeatInterval/ReconnectMin/
//     ReconnectMax, etc.) is the same for all gateways and lives in Options;
//   - Callbacks need to know which gateway triggered them (e.g. an authentication failure only marks that gateway's Token invalid),
//     so a version with a gateway parameter is provided separately.
//
// Note: if OnStateChange / OnAuthError / OnSession in Options are set,
// they are overwritten by the Manager with a wrapper that "first injects the gateway, then calls the corresponding Gateway version callback",
// to prevent the upper layer from getting a callback that cannot distinguish gateways.
type ManagerOptions struct {
	// Options is the shared configuration template for each gateway's Client (Gateway/Token are overwritten).
	Options Options
	// OnGatewayStateChange is called when a gateway's connection state changes.
	OnGatewayStateChange func(gateway, state string)
	// OnGatewayAuthError is called when a gateway's authentication fails (on receiving 4401/4403).
	OnGatewayAuthError func(gateway string, code int, reason string)
	// OnGatewaySession is called when a gateway receives hello_ack.
	OnGatewaySession func(gateway, sessionID string)
	// OnGatewayHelloAck is called when a gateway receives hello_ack, additionally carrying the
	// latest extension version sent by the gateway (latest_extension_version; empty string when the gateway does not provide it).
	//
	// Used for "version comparison -> auto update extension"; can be set together with OnGatewaySession.
	OnGatewayHelloAck func(gateway, sessionID, latestExtensionVersion string)
	// OnGatewayDaemonUpdate is called when a gateway receives hello_ack and sent a daemon_update,
	// with the gateway address, session_id, and the raw update command map as parameters.
	//
	// Independent of OnGatewayHelloAck: the former is for extension auto-update, this callback is for daemon auto-update.
	OnGatewayDaemonUpdate func(gateway, sessionID string, info map[string]any)
	// AllowGateway determines whether a gateway is allowed to establish a connection (gateway allow/deny list).
	//
	// When it returns false, ConnectWithName skips that gateway and does not create a connection (existing
	// old connections are not actively disconnected, matching the "only block new connections" semantics).
	//
	// nil means no restriction (default). A function value is used deliberately rather than a concrete type: wsclient should not
	// depend on the config / gatewayfilter packages; the upper layer just injects the decision logic.
	AllowGateway func(gateway string) bool
}

// Manager manages WebSocket connections to multiple gateways.
//
// Semantics match the browser extension browser_extension/background/service_worker.js's
// Map<gateway, ...>:
//   - each gateway has its own independent Client (independent connection, independent session_id);
//   - only the latest connection is kept per gateway (reconnecting stops the old connection first);
//   - disconnecting one gateway does not affect other gateways;
//   - authentication failure only affects that gateway.
//
// Internally keyed by auth.GatewayKey(gateway), so protocol differences are ignored
// (http://h:443 and https://h:443 are treated as the same gateway).
type Manager struct {
	mu sync.Mutex
	// opts is the configuration template for creating each gateway's Client (Gateway/Token are overwritten).
	opts Options
	// onStateChange / onAuthError / onSession are callbacks with a gateway dimension.
	onStateChange func(gateway, state string)
	onAuthError   func(gateway string, code int, reason string)
	onSession     func(gateway, sessionID string)
	// onHelloAck is the hello_ack callback with a gateway dimension, carrying the latest extension version.
	onHelloAck func(gateway, sessionID, latestExtensionVersion string)
	// onDaemonUpdate is the daemon update command callback with a gateway dimension (daemon_update).
	onDaemonUpdate func(gateway, sessionID string, info map[string]any)
	// allowGateway determines whether a gateway is allowed to connect (gateway allow/deny list); nil means no restriction.
	// Injected via ManagerOptions.AllowGateway, called by ConnectWithName before establishing a connection.
	allowGateway func(gateway string) bool
	// clients is keyed by auth.GatewayKey.
	clients map[string]*Client
	// gateways records the original gateway address for each key, for Status display and Disconnect lookups.
	gateways map[string]string
	// tokens records the most recently set Token for each gateway, for Status to determine token validity.
	tokens map[string]string
	// names records the most recently set "terminal name" for each gateway, for injection into hello at Connect time.
	names map[string]string
}

// NewManager creates a multi-gateway connection manager.
//
// opts serves as the shared configuration template for all gateway Clients (ClientID/Version/Registry/
// HeartbeatInterval/ReconnectMin/ReconnectMax, etc.); Gateway and Token among them
// are overwritten per specific gateway at Connect time. The callbacks in Options (OnStateChange /
// OnAuthError / OnSession) are ignored; use the ManagerOptions
// OnGateway* versions instead to get gateway context.
func NewManager(opts Options) *Manager {
	return NewManagerWithOptions(ManagerOptions{Options: opts})
}

// NewManagerWithOptions creates a multi-gateway connection manager and supports callbacks with a gateway dimension.
func NewManagerWithOptions(mopts ManagerOptions) *Manager {
	// Callbacks in Options cannot distinguish gateways; the Manager uniformly injects the gateway and forwards,
	// so they are cleared here to avoid being called directly by the Client, which would leave the upper layer without gateway context.
	opts := mopts.Options
	opts.OnStateChange = nil
	opts.OnAuthError = nil
	opts.OnSession = nil
	opts.OnHelloAck = nil
	opts.OnDaemonUpdate = nil
	return &Manager{
		opts:           opts,
		onStateChange:  mopts.OnGatewayStateChange,
		onAuthError:    mopts.OnGatewayAuthError,
		onSession:      mopts.OnGatewaySession,
		onHelloAck:     mopts.OnGatewayHelloAck,
		onDaemonUpdate: mopts.OnGatewayDaemonUpdate,
		allowGateway:   mopts.AllowGateway,
		clients:        make(map[string]*Client),
		gateways:       make(map[string]string),
		tokens:         make(map[string]string),
		names:          make(map[string]string),
	}
}

// Connect connects to the specified gateway with the given credentials.
//
// If the gateway already has a connection, stop the old Client and rebuild (only the latest connection is kept per gateway),
// without affecting other gateways. Returns immediately (no-op) when gateway or token is empty.
func (m *Manager) Connect(gateway, token string) {
	m.ConnectWithName(gateway, token, "")
}

// ConnectWithName extends Connect with a "terminal name".
//
// name is reported to the gateway with the hello frame, so the gateway can distinguish terminals (when empty the gateway side falls back to hostname).
// When name is empty, keep the name previously recorded for that gateway, so a "token-only update" push does not lose the name.
//
// Idempotent: if the gateway already has a Client, and the token and name are exactly the same as this push, and the connection is in a
// normal state (not disconnected, no authentication failure), return directly without rebuilding the connection.
//
// Why idempotency is required: the web page pushes /api/auth on page load, token changes, setting changes, etc.,
// and multiple pages may push at the same time. Without unconditional rebuild, each push would drop the old connection and create a new one; the gateway side
// would allocate a new session_id for each new connection, manifesting as "the session id keeps changing", and would also cause in-progress
// capability calls to fail because the connection was replaced.
func (m *Manager) ConnectWithName(gateway, token, name string) {
	key := auth.GatewayKey(gateway)
	if key == "" || token == "" {
		return
	}
	// Gateway allow/deny list interception: disallowed gateways are skipped directly and no connection is created.
	// Deliberately placed before locking: the decision is injected by the upper layer (may read config) and should not hold the Manager lock;
	// and it only blocks "new connections", not actively disconnecting existing old connections (matching the semantics the user requested).
	if m.allowGateway != nil && !m.allowGateway(gateway) {
		log.Printf("[wsclient] Gateway is not in the allow list; skipping connection: %s", gateway)
		return
	}
	normalized := auth.NormalizeGateway(gateway)

	// Complete the map update and take out the old Client under the lock first; then Stop after unlocking,
	// avoiding executing a potentially blocking Stop while holding the lock (and avoiding mutual blocking with Status).
	m.mu.Lock()
	old := m.clients[key]
	if name == "" {
		name = m.names[key]
	}
	// Idempotency check: when neither credentials nor name changed and the existing connection is still usable, do not rebuild.
	// Only "connected / connecting" states count: a disconnected state means a reconnect is needed, and an authentication-failed state means
	// a new token is needed (here the token is the same, so rebuilding is useless; let the upper layer push again).
	if old != nil && m.tokens[key] == token && m.names[key] == name {
		state := old.State()
		if state == StateConnected || state == StateConnecting {
			m.mu.Unlock()
			return
		}
	}
	opts := m.opts
	opts.Gateway = normalized
	opts.Token = token
	opts.Name = name
	// Inject callbacks separately for each gateway so the upper layer can tell which gateway triggered them.
	// Use normalized as the gateway in callbacks, consistent with the address shown by Status().
	if m.onStateChange != nil {
		opts.OnStateChange = func(state string) { m.onStateChange(normalized, state) }
	}
	if m.onAuthError != nil {
		opts.OnAuthError = func(code int, reason string) { m.onAuthError(normalized, code, reason) }
	}
	if m.onSession != nil {
		opts.OnSession = func(sessionID string) { m.onSession(normalized, sessionID) }
	}
	if m.onHelloAck != nil {
		opts.OnHelloAck = func(sessionID, latest string) {
			m.onHelloAck(normalized, sessionID, latest)
		}
	}
	if m.onDaemonUpdate != nil {
		opts.OnDaemonUpdate = func(sessionID string, info map[string]any) {
			m.onDaemonUpdate(normalized, sessionID, info)
		}
	}
	client := New(opts)
	m.clients[key] = client
	m.gateways[key] = normalized
	m.tokens[key] = token
	m.names[key] = name
	m.mu.Unlock()

	if old != nil {
		old.Stop()
	}
	client.Start()
}

// Disconnect disconnects the specified gateway and removes its connection (without affecting other gateways).
// No-op when the gateway does not exist.
func (m *Manager) Disconnect(gateway string) {
	key := auth.GatewayKey(gateway)
	if key == "" {
		return
	}
	m.mu.Lock()
	client := m.clients[key]
	delete(m.clients, key)
	delete(m.gateways, key)
	delete(m.tokens, key)
	delete(m.names, key)
	m.mu.Unlock()

	if client != nil {
		client.Stop()
	}
}

// DisconnectAll disconnects all gateways and clears internal records.
func (m *Manager) DisconnectAll() {
	m.mu.Lock()
	clients := make([]*Client, 0, len(m.clients))
	for _, c := range m.clients {
		clients = append(clients, c)
	}
	m.clients = make(map[string]*Client)
	m.gateways = make(map[string]string)
	m.tokens = make(map[string]string)
	m.names = make(map[string]string)
	m.mu.Unlock()

	for _, c := range clients {
		c.Stop()
	}
}

// Get returns the Client for the specified gateway (for tests and the upper layer).
func (m *Manager) Get(gateway string) (*Client, bool) {
	key := auth.GatewayKey(gateway)
	if key == "" {
		return nil, false
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	c, ok := m.clients[key]
	return c, ok
}

// Count returns the number of gateways currently managed.
func (m *Manager) Count() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.clients)
}

// Status returns a state snapshot of all gateways, sorted lexicographically by gateway address to keep the output stable.
func (m *Manager) Status() []GatewayStatus {
	m.mu.Lock()
	keys := make([]string, 0, len(m.clients))
	for k := range m.clients {
		keys = append(keys, k)
	}
	clients := make(map[string]*Client, len(m.clients))
	gateways := make(map[string]string, len(m.gateways))
	for k, c := range m.clients {
		clients[k] = c
	}
	for k, g := range m.gateways {
		gateways[k] = g
	}
	m.mu.Unlock()

	out := make([]GatewayStatus, 0, len(keys))
	for _, k := range keys {
		c := clients[k]
		if c == nil {
			continue
		}
		state := c.State()
		out = append(out, GatewayStatus{
			Gateway:    gateways[k],
			SessionID:  c.SessionID(),
			Connected:  state == StateConnected,
			State:      state,
			TokenValid: !c.AuthFailed(),
			AuthFailed: c.AuthFailed(),
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Gateway < out[j].Gateway })
	return out
}
