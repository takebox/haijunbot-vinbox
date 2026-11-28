package jsruntime

import (
	"strings"
	"testing"
)

// TestRunScriptBasic verifies basic JS expression execution.
func TestRunScriptBasic(t *testing.T) {
	r := New()
	val, err := r.RunScript("1 + 1")
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != int64(2) {
		t.Fatalf("expected 2, got %v (%T)", val, val)
	}
}

// TestRunScriptString verifies a string result.
func TestRunScriptString(t *testing.T) {
	r := New()
	val, err := r.RunScript(`"hello " + "world"`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != "hello world" {
		t.Fatalf("expected hello world, got %v", val)
	}
}

// TestRunScriptFunction verifies function definition and invocation.
func TestRunScriptFunction(t *testing.T) {
	r := New()
	val, err := r.RunScript(`(function(a, b) { return a * b; })(6, 7)`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != int64(42) {
		t.Fatalf("expected 42, got %v", val)
	}
}

// TestRunScriptObject verifies an object literal is returned.
func TestRunScriptObject(t *testing.T) {
	r := New()
	val, err := r.RunScript(`({name: "demo", count: 3})`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	obj, ok := val.(map[string]any)
	if !ok {
		t.Fatalf("expected map[string]any, got %T", val)
	}
	if obj["name"] != "demo" || obj["count"] != int64(3) {
		t.Fatalf("object content mismatch: %v", obj)
	}
}

// TestRunScriptAsync verifies async/await and top-level Promise handling (microtask).
func TestRunScriptAsync(t *testing.T) {
	r := New()
	src := `
		(async function() {
			const x = await Promise.resolve(10);
			return x * 2;
		})();
	`
	val, err := r.RunScript(src)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != int64(20) {
		t.Fatalf("expected 20, got %v", val)
	}
}

// TestRunScriptSyntaxError verifies a syntax error is converted into a readable error.
func TestRunScriptSyntaxError(t *testing.T) {
	r := New()
	_, err := r.RunScript("function ( {")
	if err == nil {
		t.Fatal("expected a syntax error, but no error was returned")
	}
	if !strings.Contains(err.Error(), "SyntaxError") {
		t.Fatalf("the error message should contain SyntaxError, got: %v", err)
	}
}

// TestRunScriptRuntimeError verifies a runtime error (uncaught exception).
func TestRunScriptRuntimeError(t *testing.T) {
	r := New()
	_, err := r.RunScript(`throw new Error("boom")`)
	if err == nil {
		t.Fatal("expected a runtime error, but no error was returned")
	}
	if !strings.Contains(err.Error(), "boom") {
		t.Fatalf("the error message should contain boom, got: %v", err)
	}
}

// TestRunScriptRejectedPromise verifies a Promise reject is converted into an error.
func TestRunScriptRejectedPromise(t *testing.T) {
	r := New()
	_, err := r.RunScript(`Promise.reject(new Error("rejected!"))`)
	if err == nil {
		t.Fatal("expected a Promise reject error, but no error was returned")
	}
	if !strings.Contains(err.Error(), "rejected") {
		t.Fatalf("the error message should contain rejected, got: %v", err)
	}
}

// TestRunScriptFile verifies compiling with errors located by the file name.
func TestRunScriptFile(t *testing.T) {
	r := New()
	_, err := r.RunScriptFile("myscript.js", `var x = 1; x();`)
	if err == nil {
		t.Fatal("expected an error, but no error was returned")
	}
	if !strings.Contains(err.Error(), "myscript.js") {
		t.Fatalf("the error message should contain the file name myscript.js, got: %v", err)
	}
}

// TestSet verifies Set injects a global variable.
func TestSet(t *testing.T) {
	r := New()
	if err := r.Set("greeting", "hi"); err != nil {
		t.Fatalf("Set failed: %v", err)
	}
	val, err := r.RunScript(`greeting + " there"`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if val != "hi there" {
		t.Fatalf("expected hi there, got %v", val)
	}
}

// TestPrintOutput verifies print outputs to the stdout callback.
func TestPrintOutput(t *testing.T) {
	r := New()
	var stdout, stderr strings.Builder
	r.SetOutput(func(s string) { stdout.WriteString(s) }, func(s string) { stderr.WriteString(s) })

	_, err := r.RunScript(`print("hello", "world")`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if stdout.String() != "hello world\n" {
		t.Fatalf("stdout expected 'hello world\\n', got: %q", stdout.String())
	}
	if stderr.Len() != 0 {
		t.Fatalf("stderr should be empty, got: %q", stderr.String())
	}
}

// TestConsoleOutput verifies console.log/error output to stdout/stderr respectively.
func TestConsoleOutput(t *testing.T) {
	r := New()
	var stdout, stderr strings.Builder
	r.SetOutput(func(s string) { stdout.WriteString(s) }, func(s string) { stderr.WriteString(s) })

	_, err := r.RunScript(`
console.log("log", 42);
console.info("info");
console.error("boom");
console.warn("careful");
`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	if stdout.String() != "log 42\ninfo\n" {
		t.Fatalf("stdout expected 'log 42\\ninfo\\n', got: %q", stdout.String())
	}
	if stderr.String() != "boom\ncareful\n" {
		t.Fatalf("stderr expected 'boom\\ncareful\\n', got: %q", stderr.String())
	}
}

// TestConsoleObjectStringify verifies objects/arrays are serialized in the output.
func TestConsoleObjectStringify(t *testing.T) {
	r := New()
	var stdout strings.Builder
	r.SetOutput(func(s string) { stdout.WriteString(s) }, nil)

	_, err := r.RunScript(`
console.log({a: 1, b: "x"});
console.log([1, 2, 3]);
console.log(null, undefined);
`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
	want := `{"a":1,"b":"x"}
[1,2,3]
null null
`
	if stdout.String() != want {
		t.Fatalf("output mismatch, expected:\n%q\nactual:\n%q", want, stdout.String())
	}
}

// TestPrintNilSink verifies print does not panic when no output callback is set.
func TestPrintNilSink(t *testing.T) {
	r := New()
	_, err := r.RunScript(`print("no sink"); console.log("ok")`)
	if err != nil {
		t.Fatalf("execution failed: %v", err)
	}
}