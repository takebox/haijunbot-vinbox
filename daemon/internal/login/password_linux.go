//go:build linux

package login

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

// ReadPassword prints the prompt and reads a line of password, without echoing it back on the terminal.
//
// Implementation: use ioctl(TCGETS/TCSETS) to read and write the terminal termios, clear the ECHO bit and then read;
// restore it immediately with defer when done (including error paths), to avoid leaving the terminal in a no-echo state.
//
// When it is not a terminal (e.g. a pipe or redirection), the ioctl fails and it degrades to a plain read (no hiding),
// enabling scripted use (e.g. echo "$PASS" | haijunbot-daemon login ...).
//
// golang.org/x/term is not introduced: the project constraints forbid third-party dependencies.
func ReadPassword(prompt string) (string, error) {
	fmt.Fprint(os.Stderr, prompt)

	fd := int(os.Stdin.Fd())

	// Try to disable echo; a failure means it is not a terminal, degrade to a plain read.
	oldState, err := disableEcho(fd)
	if err != nil {
		return readLine(os.Stdin)
	}
	// Restore the terminal attributes regardless of what happens afterwards.
	defer restoreEcho(fd, oldState)

	line, err := readLine(os.Stdin)
	// With echo disabled, the Enter pressed by the user does not advance the line; add one here to keep the output tidy.
	fmt.Fprintln(os.Stderr)
	return line, err
}

// readLine reads one line from r, stripping the trailing \n and \r.
func readLine(r *os.File) (string, error) {
	reader := bufio.NewReader(r)
	line, err := reader.ReadString('\n')
	if err != nil && line == "" {
		return "", err
	}
	return strings.TrimRight(line, "\r\n"), nil
}

// disableEcho disables terminal echo and returns the original termios for restoration.
func disableEcho(fd int) (*syscall.Termios, error) {
	var old syscall.Termios
	if err := ioctlTermios(fd, syscall.TCGETS, &old); err != nil {
		return nil, err
	}
	newState := old
	// Clear ECHO (echo) and ECHONL (newline echo).
	newState.Lflag &^= syscall.ECHO | syscall.ECHONL
	if err := ioctlTermios(fd, syscall.TCSETS, &newState); err != nil {
		return nil, err
	}
	return &old, nil
}

// restoreEcho restores a previously saved termios.
func restoreEcho(fd int, state *syscall.Termios) {
	if state == nil {
		return
	}
	_ = ioctlTermios(fd, syscall.TCSETS, state)
}

// ioctlTermios performs a termios-related ioctl on fd.
//
// The syscall package does not directly export a wrapper like IoctlGetTermios (that lives in x/term),
// so the SYS_IOCTL system call is used directly here.
func ioctlTermios(fd int, req uintptr, state *syscall.Termios) error {
	_, _, errno := syscall.Syscall(
		syscall.SYS_IOCTL,
		uintptr(fd),
		req,
		uintptr(unsafe.Pointer(state)),
	)
	if errno != 0 {
		return errno
	}
	return nil
}
