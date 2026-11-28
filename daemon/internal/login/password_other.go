//go:build !linux && !windows

package login

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// ReadPassword prints the prompt and reads a line of password.
//
// This platform (e.g. macOS) has no hidden-input implementation, so the password is echoed normally. To hide it,
// add the platform's termios implementation here (macOS's termios structure differs from Linux's).
func ReadPassword(prompt string) (string, error) {
	fmt.Fprint(os.Stderr, prompt)
	reader := bufio.NewReader(os.Stdin)
	line, err := reader.ReadString('\n')
	if err != nil && line == "" {
		return "", err
	}
	return strings.TrimRight(line, "\r\n"), nil
}
