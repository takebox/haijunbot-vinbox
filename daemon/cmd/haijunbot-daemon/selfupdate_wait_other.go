//go:build !windows

package main

import "time"

// waitForReplaceTarget requires no waiting on non-Windows platforms: Linux allows replacing a running
// executable directly, and this helper subcommand is not triggered on those platforms either. An empty implementation is kept here for cross-platform compilation.
func waitForReplaceTarget(_ string, _ time.Duration) error { return nil }
