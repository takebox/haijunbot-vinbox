package capability

// This file provides the in-memory state of the "whether to automatically install/update browser extensions" switch.
//
// Why it is needed: installing/overwriting browser extensions is an operation with side effects (it rewrites the
// extension directory on the user's disk) and should not be performed automatically and unconditionally. After the
// user explicitly turns on the switch in the Web settings UI, the frontend pushes the value to the local daemon along
// with the login state, and the daemon uses it to decide whether to automatically download and overwrite the local
// extension when the gateway's extension version changes.
//
// Why it is placed in the capability package:
//   - It is in the same package as browser_ext.go, so maybeAutoSyncBrowserExt in cmd/haijunbot-daemon/main.go
//     can read it directly without adding another layer across packages;
//   - It stays consistent with the "package-level variable + sync.RWMutex + exported getter/setter" pattern of
//     browser_ext_cred.go, keeping the style uniform.
//
// Why it is in-memory only and not persisted: the user explicitly requires that this switch "only be stored in browser storage" (localStorage) and not
// persisted by the daemon. Therefore only the in-memory state is kept here: after the daemon restarts it returns to the default value false (off by default), waiting for the frontend to push again — which is exactly the safe direction (never auto-install unless a push is received).
import "sync"

var (
	// autoInstallBrowserExtMu protects the switch below; reads are far more frequent than writes, so RWMutex is used.
	// Concurrency sources: the WS read loop (hello_ack callback → maybeAutoSyncBrowserExt read)
	// and the HTTP handler (/api/auth, /api/settings writes).
	autoInstallBrowserExtMu sync.RWMutex
	// autoInstallBrowserExt is the current value of the switch, default false (off).
	autoInstallBrowserExt bool
)

// SetAutoInstallBrowserExt sets the "automatically install/update browser extensions" switch.
//
// Called by localapi when a push for /api/settings or /api/auth is received.
//
// Returns "whether this call caused a false → true transition" (i.e. the switch moved from off to on).
// The caller uses it to decide whether to immediately perform an extra extension sync check: the daemon only checks the
// switch once upon receiving hello_ack, while the frontend's switch push is usually later than hello_ack (the daemon
// connects to the gateway first after startup, and the frontend pushes settings afterwards), so without the extra check
// the user, despite having turned the switch on, would see "off, skipping auto-sync", and that state would persist until the next reconnect.
func SetAutoInstallBrowserExt(enabled bool) bool {
	autoInstallBrowserExtMu.Lock()
	defer autoInstallBrowserExtMu.Unlock()
	transitioned := enabled && !autoInstallBrowserExt
	autoInstallBrowserExt = enabled
	return transitioned
}

// AutoInstallBrowserExt returns the current value of the switch; default false (off).
//
// Called by maybeAutoSyncBrowserExt in cmd/haijunbot-daemon/main.go before deciding whether to automatically
// sync extensions.
func AutoInstallBrowserExt() bool {
	autoInstallBrowserExtMu.RLock()
	defer autoInstallBrowserExtMu.RUnlock()
	return autoInstallBrowserExt
}
