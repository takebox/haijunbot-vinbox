package jsruntime

import (
	"strings"
	"testing"

	"github.com/dop251/goja"

	"haijunbot-daemon/internal/capability"
)

// newTestRegistry creates a registry with fake capabilities registered, used for bridge tests.
func newTestRegistry() *capability.Registry {
	reg := capability.NewRegistry()
	_ = reg.Register(capability.Capability{
		Name:        "demo.echo",
		Description: "echo the params",
		Platform:    capability.PlatformAny,
		Handler: func(params map[string]any) (any, error) {
			return params, nil
		},
	})
	_ = reg.Register(capability.Capability{
		Name:        "demo.add",
		Description: "add two numbers",
		Platform:    capability.PlatformAny,
		Handler: func(params map[string]any) (any, error) {
			a, _ := params["a"].(int64)
			b, _ := params["b"].(int64)
			return a + b, nil
		},
	})
	_ = reg.Register(capability.Capability{
		Name:        "demo.fail",
		Description: "always fails",
		Platform:    capability.PlatformAny,
		Handler: func(params map[string]any) (any, error) {
			return nil, errDemoFail
		},
	})
	_ = reg.Register(capability.Capability{
		Name:        "demo.nested.deep",
		Description: "nested capability",
		Platform:    capability.PlatformAny,
		Handler: func(params map[string]any) (any, error) {
			return "deep-result", nil
		},
	})
	return reg
}

var errDemoFail = &demoFailError{}

type demoFailError struct{}

func (e *demoFailError) Error() string { return "demo failed intentionally" }

// runWithBridge creates a runtime, injects the bridge, and runs the script.
func runWithBridge(t *testing.T, reg *capability.Registry, src string) (any, error) {
	t.Helper()
	r := New()
	if err := InstallBridge(r, reg); err != nil {
		t.Fatalf("InstallBridge failed: %v", err)
	}
	return r.RunScript(src)
}

// TestCapSuccess verifies haijunbot.cap calls a successful capability.
func TestCapSuccess(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `haijunbot.cap("demo.add", {a: 3, b: 4})`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	obj, ok := val.(map[string]any)
	if !ok {
		t.Fatalf("expected a map, got %T", val)
	}
	if obj["success"] != true {
		t.Fatalf("expected success=true, got %v", obj)
	}
	if obj["data"] != int64(7) {
		t.Fatalf("expected data=7, got %v", obj)
	}
}

// TestCapUnknown verifies haijunbot.cap returns an error for an unregistered capability.
func TestCapUnknown(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `haijunbot.cap("no.such.cap")`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	obj, ok := val.(map[string]any)
	if !ok {
		t.Fatalf("expected a map, got %T", val)
	}
	if obj["success"] != false {
		t.Fatalf("expected success=false, got %v", obj)
	}
	if obj["error"] == "" {
		t.Fatal("expected a non-empty error")
	}
}

// TestCapParams verifies parameter passing (string/number/bool/nested object).
func TestCapParams(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg,
		`haijunbot.cap("demo.echo", {s: "hi", n: 42, b: true, nested: {x: 1, y: "z"}})`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	obj := val.(map[string]any)
	data := obj["data"].(map[string]any)
	if data["s"] != "hi" || data["n"] != int64(42) || data["b"] != true {
		t.Fatalf("parameter passing mismatch: %v", data)
	}
	nested, ok := data["nested"].(map[string]any)
	if !ok || nested["x"] != int64(1) || nested["y"] != "z" {
		t.Fatalf("nested parameters mismatch: %v", data["nested"])
	}
}

// TestCapsNested verifies calling the haijunbot.caps nested namespace.
func TestCapsNested(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `haijunbot.caps.demo.add({a: 10, b: 32})`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != int64(42) {
		t.Fatalf("expected 42, got %v", val)
	}
}

// TestCapsDeep verifies a multi-level nested capability.
func TestCapsDeep(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `haijunbot.caps.demo.nested.deep({})`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != "deep-result" {
		t.Fatalf("expected deep-result, got %v", val)
	}
}

