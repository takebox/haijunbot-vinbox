//go:build !linux && !windows

package selfupdate

import "fmt"

// restartService does not restart the service on other platforms (e.g. darwin).
//
// This project only guarantees Windows and Linux; this implementation exists only so the code compiles on darwin.
func restartService() error {
	return fmt.Errorf("automatic service restart is not supported on the current platform")
}
