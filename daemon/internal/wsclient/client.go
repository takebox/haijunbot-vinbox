// Package wsclient implements the WebSocket connection to the gateway.
//
// The protocol is the same as the browser extension, but uses a separate daemon endpoint:
//   - connects to {ws_gateway}/api/daemon/ws
//   - subprotocols ["haijunbot-daemon", "haijunbot-token.<urlencoded-token>"]
//   - first frame hello, reply hello_ack
//   - periodic ping / pong
//   - close codes 4401/4403 indicate authentication failure; no further reconnects
package wsclient

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"

	"haijunbot-daemon/internal/buildinfo"
	"haijunbot-daemon/internal/capability"
	"haijunbot-daemon/internal/handler"
	"haijunbot-daemon/internal/proxy"
)

// Close codes used on gateway authentication failure (same as the gateway app.py extension WS endpoint).
const (
	closeAuthFailed = 4401
	closeForbidden  = 4403
)

// Options is the client configuration.
type Options struct {
	// Gateway is the gateway address, e.g. https://hjb-ai.cn or http://127.0.0.1:8000.
	Gateway string
	// Token is the gateway JWT.
	Token string
	// ClientID is this client's identifier.
	ClientID string
	// Version is the daemon version, reported as extension_version.
	Version string
	// Name is the "terminal name" set by the user (defaults to the computer name), reported to the gateway with hello,
	// so the gateway can distinguish terminals; when empty, hello omits the name field (the gateway side falls back to hostname).
	Name string
	// HeartbeatInterval is the default heartbeat interval (seconds); hello_ack may override it.
	HeartbeatInterval int
	// ReconnectMin / ReconnectMax are the lower and upper bounds of the reconnect backoff (seconds).
	ReconnectMin int
	ReconnectMax int
	// OnStateChange is called when the connection state changes (connecting/connected/disconnected).
	OnStateChange func(state string)
	// OnAuthError is called on authentication failure (on receiving 4401/4403).
	OnAuthError func(code int, reason string)
	// OnSession is called on receiving hello_ack, with session_id as the parameter.
	OnSession func(sessionID string)
	// OnHelloAck is called on receiving hello_ack, additionally carrying the latest extension version
	// sent by the gateway (latest_extension_version; empty string when the gateway does not provide it).
	//
	// Difference from OnSession: OnSession only cares about session establishment, while this callback is for "version comparison -> auto update".
	// Both can be set at the same time; for backward compatibility, behavior is unchanged when OnHelloAck is not set.
	OnHelloAck func(sessionID, latestExtensionVersion string)
	// OnDaemonUpdate is called when hello_ack is received and the gateway sent a daemon_update,
	// with session_id and the raw update command map (corresponding to the daemon_update object) as parameters.
	//
	// Whether the update is actually performed is decided by the upper layer (both "auto-update switch on" and "command available" must be satisfied).
	// For backward compatibility, behavior is unchanged when this callback is not set; it is not called when the gateway does not send daemon_update.
	OnDaemonUpdate func(sessionID string, info map[string]any)
	// Registry is the capability registry; when nil, falls back to the old placeholder Dispatch behavior.
	Registry *capability.Registry
}

// Client is the gateway WebSocket client.
type Client struct {
	opts Options

	mu        sync.RWMutex
	state     string
	sessionID string
	ws        *websocket.Conn

	// writeMu serializes write operations to the same connection.
	//
	// gorilla/websocket explicitly requires "only one writer at a time", otherwise concurrent writes
	// would corrupt frame boundaries. After introducing asynchronous execution (see handleCapabilityCall / handleCommand),
	// the read loop, heartbeat loop, and execution goroutines may all write at the same time, so a lock is required.
	writeMu sync.Mutex

	// controls reconnect and heartbeat
	cancel  context.CancelFunc
	stopped bool
	// authFailed indicates the current Token is invalid and reconnection is stopped.
	authFailed bool
}

