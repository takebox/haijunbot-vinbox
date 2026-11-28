// Package jsruntime provides a goja-based JS runtime wrapper for haijunbot-daemon to execute
// user-written JS automation scripts. Scripts call capability capabilities through the global haijunbot object.
//
// goja is a pure-Go ES5.1+ engine (zero cgo), consistent with the daemon's existing "pure syscall + zero cgo"
// design philosophy. This package only wraps the runtime itself and the capability bridge; it does not depend on external state.
package jsruntime

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/dop251/goja"
)

// Runtime wraps a goja runtime.
//
// Each Runtime instance corresponds to an independent JS virtual machine; scripts do not share state with each other.
// One Runtime can run multiple scripts (sharing the global object), but usually one Runtime runs one script.
type Runtime struct {
	vm *goja.Runtime

	// stdout/stderr are the callbacks for script output (print/console.log etc.); output is dropped when nil.
	// Callers can inject them via SetOutput to relay script output back to the CLI or collect it into a buffer.
	stdout func(string)
	stderr func(string)
}

// New creates and returns a new JS runtime.
//
// By default it injects output functions like print / console.log, forwarded through the stdout/stderr callbacks
// (dropped by default; settable via SetOutput). A haijunbot placeholder object is also injected (filled by InstallBridge).
func New() *Runtime {
	vm := goja.New()
	r := &Runtime{vm: vm}
	r.installConsole()
	return r
}

// SetOutput sets the callbacks for script output (print/console.log etc.).
//
// stdout receives standard output, stderr receives error/warning output. Passing nil drops the corresponding output.
func (r *Runtime) SetOutput(stdout, stderr func(string)) {
	r.stdout = stdout
	r.stderr = stderr
}

// installConsole injects global output functions like print / console.log.
//
// goja core does not include console/print; browser semantics are implemented here: multiple arguments separated by
// spaces, all written to stdout (console.error/warn write to stderr).
func (r *Runtime) installConsole() {
	vm := r.vm

	// Generic output function: converts the arguments to strings and joins them.
	makePrinter := func(sink func(string)) func(call goja.FunctionCall) goja.Value {
		return func(call goja.FunctionCall) goja.Value {
			parts := make([]string, 0, len(call.Arguments))
			for _, a := range call.Arguments {
				parts = append(parts, stringify(a))
			}
			if sink != nil {
				sink(strings.Join(parts, " ") + "\n")
			}
			return goja.Undefined()
		}
	}

	// print(...) → stdout
	_ = vm.Set("print", vm.ToValue(makePrinter(func(s string) { r.writeStdout(s) })))

	// console.log/info/debug → stdout; console.warn/error → stderr
	console := vm.NewObject()
	_ = console.Set("log", vm.ToValue(makePrinter(func(s string) { r.writeStdout(s) })))
	_ = console.Set("info", vm.ToValue(makePrinter(func(s string) { r.writeStdout(s) })))
	_ = console.Set("debug", vm.ToValue(makePrinter(func(s string) { r.writeStdout(s) })))
	_ = console.Set("warn", vm.ToValue(makePrinter(func(s string) { r.writeStderr(s) })))
	_ = console.Set("error", vm.ToValue(makePrinter(func(s string) { r.writeStderr(s) })))
	_ = vm.Set("console", console)
}

// writeStdout / writeStderr forward one line of output to the corresponding callback (dropped when nil).
func (r *Runtime) writeStdout(s string) {
	if r.stdout != nil {
		r.stdout(s)
	}
}

func (r *Runtime) writeStderr(s string) {
	if r.stderr != nil {
		r.stderr(s)
	}
}

