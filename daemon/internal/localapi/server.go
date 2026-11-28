// Package localapi provides a local HTTP interface for web pages to push login info and query status.
//
// It only listens on loopback addresses and does no extra authentication (confirmed).
//
// It supports multiple gateways coexisting: web pages can push credentials to different gateways one after another, each gateway connects
// independently without overwriting the others; status queries return a snapshot of all gateways.
package localapi

import (
	"encoding/json"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/capability"
	"haijunbot-daemon/internal/gatewayfilter"
	"haijunbot-daemon/internal/wsclient"
)

// Server is the local API service.
type Server struct {
	store   *auth.Store
	manager *wsclient.Manager
	version string
	// onBrowserExtEnabled is called when the "auto install/update browser extension" switch changes from off to on.
	//
	// Why it is needed: the daemon checks this switch only once when it receives hello_ack, while the frontend push of the switch
	// usually arrives after hello_ack (the daemon connects to the gateway first on startup, and the frontend pushes settings later), causing the user's
	// already-enabled switch to still be judged as "off" and the sync to be skipped, persisting until the next reconnect.
	// This callback is injected by the upper layer to perform one supplementary sync check when the switch turns on.
	//
	// May be nil (does nothing when not injected), for ease of testing and minimal changes.
	onBrowserExtEnabled func()
	// getGatewayFilter returns the current gateway allow/deny list (mode, patterns).
	// Injected by main (reads the same gatewayfilter.Filter); when nil it returns off + nil.
	getGatewayFilter func() (string, []string)
	// setGatewayFilter updates the gateway allow/deny list and persists it; returns the actual updated value and an error.
	// Injected by main (updates gatewayfilter.Filter and writes back to config.yaml);
	// when nil the endpoint returns 501, avoiding "looks successful but did not take effect".
	setGatewayFilter func(mode string, patterns []string) (string, []string, error)
}

// SetGatewayFilter injects the read and update callbacks for the gateway allow/deny list; called by main during assembly.
//
// Injection rather than a direct dependency on config/gatewayfilter: localapi is only responsible for the HTTP layer,
// while ownership and persistence of the list are decided by the upper layer, for ease of testing and decoupling.
func (s *Server) SetGatewayFilter(
	get func() (string, []string),
	set func(mode string, patterns []string) (string, []string, error),
) {
	s.getGatewayFilter = get
	s.setGatewayFilter = set
}

// SetOnBrowserExtEnabled injects the callback for when the "extension switch is turned on"; called by main during assembly.
func (s *Server) SetOnBrowserExtEnabled(fn func()) {
	s.onBrowserExtEnabled = fn
}

// notifyBrowserExtEnabled triggers the callback on a false → true transition of the switch (callback may be nil).
func (s *Server) notifyBrowserExtEnabled(transitioned bool) {
	if transitioned && s.onBrowserExtEnabled != nil {
		s.onBrowserExtEnabled()
	}
}

// New creates the local API service.
//
// store holds the credentials for each gateway, manager manages the WebSocket connections for each gateway;
// both use auth.GatewayKey as the key, so the keys naturally align.
func New(store *auth.Store, manager *wsclient.Manager, version string) *Server {
	return &Server{
		store:   store,
		manager: manager,
		version: version,
	}
}

// Handler returns the routes.
//
// The outer layer wraps CORS handling: web pages may be deployed on any origin (e.g. https://hjb-ai.cn),
// while this service always listens on http://127.0.0.1:17800, so cross-origin access inevitably triggers a preflight,
// and without CORS response headers the browser blocks the request outright.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/auth", s.handleAuth)
	mux.HandleFunc("/api/status", s.handleStatus)
	mux.HandleFunc("/api/logout", s.handleLogout)
	mux.HandleFunc("/api/settings", s.handleSettings)
	// Gateway allow/deny list: **local access only** (the handler validates that the source is loopback).
	// Unlike /api/auth etc., this endpoint is not for remote web pages/other machines to call: the list is the daemon's
	// own configuration, and the endpoint has no authentication, so exposing it means anyone could modify it.
	mux.HandleFunc("/api/gateway-filter", s.handleGatewayFilter)
	return withCORS(mux)
}

// withCORS adds CORS headers to all responses and directly answers preflight requests.
//
// Allows any origin (*): this service only listens on loopback addresses and does no authentication, so to be reachable the
// request must already have reached the user's local machine; credentials are carried in the request body and no cookies are used, so
// Access-Control-Allow-Credentials is not needed.
// It also allows the headers required by Chrome Private Network Access (PNA), avoiding a public page being blocked by an extra
// private network preflight when accessing a local loopback address.
func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("Access-Control-Allow-Origin", "*")
		h.Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		h.Set("Access-Control-Allow-Headers", "Content-Type")
		h.Set("Access-Control-Max-Age", "600")
		h.Set("Access-Control-Allow-Private-Network", "true")

		// Preflight request: CORS headers are already written, return 204 directly without entering the business routes.
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

