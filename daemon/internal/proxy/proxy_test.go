package proxy

import (
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"testing"
)

// Note: http.ProxyFromEnvironment caches environment variables internally with sync.Once
// (read on first call, then never changes). Therefore test cases of "set different proxy
// environment variables -> observe different results" cannot be completed in the same
// process; a child process is required (each is a brand-new process with a fresh cache).
//
// Convention: when the PROXY_TEST_CHILD environment variable is non-empty, this test binary
// runs as a child process, executes the logic under test directly, and expresses the result
// via the exit code.

const (
	childEnvKey    = "PROXY_TEST_CHILD"
	e2eChildEnvKey = "PROXY_TEST_E2E_CHILD"
	childEnvVal    = "1"
)

// runChildE2E runs TestE2EProxyTransportChild as a child process.
func runChildE2E(t *testing.T) string {
	t.Helper()
	cmd := exec.Command(os.Args[0], "-test.run=^TestE2EProxyTransportChild$", "-test.v")
	cmd.Env = append(os.Environ(), e2eChildEnvKey+"="+childEnvVal)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("child process failed: %v\n%s", err, out)
	}
	return "ok"
}

// TestProxyFuncFromEnvironment verifies that after setting HTTP_PROXY / HTTPS_PROXY,
// ProxyFunc returns the environment proxy for requests of the corresponding protocol.
func TestProxyFuncFromEnvironment(t *testing.T) {
	out := runChild(t, map[string]string{
		"HTTP_PROXY":  "http://proxy.example:8080",
		"HTTPS_PROXY": "http://secure.example:8443",
		"NO_PROXY":    "",
	})
	if out != "ok" {
		t.Fatalf("child process result unexpected: %s", out)
	}
}

// TestProxyFuncNoProxy verifies that hosts matched by NO_PROXY do not go through the proxy.
func TestProxyFuncNoProxy(t *testing.T) {
	out := runChild(t, map[string]string{
		"HTTP_PROXY": "http://proxy.example:8080",
		"NO_PROXY":   "skip.example",
	})
	if out != "ok" {
		t.Fatalf("child process result unexpected: %s", out)
	}
}

// TestProxyFuncNoEnv verifies that no proxy is used when no proxy environment variables are set.
//
// Note: on Windows the host may have a system proxy enabled, in which case the system proxy
// is returned instead of nil, so this assertion only takes effect on non-Windows platforms.
func TestProxyFuncNoEnv(t *testing.T) {
	if isWindows() {
		t.Skip("system proxy on Windows affects the result, skipping")
	}
	out := runChild(t, map[string]string{
		"HTTP_PROXY":  "",
		"HTTPS_PROXY": "",
		"NO_PROXY":    "",
		"http_proxy":  "",
		"https_proxy": "",
		"no_proxy":    "",
	})
	if out != "ok" {
		t.Fatalf("child process result unexpected: %s", out)
	}
}

// TestProxyFuncChild is the child process entry point: executes assertions per the scenario specified by PROXY_TEST_CHILD.
func TestProxyFuncChild(t *testing.T) {
	if os.Getenv(childEnvKey) != childEnvVal {
		t.Skip("only runs in child process")
	}
	scenario := os.Getenv("PROXY_TEST_SCENARIO")
	fn := ProxyFunc()

	req, _ := http.NewRequest(http.MethodGet, "http://target.example/path", nil)
	got, err := fn(req)
	if err != nil {
		t.Fatalf("proxy decision failed: %v", err)
	}

	switch scenario {
	case "env":
		assertProxyURL(t, got, "http://proxy.example:8080")
		httpsReq, _ := http.NewRequest(http.MethodGet, "https://target.example/path", nil)
		got, err = fn(httpsReq)
		if err != nil {
			t.Fatalf("https proxy decision failed: %v", err)
		}
		assertProxyURL(t, got, "http://secure.example:8443")
	case "noproxy":
		skipReq, _ := http.NewRequest(http.MethodGet, "http://skip.example/path", nil)
		got, err = fn(skipReq)
		if err != nil {
		t.Fatalf("proxy decision failed: %v", err)
		}
		if got != nil {
			t.Fatalf("host matched by NO_PROXY should not go through proxy, got %v", got)
		}
	case "noenv":
		if got != nil {
			t.Fatalf("no proxy should be returned when none is configured, got %v", got)
		}
	default:
		t.Fatalf("unknown scenario: %q", scenario)
	}
}

