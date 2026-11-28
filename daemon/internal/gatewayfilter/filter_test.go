package gatewayfilter

import (
	"reflect"
	"testing"
)

func TestMatch(t *testing.T) {
	cases := []struct {
		name    string
		pattern string
		input   string
		want    bool
	}{
		{"exact match", "example.com:8000", "example.com:8000", true},
		{"exact non-match", "example.com:8000", "example.com:8001", false},
		{"star prefix", "*.example.com:8000", "a.example.com:8000", true},
		{"star prefix does not match root", "*.example.com:8000", "example.com:8000", false},
		{"star matches any including empty", "a*b", "ab", true},
		{"star matches middle", "a*b", "axxxb", true},
		{"star at end", "192.168.*", "192.168.1.5:8000", true},
		{"star at start", "*:8000", "anything:8000", true},
		{"star only matches everything", "*", "whatever:1234", true},
		{"question mark single char", "a?c", "abc", true},
		{"question mark does not match multiple", "a?c", "abbc", false},
		{"question mark does not match empty", "a?c", "ac", false},
		{"case-insensitive pattern", "Example.COM:8000", "example.com:8000", true},
		{"case-insensitive input", "example.com:8000", "EXAMPLE.COM:8000", true},
		{"trimming surrounding whitespace", "  example.com:8000  ", "example.com:8000", true},
		{"empty pattern empty input", "", "", true},
		{"empty pattern non-empty input", "", "x", false},
		{"port wildcard", "192.168.*:*", "192.168.1.5:9999", true},
		{"multi-segment star", "*.example.*:8000", "a.example.com:8000", true},
		{"non-matching prefix", "example.com:8000", "xexample.com:8000", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := Match(c.pattern, c.input); got != c.want {
				t.Fatalf("Match(%q, %q) = %v, want %v", c.pattern, c.input, got, c.want)
			}
		})
	}
}