// writeJSON serially writes a JSON frame to the connection.
//
// All write operations must go through this function to ensure no concurrent writes occur on the same connection.
func (c *Client) writeJSON(conn *websocket.Conn, v any) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	return conn.WriteJSON(v)
}

// Send sends a JSON frame to the current connection (returns an error when not connected; does not block).
//
// Used by the upper layer to report progress after receiving a gateway command (e.g. daemon.update.status);
// reuses writeJSON's write lock to ensure it does not concurrently write to the same connection with heartbeats/capability results.
func (c *Client) Send(v any) error {
	c.mu.RLock()
	conn := c.ws
	c.mu.RUnlock()
	if conn == nil {
		return errors.New("connection not established")
	}
	return c.writeJSON(conn, v)
}

// Connection states.
const (
	StateDisconnected = "disconnected"
	StateConnecting   = "connecting"
	StateConnected    = "connected"
)

// New creates a client.
func New(opts Options) *Client {
	if opts.HeartbeatInterval <= 0 {
		opts.HeartbeatInterval = 20
	}
	if opts.ReconnectMin <= 0 {
		opts.ReconnectMin = 1
	}
	if opts.ReconnectMax < opts.ReconnectMin {
		opts.ReconnectMax = 30
	}
	return &Client{opts: opts, state: StateDisconnected}
}

// State returns the current connection state.
func (c *Client) State() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.state
}

// SessionID returns the current session ID (empty when not connected).
func (c *Client) SessionID() string {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.sessionID
}

// AuthFailed reports whether it stopped due to authentication failure.
func (c *Client) AuthFailed() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.authFailed
}

// UpdateCredentials updates the gateway and Token.
//
// Should be called before Start; if the connection is already running, the caller must Stop and then Start again.
func (c *Client) UpdateCredentials(gateway, token string) {
	c.mu.Lock()
	c.opts.Gateway = gateway
	c.opts.Token = token
	c.authFailed = false
	c.mu.Unlock()
}

// Start starts the connection loop (non-blocking). Repeated calls stop the old loop first.
func (c *Client) Start() {
	c.Stop()
	ctx, cancel := context.WithCancel(context.Background())
	c.mu.Lock()
	c.cancel = cancel
	c.stopped = false
	c.authFailed = false
	c.mu.Unlock()
	go c.run(ctx)
}

// Stop stops the connection loop and disconnects.
func (c *Client) Stop() {
	c.mu.Lock()
	if c.cancel != nil {
		c.cancel()
		c.cancel = nil
	}
	c.stopped = true
	ws := c.ws
	c.ws = nil
	c.sessionID = ""
	c.mu.Unlock()
	if ws != nil {
		_ = ws.Close()
	}
	c.setState(StateDisconnected)
}

func (c *Client) setState(state string) {
	c.mu.Lock()
	// A stopped Client may only return to disconnected: after Stop, the connection goroutine may still
	// set the state to connecting/connected in connectAndServe; without interception it would overwrite
	// the disconnected state already set by Stop (manifesting as "state is still connecting after Stop").
	if c.stopped && state != StateDisconnected {
		c.mu.Unlock()
		return
	}
	if c.state == state {
		c.mu.Unlock()
		return
	}
	c.state = state
	c.mu.Unlock()
	if c.opts.OnStateChange != nil {
		c.opts.OnStateChange(state)
	}
}

// run is the main connection loop: connect -> send/receive -> disconnect -> backoff reconnect.
func (c *Client) run(ctx context.Context) {
	attempt := 0
	for {
		if ctx.Err() != nil {
			return
		}
		err := c.connectAndServe(ctx)
		if ctx.Err() != nil {
			return
		}
		if errors.Is(err, errAuthFailed) {
			log.Printf("[wsclient] Authentication failed, stopping reconnect: %v", err)
			return
		}
		if err != nil {
			log.Printf("[wsclient] Connection ended: %v", err)
		}
		delay := ReconnectDelay(attempt, c.opts.ReconnectMin, c.opts.ReconnectMax)
		attempt++
		log.Printf("[wsclient] Reconnecting in %s (attempt %d)", delay, attempt)
		select {
		case <-ctx.Done():
			return
		case <-time.After(delay):
		}
	}
}

