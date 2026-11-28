package auth

import (
	"os"
	"path/filepath"
	"sync"
	"testing"
)

func TestNormalizeGateway(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"", ""},
		{"   ", ""},
		{"https://hjb-ai.cn", "https://hjb-ai.cn"},
		{"https://hjb-ai.cn/", "https://hjb-ai.cn"},
		{"https://hjb-ai.cn///", "https://hjb-ai.cn"},
		{"  https://hjb-ai.cn/  ", "https://hjb-ai.cn"},
		{"127.0.0.1:8000", "http://127.0.0.1:8000"},
		{"127.0.0.1:8000/", "http://127.0.0.1:8000"},
		{"HTTP://Host:8000/", "HTTP://Host:8000"},
		{"hjb-ai.cn", "http://hjb-ai.cn"},
		// ws/wss must be preserved as-is: if an http:// prefix were wrongly added, GatewayKey would treat "ws"
		// as the hostname, making the credential index key wrong and the connection bound to fail.
		{"ws://127.0.0.1:8000", "ws://127.0.0.1:8000"},
		{"wss://hjb-ai.cn/", "wss://hjb-ai.cn"},
		{"  ws://h:9//  ", "ws://h:9"},
	}
	for _, c := range cases {
		if got := NormalizeGateway(c.in); got != c.want {
			t.Errorf("NormalizeGateway(%q) = %q, expected %q", c.in, got, c.want)
		}
	}
}

func TestGatewayKeyIgnoresScheme(t *testing.T) {
	// Protocol differences must be treated as the same gateway (deliberate design, consistent with the extension).
	a := GatewayKey("http://h.example:443")
	b := GatewayKey("https://h.example:443")
	if a != b {
		t.Errorf("protocol differences should share the same key: %q != %q", a, b)
	}
	if a != "h.example:443" {
		t.Errorf("GatewayKey result mismatch: %q", a)
	}

	// Default ports when the port is missing.
	if got := GatewayKey("https://h.example"); got != "h.example:443" {
		t.Errorf("https default port should be 443, got %q", got)
	}
	if got := GatewayKey("http://h.example"); got != "h.example:80" {
		t.Errorf("http default port should be 80, got %q", got)
	}
	if got := GatewayKey("h.example:8000"); got != "h.example:8000" {
		t.Errorf("input without a protocol should get http added and take host:port, got %q", got)
	}
	if got := GatewayKey(""); got != "" {
		t.Errorf("empty input should return an empty key, got %q", got)
	}
}

// TestGatewayKeyWebSocketScheme regression test: ws/wss and http/https should be treated as the same gateway,
// and ws→80, wss→443. Before the fix, ws:// got an http:// prefix wrongly added and the key became "ws:80".
func TestGatewayKeyWebSocketScheme(t *testing.T) {
	if got := GatewayKey("ws://h.example:8000"); got != "h.example:8000" {
		t.Errorf("ws with a port should take host:port, got %q", got)
	}
	if got := GatewayKey("wss://h.example:8000"); got != "h.example:8000" {
		t.Errorf("wss with a port should take host:port, got %q", got)
	}
	// Protocol differences (including ws/wss vs http/https) should be treated as the same gateway.
	if a, b := GatewayKey("ws://h.example:443"), GatewayKey("https://h.example:443"); a != b {
		t.Errorf("ws and https with the same port should share the same key: %q != %q", a, b)
	}
	// Default ports when the port is missing.
	if got := GatewayKey("ws://h.example"); got != "h.example:80" {
		t.Errorf("ws default port should be 80, got %q", got)
	}
	if got := GatewayKey("wss://h.example"); got != "h.example:443" {
		t.Errorf("wss default port should be 443, got %q", got)
	}
}

func TestStoreMultiGatewayIsolation(t *testing.T) {
	s := NewStore()
	s.Set("http://127.0.0.1:8000", "tok-local")
	s.Set("https://hjb-ai.cn", "tok-remote")

	if len(s.List()) != 2 {
		t.Fatalf("expected 2 credentials, got %d", len(s.List()))
	}

	local, err := s.Get("http://127.0.0.1:8000")
	if err != nil {
		t.Fatalf("Get local gateway error: %v", err)
	}
	if local.Token != "tok-local" {
		t.Errorf("local gateway token mismatch: %+v", local)
	}

	remote, err := s.Get("https://hjb-ai.cn")
	if err != nil {
		t.Fatalf("Get remote gateway error: %v", err)
	}
	if remote.Token != "tok-remote" {
		t.Errorf("remote gateway token mismatch: %+v", remote)
	}

	// An unauthenticated third gateway should return ErrNoCredentials.
	if _, err := s.Get("http://other:9000"); err != ErrNoCredentials {
		t.Errorf("an unauthenticated gateway should return ErrNoCredentials, got %v", err)
	}
}

