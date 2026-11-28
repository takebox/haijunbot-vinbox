package capability

// This file tests the pure logic functions in windows_gui_parse.go.
//
// These functions deliberately carry no //go:build windows tag, so they can be compiled and run on Linux/macOS,
// thereby, under the premise of "no Windows runtime environment locally", still verifying the correctness of the parameter
// parsing and encoding logic in the Windows GUI capabilities (especially the anti-command-injection encodePowerShellText).
//
// Only the standard library testing package is used; no third-party assertion library is imported.

import (
	"strings"
	"testing"
)

// TestParseWindowIDString covers the normal and error paths of window ID parsing.
func TestParseWindowIDString(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		want    uint64
		wantErr bool
	}{
		{name: "hex lowercase prefix", in: "0x00010A2C", want: 0x00010A2C},
		{name: "hex uppercase prefix", in: "0X00010A2C", want: 0x00010A2C},
		{name: "hex without zero padding", in: "0x1", want: 1},
		{name: "decimal", in: "65535", want: 65535},
		{name: "surrounding whitespace trimmed", in: "  0x10  ", want: 0x10},
		{name: "empty string errors", in: "", wantErr: true},
		{name: "pure whitespace errors", in: "   ", wantErr: true},
		{name: "non-numeric errors", in: "abc", wantErr: true},
		{name: "zero value errors", in: "0", wantErr: true},
		{name: "hex zero errors", in: "0x0", wantErr: true},
		{name: "negative errors", in: "-1", wantErr: true},
		{name: "decimal fraction errors", in: "1.5", wantErr: true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := parseWindowIDString(tc.in)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("parseWindowIDString(%q) expected an error, actually returned %d", tc.in, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("parseWindowIDString(%q) unexpected error: %v", tc.in, err)
			}
			if got != tc.want {
				t.Fatalf("parseWindowIDString(%q) = %d, want %d", tc.in, got, tc.want)
			}
		})
	}
}

// TestParseWindowsKeyCombo covers key combination parsing.
func TestParseWindowsKeyCombo(t *testing.T) {
	t.Run("no modifier keys", func(t *testing.T) {
		mods, key, err := parseWindowsKeyCombo("Return")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 0 {
			t.Fatalf("expected no modifier keys, actually %v", mods)
		}
		if key != "Return" {
			t.Fatalf("main key should be Return, actually %q", key)
		}
	})

	t.Run("single modifier key", func(t *testing.T) {
		mods, key, err := parseWindowsKeyCombo("ctrl+c")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 1 || mods[0] != "ctrl" {
			t.Fatalf("modifier keys should be [ctrl], actually %v", mods)
		}
		if key != "c" {
			t.Fatalf("main key should be c, actually %q", key)
		}
	})

	t.Run("multiple modifier keys keep input order", func(t *testing.T) {
		mods, key, err := parseWindowsKeyCombo("ctrl+shift+s")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 2 || mods[0] != "ctrl" || mods[1] != "shift" {
			t.Fatalf("modifier keys should be [ctrl shift], actually %v", mods)
		}
		if key != "s" {
			t.Fatalf("main key should be s, actually %q", key)
		}
	})

	t.Run("modifier key aliases normalized", func(t *testing.T) {
		mods, _, err := parseWindowsKeyCombo("control+alt+super+Tab")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		want := []string{"ctrl", "alt", "win"}
		if len(mods) != len(want) {
			t.Fatalf("modifier key count mismatch: got %v, want %v", mods, want)
		}
		for i := range want {
			if mods[i] != want[i] {
				t.Fatalf("modifier key %d mismatch: got %v, want %v", i, mods, want)
			}
		}
	})

	t.Run("modifier keys case-insensitive", func(t *testing.T) {
		mods, key, err := parseWindowsKeyCombo("CTRL+C")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 1 || mods[0] != "ctrl" {
			t.Fatalf("modifier keys should be [ctrl], actually %v", mods)
		}
		// The main key preserves its original case (virtualKeyCode then does the case-insensitive matching).
		if key != "C" {
			t.Fatalf("main key should preserve the original case C, actually %q", key)
		}
	})

	t.Run("duplicate modifier keys deduplicated", func(t *testing.T) {
		mods, _, err := parseWindowsKeyCombo("ctrl+ctrl+c")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 1 {
			t.Fatalf("duplicate modifier keys should deduplicate to 1, actually %v", mods)
		}
	})

	t.Run("duplicate aliases also deduplicated", func(t *testing.T) {
		mods, _, err := parseWindowsKeyCombo("ctrl+control+c")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 1 {
			t.Fatalf("duplicate aliases should deduplicate to 1, actually %v", mods)
		}
	})

	t.Run("whitespace within segments trimmed", func(t *testing.T) {
		mods, key, err := parseWindowsKeyCombo(" ctrl + c ")
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(mods) != 1 || mods[0] != "ctrl" {
			t.Fatalf("modifier keys should be [ctrl], actually %v", mods)
		}
		if key != "c" {
			t.Fatalf("main key should be c, actually %q", key)
		}
	})

	errCases := []struct {
		name string
		in   string
	}{
		{name: "empty string", in: ""},
		{name: "pure whitespace", in: "   "},
		{name: "starts with plus", in: "+c"},
		{name: "ends with plus", in: "ctrl+"},
		{name: "consecutive plus", in: "ctrl++c"},
		{name: "unknown modifier key", in: "foo+c"},
		{name: "only modifier keys", in: "ctrl+"},
	}
	for _, tc := range errCases {
		t.Run(tc.name, func(t *testing.T) {
			if _, _, err := parseWindowsKeyCombo(tc.in); err == nil {
				t.Fatalf("parseWindowsKeyCombo(%q) expected an error", tc.in)
			}
		})
	}
}