type authRequest struct {
	Gateway string `json:"gateway"`
	Token   string `json:"token"`
	// Name is the "terminal name" set by the frontend (defaults to the computer name), reported to the gateway with hello.
	// Optional: when empty, the gateway's existing name is kept.
	Name string `json:"name"`
	// AutoInstallBrowserExt is the "whether to auto install/update the browser extension" switch, pushed by the frontend
	// along with the login state. Uses *bool to distinguish "not provided" (nil, keep the original value, compatible with old frontends) from
	// "explicitly off" (false).
	AutoInstallBrowserExt *bool `json:"auto_install_browser_ext"`
}

// logoutRequest's gateway is optional: if present, only that gateway is logged out; if absent, all are logged out.
type logoutRequest struct {
	Gateway string `json:"gateway"`
}

// settingsRequest is the request body for /api/settings.
//
// AutoInstallBrowserExt uses *bool: nil means the request did not provide the field (returns 400),
// to distinguish "not provided" from "explicitly off". Currently this is the only item, extensible later.
type settingsRequest struct {
	AutoInstallBrowserExt *bool `json:"auto_install_browser_ext"`
}

// handleAuth receives the credentials pushed by the web page and triggers the corresponding gateway connection.
//
// Multiple gateways coexist: only the gateway specified in the request is affected; other gateways' connections are not displaced.
func (s *Server) handleAuth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
		return
	}
	var req authRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "invalid json: " + err.Error(),
		})
		return
	}
	if req.Gateway == "" || req.Token == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "gateway and token are required",
		})
		return
	}
	s.store.SetWithName(req.Gateway, req.Token, req.Name)
	s.manager.ConnectWithName(req.Gateway, req.Token, req.Name)
	// The frontend may push the "auto install browser extension" switch along with the login state; when not provided (nil) the original value is kept,
	// for compatibility with old frontends. The switch is in-memory only and not persisted (the user requested that it be stored only in browser storage).
	if req.AutoInstallBrowserExt != nil {
		s.notifyBrowserExtEnabled(capability.SetAutoInstallBrowserExt(*req.AutoInstallBrowserExt))
	}
	log.Printf("[localapi] received auth push: gateway=%s token=%s... name=%q",
		req.Gateway, maskToken(req.Token), req.Name)
	writeJSON(w, http.StatusOK, map[string]any{
		"success":        true,
		"status":         "connecting",
		"daemon_version": s.version,
	})
}

// handleStatus returns a status snapshot of all gateways.
//
// token_valid is based on the credential store (false after an auth failure); the other fields come from the connection manager.
func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
		return
	}
	statuses := s.manager.Status()
	gateways := make([]wsclient.GatewayStatus, 0, len(statuses))
	for _, st := range statuses {
		// The manager and store use the same key (both GatewayKey), but Gateway in Status
		// is the normalized full address, so it must be normalized before querying the store.
		st.TokenValid = s.store.TokenValid(st.Gateway)
		gateways = append(gateways, st)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"success":        true,
		"gateways":       gateways,
		"daemon_version": s.version,
		// hostname is used by the frontend as the default when the user has not set a "terminal name"
		// (the browser cannot directly read the system hostname, so it is provided by the daemon).
		"hostname": localHostname(),
	})
}

// localHostname returns the local hostname; returns an empty string on failure (the frontend will keep the name empty).
func localHostname() string {
	host, err := os.Hostname()
	if err != nil {
		return ""
	}
	return host
}

// handleLogout logs out: the request body may include gateway to specify a single gateway; if absent, all are cleared.
func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
		return
	}
	// The request body may be empty (old clear-all semantics); on parse failure it is treated as clear-all.
	var req logoutRequest
	_ = json.NewDecoder(r.Body).Decode(&req)

	if req.Gateway != "" {
		s.store.Clear(req.Gateway)
		s.manager.Disconnect(req.Gateway)
		log.Printf("[localapi] logged out gateway %s", req.Gateway)
	} else {
		s.store.ClearAll()
		s.manager.DisconnectAll()
		log.Printf("[localapi] logged out all gateways, connections closed")
	}
	writeJSON(w, http.StatusOK, map[string]any{"success": true})
}