// TestCapsFailThrows verifies a failed haijunbot.caps call throws a JS exception.
func TestCapsFailThrows(t *testing.T) {
	reg := newTestRegistry()
	_, err := runWithBridge(t, reg, `haijunbot.caps.demo.fail({})`)
	if err == nil {
		t.Fatal("expected the capability failure to throw an exception, but no error was returned")
	}
	if err.Error() == "" {
		t.Fatal("the error message should not be empty")
	}
}

// TestCapsFailCatchable verifies a haijunbot.caps failure can be caught with try/catch.
func TestCapsFailCatchable(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `
		try {
			haijunbot.caps.demo.fail({});
			"no-throw";
		} catch (e) {
			"caught:" + e.message;
		}
	`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != "caught:capability demo.fail call failed: demo failed intentionally" {
		t.Fatalf("expected the caught exception info, got %v", val)
	}
}

// TestListCaps verifies haijunbot.listCaps lists the capabilities.
func TestListCaps(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `haijunbot.listCaps().length`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	// At least the 4 demo.* capabilities.
	if val.(int64) < 4 {
		t.Fatalf("expected at least 4 capabilities, got %v", val)
	}
}

// TestListCapsContains verifies listCaps returns the capability names (including the fake capabilities).
func TestListCapsContains(t *testing.T) {
	reg := newTestRegistry()
	val, err := runWithBridge(t, reg, `
		haijunbot.listCaps().map(c => c.name).join(",")
	`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	names, ok := val.(string)
	if !ok {
		t.Fatalf("expected a string, got %T", val)
	}
	for _, want := range []string{"demo.add", "demo.echo", "demo.fail", "demo.nested.deep"} {
		if !strings.Contains(names, want) {
			t.Fatalf("the capability list should contain %s, actual: %s", want, names)
		}
	}
}

// TestSleep verifies haijunbot.sleep does not error.
func TestSleep(t *testing.T) {
	reg := newTestRegistry()
	_, err := runWithBridge(t, reg, `haijunbot.sleep(1); "done"`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
}

// TestBridgeNilRegistry verifies a nil registry keeps the bridge usable but capability calls fail.
func TestBridgeNilRegistry(t *testing.T) {
	r := New()
	if err := InstallBridge(r, nil); err != nil {
		t.Fatalf("InstallBridge(nil) failed: %v", err)
	}
	val, err := r.RunScript(`haijunbot.cap("anything").success`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != false {
		t.Fatalf("expected success=false, got %v", val)
	}
}

// TestGojaValueExport verifies goja value export types (auxiliary confirmation of parameter conversion).
func TestGojaValueExport(t *testing.T) {
	vm := goja.New()
	v, _ := vm.RunString(`({a: 1, b: "x"})`)
	m := v.Export().(map[string]any)
	if m["a"] != int64(1) || m["b"] != "x" {
		t.Fatalf("export mismatch: %v", m)
	}
}

// TestInstallScriptArgs verifies haijunbot.args injects the script arguments.
func TestInstallScriptArgs(t *testing.T) {
	r := New()
	reg := newTestRegistry()
	if err := InstallBridge(r, reg); err != nil {
		t.Fatalf("InstallBridge failed: %v", err)
	}
	if err := InstallScriptArgs(r, map[string]string{"path": "/tmp", "mode": "fast"}); err != nil {
		t.Fatalf("InstallScriptArgs failed: %v", err)
	}

	val, err := r.RunScript(`haijunbot.args.path + ":" + haijunbot.args.mode`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != "/tmp:fast" {
		t.Fatalf("expected '/tmp:fast', got %v", val)
	}
}

// TestInstallScriptArgsBeforeBridge verifies InstallScriptArgs errors when InstallBridge has not been called.
func TestInstallScriptArgsBeforeBridge(t *testing.T) {
	r := New()
	if err := InstallScriptArgs(r, map[string]string{"a": "1"}); err == nil {
		t.Fatalf("expected an error (the haijunbot object does not exist), got no error")
	}
}