func TestStoreSetOverwritesSameGateway(t *testing.T) {
	s := NewStore()
	s.Set("http://127.0.0.1:8000", "old")
	s.Set("https://hjb-ai.cn", "remote")
	// A repeated Set for the same gateway (including protocol differences) should overwrite without affecting other gateways.
	s.Set("https://127.0.0.1:8000", "new")

	if len(s.List()) != 2 {
		t.Fatalf("expected 2 entries after overwrite, got %d", len(s.List()))
	}
	creds, err := s.Get("http://127.0.0.1:8000")
	if err != nil {
		t.Fatalf("Get error: %v", err)
	}
	if creds.Token != "new" {
		t.Errorf("token after overwrite should be new, got %q", creds.Token)
	}
	remote, err := s.Get("https://hjb-ai.cn")
	if err != nil || remote.Token != "remote" {
		t.Errorf("the overwrite should not affect other gateways: %+v err=%v", remote, err)
	}
}

func TestStoreClearSingleGateway(t *testing.T) {
	s := NewStore()
	s.Set("http://127.0.0.1:8000", "a")
	s.Set("https://hjb-ai.cn", "b")

	s.Clear("http://127.0.0.1:8000")

	if s.Has("http://127.0.0.1:8000") {
		t.Error("Has should be false for this gateway after Clear")
	}
	if s.TokenValid("http://127.0.0.1:8000") {
		t.Error("TokenValid should be false for this gateway after Clear")
	}
	if _, err := s.Get("http://127.0.0.1:8000"); err != ErrNoCredentials {
		t.Errorf("Get should return ErrNoCredentials after Clear, got %v", err)
	}
	// Other gateways are not affected.
	if !s.Has("https://hjb-ai.cn") {
		t.Error("clearing one gateway should not affect other gateways")
	}
	if len(s.List()) != 1 {
		t.Errorf("expected 1 entry after Clear, got %d", len(s.List()))
	}
}

func TestStoreClearAll(t *testing.T) {
	s := NewStore()
	s.Set("http://127.0.0.1:8000", "a")
	s.Set("https://hjb-ai.cn", "b")

	s.ClearAll()

	if len(s.List()) != 0 {
		t.Errorf("expected no credentials after ClearAll, got %d", len(s.List()))
	}
	if s.Has("http://127.0.0.1:8000") || s.Has("https://hjb-ai.cn") {
		t.Error("Has should all be false after ClearAll")
	}
	if _, err := s.Get("https://hjb-ai.cn"); err != ErrNoCredentials {
		t.Errorf("Get should return ErrNoCredentials after ClearAll, got %v", err)
	}
}

func TestStoreMarkTokenInvalid(t *testing.T) {
	s := NewStore()
	s.Set("https://hjb-ai.cn", "t")
	s.Set("http://127.0.0.1:8000", "other")

	s.MarkTokenInvalid("https://hjb-ai.cn")

	if !s.Has("https://hjb-ai.cn") {
		t.Error("marking invalid should not clear the credentials")
	}
	if s.TokenValid("https://hjb-ai.cn") {
		t.Error("TokenValid should be false after marking")
	}
	// Only this gateway is affected.
	if !s.TokenValid("http://127.0.0.1:8000") {
		t.Error("marking one gateway should not affect other gateways' TokenValid")
	}
	// Re-Set should restore validity.
	s.Set("https://hjb-ai.cn", "t2")
	if !s.TokenValid("https://hjb-ai.cn") {
		t.Error("TokenValid should be restored to true after re-Set")
	}
}

func TestStoreMarkTokenInvalidWithoutCreds(t *testing.T) {
	s := NewStore()
	s.MarkTokenInvalid("https://hjb-ai.cn") // should not panic
	if s.Has("https://hjb-ai.cn") {
		t.Error("marking without credentials should not create credentials")
	}
	if s.TokenValid("https://hjb-ai.cn") {
		t.Error("TokenValid should be false without credentials")
	}
}

