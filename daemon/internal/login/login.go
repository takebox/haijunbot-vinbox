// Package login implements the pure logic for "logging into the gateway with username/password and pushing the credentials to the local daemon".
//
// Background: the daemon's Token is by default pushed only from a web page (browser → local /api/auth);
// on a headless machine there is no browser, so that path is unavailable. This package provides command-line login:
//
//	username + password → POST {gateway}/api/auth/login to exchange for a JWT
//	                   → POST http://{listen}/api/auth to push to the local daemon
//
// Design highlights:
//   - This file only contains testable pure logic (no os.Stdin reads, no command-line parsing), so each branch can be
//     covered with httptest; interactive input is handled by the cmd layer and password_*.go.
//   - Credentials are still kept only in the daemon's memory (see internal/auth/store.go); this package does not persist them.
package login

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"haijunbot-daemon/internal/proxy"
)

// loginTimeout is the overall timeout for a login request.
//
// Login involves only one lightweight JSON round trip; 15s covers slow networks while keeping the command line
// from hanging for a long time when the gateway does not respond.
const loginTimeout = 15 * time.Second

// pushTimeout is the timeout for pushing credentials to the local daemon.
//
// A local loopback call should be very fast; a short timeout quickly surfaces problems like "the daemon is not running".
const pushTimeout = 10 * time.Second

// maxErrBodyBytes is the maximum number of bytes read from an error response body, for building readable error messages.
const maxErrBodyBytes = 512

// LoginResult is the result of a successful login.
type LoginResult struct {
	// Token is the JWT issued by the gateway.
	Token string
	// Username is the login username (the normalized username returned by the gateway).
	Username string
	// DisplayName is the user display name, may be empty.
	DisplayName string
	// IsAdmin indicates whether the user is an administrator.
	IsAdmin bool
}

// loginRequest is the request body of POST {gateway}/api/auth/login.
type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

// loginResponse is the response body of the login endpoint.
//
// Success: {"success":true,"data":{"token":..,"user":{..}}}
// Failure: {"success":false,"error":{"code":..,"message":..}}
type loginResponse struct {
	Success bool `json:"success"`
	Data    struct {
		Token string `json:"token"`
		User  struct {
			UserID      string `json:"user_id"`
			Username    string `json:"username"`
			DisplayName string `json:"display_name"`
			IsAdmin     bool   `json:"is_admin"`
		} `json:"user"`
	} `json:"data"`
	Error struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

// NormalizeGateway normalizes a gateway address: trims surrounding whitespace and trailing slashes.
//
// It is consistent with the "strip trailing slash" part of internal/auth.NormalizeGateway semantics, but does not add
// an http:// prefix here--login needs the user to supply a genuinely reachable address, and silent completion would
// easily hide mistakes. ws:// and wss:// are kept as-is (the daemon side can recognize them when pushing credentials),
// and they are only converted by HTTPGateway when an actual HTTP login request is sent.
func NormalizeGateway(gateway string) string {
	return strings.TrimRight(strings.TrimSpace(gateway), "/")
}

// HTTPGateway converts a gateway address into a form usable for HTTP requests.
//
// The login endpoint has HTTP semantics, but users may use the WebSocket habit of filling in ws:// or wss://
// (the two differ only at the transport layer; the host and port are the same). Without conversion, http.Client
// directly reports "unsupported protocol scheme ws". http(s) and other forms are returned unchanged.
func HTTPGateway(gateway string) string {
	lower := strings.ToLower(gateway)
	if strings.HasPrefix(lower, "wss://") {
		return "https://" + gateway[len("wss://"):]
	}
	if strings.HasPrefix(lower, "ws://") {
		return "http://" + gateway[len("ws://"):]
	}
	return gateway
}

// Login logs into the gateway with username/password and returns the JWT and user info on success.
//
// Error branches:
//   - gateway / username / password empty: returns an argument error directly;
//   - network unreachable: returns a request error including the address;
//   - HTTP non-200: the error message includes the status code and a snippet of the response body;
//   - success=false: the error message includes the gateway-returned error.message;
//   - success=true but token empty: treated as an abnormal response.
func Login(gateway, username, password string) (LoginResult, error) {
	gateway = NormalizeGateway(gateway)
	if gateway == "" {
		return LoginResult{}, fmt.Errorf("the gateway address is empty")
	}
	if strings.TrimSpace(username) == "" {
		return LoginResult{}, fmt.Errorf("the username cannot be empty")
	}
	if password == "" {
		return LoginResult{}, fmt.Errorf("the password cannot be empty")
	}

	body, err := json.Marshal(loginRequest{Username: username, Password: password})
	if err != nil {
		return LoginResult{}, fmt.Errorf("failed to serialize the login request: %w", err)
	}

	url := HTTPGateway(gateway) + "/api/auth/login"
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return LoginResult{}, fmt.Errorf("failed to build the login request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: loginTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return LoginResult{}, fmt.Errorf("login request failed (%s): %w", url, err)
	}
	defer resp.Body.Close()

	// Read the response body: a normal response is small; the 1MiB cap is enough and prevents an abnormal response from exhausting memory.
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return LoginResult{}, fmt.Errorf("failed to read the login response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return LoginResult{}, fmt.Errorf("login failed (HTTP %d): %s",
			resp.StatusCode, strings.TrimSpace(truncate(raw, maxErrBodyBytes)))
	}

	var parsed loginResponse
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return LoginResult{}, fmt.Errorf("failed to parse the login response: %w", err)
	}

	if !parsed.Success {
		msg := strings.TrimSpace(parsed.Error.Message)
		if msg == "" {
			msg = strings.TrimSpace(truncate(raw, maxErrBodyBytes))
		}
		if msg == "" {
			msg = "the gateway rejected the login request"
		}
		return LoginResult{}, fmt.Errorf("login rejected: %s", msg)
	}

	if strings.TrimSpace(parsed.Data.Token) == "" {
		return LoginResult{}, fmt.Errorf("the login response is missing a token")
	}

	return LoginResult{
		Token:       parsed.Data.Token,
		Username:    parsed.Data.User.Username,
		DisplayName: parsed.Data.User.DisplayName,
		IsAdmin:     parsed.Data.User.IsAdmin,
	}, nil
}

