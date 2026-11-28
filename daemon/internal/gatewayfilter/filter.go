// Package gatewayfilter provides the "gateway whitelist/blacklist" matching and decision capability.
//
// Background: the daemon/browser extension automatically establishes a connection when a user logs into a gateway.
// If a user only logs into a gateway once in a while (e.g. a test environment or someone else's server), it will be
// auto-discovered and stay connected for a long time, causing an "accidental connection to a gateway that should not
// be connected to". This package provides a configurable list to restrict which gateways are allowed/denied.
//
// Three modes:
//   - off: no restriction, every gateway is allowed (default).
//   - whitelist: only gateways matching the list are allowed to connect.
//   - blacklist: gateways matching the list are denied; the rest are allowed.
//
// The matching target is "host:port" (consistent with the auth.GatewayKey semantics, protocol differences ignored),
// with wildcard support: '*' matches a run of any length (including empty), '?' matches exactly one character.
//
// This package deliberately does not import auth: first, to avoid an unnecessary dependency coupling with upper-layer
// packages; second, the hostPort normalization logic is short, so implementing it here is more straightforward (semantics align with auth.GatewayKey).
package gatewayfilter

import (
	"net/url"
	"strings"
	"sync"
)

// Mode constants.
const (
	// ModeOff means no restriction (default).
	ModeOff = "off"
	// ModeWhitelist means whitelist: only a match in the list is allowed.
	ModeWhitelist = "whitelist"
	// ModeBlacklist means blacklist: a match in the list is denied.
	ModeBlacklist = "blacklist"
)

// NormalizeMode normalizes a mode string: trims whitespace, lowercases; empty or invalid values fall back to ModeOff.
//
// Falling back to "no restriction" rather than erroring makes config parsing and frontend pushes tolerant: an invalid
// value should neither fail daemon startup nor accidentally lock the user out (the "default off" ensures the safe direction).
func NormalizeMode(s string) string {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case ModeWhitelist:
		return ModeWhitelist
	case ModeBlacklist:
		return ModeBlacklist
	default:
		return ModeOff
	}
}

// ValidMode reports whether the mode string is one of the three valid values (after normalization).
func ValidMode(s string) bool {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case ModeOff, ModeWhitelist, ModeBlacklist:
		return true
	default:
		return false
	}
}

// Match reports whether hostPort matches pattern (wildcards: '*' matches any length including empty, '?' matches exactly one character).
//
// Case-insensitive; both pattern and hostPort are trimmed first.
// Implemented with two pointers + backtracking (worst case O(n*m)); regexp is deliberately avoided: a user-supplied
// pattern must not be parsed as a regular expression (injection/performance trap), and the wildcard semantics are more intuitive.
func Match(pattern, hostPort string) bool {
	p := strings.ToLower(strings.TrimSpace(pattern))
	s := strings.ToLower(strings.TrimSpace(hostPort))
	if p == "" {
		// An empty pattern matches nothing non-empty; an empty input also does not match.
		return s == ""
	}

	// Classic wildcard matching: pi points into pattern, si into hostPort;
	// star records the most recent '*' position, mark records the si corresponding to that '*' at the time.
	pi, si := 0, 0
	star := -1
	mark := 0
	for si < len(s) {
		if pi < len(p) && (p[pi] == '?' || p[pi] == s[si]) {
			pi++
			si++
			continue
		}
		if pi < len(p) && p[pi] == '*' {
			// Record a backtrack point: first try making '*' match the empty string.
			star = pi
			mark = si
			pi++
			continue
		}
		if star >= 0 {
			// Backtrack: make the most recent '*' consume one more character and retry.
			pi = star + 1
			mark++
			si = mark
			continue
		}
		return false
	}
	// hostPort is exhausted; the remaining pattern must all be '*' to match.
	for pi < len(p) && p[pi] == '*' {
		pi++
	}
	return pi == len(p)
}

// hostPort normalizes a gateway address to "host:port" (consistent with the auth.GatewayKey semantics): it takes
// hostname:port after parsing the URL; when the port is missing, https/wss→443 and http/ws→80; on a parse failure it falls back to the original string.
//
// ws:// and wss:// must be explicitly recognized: a gateway address the daemon connects to may naturally be in
// WebSocket form (e.g. ws://host:9999). If only http(s) were recognized, an "http://" prefix would be wrongly added,
// making url.Parse treat "ws" as the hostname and lose the port, so the whitelist/blacklist would mismatch.
func hostPort(gateway string) string {
	g := strings.TrimSpace(gateway)
	if g == "" {
		return ""
	}
	lower := strings.ToLower(g)
	if !strings.HasPrefix(lower, "http://") && !strings.HasPrefix(lower, "https://") &&
		!strings.HasPrefix(lower, "ws://") && !strings.HasPrefix(lower, "wss://") {
		g = "http://" + g
	}
	g = strings.TrimRight(g, "/")
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

// Filter holds the current list configuration (thread-safe; reads dominate, uses an RWMutex).
//
// The zero value is unusable; construct one with New. (*Filter)(nil) is allowed as a "no restriction" sentinel:
// every method is nil-receiver safe (Allows returns true, the rest are no-ops/empty values).
type Filter struct {
	mu       sync.RWMutex
	mode     string
	patterns []string
}

// New constructs a Filter; mode is normalized via NormalizeMode, patterns are trimmed with empty items removed.
func New(mode string, patterns []string) *Filter {
	f := &Filter{}
	f.Set(mode, patterns)
	return f
}

// Set updates the mode and list (locked).
func (f *Filter) Set(mode string, patterns []string) {
	if f == nil {
		return
	}
	cleaned := make([]string, 0, len(patterns))
	for _, p := range patterns {
		if v := strings.TrimSpace(p); v != "" {
			cleaned = append(cleaned, v)
		}
	}
	f.mu.Lock()
	f.mode = NormalizeMode(mode)
	f.patterns = cleaned
	f.mu.Unlock()
}

// Snapshot returns a copy of the current mode and list (locked), for state queries/persistence.
func (f *Filter) Snapshot() (string, []string) {
	if f == nil {
		return ModeOff, nil
	}
	f.mu.RLock()
	defer f.mu.RUnlock()
	out := make([]string, len(f.patterns))
	copy(out, f.patterns)
	return f.mode, out
}

// Allows determines whether the given gateway is allowed to connect.
//
// Decision rules:
//   - nil receiver / ModeOff → true (no restriction).
//   - ModeWhitelist → true only when any pattern in the list matches the host:port; an empty list is false
//     (an empty whitelist means "nobody is allowed", the safe direction).
//   - ModeBlacklist → false when any pattern in the list matches; an empty list is true (no restriction).
func (f *Filter) Allows(gateway string) bool {
	if f == nil {
		return true
	}
	f.mu.RLock()
	mode := f.mode
	patterns := f.patterns
	f.mu.RUnlock()

	if mode == ModeOff {
		return true
	}
	hp := hostPort(gateway)
	if hp == "" {
		// An unnormalizable address: denied under whitelist (safe direction), allowed under blacklist.
		return mode != ModeWhitelist
	}
	hit := false
	for _, p := range patterns {
		if Match(p, hp) {
			hit = true
			break
		}
	}
	if mode == ModeWhitelist {
		return hit
	}
	// ModeBlacklist
	return !hit
}
