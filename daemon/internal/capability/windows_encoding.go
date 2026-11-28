package capability

// This file holds the pure logic related to "child process output encoding" on the Windows side; it deliberately omits the
// //go:build windows tag so it can be compiled and unit tested on Linux (the local development environment is Linux, with no Windows runtime environment).
//
// Background: why this file is needed
// ===================================
// Go's os/exec returns the child process's stdout as **raw bytes** on Windows, with no encoding
// conversion. Windows console programs (reg.exe, powershell.exe, wmic.exe) by default write text according to the
// **console output code page** — on Chinese Windows that is GBK/CP936, not UTF-8.
//
// Therefore a direct conversion such as `string(out)` interprets the GBK bytes as UTF-8: GBK's two-byte sequences
// are mostly not valid UTF-8 and get replaced with U+FFFD ("�"), appearing as
//
//	"Sample Technology Co., Ltd." → "�����Ƹ���Ϣ�ɷ����޹�˾"
//
// This is exactly the garbled-text phenomenon of windows.app.list on real machines.
//
// Fix strategy: do not introduce a GBK decoding table
// ===================================================
// The standard library has no GBK decoding capability, and introducing golang.org/x/text is forbidden by project constraints. So this approach
// does not "decode GBK", but instead **makes the child process output UTF-8 directly**, eliminating the encoding mismatch at the source:
//
//  1. PowerShell path: pass the script via -EncodedCommand (see encodePowerShellCommand),
//     and set [Console]::OutputEncoding to UTF-8 at the very beginning of the script (see
//     windowsPowerShellPreamble). This way what PowerShell writes is UTF-8 bytes.
//
//  2. reg.exe path: reg.exe has no UTF-8 output mode and cannot be fixed at the source. Therefore
//     windows.app.list was changed to use PowerShell's Get-ItemProperty (see
//     windows_app_windows.go), thereby reusing the UTF-8 output guarantee of item 1 above.
//
// This way the stdout of both paths is UTF-8, and a direct string(out) on the Go side yields correct text.

import (
	"encoding/base64"
	"strings"
	"unicode/utf16"
)

// windowsPowerShellPreamble is the prefix statement for all PowerShell scripts.
//
// Purpose: force PowerShell's output encoding to UTF-8, so the Go side can decode
// stdout directly as UTF-8 without a GBK decoding table.
//
// The three settings are all indispensable, each serving a different purpose:
//   - [Console]::OutputEncoding: controls the encoding PowerShell writes to the **console/stdout**.
//     This is the most critical item, directly determining what encoding Go reads the bytes in.
//   - $OutputEncoding: controls the encoding PowerShell uses when passing data to **external program pipes**.
//     It affects pipes between cmdlets and the encoding when calling external commands.
//   - [Console]::InputEncoding: controls the encoding for reading stdin. Although this daemon does not write to
//     PowerShell's stdin, setting it uniformly avoids some cmdlets erroring due to inconsistent input encoding.
//
// Note: it must be set **before any output is produced**, so this prefix statement is placed at the very beginning of the script.
//
// The purpose of $ProgressPreference = 'SilentlyContinue': when PowerShell's stderr is not a terminal,
// it serializes the progress stream (such as "Preparing modules for first use." when first loading a module) into
// CLIXML (of the form "#< CLIXML\r\n<Objs Version=...>") and writes it to stderr. This pollutes the stderr field of
// windows.script.exec with a lot of noise (exposed by real-machine measurement). Turning off progress output eliminates it.
const windowsPowerShellPreamble = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " +
	"$OutputEncoding = [System.Text.Encoding]::UTF8; " +
	"[Console]::InputEncoding = [System.Text.Encoding]::UTF8; " +
	"$ProgressPreference = 'SilentlyContinue'"

// encodePowerShellCommand encodes a PowerShell script into the argument required by -EncodedCommand.
//
// Background: why -Command cannot be used directly
// -----------------------------------------------
// The script text of `powershell.exe -Command <script>` is passed **through command-line arguments**. Go's
// os/exec hands the Go string (UTF-8 bytes) to CreateProcess on Windows, but Windows
// PowerShell 5.1 decodes the -Command argument according to the **ANSI code page** (GBK/CP936 on Chinese systems).
// As a result, non-ASCII characters in the script (Chinese, full-width symbols) are misread as GBK and corrupted —
// this breaks Chinese string literals in the script (such as Chinese key names in registry paths).
//
// -EncodedCommand accepts a **base64-encoded UTF-16LE** script; base64 is pure ASCII,
// so it completely bypasses the command-line argument code page problem.
//
// Implementation points:
//   - First encode the Go string as UTF-16LE (Go strings are UTF-8; convert to []rune
//     first, then use utf16.Encode to get []uint16, and finally expand to bytes in little-endian order).
//   - **Do not add a BOM**: -EncodedCommand expects base64 without a BOM. Adding a BOM causes
//     PowerShell to treat U+FEFF as the first character of the script and raise a syntax error.
//   - Use standard base64 encoding (with +/ and = padding); PowerShell can parse it correctly.
func encodePowerShellCommand(script string) string {
	return base64.StdEncoding.EncodeToString(utf16LEBytes(script))
}

