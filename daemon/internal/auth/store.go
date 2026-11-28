// Package auth provides a thread-safe in-memory credentials store (supporting multiple gateways).
//
// Tokens live only in memory, never persisted to disk; they expire when the process exits.
//
// Multi-gateway model: one daemon can hold credentials for several gateways at once, each independent and not overwriting
// the others. The semantics are consistent with the browser extension browser_extension/background/service_worker.js:
// credentials are archived by a "gateway index key" (GatewayKey, the protocol-agnostic host:port).
package auth

import (
	"encoding/json"
	"errors"
	"log"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// ErrNoCredentials indicates that there are no usable credentials for the specified gateway.
var ErrNoCredentials = errors.New("no usable credentials")

// Credentials is the content of a single auth push.
type Credentials struct {
	Gateway string
	Token   string
	// Name is the "terminal name" set by the user in the frontend (defaults to the computer name).
	// It is reported to the gateway when logging in (hello frame), so the gateway can distinguish terminals.
	// An empty value means the user has not set it, in which case the gateway falls back to the hostname.
	Name string
}

// NormalizeGateway normalizes a gateway address: trims surrounding whitespace; adds http:// when there is no protocol
// prefix; strips trailing slashes. The semantics are consistent with the extension's normalizeGateway.
//
// ws:// and wss:// are explicitly recognized: a gateway address may naturally be in WebSocket form (e.g.
// ws://host:9999). Without recognition it would wrongly get an "http://" prefix, producing
// "http://ws://host:9999"; a subsequent url.Parse would then treat "ws" as the hostname and lose the port,
// making the credential index key wrong and the connection fail silently.
func NormalizeGateway(gateway string) string {
	g := strings.TrimSpace(gateway)
	if g == "" {
		return ""
	}
	lower := strings.ToLower(g)
	if !strings.HasPrefix(lower, "http://") && !strings.HasPrefix(lower, "https://") &&
		!strings.HasPrefix(lower, "ws://") && !strings.HasPrefix(lower, "wss://") {
		g = "http://" + g
	}
	return strings.TrimRight(g, "/")
}

// GatewayKey returns the gateway key used to index credentials: it parses the URL and takes hostname:port
// (when the port is missing, https/wss defaults to 443 and http/ws to 80).
//
// Protocol differences are deliberately ignored: http://host:443 and https://host:443 are treated as the same gateway,
// because the gateway declared on the frontend page and the one filled in by the user may differ in protocol.
// Similarly ws/wss and http/https are treated as the same gateway (WebSocket is only a transport-layer difference).
// When parsing fails, the result of NormalizeGateway is used as the fallback.
func GatewayKey(gateway string) string {
	g := NormalizeGateway(gateway)
	if g == "" {
		return ""
	}
	u, err := url.Parse(g)
	if err != nil || u.Hostname() == "" {
		return g
	}
	port := u.Port()
	if port == "" {
		if strings.EqualFold(u.Scheme, "https") || strings.EqualFold(u.Scheme, "wss") {
			port = "443"
		} else {
			port = "80"
		}
	}
	return u.Hostname() + ":" + port
}

// Store is a thread-safe multi-gateway credentials store.
type Store struct {
	mu sync.RWMutex
	// creds is keyed by GatewayKey; a missing key means that gateway is unauthenticated.
	creds map[string]Credentials
	// valid marks whether each gateway's Token is still valid (set to false after receiving 4401/4403).
	valid map[string]bool
	// path is the persistence file path; an empty value means no persistence (pure memory, credentials expire when the process exits).
	// When non-empty, every write synchronously persists all credentials to this file for recovery after a restart.
	path string
}

// NewStore creates an empty credentials store (pure memory, no persistence).
func NewStore() *Store {
	return &Store{
		creds: make(map[string]Credentials),
		valid: make(map[string]bool),
	}
}

// NewPersistentStore creates a credentials store with persistence: every write synchronously writes all credentials
// to path (0600), so the login state can be restored after a process restart.
//
// A persistence failure is only logged and does not affect the in-memory semantics (worst case: credentials must be re-pushed after a restart).
func NewPersistentStore(path string) *Store {
	s := NewStore()
	s.path = path
	return s
}

// LoadStore loads credentials from a persistence file and returns a Store with persistence.
//
// A missing file or a parse failure returns an empty Store (no error, the caller skips silently),
// so the daemon starts normally on the first launch or when the credentials file is corrupt.
func LoadStore(path string) *Store {
	s := NewPersistentStore(path)
	if path == "" {
		return s
	}
	blob, err := os.ReadFile(path)
	if err != nil {
		return s
	}
	var creds []Credentials
	if err := json.Unmarshal(blob, &creds); err != nil {
		log.Printf("[auth] failed to parse the credentials file (%s): %v", path, err)
		return s
	}
	for _, c := range creds {
		if c.Gateway == "" || c.Token == "" {
			continue
		}
		key := GatewayKey(c.Gateway)
		if key == "" {
			continue
		}
		s.creds[key] = c
		s.valid[key] = true
	}
	return s
}

// persist synchronously writes all current credentials to the persistence file (atomic write: temp file + rename).
// It is a no-op when path is empty. A write failure is only logged and does not affect the in-memory semantics.
// Note: must be called while holding the s.mu write lock (it reads s.creds directly, to avoid a deadlock).
func (s *Store) persist() {
	if s.path == "" {
		return
	}
	creds := make([]Credentials, 0, len(s.creds))
	for _, c := range s.creds {
		creds = append(creds, c)
	}
	blob, err := json.Marshal(creds)
	if err != nil {
		log.Printf("[auth] failed to serialize the credentials: %v", err)
		return
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o700); err != nil {
		log.Printf("[auth] failed to create the credentials directory: %v", err)
		return
	}
	tmp := s.path + ".tmp"
	if err := os.WriteFile(tmp, blob, 0o600); err != nil {
		log.Printf("[auth] failed to write the credentials temp file: %v", err)
		return
	}
	_ = os.Chmod(tmp, 0o600)
	if err := os.Rename(tmp, s.path); err != nil {
		_ = os.Remove(tmp)
		log.Printf("[auth] failed to save the credentials file: %v", err)
	}
}

// Set writes the credentials for the specified gateway and resets that gateway's tokenValid to true.
// A repeated Set for the same gateway is treated as an overwrite (token update) and does not affect other gateways.
func (s *Store) Set(gateway, token string) {
	key := GatewayKey(gateway)
	if key == "" {
		return
	}
	s.mu.Lock()
	s.creds[key] = Credentials{Gateway: gateway, Token: token}
	s.valid[key] = true
	s.persist()
	s.mu.Unlock()
}

// SetWithName writes the credentials for the specified gateway (including the terminal name) and resets that
// gateway's tokenValid to true. An empty name keeps that gateway's existing name (so a "token-only update" push does not clear the name).
func (s *Store) SetWithName(gateway, token, name string) {
	key := GatewayKey(gateway)
	if key == "" {
		return
	}
	s.mu.Lock()
	prev := s.creds[key]
	if name == "" {
		name = prev.Name
	}
	s.creds[key] = Credentials{Gateway: gateway, Token: token, Name: name}
	s.valid[key] = true
	s.persist()
	s.mu.Unlock()
}

// Get returns a copy of the credentials for the specified gateway; returns ErrNoCredentials when unauthenticated.
func (s *Store) Get(gateway string) (Credentials, error) {
	key := GatewayKey(gateway)
	if key == "" {
		return Credentials{}, ErrNoCredentials
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	creds, ok := s.creds[key]
	if !ok {
		return Credentials{}, ErrNoCredentials
	}
	return creds, nil
}

// Clear removes the credentials for the specified gateway (without affecting other gateways).
func (s *Store) Clear(gateway string) {
	key := GatewayKey(gateway)
	if key == "" {
		return
	}
	s.mu.Lock()
	delete(s.creds, key)
	delete(s.valid, key)
	s.persist()
	s.mu.Unlock()
}

// ClearAll clears the credentials of all gateways.
func (s *Store) ClearAll() {
	s.mu.Lock()
	s.creds = make(map[string]Credentials)
	s.valid = make(map[string]bool)
	s.persist()
	s.mu.Unlock()
}

// List returns a slice of copies of all credentials (without exposing the internal map).
func (s *Store) List() []Credentials {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Credentials, 0, len(s.creds))
	for _, c := range s.creds {
		out = append(out, c)
	}
	return out
}

// MarkTokenInvalid marks the Token of the specified gateway as invalid (called when authentication fails).
func (s *Store) MarkTokenInvalid(gateway string) {
	key := GatewayKey(gateway)
	if key == "" {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.creds[key]; ok {
		s.valid[key] = false
	}
}

// Has reports whether the specified gateway is authenticated.
func (s *Store) Has(gateway string) bool {
	key := GatewayKey(gateway)
	if key == "" {
		return false
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	_, ok := s.creds[key]
	return ok
}

// TokenValid reports whether the Token of the specified gateway is still valid.
func (s *Store) TokenValid(gateway string) bool {
	key := GatewayKey(gateway)
	if key == "" {
		return false
	}
	s.mu.RLock()
	defer s.mu.RUnlock()
	_, ok := s.creds[key]
	return ok && s.valid[key]
}
