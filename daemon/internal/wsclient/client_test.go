package wsclient

import (
	"testing"
	"time"
)

func TestBuildSubprotocols(t *testing.T) {
	got := BuildSubprotocols("abc.def-ghi")
	want := []string{"haijunbot-daemon", "haijunbot-token.abc.def-ghi"}
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got=%v want=%v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("item %d mismatch: got=%q want=%q", i, got[i], want[i])
		}
	}
}

func TestBuildSubprotocolsEscapesToken(t *testing.T) {
	// JWTs contain '.' and '-'; after QueryEscape they should remain safe to put into a subprotocol.
	got := BuildSubprotocols("a b+c/d")
	if len(got) != 2 {
		t.Fatalf("expected 2 subprotocols, got %d", len(got))
	}
	if got[1] != "haijunbot-token.a+b%2Bc%2Fd" {
		t.Errorf("escape result mismatch: %q", got[1])
	}
}

func TestBuildSubprotocolsNoToken(t *testing.T) {
	got := BuildSubprotocols("")
	if len(got) != 1 || got[0] != "haijunbot-daemon" {
		t.Errorf("with no Token there should be only haijunbot-daemon, got %v", got)
	}
}

func TestNormalizeGateway(t *testing.T) {
	cases := map[string]string{
		"https://hjb-ai.cn/":     "https://hjb-ai.cn",
		"http://127.0.0.1:8000/": "http://127.0.0.1:8000",
		"hjb-ai.cn":              "https://hjb-ai.cn",
		"  hjb-ai.cn//  ":        "https://hjb-ai.cn",
		// ws/wss must be preserved as-is: if an https:// prefix were mistakenly added, url.Parse would treat "ws"
		// as a hostname and the connection would inevitably fail.
		"ws://127.0.0.1:8000": "ws://127.0.0.1:8000",
		"wss://hjb-ai.cn/":    "wss://hjb-ai.cn",
		"  ws://h:9//  ":      "ws://h:9",
		"":                    "",
	}
	for in, want := range cases {
		if got := NormalizeGateway(in); got != want {
			t.Errorf("NormalizeGateway(%q)=%q, want %q", in, got, want)
		}
	}
}

func TestBuildWSURL(t *testing.T) {
	cases := map[string]string{
		"https://hjb-ai.cn":      "wss://hjb-ai.cn/api/daemon/ws",
		"http://127.0.0.1:8000":  "ws://127.0.0.1:8000/api/daemon/ws",
		"http://127.0.0.1:8000/": "ws://127.0.0.1:8000/api/daemon/ws",
		// An address that is already ws(s) should be converted idempotently, without producing malformed URLs like "ws://ws://...".
		"ws://127.0.0.1:8000":  "ws://127.0.0.1:8000/api/daemon/ws",
		"wss://hjb-ai.cn":      "wss://hjb-ai.cn/api/daemon/ws",
		"ws://127.0.0.1:8000/": "ws://127.0.0.1:8000/api/daemon/ws",
	}
	for in, want := range cases {
		got, err := BuildWSURL(in)
		if err != nil {
			t.Fatalf("BuildWSURL(%q) error: %v", in, err)
		}
		if got != want {
			t.Errorf("BuildWSURL(%q)=%q, want %q", in, got, want)
		}
	}
	if _, err := BuildWSURL(""); err == nil {
		t.Error("an empty gateway address should error")
	}
}

func TestReconnectDelay(t *testing.T) {
	// Consistent with the extension: min(base*2^attempt, max), base=1s max=30s.
	cases := []struct {
		attempt int
		want    time.Duration
	}{
		{0, 1 * time.Second},
		{1, 2 * time.Second},
		{2, 4 * time.Second},
		{3, 8 * time.Second},
		{4, 16 * time.Second},
		{5, 30 * time.Second}, // 32 is truncated to 30
		{6, 30 * time.Second},
		{100, 30 * time.Second},
	}
	for _, c := range cases {
		if got := ReconnectDelay(c.attempt, 1, 30); got != c.want {
			t.Errorf("ReconnectDelay(%d)=%v, want %v", c.attempt, got, c.want)
		}
	}
}

func TestReconnectDelayCustomBase(t *testing.T) {
	if got := ReconnectDelay(0, 2, 10); got != 2*time.Second {
		t.Errorf("the first backoff should be base, got %v", got)
	}
	if got := ReconnectDelay(10, 2, 10); got != 10*time.Second {
		t.Errorf("should truncate to max, got %v", got)
	}
}

func TestReconnectDelayNegativeAttempt(t *testing.T) {
	if got := ReconnectDelay(-1, 1, 30); got != 1*time.Second {
		t.Errorf("a negative attempt should be treated as 0, got %v", got)
	}
}
