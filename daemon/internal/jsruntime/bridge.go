package jsruntime

import (
	"fmt"
	"strings"
	"time"

	"github.com/dop251/goja"

	"haijunbot-daemon/internal/capability"
)

// InstallBridge exposes the capability capabilities as a global haijunbot object and injects it into the runtime.
//
// Injected objects:
//   - haijunbot.cap(name, params): calls a capability by name, returns {success, data, error}
//   - haijunbot.caps.<domain>.<action>(params): nested namespace, throws a JS exception on failure
//   - haijunbot.listCaps(): lists the capabilities available on the current platform
//   - haijunbot.sleep(ms): a Go-side blocking delay (replacing the setTimeout macro task)
//
// A nil registry is treated as an empty registry (scripts run but any capability call fails).
func InstallBridge(r *Runtime, registry *capability.Registry) error {
	vm := r.vm
	if registry == nil {
		registry = capability.NewRegistry()
	}

	// Build the haijunbot object.
	haijunbot := vm.NewObject()
	if err := vm.Set("haijunbot", haijunbot); err != nil {
		return fmt.Errorf("failed to inject the haijunbot object: %w", err)
	}

	// haijunbot.cap(name, params)
	if err := haijunbot.Set("cap", vm.ToValue(func(call goja.FunctionCall) goja.Value {
		name := call.Argument(0).String()
		params := toParams(call.Argument(1))
		res := registry.Execute(name, params)
		return vm.ToValue(map[string]any{
			"success": res.Success,
			"data":    res.Data,
			"error":   res.Error,
		})
	})); err != nil {
		return fmt.Errorf("failed to inject haijunbot.cap: %w", err)
	}

	// haijunbot.listCaps()
	if err := haijunbot.Set("listCaps", vm.ToValue(func(call goja.FunctionCall) goja.Value {
		caps := registry.ListForPlatform(capability.Current())
		out := make([]map[string]any, 0, len(caps))
		for _, c := range caps {
			out = append(out, map[string]any{
				"name":        c.Name,
				"description": c.Description,
				"parameters":  c.Parameters,
				"platform":    string(c.Platform),
			})
		}
		return vm.ToValue(out)
	})); err != nil {
		return fmt.Errorf("failed to inject haijunbot.listCaps: %w", err)
	}

	// haijunbot.sleep(ms)
	if err := haijunbot.Set("sleep", vm.ToValue(func(call goja.FunctionCall) goja.Value {
		ms := toInt64(call.Argument(0))
		if ms > 0 {
			time.Sleep(time.Duration(ms) * time.Millisecond)
		}
		return goja.Undefined()
	})); err != nil {
		return fmt.Errorf("failed to inject haijunbot.sleep: %w", err)
	}

	// The haijunbot.caps nested namespace.
	capsObj, err := buildCapsNamespace(vm, registry)
	if err != nil {
		return err
	}
	if err := haijunbot.Set("caps", capsObj); err != nil {
		return fmt.Errorf("failed to inject haijunbot.caps: %w", err)
	}

	return nil
}

// buildCapsNamespace walks the registry, splitting capability names by '.' into nested objects, with the leaf nodes
// being callable functions.
//
// For example linux.fs.read → haijunbot.caps.linux.fs.read({path}).
// A leaf call throws a JS exception on failure (catchable with try/catch); on success it returns data.
func buildCapsNamespace(vm *goja.Runtime, registry *capability.Registry) (*goja.Object, error) {
	root := vm.NewObject()
	caps := registry.ListForPlatform(capability.Current())

	for _, c := range caps {
		parts := strings.Split(c.Name, ".")
		cur := root
		// Create nested objects level by level; the leaf (last segment) binds the call function.
		for i, part := range parts {
			if part == "" {
				continue
			}
			last := i == len(parts)-1
			if last {
				// Leaf node: bind the capability call function.
				name := c.Name
				if err := cur.Set(part, vm.ToValue(func(call goja.FunctionCall) goja.Value {
					return invokeCap(vm, registry, name, call)
				})); err != nil {
					return nil, fmt.Errorf("failed to bind capability %s: %w", name, err)
				}
			} else {
				// Intermediate node: get or create the child object.
				child := cur.Get(part)
				if child == nil || goja.IsUndefined(child) || goja.IsNull(child) {
					child = vm.NewObject()
					if err := cur.Set(part, child); err != nil {
						return nil, fmt.Errorf("failed to create the namespace %s: %w", part, err)
					}
				}
				cur = child.ToObject(vm)
			}
		}
	}
	return root, nil
}

// invokeCap executes one capability call (for a haijunbot.caps leaf node).
//
// On success it returns data; on failure it throws a JS exception (the Error carries the capability error message).
func invokeCap(vm *goja.Runtime, registry *capability.Registry, name string, call goja.FunctionCall) goja.Value {
	params := toParams(call.Argument(0))
	res := registry.Execute(name, params)
	if !res.Success {
		panic(vm.NewGoError(fmt.Errorf("capability %s call failed: %s", name, res.Error)))
	}
	return vm.ToValue(res.Data)
}

// InstallScriptArgs injects the script arguments into the haijunbot.args object.
//
// Must be called after InstallBridge (it depends on the already created haijunbot object). When args is nil an empty
// object is injected and scripts can still safely access haijunbot.args.
func InstallScriptArgs(r *Runtime, args map[string]string) error {
	vm := r.vm
	haijunbotVal := vm.Get("haijunbot")
	if haijunbotVal == nil || goja.IsUndefined(haijunbotVal) || goja.IsNull(haijunbotVal) {
		return fmt.Errorf("the haijunbot object does not exist, call InstallBridge first")
	}
	haijunbot := haijunbotVal.ToObject(vm)
	argsObj := vm.NewObject()
	for k, v := range args {
		if err := argsObj.Set(k, v); err != nil {
			return fmt.Errorf("failed to inject argument %s: %w", k, err)
		}
	}
	if err := haijunbot.Set("args", argsObj); err != nil {
		return fmt.Errorf("failed to inject haijunbot.args: %w", err)
	}
	return nil
}

// toParams converts a goja argument into map[string]any capability parameters.
//
// undefined/null returns an empty map; an object exports its properties;
// other types (non-objects) return an empty map (the capability caller handles missing parameters itself).
func toParams(v goja.Value) map[string]any {
	if v == nil || goja.IsUndefined(v) || goja.IsNull(v) {
		return map[string]any{}
	}
	exported := v.Export()
	if m, ok := exported.(map[string]any); ok {
		return m
	}
	// A non-object argument (e.g. a string/number) cannot be a capability parameter object; return an empty map.
	return map[string]any{}
}

// toInt64 safely converts a goja value to int64; invalid values return 0.
func toInt64(v goja.Value) int64 {
	if v == nil || goja.IsUndefined(v) || goja.IsNull(v) {
		return 0
	}
	return v.ToInteger()
}