func TestStoreEmptyGatewayNoop(t *testing.T) {
	s := NewStore()
	s.Set("", "t")
	s.Set("   ", "t")
	if len(s.List()) != 0 {
		t.Errorf("an empty gateway should not write credentials, got %d", len(s.List()))
	}
	if s.Has("") || s.TokenValid("") {
		t.Error("Has/TokenValid should be false for an empty gateway")
	}
	s.Clear("") // should not panic
	s.MarkTokenInvalid("")
}

func TestStoreListReturnsCopy(t *testing.T) {
	s := NewStore()
	s.Set("https://hjb-ai.cn", "t")
	list := s.List()
	list[0].Token = "mutated"
	creds, err := s.Get("https://hjb-ai.cn")
	if err != nil {
		t.Fatalf("Get error: %v", err)
	}
	if creds.Token != "t" {
		t.Errorf("List should return copies; the internal data was tampered with: %q", creds.Token)
	}
}

func TestStoreConcurrentAccess(t *testing.T) {
	s := NewStore()
	gateways := []string{
		"http://127.0.0.1:8000",
		"https://hjb-ai.cn",
		"http://other:9000",
	}
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(n int) {
			defer wg.Done()
			g := gateways[n%len(gateways)]
			s.Set(g, "tok")
			_, _ = s.Get(g)
			s.Has(g)
			s.TokenValid(g)
			s.List()
			s.MarkTokenInvalid(g)
			if n%5 == 0 {
				s.Clear(g)
			}
			if n%7 == 0 {
				s.ClearAll()
			}
		}(i)
	}
	wg.Wait()
}

func TestPersistentStoreRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "credentials.json")

	s := NewPersistentStore(path)
	s.Set("https://gw1.example.com", "token-1")
	s.SetWithName("https://gw2.example.com", "token-2", "gw2")
	s.Set("http://127.0.0.1:8000", "token-3")

	// Reload and verify the credentials were restored from persistence.
	loaded := LoadStore(path)
	if !loaded.Has("https://gw1.example.com") {
		t.Error("gw1 credentials were not restored from disk")
	}
	if c, err := loaded.Get("https://gw1.example.com"); err != nil || c.Token != "token-1" {
		t.Errorf("gw1 token restore error: %+v err=%v", c, err)
	}
	if c, err := loaded.Get("https://gw2.example.com"); err != nil || c.Token != "token-2" {
		t.Errorf("gw2 token restore error: %+v err=%v", c, err)
	}
	if c, _ := loaded.Get("https://gw2.example.com"); c.Name != "gw2" {
		t.Errorf("gw2 name restore error: %q", c.Name)
	}
	if c, err := loaded.Get("http://127.0.0.1:8000"); err != nil || c.Token != "token-3" {
		t.Errorf("127.0.0.1 token restore error: %+v err=%v", c, err)
	}
}

func TestPersistentStoreClearSyncsDisk(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "credentials.json")

	s := NewPersistentStore(path)
	s.Set("https://gw1.example.com", "token-1")
	s.Set("https://gw2.example.com", "token-2")

	// Disk sync after clearing a single gateway.
	s.Clear("https://gw1.example.com")
	loaded := LoadStore(path)
	if loaded.Has("https://gw1.example.com") {
		t.Error("gw1 is still kept on disk after Clear")
	}
	if !loaded.Has("https://gw2.example.com") {
		t.Error("Clear mistakenly removed gw2")
	}

	// Disk is empty after ClearAll.
	s.ClearAll()
	loaded2 := LoadStore(path)
	if len(loaded2.List()) != 0 {
		t.Errorf("still %d credentials remain on disk after ClearAll", len(loaded2.List()))
	}
}

func TestLoadStoreMissingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "does-not-exist.json")
	s := LoadStore(path)
	if len(s.List()) != 0 {
		t.Errorf("a missing file should return an empty Store, got %d entries", len(s.List()))
	}
	// And it must not error (a missing file is normal on the daemon's first launch).
	if _, err := os.Stat(path); err == nil {
		t.Error("LoadStore should not create a persistence file for a missing file")
	}
}

func TestLoadStoreInvalidJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "credentials.json")
	if err := os.WriteFile(path, []byte("{not-valid-json"), 0600); err != nil {
		t.Fatal(err)
	}
	s := LoadStore(path)
	if len(s.List()) != 0 {
		t.Errorf("a corrupt file should return an empty Store, got %d entries", len(s.List()))
	}
}
