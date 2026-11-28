//go:build !windows

package selfupdate

// exitForHelperReplacement is an empty implementation on non-Windows platforms.
//
// Why it is needed: the helper replacement path is only really used on Windows (Linux can replace a running
// executable via rename directly, see apply_linux.go; SpawnApplyHelper returns (0, nil) on non-Windows, and the caller
// uses that to know "no helper needed"). This empty implementation lets updater.go call it unconditionally across platforms,
// avoiding platform branches in the upper layer.
func exitForHelperReplacement() {}
