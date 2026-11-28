//go:build !windows

package proxy

import (
	"net/http"
	"net/url"
)

// systemProxyForRequest: non-Windows platforms have no concept of a "system proxy";
// the proxy is determined solely by environment variables (already handled by http.ProxyFromEnvironment),
// so it always returns nil.
func systemProxyForRequest(*http.Request) (*url.URL, error) {
	return nil, nil
}