// TestTransportUsesProxyFunc verifies that the Transport's Proxy field is wired up.
func TestTransportUsesProxyFunc(t *testing.T) {
	if Transport().Proxy == nil {
		t.Fatal("Transport().Proxy should not be nil")
	}
	if DirectTransport().Proxy != nil {
		t.Fatal("DirectTransport().Proxy should be nil (no proxy used)")
	}
}

// TestPickProxyForScheme covers both forms of ProxyServer.
func TestPickProxyForScheme(t *testing.T) {
	cases := []struct {
		name   string
		server string
		scheme string
		want   string
	}{
		{"single address any protocol", "host:8080", "http", "host:8080"},
		{"single address https", "host:8080", "https", "host:8080"},
		{"per-protocol match hit", "http=a:1;https=b:2", "https", "b:2"},
		{"per-protocol case-insensitive", "HTTP=a:1;HTTPS=b:2", "https", "b:2"},
		{"per-protocol no match", "http=a:1;https=b:2", "socks", ""},
		{"empty string", "", "http", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := pickProxyForScheme(c.server, c.scheme); got != c.want {
				t.Fatalf("pickProxyForScheme(%q,%q)=%q, want %q",
					c.server, c.scheme, got, c.want)
			}
		})
	}
}

// TestParseProxyURL covers both forms: with and without a protocol prefix.
func TestParseProxyURL(t *testing.T) {
	got, err := parseProxyURL("host:8080")
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}
	assertProxyURL(t, got, "http://host:8080")

	got, err = parseProxyURL("socks5://host:1080")
	if err != nil {
		t.Fatalf("parse failed: %v", err)
	}
	assertProxyURL(t, got, "socks5://host:1080")

	got, err = parseProxyURL("  ")
	if err != nil || got != nil {
		t.Fatalf("empty string should return (nil,nil), got (%v,%v)", got, err)
	}
}

// TestMatchProxyOverride covers the various matching rules of ProxyOverride.
func TestMatchProxyOverride(t *testing.T) {
	cases := []struct {
		name     string
		host     string
		override string
		want     bool
	}{
		{"wildcard all", "any.example", "*", true},
		{"exact match", "example.com", "example.com", true},
		{"suffix match", "a.example.com", "example.com", true},
		{"different prefix no match", "notexample.com", "example.com", false},
		{"semicolon separated", "a.com", "b.com;a.com", true},
		{"comma separated", "a.com", "b.com,a.com", true},
		{"leading dot", "a.example.com", ".example.com", true},
		{"local matches host without dot", "myhost", "<local>", true},
		{"local does not match host with dot", "my.host", "<local>", false},
		{"case-insensitive", "A.Example.COM", "example.com", true},
		{"empty override", "a.com", "", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := matchProxyOverride(c.host, c.override); got != c.want {
				t.Fatalf("matchProxyOverride(%q,%q)=%v, want %v",
					c.host, c.override, got, c.want)
			}
		})
	}
}

// runChild runs this test binary as a child process, executing only TestProxyFuncChild,
// and specifies the proxy configuration and scenario via environment variables. On success the
// child outputs "ok".
//
// A child process is used because http.ProxyFromEnvironment caches environment variables, so
// multiple environment variable changes cannot be observed within the same process.
func runChild(t *testing.T, env map[string]string) string {
	t.Helper()
	cmd := exec.Command(os.Args[0], "-test.run=^TestProxyFuncChild$", "-test.v")
	cmd.Env = append(os.Environ(), childEnvKey+"="+childEnvVal)
	for k, v := range env {
		cmd.Env = append(cmd.Env, k+"="+v)
	}
	cmd.Env = append(cmd.Env, "PROXY_TEST_SCENARIO="+scenarioOf(env))
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("child process failed: %v\n%s", err, out)
	}
	return "ok"
}

// scenarioOf infers the child process scenario from the passed environment variables.
func scenarioOf(env map[string]string) string {
	if env["NO_PROXY"] == "skip.example" {
		return "noproxy"
	}
	if env["HTTP_PROXY"] == "" {
		return "noenv"
	}
	return "env"
}

// assertProxyURL asserts that the parsed proxy URL matches the expectation.
func assertProxyURL(t *testing.T, got *url.URL, want string) {
	t.Helper()
	if got == nil {
		t.Fatalf("expected proxy %s, got nil", want)
	}
	if got.String() != want {
		t.Fatalf("proxy URL = %s, want %s", got.String(), want)
	}
}