// errAuthFailed indicates authentication failure; should not reconnect.
var errAuthFailed = errors.New("authentication failed")

// connectAndServe establishes one connection and processes messages until disconnected.
func (c *Client) connectAndServe(ctx context.Context) error {
	c.setState(StateConnecting)

	wsURL, err := BuildWSURL(c.opts.Gateway)
	if err != nil {
		return err
	}
	protocols := BuildSubprotocols(c.opts.Token)

	dialer := websocket.Dialer{
		Subprotocols:     protocols,
		HandshakeTimeout: 15 * time.Second,
		// Use the proxy configured via environment variables / the system proxy (Windows); otherwise the gateway is unreachable behind a proxy.
		Proxy: proxy.ProxyFunc(),
	}
	conn, resp, err := dialer.DialContext(ctx, wsURL, http.Header{})
	if err != nil {
		// Rejected during the handshake: the gateway closes with 4401, but on handshake failure gorilla
		// can only obtain the HTTP response, not the close code, so judge by HTTP status here.
		if resp != nil && (resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden) {
			c.markAuthFailed(resp.StatusCode)
			return fmt.Errorf("%w: HTTP %d", errAuthFailed, resp.StatusCode)
		}
		return fmt.Errorf("connection failed: %w", err)
	}
	defer conn.Close()

	c.mu.Lock()
	c.ws = conn
	c.mu.Unlock()
	defer func() {
		c.mu.Lock()
		if c.ws == conn {
			c.ws = nil
			c.sessionID = ""
		}
		c.mu.Unlock()
	}()

	c.setState(StateConnected)
	log.Printf("[wsclient] Connected to %s (subprotocol %v)", wsURL, conn.Subprotocol())

	// Send hello
	//
	// The daemon only reports its own (user-side service) system info; browser info is reported
	// by the browser extension itself, and the daemon does not report it on its behalf, so browser_info is no longer sent here.
	hello := map[string]any{
		"type":              "hello",
		"client_id":         c.opts.ClientID,
		"extension_version": c.opts.Version,
		"tabs":              []any{},
	}
	// Terminal name: set by the user in the front end and pushed with /api/auth, used so the gateway can distinguish terminals.
	// When empty, omit this field to stay compatible with old gateways (the gateway side falls back to hostname).
	if c.opts.Name != "" {
		hello["name"] = c.opts.Name
	}
	// System info: **must use the fast version** (CollectSystemInfoFast), containing only zero-cost fields
	// (hostname/arch/cpu_count/user/home, etc.), returning in milliseconds, ensuring the first hello frame is
	// sent immediately. The full CollectSystemInfo on Windows has to launch PowerShell to collect
	// OS version/memory/start time (cold start takes seconds); waiting synchronously here would very likely hit the gateway's first-frame
	// timeout (10s) and be disconnected with close(4400), manifesting as "hello sent about 10s after connecting, then
	// repeated reconnects". The full system info is incrementally sent by a later system_info_update message.
	hello["system_info"] = capability.CollectSystemInfoFast()
	log.Printf("[wsclient] hello will report system_info (fast version)")
	// Carry the capability list directly in hello.
	//
	// Why it must be in hello: the gateway's /api/daemon/sessions only reads capabilities from the session cache,
	// and that cache is populated only after the gateway initiates a capability.list round trip.
	// If not included in the handshake, the capability list would always be empty when the session is first registered; more importantly, when the daemon
	// is executing a time-consuming capability (e.g. windows.app.list launching PowerShell), the read loop
	// is occupied, the capability.list sent by the gateway cannot be read in time, and the query returns empty due to timeout.
	// Therefore report it once during the handshake so the gateway can cache it immediately, no longer relying on runtime queries.
	if c.opts.Registry != nil {
		hello["capabilities"] = c.opts.Registry.List()
	}
	// Carry build info (build time, etc.) in hello.
	//
	// The build time comes from the exe's own mtime (see internal/buildinfo), not injected via ldflags,
	// to avoid breaking reproducible builds. The gateway side can use it to determine "which version is running and when it was built".
	buildInfo := buildinfo.Collect(c.opts.Version)
	hello["build_info"] = buildInfo.AsMap()
	log.Printf("[wsclient] hello will report build_info: version=%s build_time=%s source=%s",
		buildInfo.Version, buildInfo.BuildTime, buildInfo.BuildTimeSource)
	if err := c.writeJSON(conn, hello); err != nil {
		return fmt.Errorf("failed to send hello: %w", err)
	}

	// Incremental sending of full system info.
	//
	// The first hello frame carries only the "fast version" system info (zero-cost fields) to keep the handshake from slowing down;
	// the full info (on Windows including OS version/memory/start time, requiring launching PowerShell) is
	// sent via a system_info_update message after collection completes in the background. The gateway merges it into the session cache upon receipt,
	// so /api/daemon/sessions can reflect the full info.
	//
	// Note: this uses a separate goroutine and **does not block the read loop**; on collection failure/timeout the message is not sent
	// (the field is optional and does not affect the session). Old gateways ignore unknown message types, so it is naturally compatible.
	go c.sendFullSystemInfo(conn)

	// Heartbeat
	hbCtx, hbCancel := context.WithCancel(ctx)
	defer hbCancel()
	go c.heartbeatLoop(hbCtx, conn)

	// Read loop
	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			return c.classifyClose(err)
		}
		var msg map[string]any
		if err := json.Unmarshal(data, &msg); err != nil {
			log.Printf("[wsclient] Received invalid JSON, ignored: %s", string(data))
			continue
		}
		c.handleMessage(conn, msg)
	}
}