// TestVirtualKeyCode covers the mapping from key name to virtual key code.
func TestVirtualKeyCode(t *testing.T) {
	cases := []struct {
		name   string
		in     string
		want   uint16
		wantOK bool
	}{
		{name: "lowercase letter", in: "a", want: 0x41, wantOK: true},
		{name: "uppercase letter", in: "Z", want: 0x5A, wantOK: true},
		{name: "digit", in: "0", want: 0x30, wantOK: true},
		{name: "digit nine", in: "9", want: 0x39, wantOK: true},
		{name: "return lowercase", in: "return", want: 0x0D, wantOK: true},
		{name: "return alias", in: "Enter", want: 0x0D, wantOK: true},
		{name: "Tab", in: "tab", want: 0x09, wantOK: true},
		{name: "Esc alias", in: "escape", want: 0x1B, wantOK: true},
		{name: "space", in: "space", want: 0x20, wantOK: true},
		{name: "backspace", in: "backspace", want: 0x08, wantOK: true},
		{name: "Delete alias", in: "del", want: 0x2E, wantOK: true},
		{name: "Insert alias", in: "ins", want: 0x2D, wantOK: true},
		{name: "PageUp alias", in: "prior", want: 0x21, wantOK: true},
		{name: "PageDown alias", in: "next", want: 0x22, wantOK: true},
		{name: "arrow key left", in: "left", want: 0x25, wantOK: true},
		{name: "arrow key down", in: "DOWN", want: 0x28, wantOK: true},
		{name: "F1", in: "f1", want: 0x70, wantOK: true},
		{name: "F12", in: "F12", want: 0x7B, wantOK: true},
		{name: "surrounding whitespace", in: "  tab  ", want: 0x09, wantOK: true},

		{name: "empty string", in: "", wantOK: false},
		{name: "whitespace string", in: "   ", wantOK: false},
		{name: "unknown key name", in: "unknownkey", wantOK: false},
		{name: "F0 out of range", in: "f0", wantOK: false},
		{name: "F13 out of range", in: "f13", wantOK: false},
		{name: "symbol key unsupported", in: "+", wantOK: false},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := virtualKeyCode(tc.in)
			if ok != tc.wantOK {
				t.Fatalf("virtualKeyCode(%q) ok = %v, want %v", tc.in, ok, tc.wantOK)
			}
			if tc.wantOK && got != tc.want {
				t.Fatalf("virtualKeyCode(%q) = 0x%02X, want 0x%02X", tc.in, got, tc.want)
			}
		})
	}
}

// TestMouseButtonFlags covers the mouse button flag mapping.
func TestMouseButtonFlags(t *testing.T) {
	cases := []struct {
		name   string
		button string
		down   bool
		want   uint32
		wantOK bool
	}{
		{name: "left button down", button: "left", down: true, want: 0x0002, wantOK: true},
		{name: "left button up", button: "left", down: false, want: 0x0004, wantOK: true},
		{name: "right button down", button: "right", down: true, want: 0x0008, wantOK: true},
		{name: "right button up", button: "right", down: false, want: 0x0010, wantOK: true},
		{name: "middle button down", button: "middle", down: true, want: 0x0020, wantOK: true},
		{name: "middle button up", button: "middle", down: false, want: 0x0040, wantOK: true},
		{name: "case-insensitive", button: "LEFT", down: true, want: 0x0002, wantOK: true},
		{name: "surrounding whitespace", button: "  right  ", down: false, want: 0x0010, wantOK: true},
		{name: "unknown button", button: "back", down: true, wantOK: false},
		{name: "empty string", button: "", down: true, wantOK: false},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := mouseButtonFlags(tc.button, tc.down)
			if ok != tc.wantOK {
				t.Fatalf("mouseButtonFlags(%q, %v) ok = %v, want %v",
					tc.button, tc.down, ok, tc.wantOK)
			}
			if tc.wantOK && got != tc.want {
				t.Fatalf("mouseButtonFlags(%q, %v) = 0x%04X, want 0x%04X",
					tc.button, tc.down, got, tc.want)
			}
		})
	}
}