// stringify converts a goja value to a string (for print/console output).
//
// Objects/arrays are JSON serialized (approximating browser console behavior); null/undefined output the literals.
func stringify(v goja.Value) string {
	if v == nil {
		return "null"
	}
	exported := v.Export()
	switch t := exported.(type) {
	case nil:
		return "null"
	case string:
		return t
	case bool:
		if t {
			return "true"
		}
		return "false"
	case float64:
		// Integers drop the fractional part, consistent with JS number printing.
		if t == float64(int64(t)) {
			return fmt.Sprintf("%d", int64(t))
		}
		return fmt.Sprintf("%v", t)
	default:
		// Objects/arrays etc.: try JSON serialization, fall back to String() on failure.
		if b, err := json.Marshal(exported); err == nil {
			return string(b)
		}
		return v.String()
	}
}

// VM returns the underlying goja runtime, for extensions like the capability bridge.
func (r *Runtime) VM() *goja.Runtime {
	return r.vm
}

// Set binds a Go value to the specified name on the global object.
//
// For injecting globals like the haijunbot object, args, etc.
func (r *Runtime) Set(name string, value any) error {
	if err := r.vm.Set(name, value); err != nil {
		return fmt.Errorf("failed to set the global %s: %w", name, err)
	}
	return nil
}

// RunScript executes a piece of JS source and returns its completion value (as a Go value).
//
// A Promise returned at the script top level is handled: Fulfilled returns the result, Rejected returns an error,
// Pending returns an error note (macro tasks like setTimeout need an event loop, not supported in the first version;
// use the haijunbot.sleep() capability for delays). Syntax errors and runtime errors are returned as *Error.
func (r *Runtime) RunScript(source string) (any, error) {
	value, err := r.vm.RunString(source)
	if err != nil {
		return nil, wrapError(err)
	}
	return r.exportValue(value)
}

// RunScriptFile reads the file content and executes it (equivalent to RunScript, but errors are located by file name).
func (r *Runtime) RunScriptFile(name, source string) (any, error) {
	program, err := goja.Compile(name, source, false)
	if err != nil {
		return nil, wrapError(err)
	}
	value, err := r.vm.RunProgram(program)
	if err != nil {
		return nil, wrapError(err)
	}
	return r.exportValue(value)
}

// exportValue converts a goja value to a Go value; a Promise is handled by its final state.
func (r *Runtime) exportValue(value goja.Value) (any, error) {
	if p, ok := value.Export().(*goja.Promise); ok {
		switch p.State() {
		case goja.PromiseStateFulfilled:
			return p.Result().Export(), nil
		case goja.PromiseStateRejected:
			return nil, &Error{Message: fmt.Sprintf("Promise rejected: %s", p.Result().String())}
		default: // Pending
			return nil, &Error{Message: "the script returned an unfinished Promise (including macro tasks such as setTimeout). " +
				"Please use the haijunbot.sleep() capability for delays, or ensure the script resolves before synchronous completion."}
		}
	}
	return value.Export(), nil
}

// wrapError converts an error thrown by goja into an *Error with readable information.
//
// goja.Exception carries the JS-side stack (file/line number); it is extracted here uniformly for convenient CLI output.
func wrapError(err error) error {
	if ex, ok := err.(*goja.Exception); ok {
		return &Error{
			Message: ex.String(),
			Stack:   formatStack(ex.Stack()),
		}
	}
	return &Error{Message: err.Error()}
}

// formatStack converts goja's stack frame list into readable multi-line text.
func formatStack(frames []goja.StackFrame) string {
	if len(frames) == 0 {
		return ""
	}
	var b strings.Builder
	for _, f := range frames {
		pos := f.Position()
		b.WriteString(fmt.Sprintf("  at %s (%s:%d:%d)\n", f.FuncName(), f.SrcName(), pos.Line, pos.Column))
	}
	return strings.TrimSuffix(b.String(), "\n")
}

// Error is the unified representation of a JS script execution error.
type Error struct {
	// Message is a readable error message (including the JS-side exception text).
	Message string
	// Stack is the JS-side stack info (including the file/line number), may be empty.
	Stack string
}

func (e *Error) Error() string {
	if e.Stack != "" {
		return fmt.Sprintf("%s\n%s", e.Message, e.Stack)
	}
	return e.Message
}