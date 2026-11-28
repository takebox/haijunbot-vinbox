package capability

import "runtime"

// Current returns the current running platform; returns PlatformAny for unknown platforms.
func Current() Platform {
	switch runtime.GOOS {
	case "windows":
		return PlatformWindows
	case "linux":
		return PlatformLinux
	case "darwin":
		return PlatformDarwin
	default:
		return PlatformAny
	}
}

// Matches reports whether a capability's declared platform applies to the current platform.
//
// A capability declared as PlatformAny applies to all platforms.
func Matches(capPlatform, current Platform) bool {
	return capPlatform == PlatformAny || capPlatform == current
}