// handleSettings reads and writes the daemon's settings (currently including the "auto install browser extension" switch).
//
// GET  → returns the current value, for the frontend to display when opening the settings UI;
// POST → updates the switch; the request body must contain {"auto_install_browser_ext": bool}.
//
// Note: the switch is in-memory only and not persisted (the user requested that it be stored only in browser storage); after a daemon restart it
// returns to the default false (off), waiting for the frontend to push again.
func (s *Server) handleSettings(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, map[string]any{
			"success":                  true,
			"auto_install_browser_ext": capability.AutoInstallBrowserExt(),
		})
	case http.MethodPost:
		var req settingsRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"success": false,
				"error":   "invalid json: " + err.Error(),
			})
			return
		}
		// A missing field (nil) is treated as an invalid request: the semantics are explicit, avoiding "silently unchanged" confusing the caller.
		if req.AutoInstallBrowserExt == nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"success": false,
				"error":   "auto_install_browser_ext is required",
			})
			return
		}
		s.notifyBrowserExtEnabled(capability.SetAutoInstallBrowserExt(*req.AutoInstallBrowserExt))
		log.Printf("[localapi] updated settings: auto_install_browser_ext=%v", *req.AutoInstallBrowserExt)
		// Echo the actual updated value so the caller can confirm.
		writeJSON(w, http.StatusOK, map[string]any{
			"success":                  true,
			"auto_install_browser_ext": capability.AutoInstallBrowserExt(),
		})
	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
	}
}

// gatewayFilterRequest is the request body for POST /api/gateway-filter.
//
// Both Mode and Patterns are treated as "explicitly provided": an invalid mode returns 400 directly (explicit semantics,
// no silent fallback); patterns may be an empty array (meaning clear the list).
type gatewayFilterRequest struct {
	Mode     string   `json:"mode"`
	Patterns []string `json:"patterns"`
}

// handleGatewayFilter reads and writes the gateway allow/deny list (local access only).
//
// GET  → {"success":true,"mode":<mode>,"patterns":[...]}
// POST → request body {"mode":"off|whitelist|blacklist","patterns":[...]},
//
//	updates the in-memory state and persists to config.yaml, returning the actual updated value.
//
// Security: this endpoint has no authentication, so it **enforces that the request source is a loopback address**; non-loopback always gets 403.
// This is defense in depth: even if listen is later opened to non-loopback, this endpoint will not be callable from outside.
// It deliberately does not trust X-Forwarded-For / X-Real-IP (which can be forged arbitrarily), and only looks at the TCP-layer
// RemoteAddr.
func (s *Server) handleGatewayFilter(w http.ResponseWriter, r *http.Request) {
	if !isLoopbackRequest(r) {
		writeJSON(w, http.StatusForbidden, map[string]any{
			"success": false,
			"error":   "local access only",
		})
		return
	}
	switch r.Method {
	case http.MethodGet:
		mode, patterns := "off", []string(nil)
		if s.getGatewayFilter != nil {
			mode, patterns = s.getGatewayFilter()
		}
		if patterns == nil {
			patterns = []string{}
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"success":  true,
			"mode":     mode,
			"patterns": patterns,
		})
	case http.MethodPost:
		if s.setGatewayFilter == nil {
			writeJSON(w, http.StatusNotImplemented, map[string]any{
				"success": false,
				"error":   "gateway allow/deny list not enabled",
			})
			return
		}
		var req gatewayFilterRequest
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 64<<10)).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"success": false,
				"error":   "invalid json: " + err.Error(),
			})
			return
		}
		if !gatewayfilter.ValidMode(req.Mode) {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"success": false,
				"error":   "mode must be one of off / whitelist / blacklist",
			})
			return
		}
		mode, patterns, err := s.setGatewayFilter(req.Mode, req.Patterns)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{
				"success": false,
				"error":   "save failed: " + err.Error(),
			})
			return
		}
		if patterns == nil {
			patterns = []string{}
		}
		log.Printf("[localapi] updated gateway allow/deny list: mode=%s patterns=%v", mode, patterns)
		writeJSON(w, http.StatusOK, map[string]any{
			"success":  true,
			"mode":     mode,
			"patterns": patterns,
		})
	default:
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
	}
}

// isLoopbackRequest determines whether the request comes from a local loopback address.
//
// It only looks at r.RemoteAddr (the real peer of the TCP connection) and does not accept forgeable proxy headers such as
// X-Forwarded-For. It accepts 127.0.0.0/8, ::1, and localhost.
func isLoopbackRequest(r *http.Request) bool {
	host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
	if err != nil {
		// RemoteAddr may lack a port (rare); fall back to checking the whole string.
		host = strings.TrimSpace(r.RemoteAddr)
	}
	host = strings.Trim(host, "[]")
	if host == "" {
		return false
	}
	if strings.EqualFold(host, "localhost") {
		return true
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false
	}
	return ip.IsLoopback()
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

// maskToken keeps only a few characters from the start and end of the Token, to avoid leaking full credentials in logs.
func maskToken(token string) string {
	if len(token) <= 8 {
		return "***"
	}
	return token[:4] + "..." + token[len(token)-4:]
}

// NewHTTPServer builds an http.Server with a timeout.
func NewHTTPServer(addr string, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
	}
}