// classifyClose determines the disconnect reason; marks and returns errAuthFailed on authentication failure.
func (c *Client) classifyClose(err error) error {
	var closeErr *websocket.CloseError
	if errors.As(err, &closeErr) {
		if closeErr.Code == closeAuthFailed || closeErr.Code == closeForbidden {
			c.markAuthFailed(closeErr.Code)
			return fmt.Errorf("%w: close code %d %s", errAuthFailed, closeErr.Code, closeErr.Text)
		}
		return fmt.Errorf("connection closed: %d %s", closeErr.Code, closeErr.Text)
	}
	return fmt.Errorf("read failed: %w", err)
}

func (c *Client) markAuthFailed(code int) {
	c.mu.Lock()
	c.authFailed = true
	c.mu.Unlock()
	if c.opts.OnAuthError != nil {
		c.opts.OnAuthError(code, "")
	}
}

// handleMessage processes one gateway message.
func (c *Client) handleMessage(conn *websocket.Conn, msg map[string]any) {
	msgType, _ := msg["type"].(string)
	switch msgType {
	case "pong":
		return
	case "hello_ack":
		if sid, ok := msg["session_id"].(string); ok {
			c.mu.Lock()
			c.sessionID = sid
			c.mu.Unlock()
			log.Printf("[wsclient] hello_ack: session_id=%s", sid)
			if c.opts.OnSession != nil {
				c.opts.OnSession(sid)
			}
			// The gateway sends the latest extension version with hello_ack (may be missing; empty string when missing).
			if c.opts.OnHelloAck != nil {
				latest, _ := msg["latest_extension_version"].(string)
				c.opts.OnHelloAck(sid, latest)
			}
			// The gateway sends a daemon update command with hello_ack (daemon_update; may be missing).
			// Skip when missing or not an object, so as not to disturb the existing flow.
			if c.opts.OnDaemonUpdate != nil {
				if info, ok := msg["daemon_update"].(map[string]any); ok && info != nil {
					c.opts.OnDaemonUpdate(sid, info)
				}
			}
		}
	case "command":
		c.handleCommand(conn, msg)
	case "capability.list":
		c.handleCapabilityList(conn)
	case "capability.call":
		c.handleCapabilityCall(conn, msg)
	default:
		log.Printf("[wsclient] Received unhandled message type: %s", msgType)
	}
}