func TestNormalizeMode(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"off", ModeOff},
		{"OFF", ModeOff},
		{" off ", ModeOff},
		{"whitelist", ModeWhitelist},
		{"WhiteList", ModeWhitelist},
		{"blacklist", ModeBlacklist},
		{"BLACKLIST", ModeBlacklist},
		{"", ModeOff},
		{"garbage", ModeOff},
	}
	for _, c := range cases {
		if got := NormalizeMode(c.in); got != c.want {
			t.Errorf("NormalizeMode(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestValidMode(t *testing.T) {
	for _, m := range []string{"off", "whitelist", "blacklist", "OFF", " Whitelist "} {
		if !ValidMode(m) {
			t.Errorf("ValidMode(%q) = false, want true", m)
		}
	}
	for _, m := range []string{"", "none", "allow", "deny"} {
		if ValidMode(m) {
			t.Errorf("ValidMode(%q) = true, want false", m)
		}
	}
}

func TestAllowsOffMode(t *testing.T) {
	f := New(ModeOff, []string{"example.com:8000"})
	// off mode always allows, even when the list matches.
	if !f.Allows("example.com:8000") {
		t.Fatal("off mode should allow all gateways")
	}
	if !f.Allows("other.com:9000") {
		t.Fatal("off mode should allow all gateways")
	}
}

func TestAllowsWhitelist(t *testing.T) {
	f := New(ModeWhitelist, []string{"*.example.com:8000", "192.168.1.5:*"})
	if !f.Allows("a.example.com:8000") {
		t.Fatal("a whitelist hit should be allowed")
	}
	if !f.Allows("192.168.1.5:9999") {
		t.Fatal("a whitelist hit should be allowed")
	}
	if f.Allows("other.com:8000") {
		t.Fatal("a whitelist miss should be denied")
	}
}

func TestAllowsWhitelistEmpty(t *testing.T) {
	f := New(ModeWhitelist, nil)
	// An empty whitelist = nobody is allowed (the safe direction).
	if f.Allows("example.com:8000") {
		t.Fatal("an empty whitelist should deny all gateways")
	}
}

func TestAllowsBlacklist(t *testing.T) {
	f := New(ModeBlacklist, []string{"*.example.com:8000"})
	if f.Allows("a.example.com:8000") {
		t.Fatal("a blacklist hit should be denied")
	}
	if !f.Allows("other.com:8000") {
		t.Fatal("a blacklist miss should be allowed")
	}
}

func TestAllowsBlacklistEmpty(t *testing.T) {
	f := New(ModeBlacklist, nil)
	// An empty blacklist = no restriction.
	if !f.Allows("example.com:8000") {
		t.Fatal("an empty blacklist should allow all gateways")
	}
}

func TestNilFilterAllows(t *testing.T) {
	var f *Filter
	if !f.Allows("anything:1234") {
		t.Fatal("a nil Filter should allow all gateways")
	}
	mode, patterns := f.Snapshot()
	if mode != ModeOff || patterns != nil {
		t.Fatalf("nil Filter Snapshot = (%q, %v), want (off, nil)", mode, patterns)
	}
	// Set on nil should be a no-op without panicking.
	f.Set(ModeWhitelist, []string{"x"})
}

func TestHostPortNormalization(t *testing.T) {
	f := New(ModeWhitelist, []string{"example.com:8000"})
	// With/without a protocol, and with a trailing slash, should all hit the same host:port.
	for _, gw := range []string{
		"http://example.com:8000",
		"https://example.com:8000",
		"example.com:8000",
		"http://example.com:8000/",
	} {
		if !f.Allows(gw) {
			t.Errorf("Allows(%q) = false, want true (should normalize to example.com:8000)", gw)
		}
	}
}

func TestHostPortDefaultPort(t *testing.T) {
	// https/wss→443 and http/ws→80 when the port is missing.
	fHTTPS := New(ModeWhitelist, []string{"example.com:443"})
	if !fHTTPS.Allows("https://example.com") {
		t.Fatal("https without a port should normalize to 443")
	}
	fHTTP := New(ModeWhitelist, []string{"example.com:80"})
	if !fHTTP.Allows("http://example.com") {
		t.Fatal("http without a port should normalize to 80")
	}
	fWSS := New(ModeWhitelist, []string{"example.com:443"})
	if !fWSS.Allows("wss://example.com") {
		t.Fatal("wss without a port should normalize to 443")
	}
	fWS := New(ModeWhitelist, []string{"example.com:80"})
	if !fWS.Allows("ws://example.com") {
		t.Fatal("ws without a port should normalize to 80")
	}
}

// TestHostPortWebSocketScheme regression test: a gateway address the daemon connects to may naturally be in the
// ws:// or wss:// form. If hostPort does not recognize these two protocols, an "http://" prefix would be wrongly
// added, url.Parse would treat "ws" as the hostname and lose the port, causing a silent whitelist/blacklist mismatch.
func TestHostPortWebSocketScheme(t *testing.T) {
	f := New(ModeBlacklist, []string{"bad.example.com:*"})
	for _, gw := range []string{
		"ws://bad.example.com:9999",
		"wss://bad.example.com:9999",
	} {
		if f.Allows(gw) {
			t.Errorf("Allows(%q) = true, want false (ws/wss should normalize correctly and hit the blacklist)", gw)
		}
	}
	// A non-matching ws address should still be allowed.
	if !f.Allows("ws://ok.example.com:9999") {
		t.Error("Allows(ws://ok.example.com:9999) = false, want true")
	}
}

func TestSetAndSnapshot(t *testing.T) {
	f := New(ModeOff, nil)
	f.Set(ModeBlacklist, []string{" a:1 ", "", "  b:2  "})
	mode, patterns := f.Snapshot()
	if mode != ModeBlacklist {
		t.Fatalf("mode = %q, want blacklist", mode)
	}
	// Empty items should be filtered out; the rest are trimmed.
	if !reflect.DeepEqual(patterns, []string{"a:1", "b:2"}) {
		t.Fatalf("patterns = %v, want [a:1 b:2]", patterns)
	}
	// Snapshot returns a copy: mutating the returned value should not affect the internal state.
	patterns[0] = "mutated"
	_, again := f.Snapshot()
	if again[0] != "a:1" {
		t.Fatal("Snapshot should return a copy; external mutation should not affect the internal state")
	}
}

func TestAllowsEmptyGateway(t *testing.T) {
	// An unnormalizable empty address: denied under whitelist, allowed under blacklist.
	wl := New(ModeWhitelist, []string{"*"})
	if wl.Allows("") {
		t.Fatal("an empty address should be denied under whitelist")
	}
	bl := New(ModeBlacklist, []string{"*"})
	if !bl.Allows("") {
		t.Fatal("an empty address should be allowed under blacklist")
	}
}
