//go:build !windows

package selfupdate

// SpawnApplyHelper is an empty implementation on non-Windows platforms.
//
// Why it is needed: Linux can replace a running executable directly via rename (see apply_linux.go),
// so no helper child process is needed. This empty implementation lets cmd/haijunbot-daemon call it unconditionally across platforms,
// avoiding platform branches in the upper layer.
//
// The return value is always (0, nil): the caller uses this to know "no helper needed".
func SpawnApplyHelper(_, _, _ string, _ bool) (int, error) {
	return 0, nil
}