// TestEncodePowerShellText covers PowerShell literal encoding.
//
// This is the key function for anti-command-injection, so besides "the encoding result is correct", it additionally verifies
// that dangerous characters are indeed wrapped inside the single-quoted literal and have no chance of being interpreted.
func TestEncodePowerShellText(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{name: "plain text", in: "hello", want: "'hello'"},
		{name: "empty string", in: "", want: "''"},
		{name: "single quote doubled", in: "it's", want: "'it''s'"},
		{name: "multiple single quotes", in: "''", want: "''''''"},
		{name: "semicolon not escaped but wrapped", in: "a;b", want: "'a;b'"},
		{name: "dollar sign wrapped", in: "$env:PATH", want: "'$env:PATH'"},
		{name: "backtick wrapped", in: "`whoami`", want: "'`whoami`'"},
		{name: "newline preserved", in: "a\nb", want: "'a\nb'"},
		{name: "carriage return preserved", in: "a\r\nb", want: "'a\r\nb'"},
		{name: "non-ASCII preserved", in: "héllo, wörld", want: "'héllo, wörld'"},
		{name: "backslash preserved", in: `C:\Users\me`, want: `'C:\Users\me'`},
		{name: "double quote preserved", in: `say "hi"`, want: `'say "hi"'`},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := encodePowerShellText(tc.in); got != tc.want {
				t.Fatalf("encodePowerShellText(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}

	t.Run("encoding result is always wrapped in single quotes", func(t *testing.T) {
		inputs := []string{
			"plain",
			"'; Remove-Item -Recurse -Force C:\\ #",
			"' ; Invoke-Expression 'calc'",
			"$(Get-Process)",
			"a'b'c",
		}
		for _, in := range inputs {
			got := encodePowerShellText(in)
			if !strings.HasPrefix(got, "'") || !strings.HasSuffix(got, "'") {
				t.Fatalf("encoding result is not wrapped in single quotes: %q", got)
			}
			// After removing the leading and trailing single quotes, no "stray" single quote should appear inside
			// (i.e., all single quotes must be paired, to guarantee the literal closes correctly).
			inner := got[1 : len(got)-1]
			if strings.Count(inner, "'")%2 != 0 {
				t.Fatalf("the number of inner single quotes is odd; the literal may close early: %q", got)
			}
		}
	})

	t.Run("injection attempts do not produce unescaped single quotes", func(t *testing.T) {
		// The attacker tries to use a single quote to close the literal early and append a command.
		malicious := "'; Remove-Item -Recurse -Force C:\\ ; '"
		got := encodePowerShellText(malicious)
		// Each single quote in the original text should become two, so the total number of single quotes in the result
		// = original count*2 + 1 each at the start and end.
		wantQuotes := strings.Count(malicious, "'")*2 + 2
		if n := strings.Count(got, "'"); n != wantQuotes {
			t.Fatalf("single quote count mismatch: got %d, want %d (encoding result %q)", n, wantQuotes, got)
		}
	})
}

// TestModifierNamesResolveToVirtualKeyCode is a regression test.
//
// Background: parseWindowsKeyCombo normalizes modifier keys into ctrl/alt/shift/win,
// and handleWindowsInputKeys then uses virtualKeyCode to turn these names into virtual key codes.
// There was once a break where "win" (as well as super/meta) could pass parseWindowsKeyCombo validation
// but could not be mapped by virtualKeyCode, causing combinations like "ctrl+super+Tab"
// to report "unsupported modifier key" only at runtime. This test pins that invariant:
// every modifier key name produced by parseWindowsKeyCombo must be mappable by virtualKeyCode.
func TestModifierNamesResolveToVirtualKeyCode(t *testing.T) {
	// Covers all aliases in windowsModifierNames.
	aliases := []string{
		"ctrl", "control",
		"alt",
		"shift",
		"win", "super", "meta",
	}
	for _, alias := range aliases {
		t.Run(alias, func(t *testing.T) {
			mods, key, err := parseWindowsKeyCombo(alias + "+Tab")
			if err != nil {
				t.Fatalf("parseWindowsKeyCombo(%q) unexpected error: %v", alias+"+Tab", err)
			}
			if key != "Tab" {
				t.Fatalf("main key parsing error: got %q, want %q", key, "Tab")
			}
			if len(mods) != 1 {
				t.Fatalf("modifier key count error: got %v", mods)
			}
			vk, ok := virtualKeyCode(mods[0])
			if !ok {
				t.Fatalf("modifier key %q (from alias %q) cannot be mapped to a virtual key code", mods[0], alias)
			}
			if vk == 0 {
				t.Fatalf("modifier key %q maps to virtual key code 0, illegal", mods[0])
			}
		})
	}
}

// TestVirtualKeyCodeModifiers verifies the virtual key code values of the modifier keys themselves are correct.
func TestVirtualKeyCodeModifiers(t *testing.T) {
	cases := map[string]uint16{
		"ctrl":    0x11, // VK_CONTROL
		"control": 0x11,
		"alt":     0x12, // VK_MENU
		"shift":   0x10, // VK_SHIFT
		"win":     0x5B, // VK_LWIN
		"super":   0x5B,
		"meta":    0x5B,
	}
	for name, want := range cases {
		t.Run(name, func(t *testing.T) {
			got, ok := virtualKeyCode(name)
			if !ok {
				t.Fatalf("virtualKeyCode(%q) should be mappable", name)
			}
			if got != want {
				t.Fatalf("virtualKeyCode(%q) = 0x%02X, want 0x%02X", name, got, want)
			}
		})
	}
}