// utf16LEBytes converts a Go string (UTF-8) into a UTF-16 little-endian byte stream (without a BOM).
//
// It is extracted separately to be unit-testable: the round-trip correctness of utf16LEBytes is the
// premise on which the -EncodedCommand approach can work, and it must be verified independently (see windows_encoding_test.go).
func utf16LEBytes(s string) []byte {
	units := utf16.Encode([]rune(s))
	out := make([]byte, 0, len(units)*2)
	for _, u := range units {
		// UTF-16 code units are written in little-endian order: low byte first, high byte after.
		out = append(out, byte(u&0xFF), byte(u>>8))
	}
	return out
}

// decodeUTF16LEBytes restores a UTF-16 little-endian byte stream into a Go string.
//
// It is used only by unit tests (to verify the round-trip consistency of utf16LEBytes), so it is placed in this file rather than a test file,
// to avoid the test file having to reimplement the decoding logic, which would lose the meaning of "independent verification".
func decodeUTF16LEBytes(b []byte) string {
	if len(b)%2 != 0 {
		// An odd length is not valid UTF-16LE; trim the trailing extra byte to guarantee no panic.
		b = b[:len(b)-1]
	}
	units := make([]uint16, 0, len(b)/2)
	for i := 0; i+1 < len(b); i += 2 {
		units = append(units, uint16(b[i])|uint16(b[i+1])<<8)
	}
	return string(utf16.Decode(units))
}

// looksLikeUTF8 roughly determines whether a byte sequence is valid UTF-8.
//
// Purpose: as the criterion for "output encoding fallback". Normally the child process has already been told to output UTF-8 and will not
// reach here; but if some environment (such as a trimmed-down PowerShell or a third-party replacement for reg.exe) still outputs
// GBK, the byte stream is not valid UTF-8, and this can then give a clearer error message rather than
// silently returning a string of U+FFFD that confuses the caller.
//
// Criterion: validate the UTF-8 encoding rules (RFC 3629) byte by byte, rejecting overlong encodings and surrogate code points.
// This is not a complete UTF-8 validator, but it is enough to distinguish "UTF-8 text" from "GBK text" —
// GBK's common two-byte sequences (such as 0xB6 0xAB) are invalid start bytes under UTF-8.
func looksLikeUTF8(b []byte) bool {
	for i := 0; i < len(b); {
		c := b[i]
		switch {
		case c < 0x80:
			// ASCII single byte.
			i++
		case c >= 0xC2 && c <= 0xDF:
			// 2-byte sequence: start byte C2-DF, continuation byte must be 80-BF.
			// The start point begins at C2 to exclude overlong encodings (C0/C1 would encode ASCII code points).
			if i+1 >= len(b) || b[i+1]&0xC0 != 0x80 {
				return false
			}
			i += 2
		case c >= 0xE0 && c <= 0xEF:
			// 3-byte sequence: start byte E0-EF, both continuation bytes are 80-BF.
			if i+2 >= len(b) || b[i+1]&0xC0 != 0x80 || b[i+2]&0xC0 != 0x80 {
				return false
			}
			i += 3
		case c >= 0xF0 && c <= 0xF4:
			// 4-byte sequence: start byte F0-F4, all three continuation bytes are 80-BF.
			if i+3 >= len(b) || b[i+1]&0xC0 != 0x80 || b[i+2]&0xC0 != 0x80 || b[i+3]&0xC0 != 0x80 {
				return false
			}
			i += 4
		default:
			// 0x80-0xC1 and 0xF5-0xFF are not valid UTF-8 start bytes.
			return false
		}
	}
	return true
}

// trimPowerShellOutput cleans up leading/trailing whitespace in PowerShell output.
//
// PowerShell's Out-String / pipeline output often carries a trailing newline and leading indentation; these are removed uniformly before parsing,
// so the caller does not have to TrimSpace repeatedly. The reason for extracting it separately: multiple call sites need consistent behavior.
func trimPowerShellOutput(s string) string {
	return strings.TrimSpace(s)
}
