//go:build windows

package main

import (
	"fmt"
	"os"
	"time"
)

// waitForReplaceTarget polls on Windows, waiting until the target executable is no longer in use (the parent process has exited).
//
// Approach: repeatedly try to open the target file with "exclusive write"; success means the old process has released the handle.
// If it still has not succeeded when timeout is reached, return an error (the caller still attempts the replacement, which may just fail).
func waitForReplaceTarget(target string, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		f, err := os.OpenFile(target, os.O_WRONLY, 0)
		if err == nil {
			_ = f.Close()
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("timed out waiting for %s to be writable: %w", target, err)
		}
		time.Sleep(500 * time.Millisecond)
	}
}
