// Package webui provides a Web login interface **oriented to external browsers**.
//
// Background: hosts without a GUI (such as Linux servers with no desktop) have no browser
// available and cannot push credentials to the daemon via the browser extension. This service
// lets users access the host from **another machine's browser**, fill in "gateway address +
// username + password" on the page, and have the daemon log in to the gateway on their behalf
// and establish a connection directly after obtaining the JWT.
//
// The difference from internal/localapi:
//   - localapi only listens on the loopback address and is for this machine's browser/extension
//     to push already-issued credentials;
//   - this service deliberately listens on 0.0.0.0 for access by **other machines'** browsers,
//     and therefore receives passwords.
//
// Security note (option A, login only, no extra protection):
//   - The page and API use plaintext HTTP, so passwords are transmitted in plaintext within the
//     LAN; it should only be used on trusted internal networks;
//   - The service performs no authentication on visitors; anyone who can reach the port can
//     attempt to log in;
//   - When deploying, use a firewall to restrict the source network segments.
package webui

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"haijunbot-daemon/internal/auth"
	"haijunbot-daemon/internal/login"
	"haijunbot-daemon/internal/wsclient"
)

// Server is the Web login service.
//
// It is isomorphic to localapi.Server: it holds the same credential store and connection manager,
// so after a successful login it directly reuses the existing "write credentials + initiate
// connection" chain without starting a separate set of state.
type Server struct {
	store   *auth.Store
	manager *wsclient.Manager
	version string
}

// New creates a Web login service.
func New(store *auth.Store, manager *wsclient.Manager, version string) *Server {
	return &Server{store: store, manager: manager, version: version}
}

// loginRequest is the request body of POST /api/login.
type loginRequest struct {
	Gateway  string `json:"gateway"`
	Username string `json:"username"`
	Password string `json:"password"`
	// Name is the terminal name (optional): when left empty, the daemon keeps the gateway's existing name.
	Name string `json:"name"`
}

// Handler returns the routes.
func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/api/login", s.handleLogin)
	return mux
}

// handleIndex returns the embedded login page.
//
// It only responds to the root path; all other paths return 404 to avoid mistaking the page for a
// catch-all fallback.
func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	// The login page contains a credentials form and must not be cached.
	w.Header().Set("Cache-Control", "no-store")
	_, _ = w.Write([]byte(indexHTML))
}

// handleLogin receives the credentials submitted by the browser, logs in to the gateway on their
// behalf, and establishes a connection.
//
// Success: writes to the credential store and triggers the connection, returns
// {"success":true,"message":"..."}.
// Failure: returns 400 with a readable error message (not containing the password).
func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{
			"success": false,
			"error":   "method not allowed",
		})
		return
	}

	var req loginRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 64<<10)).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "request body format error: " + err.Error(),
		})
		return
	}

	gateway := login.NormalizeGateway(req.Gateway)
	username := strings.TrimSpace(req.Username)
	if gateway == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "please fill in the gateway address",
		})
		return
	}
	if username == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "please fill in the username",
		})
		return
	}
	if req.Password == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   "please fill in the password",
		})
		return
	}

	// Reuse the same logic as command-line login to avoid writing an HTTP call in two places.
	result, err := login.Login(gateway, username, req.Password)
	if err != nil {
		// The error message may come from the gateway (e.g. "invalid username or password"); echo it
		// directly to the page; never log the password itself.
		log.Printf("[webui] login failed: gateway=%s username=%s err=%v", gateway, username, err)
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"success": false,
			"error":   err.Error(),
		})
		return
	}

	// Same entry as localapi.handleAuth: write credentials + initiate connection (multiple
	// coexisting gateways do not overwrite each other).
	s.store.SetWithName(gateway, result.Token, req.Name)
	s.manager.ConnectWithName(gateway, result.Token, req.Name)

	log.Printf("[webui] login successful and connected: gateway=%s username=%s token=%s",
		gateway, username, login.MaskToken(result.Token))

	displayName := result.DisplayName
	if displayName == "" {
		displayName = result.Username
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"success": true,
		"message": "Login successful, the daemon has connected to the gateway, you can close this page now",
		"user":    displayName,
	})
}

// writeJSON writes a JSON response.
func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
