package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

// TestE2EProxyTransport is an end-to-end verification: after setting HTTP_PROXY, Transport sends
// requests for **non-loopback** hosts through the proxy; DirectTransport bypasses the proxy.
//
// Note: Go's httpproxy automatically connects directly for 127.0.0.1/localhost, so this uses a
// non-resolvable hostname like example.invalid as the target — the request must go through the
// proxy to succeed, which proves the proxy actually takes effect.
//
// This test case runs in a child process (see runChildE2E) to avoid the environment variable cache
// of http.ProxyFromEnvironment being polluted by other tests in the same package.
func TestE2EProxyTransport(t *testing.T) {
	out := runChildE2E(t)
	if out != "ok" {
		t.Fatalf("child process result unexpected: %s", out)
	}
}

// TestE2EProxyTransportChild is the child process entry point, executing the real end-to-end assertions.
func TestE2EProxyTransportChild(t *testing.T) {
	if os.Getenv(e2eChildEnvKey) != childEnvVal {
		t.Skip("only runs in child process")
	}

	var (
		proxied bool
		gotURL  string
	)
	proxySrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		proxied = true
		gotURL = r.URL.String()
		io.WriteString(w, "via-proxy")
	}))
	defer proxySrv.Close()

	os.Setenv("HTTP_PROXY", proxySrv.URL)
	os.Setenv("http_proxy", proxySrv.URL)
	os.Setenv("NO_PROXY", "")
	os.Setenv("no_proxy", "")

	client := &http.Client{Transport: Transport()}
	resp, err := client.Get("http://example.invalid/hello")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !proxied || string(body) != "via-proxy" {
		t.Fatalf("should go through proxy, got proxied=%v body=%q", proxied, body)
	}
	if gotURL != "http://example.invalid/hello" {
		t.Fatalf("target URL received by proxy mismatch: %q", gotURL)
	}

	// DirectTransport: under the same environment variables it should connect directly (and fail because example.invalid is non-resolvable).
	direct := &http.Client{Transport: DirectTransport()}
	if _, err := direct.Get("http://example.invalid/hello"); err == nil {
		t.Fatal("DirectTransport should not go through the proxy (example.invalid should fail to connect directly)")
	}
	t.Logf("end-to-end: Transport goes through proxy (target=%s), DirectTransport connects directly and fails, both as expected", gotURL)
}
