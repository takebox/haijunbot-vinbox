package capability

// This file implements the registration and handling logic of the "browser extension automatic download and update" capability (shared across platforms).
//
// The platform difference is only in the Platform field (windows / linux); the parameters and return structure are identical,
// so the registration and handling logic is placed here, and registry_windows.go / registry_linux.go call
// registerBrowserExt(reg, platform) per platform.

import (
	"fmt"
	"strings"
)

// registerBrowserExt registers the browser extension capability for the specified platform.
func registerBrowserExt(reg *Registry, platform Platform) {
	_ = reg.Register(Capability{
		Name: "browser.ext.status",
		Description: "Queries the local copy status of the browser extension on this machine: local directory, local version, and the gateway's latest version. " +
			"Used to decide whether browser.ext.sync needs to be run. When not installed locally, local_version is an empty string.",
		Platform: platform,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"gateway": map[string]any{
					"type": "string",
					"description": "Optional. Specifies the gateway address; when provided and the gateway has an available Token, " +
						"the gateway-side latest version (latest_version) is also returned.",
				},
			},
		},
		Handler: handleBrowserExtStatus,
	})

	_ = reg.Register(Capability{
		Name: "browser.ext.sync",
		Description: "Downloads the browser extension zip package from the gateway and extracts/overwrites it into the local directory (~/.haijunbot/browser_extension). " +
			"The browser is not restarted: after the write, the user must manually click \"refresh\" once in chrome://extensions for the new version to take effect.",
		Platform: platform,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"gateway": map[string]any{
					"type": "string",
					"description": "Gateway address (such as http://127.0.0.1:8000). " +
						"When omitted, the first gateway the daemon has authenticated with is used.",
				},
			},
		},
		Handler: handleBrowserExtSync,
	})
}

// handleBrowserExtStatus is the implementation of browser.ext.status.
func handleBrowserExtStatus(params map[string]any) (any, error) {
	dir, err := BrowserExtDir()
	if err != nil {
		return nil, err
	}
	localVersion := LocalBrowserExtVersion()

	result := map[string]any{
		"ext_dir":       dir,
		"local_version": localVersion,
		"installed":     localVersion != "",
	}

	gateway, err := browserExtOptionalString(params, "gateway")
	if err != nil {
		return nil, err
	}
	if gateway != "" {
		result["gateway"] = gateway
		if token, ok := browserExtToken(gateway); ok && token != "" {
			result["token_available"] = true
			if latest, err := fetchRemoteExtVersion(gateway, token); err == nil {
				result["latest_version"] = latest
				result["needs_update"] = latest != "" && latest != localVersion
			} else {
				result["version_error"] = err.Error()
			}
		} else {
			result["token_available"] = false
		}
	}
	return result, nil
}

// handleBrowserExtSync is the implementation of browser.ext.sync.
func handleBrowserExtSync(params map[string]any) (any, error) {
	gateway, err := browserExtOptionalString(params, "gateway")
	if err != nil {
		return nil, err
	}
	gateway = strings.TrimSpace(gateway)
	if gateway == "" {
		return nil, fmt.Errorf("parameter gateway must be specified (browser extension sync needs to know which gateway to download from)")
	}

	token, ok := browserExtToken(gateway)
	if !ok || token == "" {
		return nil, fmt.Errorf("gateway %s has no available credentials; please log in on the web page and push the login information first", gateway)
	}

	dir, err := BrowserExtDir()
	if err != nil {
		return nil, err
	}
	before := LocalBrowserExtVersion()

	count, version, err := SyncBrowserExt(gateway, token)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"gateway":           gateway,
		"ext_dir":           dir,
		"file_count":        count,
		"version":           version,
		"previous":          before,
		"updated":           version != before,
		"need_reload":       true,
		"reload_hint":       "Open chrome://extensions in the browser, find HaijunBot Browser Bridge, and click \"refresh\"; if it is not installed, click \"load unpacked extension\" and select that directory.",
		"browser_restarted": false,
	}, nil
}

// browserExtOptionalString reads an optional string parameter; it returns an empty string when missing or nil.
//
// It does not reuse the platform-side (linux/windows) optionalString: those functions carry build tags and do not participate in compilation
// on platforms such as darwin, whereas this file is shared across platforms.
func browserExtOptionalString(params map[string]any, key string) (string, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return "", nil
	}
	s, ok := v.(string)
	if !ok {
		return "", fmt.Errorf("parameter %s must be a string, actual %T", key, v)
	}
	return s, nil
}

// fetchRemoteExtVersion queries the gateway-side latest extension version.
//
// It reuses the /api/browser-ext/version interface; it is only called by the status capability, and a failure is not fatal.
func fetchRemoteExtVersion(gateway, token string) (string, error) {
	body, err := httpGetJSON(gateway, "/api/browser-ext/version", token)
	if err != nil {
		return "", err
	}
	version, _ := body["latest_version"].(string)
	return strings.TrimSpace(version), nil
}