// handleCapabilityList responds to the gateway's capability list query.
func (c *Client) handleCapabilityList(conn *websocket.Conn) {
	caps := []capability.Capability{}
	if c.opts.Registry != nil {
		caps = c.opts.Registry.List()
	}
	reply := map[string]any{
		"type":         "capability.list.result",
		"capabilities": caps,
	}
	if err := c.writeJSON(conn, reply); err != nil {
		log.Printf("[wsclient] Failed to reply with capability list: %v", err)
	}
}

// handleCapabilityCall executes a capability call and replies with the result.
//
// Execution is placed in a separate goroutine to avoid blocking the read loop.
//
// Why it must be asynchronous: the read loop processes messages sequentially in a single goroutine. If a capability is executed synchronously here,
// a time-consuming capability (e.g. windows.app.list launching PowerShell, windows.screenshot
// loading System.Drawing) would occupy the read loop for seconds; during that time capability.list sent by the gateway
// cannot be read, and the gateway side times out, manifesting as "capability list query returns empty". With asynchronous execution,
// the read loop can always respond to list queries and heartbeats in time.
func (c *Client) handleCapabilityCall(conn *websocket.Conn, msg map[string]any) {
	callID, _ := msg["id"].(string)
	name, _ := msg["name"].(string)
	params, _ := msg["params"].(map[string]any)

	go func() {
		var res capability.Result
		switch {
		case c.opts.Registry == nil:
			res = capability.Result{Success: false, Error: "capability registry is nil"}
		case name == "":
			res = capability.Result{Success: false, Error: "capability name is empty"}
		default:
			res = c.opts.Registry.Execute(name, params)
		}

		reply := map[string]any{
			"type":    "capability.call.result",
			"id":      callID,
			"success": res.Success,
			"data":    res.Data,
			"error":   res.Error,
		}
		if err := c.writeJSON(conn, reply); err != nil {
			log.Printf("[wsclient] Failed to reply with capability call result: %v", err)
		}
	}()
}

// handleCommand processes a command and replies with the result.
//
// Like handleCapabilityCall, command dispatch is also placed in a separate goroutine,
// avoiding time-consuming commands blocking the read loop (which would in turn drag down heartbeats and capability list queries).
func (c *Client) handleCommand(conn *websocket.Conn, msg map[string]any) {
	raw, err := json.Marshal(msg)
	if err != nil {
		log.Printf("[wsclient] Failed to serialize command: %v", err)
		return
	}
	var cmd handler.Command
	if err := json.Unmarshal(raw, &cmd); err != nil {
		log.Printf("[wsclient] Failed to parse command: %v", err)
		return
	}
	go func() {
		// Use the registry when the capability registry is wired in; otherwise keep the old placeholder behavior.
		var result handler.Result
		if c.opts.Registry != nil {
			result = handler.DispatchWith(c.opts.Registry, cmd)
		} else {
			result = handler.Dispatch(cmd)
		}
		if err := c.writeJSON(conn, result); err != nil {
			log.Printf("[wsclient] Failed to reply with result: %v", err)
		}
	}()
}

