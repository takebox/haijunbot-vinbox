// Package capability provides the daemon's capability registry.
//
// The design references the Tool / ToolRegistry model of src/haijunbot/haijunbot_tools/registry.py on the Python side:
// each capability has a name, description, parameter schema and handler function; the registry is responsible for registering, looking up, listing by platform, and executing.
// Platform-specific capabilities are assembled at NewRegistry time via build tags (see registry_linux.go / registry_windows.go / registry_other.go),
// avoiding references to platform-specific types in files without build tags.
//
// This round only implements the framework and registers no actual capabilities.
package capability

import (
	"fmt"
	"sort"
	"sync"
)

// Platform represents the platform a capability applies to.
type Platform string

// Platform constants. PlatformAny represents a cross-platform capability.
const (
	PlatformWindows Platform = "windows"
	PlatformLinux   Platform = "linux"
	PlatformDarwin  Platform = "darwin"
	PlatformAny     Platform = "any"
)

// Capability describes a capability that can be called by the gateway.
type Capability struct {
	// Name is the unique capability name; the "domain.action" form (such as "fs.read") is recommended.
	Name string `json:"name"`
	// Description is the capability description, for the model to understand its purpose.
	Description string `json:"description"`
	// Parameters is the parameter JSON schema description; may be empty.
	Parameters map[string]any `json:"parameters,omitempty"`
	// Platform is the platform the capability applies to; when empty it is treated as PlatformAny.
	Platform Platform `json:"platform"`
	// Handler is the capability implementation; params are the call parameters, and it returns a result and an error.
	Handler func(params map[string]any) (any, error) `json:"-"`
}

// Result is the result of a single capability call.
type Result struct {
	// Success indicates whether the call succeeded.
	Success bool `json:"success"`
	// Data is the return data on success.
	Data any `json:"data,omitempty"`
	// Error is the failure reason.
	Error string `json:"error,omitempty"`
}

// Registry is the capability registry; it is concurrency-safe.
type Registry struct {
	mu   sync.RWMutex
	caps map[string]*Capability
}

// NewRegistry creates the registry and assembles the capabilities of the current platform.
func NewRegistry() *Registry {
	r := &Registry{caps: make(map[string]*Capability)}
	registerPlatformCapabilities(r)
	return r
}

// Register registers a capability.
//
// An empty name or a duplicate registration returns an error (it does not silently overwrite).
func (r *Registry) Register(cap Capability) error {
	if cap.Name == "" {
		return fmt.Errorf("capability name is empty")
	}
	if cap.Platform == "" {
		cap.Platform = PlatformAny
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, exists := r.caps[cap.Name]; exists {
		return fmt.Errorf("capability already registered: %s", cap.Name)
	}
	c := cap
	r.caps[cap.Name] = &c
	return nil
}

// Get looks up a capability by name.
func (r *Registry) Get(name string) (*Capability, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	c, ok := r.caps[name]
	return c, ok
}

// List returns copies of all capabilities, sorted ascending by name.
func (r *Registry) List() []Capability {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Capability, 0, len(r.caps))
	for _, c := range r.caps {
		out = append(out, *c)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

// ListForPlatform returns the capabilities applicable to the specified platform (including PlatformAny capabilities), sorted ascending by name.
func (r *Registry) ListForPlatform(p Platform) []Capability {
	all := r.List()
	out := make([]Capability, 0, len(all))
	for _, c := range all {
		if Matches(c.Platform, p) {
			out = append(out, c)
		}
	}
	return out
}

// Execute executes a capability by name.
//
// An unregistered capability returns Success=false with Error containing "unknown capability: <name>";
// a nil Handler returns a clear error; a Handler panic is recovered and turned into an error.
func (r *Registry) Execute(name string, params map[string]any) (res Result) {
	cap, ok := r.Get(name)
	if !ok {
		return Result{Success: false, Error: fmt.Sprintf("unknown capability: %s", name)}
	}
	if cap.Handler == nil {
		return Result{Success: false, Error: fmt.Sprintf("capability not implemented: %s", name)}
	}
	defer func() {
		if rec := recover(); rec != nil {
			res = Result{Success: false, Error: fmt.Sprintf("capability %s panicked: %v", name, rec)}
		}
	}()
	data, err := cap.Handler(params)
	if err != nil {
		return Result{Success: false, Error: err.Error()}
	}
	return Result{Success: true, Data: data}
}
