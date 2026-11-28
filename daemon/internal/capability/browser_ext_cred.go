package capability

// This file provides the credential injection point required by "browser extension sync".
//
// Why injection is needed: the capability Handler signature is func(map[string]any)(any,error), so it cannot
// directly obtain the daemon's credential store (auth.Store lives in internal/auth, and the capability package
// should not depend on it in reverse). Therefore, during assembly in main.go, the function that "fetches the Token by gateway"
// is injected, and the capability implementation only depends on this function.
//
// When not injected (such as in unit tests or unauthenticated scenarios), the sync capability returns a clear error instead of panicking.

import "sync"

// BrowserExtCredentialProvider returns an available Token by gateway; ok=false when there is no credential.
type BrowserExtCredentialProvider func(gateway string) (token string, ok bool)

var (
	browserExtCredMu       sync.RWMutex
	browserExtCredProvider BrowserExtCredentialProvider
)

// SetBrowserExtCredentialProvider injects the credential provider (called by main.go).
//
// Passing nil clears the injection, which is convenient for test isolation.
func SetBrowserExtCredentialProvider(provider BrowserExtCredentialProvider) {
	browserExtCredMu.Lock()
	defer browserExtCredMu.Unlock()
	browserExtCredProvider = provider
}

// browserExtToken fetches the Token by gateway; returns ok=false when not injected or there is no credential.
func browserExtToken(gateway string) (string, bool) {
	browserExtCredMu.RLock()
	provider := browserExtCredProvider
	browserExtCredMu.RUnlock()
	if provider == nil {
		return "", false
	}
	return provider(gateway)
}

// BrowserExtToken is the exported version of browserExtToken, used by main.go to get the Token during auto-sync.
func BrowserExtToken(gateway string) (string, bool) {
	return browserExtToken(gateway)
}
