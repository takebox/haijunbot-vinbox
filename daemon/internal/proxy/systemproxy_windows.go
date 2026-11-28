//go:build windows

package proxy

import (
	"net/http"
	"net/url"
	"strings"
	"sync"
	"syscall"
	"unsafe"
)

// Registry path and value names (Windows "Internet Options -> Connections -> LAN Settings").
const (
	regPath           = `Software\Microsoft\Windows\CurrentVersion\Internet Settings`
	regValueProxyEnab = "ProxyEnable"
	regValueProxySrv  = "ProxyServer"
	regValueProxySkip = "ProxyOverride"
)

// Registry API in advapi32. Loaded dynamically with LazyDLL to avoid depending on golang.org/x/sys.
var (
	advapi32          = syscall.NewLazyDLL("advapi32.dll")
	procRegOpenKeyEx  = advapi32.NewProc("RegOpenKeyExW")
	procRegQueryValue = advapi32.NewProc("RegQueryValueExW")
	procRegCloseKey   = advapi32.NewProc("RegCloseKey")
)

// Cache the system proxy configuration: reading the registry has syscall overhead while proxy
// settings rarely change, so cache one copy in the process. The cached value is the "raw string",
// independent of the request.
var (
	sysProxyOnce sync.Once
	sysProxySrv  string
	sysProxySkip string
)

// systemProxyForRequest decides whether a request goes through the proxy based on the Windows
// system proxy configuration. Returns nil (no proxy) when the system proxy is not enabled.
func systemProxyForRequest(req *http.Request) (*url.URL, error) {
	sysProxyOnce.Do(loadSystemProxy)

	if sysProxySrv == "" {
		return nil, nil
	}
	// ProxyOverride is equivalent to NO_PROXY: matched hosts connect directly.
	if matchProxyOverride(req.URL.Hostname(), sysProxySkip) {
		return nil, nil
	}
	raw := pickProxyForScheme(sysProxySrv, req.URL.Scheme)
	if raw == "" {
		return nil, nil
	}
	return parseProxyURL(raw)
}

// loadSystemProxy reads the system proxy configuration from the registry and writes it to the cache.
// Any read failure is treated as "no proxy configured" and returns no error (to avoid affecting normal direct connections).
func loadSystemProxy() {
	enable, ok := readRegDWORD(regValueProxyEnab)
	if !ok || enable == 0 {
		return
	}
	srv, ok := readRegString(regValueProxySrv)
	if !ok {
		return
	}
	sysProxySrv = strings.TrimSpace(srv)
	if skip, ok := readRegString(regValueProxySkip); ok {
		sysProxySkip = skip
	}
}

// pickProxyForScheme / parseProxyURL / matchProxyOverride are in parse.go (cross-platform).

// readRegDWORD reads the specified DWORD value. Returns (0, false) on read failure.
func readRegDWORD(name string) (uint32, bool) {
	data, typ, ok := readRegValue(name)
	if !ok || typ != syscall.REG_DWORD || len(data) < 4 {
		return 0, false
	}
	return *(*uint32)(unsafe.Pointer(&data[0])), true
}

// readRegString reads the specified REG_SZ value. Returns ("", false) on read failure.
func readRegString(name string) (string, bool) {
	data, typ, ok := readRegValue(name)
	if !ok || (typ != syscall.REG_SZ && typ != syscall.REG_EXPAND_SZ) {
		return "", false
	}
	return syscall.UTF16ToString(bytesToUTF16(data)), true
}

// readRegValue opens the fixed path under HKCU and reads one value, returning the raw bytes and type.
func readRegValue(name string) ([]byte, uint32, bool) {
	pathPtr, err := syscall.UTF16PtrFromString(regPath)
	if err != nil {
		return nil, 0, false
	}
	var hKey syscall.Handle
	r, _, _ := procRegOpenKeyEx.Call(
		uintptr(syscall.HKEY_CURRENT_USER),
		uintptr(unsafe.Pointer(pathPtr)),
		0,
		uintptr(syscall.KEY_READ),
		uintptr(unsafe.Pointer(&hKey)),
	)
	if r != 0 { // ERROR_SUCCESS == 0
		return nil, 0, false
	}
	defer procRegCloseKey.Call(uintptr(hKey))

	namePtr, err := syscall.UTF16PtrFromString(name)
	if err != nil {
		return nil, 0, false
	}
	var (
		typ    uint32
		size   uint32
		data   []byte
		regErr uintptr
	)
	// Query the size first, then allocate the buffer accordingly. Leave 1 extra wchar of headroom to prevent race truncation.
	for i := 0; i < 2; i++ {
		size = uint32(len(data))
		regErr, _, _ = procRegQueryValue.Call(
			uintptr(hKey),
			uintptr(unsafe.Pointer(namePtr)),
			0,
			uintptr(unsafe.Pointer(&typ)),
			uintptr(unsafe.Pointer(bufPtr(data))),
			uintptr(unsafe.Pointer(&size)),
		)
		if regErr == 0 { // ERROR_SUCCESS
			break
		}
		if regErr != uintptr(syscall.ERROR_MORE_DATA) {
			return nil, 0, false
		}
		data = make([]byte, size+2)
	}
	if len(data) == 0 {
		return nil, 0, false
	}
	return data[:size], typ, true
}

// bufPtr returns the pointer to the first element of the slice; returns nil for an empty slice (NULL for the corresponding API).
func bufPtr(b []byte) unsafe.Pointer {
	if len(b) == 0 {
		return nil
	}
	return unsafe.Pointer(&b[0])
}

// bytesToUTF16 converts a UTF-16LE byte sequence into []uint16 (for use by UTF16ToString).
func bytesToUTF16(b []byte) []uint16 {
	n := len(b) / 2
	out := make([]uint16, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, *(*uint16)(unsafe.Pointer(&b[i*2])))
	}
	return out
}