// sendFullSystemInfo collects the full system info and sends it via a system_info_update message.
//
// Why sent separately: the first hello frame must be sent as soon as possible (the gateway has a first-frame timeout), while the full system info
// on Windows requires launching PowerShell (cold start takes seconds). So hello carries only zero-cost fields,
// and this method sends the full info after collecting it in the background; the gateway merges it into the session cache.
//
// Failure handling: on collection error the message is not sent (system info is an optional display field; its absence does not affect the session).
// Note: collection may take seconds, so it runs in a separate goroutine and does not block the read loop.
func (c *Client) sendFullSystemInfo(conn *websocket.Conn) {
	info, err := capability.CollectSystemInfo()
	if err != nil {
		log.Printf("[wsclient] Failed to collect full system info; skipping send: %v", err)
		return
	}
	if len(info) == 0 {
		return
	}
	msg := map[string]any{
		"type":        "system_info_update",
		"system_info": info,
	}
	if err := c.writeJSON(conn, msg); err != nil {
		// The connection may already be down, which is normal; only log it.
		log.Printf("[wsclient] Failed to send system_info_update: %v", err)
		return
	}
	log.Printf("[wsclient] Sent system_info_update: fields=%d", len(info))
}

// heartbeatLoop periodically sends ping.
func (c *Client) heartbeatLoop(ctx context.Context, conn *websocket.Conn) {
	interval := time.Duration(c.opts.HeartbeatInterval) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := c.writeJSON(conn, map[string]string{"type": "ping"}); err != nil {
				log.Printf("[wsclient] Failed to send heartbeat: %v", err)
				return
			}
		}
	}
}

// ReconnectDelay computes the backoff duration for the attempt-th reconnection (attempt starts at 0).
//
// Formula matches the extension: min(base * 2^attempt, max).
func ReconnectDelay(attempt, minSec, maxSec int) time.Duration {
	if attempt < 0 {
		attempt = 0
	}
	delay := minSec
	for i := 0; i < attempt; i++ {
		delay *= 2
		if delay >= maxSec {
			delay = maxSec
			break
		}
	}
	if delay > maxSec {
		delay = maxSec
	}
	return time.Duration(delay) * time.Second
}

// BuildSubprotocols builds the WS subprotocol list.
func BuildSubprotocols(token string) []string {
	protocols := []string{"haijunbot-daemon"}
	if token != "" {
		protocols = append(protocols, "haijunbot-token."+url.QueryEscape(token))
	}
	return protocols
}

// BuildWSURL converts the gateway address into the WS endpoint address.
func BuildWSURL(gateway string) (string, error) {
	g := NormalizeGateway(gateway)
	if g == "" {
		return "", errors.New("gateway address is empty")
	}
	ws := ToWSURL(g)
	return ws + "/api/daemon/ws", nil
}

// NormalizeGateway normalizes the gateway address: adds the scheme, trims the trailing slash.
//
// Explicitly recognizes ws:// and wss://: the gateway address may naturally be in WebSocket form. If not recognized, it would be
// wrongly prefixed with "https://", yielding "https://ws://host:9999", and url.Parse would treat "ws"
// as the hostname, causing an unavoidable connection failure (a silent fault). ws/wss are kept as-is and handled by ToWSURL.
func NormalizeGateway(gateway string) string {
	g := strings.TrimSpace(gateway)
	if g == "" {
		return ""
	}
	lower := strings.ToLower(g)
	if !strings.HasPrefix(lower, "http://") && !strings.HasPrefix(lower, "https://") &&
		!strings.HasPrefix(lower, "ws://") && !strings.HasPrefix(lower, "wss://") {
		g = "https://" + g
	}
	return strings.TrimRight(g, "/")
}

// ToWSURL converts http(s) to ws(s); already-ws(s) is returned as-is (idempotent).
func ToWSURL(gateway string) string {
	if strings.HasPrefix(gateway, "https://") {
		return "wss://" + strings.TrimPrefix(gateway, "https://")
	}
	if strings.HasPrefix(gateway, "http://") {
		return "ws://" + strings.TrimPrefix(gateway, "http://")
	}
	return gateway
}
