//go:build !windows

package service

import "syscall"

// detachedProcAttr has no extra requirements on non-Windows platforms.
func detachedProcAttr() *syscall.SysProcAttr {
	return nil
}
