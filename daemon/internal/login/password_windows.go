//go:build windows

package login

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

// Win32 entry points needed for hidden password input.
//
// Load them dynamically with syscall.NewLazyDLL, avoiding the golang.org/x/sys dependency
// (consistent with the approach in internal/service/console_windows.go).
var (
	kernel32Login           = syscall.NewLazyDLL("kernel32.dll")
	procGetStdHandleLogin   = kernel32Login.NewProc("GetStdHandle")
	procGetConsoleModeLogin = kernel32Login.NewProc("GetConsoleMode")
	procSetConsoleModeLogin = kernel32Login.NewProc("SetConsoleMode")
)

const (
	// stdInputHandle corresponds to STD_INPUT_HANDLE.
	stdInputHandle = ^uintptr(10) + 1 // unsigned representation of -10
	// enableEchoInput corresponds to ENABLE_ECHO_INPUT.
	enableEchoInput = 0x0004
)

// ReadPassword prints the prompt and reads a line of password, without echoing it back on the console.
//
// Implementation: read the current mode with GetConsoleMode, clear ENABLE_ECHO_INPUT and then read,
// restoring the original mode immediately when done (including error paths).
//
// When it is not a console (e.g. a pipe or redirection), GetConsoleMode fails and it degrades to a plain read.
func ReadPassword(prompt string) (string, error) {
	fmt.Fprint(os.Stderr, prompt)

	handle, _, _ := procGetStdHandleLogin.Call(stdInputHandle)
	oldMode, ok := getConsoleMode(handle)
	if !ok {
		// Not a console, degrade to a plain read.
		return readLine(os.Stdin)
	}
	// Clear the echo bit; continue even on failure (worst case the password stays visible).
	_, _, _ = procSetConsoleModeLogin.Call(handle, uintptr(oldMode&^enableEchoInput))
	defer func() {
		_, _, _ = procSetConsoleModeLogin.Call(handle, uintptr(oldMode))
	}()

	line, err := readLine(os.Stdin)
	fmt.Fprintln(os.Stderr)
	return line, err
}

// readLine reads one line from r, stripping the trailing \r\n.
func readLine(r *os.File) (string, error) {
	reader := bufio.NewReader(r)
	line, err := reader.ReadString('\n')
	if err != nil && line == "" {
		return "", err
	}
	return strings.TrimRight(line, "\r\n"), nil
}

// getConsoleMode reads the console mode; returns ok=false when it is not a console.
func getConsoleMode(handle uintptr) (uint32, bool) {
	var mode uint32
	ret, _, _ := procGetConsoleModeLogin.Call(
		handle,
		uintptr(unsafe.Pointer(&mode)),
	)
	if ret == 0 {
		return 0, false
	}
	return mode, true
}
