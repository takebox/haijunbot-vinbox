package capability

// This file unit-tests the pure logic in windows_encoding.go.
//
// These tests have **no build tag**, so they can run on Linux directly — the local dev environment is Linux,
// with no Windows runtime; this is the only way to verify the correctness of -EncodedCommand encoding.

import (
	"encoding/base64"
	"strings"
	"testing"
	"unicode/utf16"
)

// TestUTF16LEBytesRoundTrip verifies the round-trip consistency of UTF-16LE encoding.
//
// This is the premise for the -EncodedCommand approach to work: if the round trip were lossy, the script PowerShell receives
// would be corrupted, and non-ASCII content such as Chinese key names would all fail.
func TestUTF16LEBytesRoundTrip(t *testing.T) {
	cases := []struct {
		name string
		in   string
	}{
		{"empty string", ""},
		{"pure ASCII", "Get-Clipboard -Raw"},
		{"non-ASCII", "Société Générale"},
		{"mixed non-ASCII and ASCII", "$k='HKLM:\\SOFTWARE\\café'; Get-ItemProperty $k"},
		{"emoji (surrogate pair)", "screenshot done ✅ 🎉"},
		{"full-width symbols", "（test）【important】、。；"},
		{"newline and tab", "line1\nline2\ttabbed\r\n"},
		{"Japanese Korean", "こんにちは 안녕하세요"},
		{"single quote and dollar sign", "Set-Clipboard -Value 'it''s $HOME'"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			encoded := utf16LEBytes(tc.in)
			got := decodeUTF16LEBytes(encoded)
			if got != tc.in {
				t.Errorf("round-trip mismatch:\n  input %q\n  got %q", tc.in, got)
			}
		})
	}
}

// TestUTF16LEBytesIsLittleEndian verifies the byte order is indeed little-endian.
//
// Big-endian would silently produce wrong results (the script PowerShell receives becomes garbled), so the byte order must be
// explicitly pinned in the unit test, rather than only verifying "round-trip consistency" — because the round trip uses the same byte-order assumption,
// and a big-endian implementation could also round-trip successfully on its own.
func TestUTF16LEBytesIsLittleEndian(t *testing.T) {
	// The UTF-16 code unit of 'A' is 0x0041: little-endian should be [0x41, 0x00].
	got := utf16LEBytes("A")
	want := []byte{0x41, 0x00}
	if len(got) != 2 || got[0] != want[0] || got[1] != want[1] {
		t.Errorf("byte order error: utf16LEBytes(\"A\") = %v, want %v (little-endian)", got, want)
	}

	// The UTF-16 code unit of 'é' is 0x00E9: little-endian should be [0xE9, 0x00].
	got = utf16LEBytes("é")
	want = []byte{0xE9, 0x00}
	if len(got) != 2 || got[0] != want[0] || got[1] != want[1] {
		t.Errorf("byte order error: utf16LEBytes(\"é\") = %v, want %v (little-endian)", got, want)
	}
}

// TestUTF16LEBytesNoBOM verifies that the encoding result contains no BOM.
//
// If a BOM (0xFF 0xFE) were added, PowerShell would treat U+FEFF as the first character of the script,
// causing an "unrecognized token" syntax error. This is a common pitfall of -EncodedCommand and must be pinned down.
func TestUTF16LEBytesNoBOM(t *testing.T) {
	got := utf16LEBytes("Get-Date")
	if len(got) >= 2 && got[0] == 0xFF && got[1] == 0xFE {
		t.Errorf("encoding result contains a UTF-16LE BOM (0xFF 0xFE), which causes a PowerShell syntax error: %v", got)
	}
	// It also should not contain a UTF-8 BOM or other leading marker.
	if len(got) >= 3 && got[0] == 0xEF && got[1] == 0xBB && got[2] == 0xBF {
		t.Errorf("encoding result contains a UTF-8 BOM, which causes a PowerShell syntax error: %v", got)
	}
}

