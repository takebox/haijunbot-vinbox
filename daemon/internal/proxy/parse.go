package proxy

import (
	"net/url"
	"runtime"
	"strings"
)

// isWindows reports whether the current process is running on Windows.
func isWindows() bool {
	return runtime.GOOS == "windows"
}

// This file holds platform-independent proxy string parsing logic so it can be unit-tested on all platforms.

// pickProxyForScheme extracts the proxy address for the given scheme from ProxyServer.
//
// ProxyServer has two forms:
//   - "host:port": shared by all protocols;
//   - "http=host:port;https=host:port;ftp=host:port;socks=host:port": differentiated by protocol.
//
// When differentiated by protocol and there is no entry for the scheme, it returns empty (no proxy).
func pickProxyForScheme(server, scheme string) string {
	if !strings.Contains(server, "=") {
		return server
	}
	scheme = strings.ToLower(scheme)
	for _, part := range strings.Split(server, ";") {
		k, v, ok := strings.Cut(part, "=")
		if !ok {
			continue
		}
		if strings.ToLower(strings.TrimSpace(k)) == scheme {
			return strings.TrimSpace(v)
		}
	}
	return ""
}

// parseProxyURL parses "host:port" or an address with a protocol into a *url.URL.
// When there is no protocol prefix, it defaults to http.
func parseProxyURL(raw string) (*url.URL, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil, nil
	}
	if !strings.Contains(raw, "://") {
		raw = "http://" + raw
	}
	return url.Parse(raw)
}

// matchProxyOverride determines whether a host matches ProxyOverride (NO_PROXY semantics).
//
// Rules (consistent with Windows/mainstream implementations):
//   - The list is separated by ';' or ',';
//   - "*" means direct connection for all;
//   - "<local>" means direct connection for local hostnames without dots;
//   - Other entries match by suffix (e.g. "example.com" matches "a.example.com").
func matchProxyOverride(host, override string) bool {
	host = strings.ToLower(strings.TrimSpace(host))
	if host == "" {
		return false
	}
	for _, item := range strings.FieldsFunc(override, func(r rune) bool {
		return r == ';' || r == ','
	}) {
		item = strings.ToLower(strings.TrimSpace(item))
		if item == "" {
			continue
		}
		switch item {
		case "*":
			return true
		case "<local>":
			if !strings.Contains(host, ".") {
				return true
			}
		default:
			item = strings.TrimPrefix(item, ".")
			if host == item || strings.HasSuffix(host, "."+item) {
				return true
			}
		}
	}
	return false
}
