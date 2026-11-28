package capability

// This file provides the gateway list injection point required by the "OCR capability".
//
// Why injection is needed: when ocr.recognize does not explicitly specify a gateway, it must fall back to the "first gateway
// the daemon has authenticated with", but the capability package cannot depend on auth.Store in reverse (which would form a
// capability → auth dependency, and auth is already assembled in main). Therefore, during assembly in main.go, the function
// that "lists authenticated gateways" is injected, and the capability implementation only depends on this function.
//
// When not injected (such as in unit tests or unauthenticated scenarios), the fallback logic returns an empty list, and the
// capability returns a clear error instead of panicking.
import "sync"

// OcrGatewayLister returns the list of currently authenticated gateway addresses (stable order, sorted ascending by address).
type OcrGatewayLister func() []string

var (
	ocrGatewayMu     sync.RWMutex
	ocrGatewayLister OcrGatewayLister
)

// SetOcrGatewayLister injects the function that "lists authenticated gateways" (called by main.go).
//
// Passing nil clears the injection, which is convenient for test isolation.
func SetOcrGatewayLister(lister OcrGatewayLister) {
	ocrGatewayMu.Lock()
	defer ocrGatewayMu.Unlock()
	ocrGatewayLister = lister
}

// ocrListGateways returns the list of authenticated gateways; returns an empty list when not injected.
func ocrListGateways() []string {
	ocrGatewayMu.RLock()
	lister := ocrGatewayLister
	ocrGatewayMu.RUnlock()
	if lister == nil {
		return nil
	}
	return lister()
}
