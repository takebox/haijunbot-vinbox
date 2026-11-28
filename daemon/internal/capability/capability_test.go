package capability

import (
	"errors"
	"testing"
)

// TestRegister covers the three cases of registration: success, empty name, and duplicate registration.
func TestRegister(t *testing.T) {
	r := NewRegistry()

	if err := r.Register(Capability{Name: "demo.echo", Description: "echo"}); err != nil {
		t.Fatalf("registration failed: %v", err)
	}
	if err := r.Register(Capability{Name: ""}); err == nil {
		t.Fatal("an empty name should return an error")
	}
	if err := r.Register(Capability{Name: "demo.echo"}); err == nil {
		t.Fatal("duplicate registration should return an error")
	}

	// When the platform is empty, it defaults to PlatformAny.
	c, ok := r.Get("demo.echo")
	if !ok {
		t.Fatal("demo.echo should be found")
	}
	if c.Platform != PlatformAny {
		t.Fatalf("the default platform should be any, actual %q", c.Platform)
	}
}

// TestGet covers a hit and a miss.
func TestGet(t *testing.T) {
	r := NewRegistry()
	_ = r.Register(Capability{Name: "a.one"})

	if _, ok := r.Get("a.one"); !ok {
		t.Fatal("a.one should be found")
	}
	if _, ok := r.Get("a.none"); ok {
		t.Fatal("a.none should not be found")
	}
}

// TestListSorted verifies that List returns a copy sorted in ascending order by name.
func TestListSorted(t *testing.T) {
	r := NewRegistry()
	for _, n := range []string{"c", "a", "b"} {
		if err := r.Register(Capability{Name: n}); err != nil {
			t.Fatalf("registering %s failed: %v", n, err)
		}
	}

	// NewRegistry assembles the platform capabilities; here only the relative order of the three registered here is checked.
	list := r.List()
	got := make([]string, 0, 3)
	for _, c := range list {
		if c.Name == "a" || c.Name == "b" || c.Name == "c" {
			got = append(got, c.Name)
		}
	}
	if len(got) != 3 {
		t.Fatalf("expected 3 items, actual %d", len(got))
	}
	want := []string{"a", "b", "c"}
	for i, name := range got {
		if name != want[i] {
			t.Fatalf("item %d should be %s, actual %s", i, want[i], name)
		}
	}

	// A copy should be returned; modifications do not affect the registry.
	list[0].Name = "mutated"
	if _, ok := r.Get("a"); !ok {
		t.Fatal("List should return a copy")
	}
}

// TestListForPlatform verifies platform filtering: both PlatformAny and platform-specific appear, while other platforms are filtered.
func TestListForPlatform(t *testing.T) {
	r := NewRegistry()
	_ = r.Register(Capability{Name: "any.cap", Platform: PlatformAny})
	_ = r.Register(Capability{Name: "linux.cap", Platform: PlatformLinux})
	_ = r.Register(Capability{Name: "windows.cap", Platform: PlatformWindows})

	linux := r.ListForPlatform(PlatformLinux)
	// NewRegistry assembles the platform capabilities; here only the three registered here are checked.
	gotLinux := namesOf(linux)
	if !containsAll(gotLinux, "any.cap", "linux.cap") {
		t.Fatalf("the Linux platform should contain any.cap and linux.cap, actual %v", gotLinux)
	}
	if contains(gotLinux, "windows.cap") {
		t.Fatalf("the Linux platform should not contain windows.cap, actual %v", gotLinux)
	}

	windows := r.ListForPlatform(PlatformWindows)
	gotWindows := namesOf(windows)
	if !containsAll(gotWindows, "any.cap", "windows.cap") {
		t.Fatalf("the Windows platform should contain any.cap and windows.cap, actual %v", gotWindows)
	}
	for _, c := range windows {
		if c.Name == "linux.cap" {
			t.Fatal("the Windows platform should not contain linux.cap")
		}
	}
}

// namesOf extracts the list of capability names, for easier assertions.
func namesOf(caps []Capability) []string {
	out := make([]string, 0, len(caps))
	for _, c := range caps {
		out = append(out, c.Name)
	}
	return out
}

// contains determines whether the name list contains the specified name.
func contains(names []string, target string) bool {
	for _, n := range names {
		if n == target {
			return true
		}
	}
	return false
}

// containsAll determines whether the name list contains all the specified names.
func containsAll(names []string, targets ...string) bool {
	for _, t := range targets {
		if !contains(names, t) {
			return false
		}
	}
	return true
}

// TestExecute covers four cases: success, not registered, Handler returning an error, and Handler panicking.
func TestExecute(t *testing.T) {
	r := NewRegistry()
	_ = r.Register(Capability{
		Name: "demo.echo",
		Handler: func(params map[string]any) (any, error) {
			return params["text"], nil
		},
	})
	_ = r.Register(Capability{
		Name: "demo.fail",
		Handler: func(map[string]any) (any, error) {
			return nil, errors.New("boom")
		},
	})
	_ = r.Register(Capability{
		Name: "demo.panic",
		Handler: func(map[string]any) (any, error) {
			panic("kaboom")
		},
	})
	_ = r.Register(Capability{Name: "demo.nil"})

	// success
	res := r.Execute("demo.echo", map[string]any{"text": "hi"})
	if !res.Success || res.Data != "hi" {
		t.Fatalf("expected success and returning hi, actual %+v", res)
	}

	// not registered
	res = r.Execute("demo.missing", nil)
	if res.Success || res.Error != "unknown capability: demo.missing" {
		t.Fatalf("an unregistered capability should return a clear error, actual %+v", res)
	}

	// Handler returns an error
	res = r.Execute("demo.fail", nil)
	if res.Success || res.Error != "boom" {
		t.Fatalf("expected the handler error to be passed through, actual %+v", res)
	}

	// Handler panic is recovered
	res = r.Execute("demo.panic", nil)
	if res.Success || res.Error == "" {
		t.Fatalf("panic should be caught and converted to an error, actual %+v", res)
	}

	// Handler is nil
	res = r.Execute("demo.nil", nil)
	if res.Success || res.Error == "" {
		t.Fatalf("a nil handler should return a clear error, actual %+v", res)
	}
}

// TestPlatformHelpers verifies Current and Matches.
func TestPlatformHelpers(t *testing.T) {
	if Current() == "" {
		t.Fatal("Current should not be empty")
	}
	if !Matches(PlatformAny, PlatformLinux) {
		t.Fatal("any should match any platform")
	}
	if !Matches(PlatformLinux, PlatformLinux) {
		t.Fatal("the same platform should match")
	}
	if Matches(PlatformWindows, PlatformLinux) {
		t.Fatal("different platforms should not match")
	}
}

// TestMultiRegistryIsolation verifies that multiple registry instances do not affect each other (corresponding to the scenario of
// multiple backend services connecting to the same gateway: each daemon holds its own registry, with no global shared state).
func TestMultiRegistryIsolation(t *testing.T) {
	r1 := NewRegistry()
	r2 := NewRegistry()

	if err := r1.Register(Capability{Name: "only.in.r1"}); err != nil {
		t.Fatalf("r1 registration failed: %v", err)
	}
	if _, ok := r2.Get("only.in.r1"); ok {
		t.Fatal("r2 should not see r1's capability; registries must be isolated")
	}
	// Both instances assembled their own platform capabilities, but the capability newly added to r1 should not appear in r2.
	for _, c := range r2.List() {
		if c.Name == "only.in.r1" {
			t.Fatal("r2 should not contain the capability registered in r1")
		}
	}
}
