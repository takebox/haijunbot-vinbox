// Package proxy provides unified proxy decisions for the daemon's outbound requests.
//
// Proxy sources are merged in the following priority:
//  1. Environment variables HTTP_PROXY / HTTPS_PROXY / NO_PROXY (including lowercase forms),
//     handled by the standard library http.ProxyFromEnvironment;
//  2. System proxy (Windows only): the ProxyEnable / ProxyServer / ProxyOverride values
//     in the registry HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings,
//     i.e. the values configured in "Internet Options / System Settings -> Proxy".
//
// Why http.ProxyFromEnvironment alone is insufficient: it only reads environment variables,
// while proxies configured in Windows system settings are not written to environment
// variables, causing the daemon to fail to connect directly.
//
// This package introduces no third-party dependencies and does not use cgo.
package proxy

import (
	"net/http"
	"net/url"
)

// ProxyFunc returns a proxy decision function, semantically compatible with http.ProxyFromEnvironment:
// returning nil means no proxy is used for that request.
//
// This function can be assigned directly to http.Transport.Proxy, or to
// gorilla/websocket's Dialer.Proxy (the two have the same signature).
func ProxyFunc() func(*http.Request) (*url.URL, error) {
	return func(req *http.Request) (*url.URL, error) {
		if u, err := http.ProxyFromEnvironment(req); err != nil || u != nil {
			return u, err
		}
		// When no proxy is specified by environment variables, fall back to the system proxy (only implemented on Windows).
		return systemProxyForRequest(req)
	}
}

// Transport returns an *http.Transport using ProxyFunc.
//
// It clones http.DefaultTransport as a template, preserving its connection pool, timeouts and other
// default settings, and only overrides the Proxy field to avoid affecting other default behavior.
func Transport() *http.Transport {
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		// Theoretically unreachable; degrade to a minimal usable configuration.
		return &http.Transport{Proxy: ProxyFunc()}
	}
	t := base.Clone()
	t.Proxy = ProxyFunc()
	return t
}

// DirectTransport returns an *http.Transport that does NOT use any proxy.
//
// It is used for accessing the machine's own loopback address (e.g. 127.0.0.1): such requests
// must never go through a proxy, even if the user configured a system or environment proxy.
// http.ProxyFromEnvironment only treats "localhost" specially and judges "127.0.0.1" by NO_PROXY,
// so it cannot be relied upon.
func DirectTransport() *http.Transport {
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		return &http.Transport{}
	}
	t := base.Clone()
	t.Proxy = nil
	return t
}