// authPushRequest is the request body of POST http://{listen}/api/auth.
//
// The fields align with authRequest in internal/localapi (gateway / token / name).
type authPushRequest struct {
	Gateway string `json:"gateway"`
	Token   string `json:"token"`
	Name    string `json:"name"`
}

// PushAuth pushes the credentials to the local daemon's /api/auth, triggering it to connect to the gateway.
//
// listen is shaped like "127.0.0.1:17800" (from the config or the default value); when name is empty, the daemon
// keeps the existing name for that gateway (see the SetWithName semantics in internal/localapi).
//
// A refused connection gives a readable hint guiding the user to start the daemon first.
func PushAuth(listen, gateway, token, name string) error {
	listen = strings.TrimSpace(listen)
	if listen == "" {
		return fmt.Errorf("the local service listen address is empty")
	}
	gateway = NormalizeGateway(gateway)
	if gateway == "" {
		return fmt.Errorf("the gateway address is empty")
	}
	if strings.TrimSpace(token) == "" {
		return fmt.Errorf("the token is empty, cannot push credentials")
	}

	body, err := json.Marshal(authPushRequest{Gateway: gateway, Token: token, Name: name})
	if err != nil {
		return fmt.Errorf("failed to serialize the credentials: %w", err)
	}

	url := "http://" + listen + "/api/auth"
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to build the credential push request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	// The target is the local loopback address; explicitly bypass the proxy (the user may have configured a system proxy).
	client := &http.Client{Timeout: pushTimeout, Transport: proxy.DirectTransport()}
	resp, err := client.Do(req)
	if err != nil {
		// When the local service is not running it is usually a connection refused; an actionable hint is given here.
		return fmt.Errorf(
			"failed to push credentials: the local background service is not running (%s), please start haijunbot-daemon first (%v)",
			listen, err)
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to push credentials (HTTP %d): %s",
			resp.StatusCode, strings.TrimSpace(truncate(raw, maxErrBodyBytes)))
	}
	return nil
}

// MaskToken keeps only a few leading and trailing characters of the Token, avoiding leaking the full credential in logs.
//
// It is consistent with the maskToken semantics in internal/localapi (this package cannot conveniently depend on localapi in reverse).
func MaskToken(token string) string {
	if len(token) <= 8 {
		return "***"
	}
	return token[:4] + "..." + token[len(token)-4:]
}

// truncate trims a byte slice to at most n bytes, for limiting the length of error messages.
func truncate(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n])
}