// TestEncodePowerShellCommandIsValidBase64 verifies the output is valid base64 and can be decoded back to the original.
//
// PowerShell's -EncodedCommand requires the argument to be base64; if the encoding result contains non-base64 characters
// (such as returning raw bytes directly), PowerShell reports "the parameter format is incorrect".
func TestEncodePowerShellCommandIsValidBase64(t *testing.T) {
	script := "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion'"

	encoded := encodePowerShellCommand(script)

	// Must be valid base64 (only A-Za-z0-9+/=).
	if strings.ContainsAny(encoded, " \t\n\r") {
		t.Errorf("encoding result contains whitespace, not a valid base64 argument: %q", encoded)
	}
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		t.Fatalf("encoding result is not valid base64: %v (value %q)", err, encoded)
	}

	// The decoded bytes must be UTF-16LE and be able to restore the original.
	if got := decodeUTF16LEBytes(raw); got != script {
		t.Errorf("original mismatch after base64 decoding:\n  want %q\n  got %q", script, got)
	}
}

// TestEncodePowerShellCommandWithChinese verifies that a script containing non-ASCII text is encoded correctly.
//
// This is the core scenario of this fix: a script may contain non-ASCII paths or key names, so PowerShell must be guaranteed
// to receive the correct text rather than garbled characters.
func TestEncodePowerShellCommandWithChinese(t *testing.T) {
	script := "Write-Output 'café résumé'"

	encoded := encodePowerShellCommand(script)
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		t.Fatalf("encoding result is not valid base64: %v", err)
	}

	// Decode independently with the standard utf16 package (not reusing decodeUTF16LEBytes), avoiding sharing
	// the same wrong assumption as the code under test.
	units := make([]uint16, 0, len(raw)/2)
	for i := 0; i+1 < len(raw); i += 2 {
		units = append(units, uint16(raw[i])|uint16(raw[i+1])<<8)
	}
	got := string(utf16.Decode(units))

	if got != script {
		t.Errorf("non-ASCII script cannot be restored after encoding:\n  want %q\n  got %q", script, got)
	}
	if !strings.Contains(got, "café") {
		t.Errorf("non-ASCII content lost, got %q", got)
	}
}

// TestEncodePowerShellCommandEmpty verifies that an empty script does not panic.
func TestEncodePowerShellCommandEmpty(t *testing.T) {
	if got := encodePowerShellCommand(""); got != "" {
		t.Errorf("empty script should encode to an empty string, got %q", got)
	}
}

// TestLooksLikeUTF8 verifies the UTF-8 heuristic can distinguish UTF-8 from GBK byte streams.
//
// The heuristic is used to give a clear error when a child process still outputs GBK, rather than silently returning U+FFFD.
func TestLooksLikeUTF8(t *testing.T) {
	cases := []struct {
		name string
		in   []byte
		want bool
	}{
		{"empty", []byte{}, true},
		{"pure ASCII", []byte("Get-Clipboard"), true},
		{"valid UTF-8 non-ASCII", []byte("café résumé"), true},
		{"valid UTF-8 emoji", []byte("✅"), true},
		{"GBK bytes", []byte{0xB6, 0xAB, 0xB7, 0xBD}, false},
		{"isolated continuation byte", []byte{0x80}, false},
		{"overlong encoding C0", []byte{0xC0, 0x80}, false},
		{"overlong encoding C1", []byte{0xC1, 0xBF}, false},
		{"invalid start byte FF", []byte{0xFF}, false},
		{"truncated 3-byte sequence", []byte{0xE4, 0xB8}, false},
		{"truncated 4-byte sequence", []byte{0xF0, 0x9F, 0x8E}, false},
		{"continuation byte in wrong position", []byte{0xE4, 0x41, 0x80}, false},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := looksLikeUTF8(tc.in); got != tc.want {
				t.Errorf("looksLikeUTF8(%v) = %v, want %v", tc.in, got, tc.want)
			}
		})
	}
}

// TestWindowsPowerShellPreambleSetsAllThreeEncodings verifies the preamble contains all three encoding settings.
//
// The three affect different stages (stdout / external pipeline / stdin), and missing any one may cause
// encoding mismatch in specific scenarios. Pinned by a test to prevent it from being "simplified away" later.
func TestWindowsPowerShellPreambleSetsAllThreeEncodings(t *testing.T) {
	required := []string{
		"[Console]::OutputEncoding",
		"$OutputEncoding",
		"[Console]::InputEncoding",
		"UTF8",
	}
	for _, r := range required {
		if !strings.Contains(windowsPowerShellPreamble, r) {
			t.Errorf("preamble is missing %q:\n%s", r, windowsPowerShellPreamble)
		}
	}
}
