package capability

// This file unit-tests the pure logic in windows_fs_parse.go (encoding parsing, binary detection, reported encoding selection).
//
// These tests **carry no build tags**, so they can be run on Linux — the local development environment is Linux,
// with no Windows runtime environment, and this is the main means of verifying the core logic of windows.fs.*.
//
// Note: the actual file read/write (windows_fs_windows.go) carries the //go:build windows tag,
// and its success path cannot be verified end-to-end locally; it can only be guaranteed to compile under GOOS=windows.

import (
	"bytes"
	"strings"
	"testing"
)

// TestResolveWindowsFSEncoding covers various values of the encoding parameter parsing.
func TestResolveWindowsFSEncoding(t *testing.T) {
	cases := []struct {
		name    string
		params  map[string]any
		def     string
		want    string
		wantErr bool
	}{
		{"absent falls back to default", map[string]any{}, "utf-8", "utf-8", false},
		{"empty string falls back to default", map[string]any{"encoding": ""}, "utf-8", "utf-8", false},
		{"utf-8 as-is", map[string]any{"encoding": "utf-8"}, "utf-8", "utf-8", false},
		{"UTF-8 case-insensitive", map[string]any{"encoding": "UTF-8"}, "utf-8", "utf-8", false},
		{"utf8 alias normalized", map[string]any{"encoding": "utf8"}, "utf-8", "utf-8", false},
		{"base64 as-is", map[string]any{"encoding": "base64"}, "utf-8", "base64", false},
		{"BASE64 case-insensitive", map[string]any{"encoding": "BASE64"}, "utf-8", "base64", false},
		{"custom default takes effect", map[string]any{}, "base64", "base64", false},
		{"unsupported value errors", map[string]any{"encoding": "gbk"}, "utf-8", "", true},
		{"type error errors", map[string]any{"encoding": 123}, "utf-8", "", true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := resolveWindowsFSEncoding(tc.params, tc.def)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected an error, actual got=%q err=nil", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("expected no error, actual err=%v", err)
			}
			if got != tc.want {
				t.Fatalf("expected %q, actual %q", tc.want, got)
			}
		})
	}
}

// TestChooseWindowsReportedEncoding covers the reporting logic of "binary content automatically downgraded to base64".
func TestChooseWindowsReportedEncoding(t *testing.T) {
	cases := []struct {
		requested string
		isBinary  bool
		want      string
	}{
		{"utf-8", false, "utf-8"},
		{"utf-8", true, "base64"}, // binary + requested utf-8 → actually returned as base64
		{"base64", false, "base64"},
		{"base64", true, "base64"},
	}

	for _, tc := range cases {
		got := chooseWindowsReportedEncoding(tc.requested, tc.isBinary)
		if got != tc.want {
			t.Errorf("chooseWindowsReportedEncoding(%q, %v) = %q, expected %q",
				tc.requested, tc.isBinary, got, tc.want)
		}
	}
}

// TestIsBinaryWindowsContent covers binary detection: NUL byte, invalid UTF-8, plain text, empty content.
func TestIsBinaryWindowsContent(t *testing.T) {
	cases := []struct {
		name string
		data []byte
		want bool
	}{
		{"empty content is not binary", []byte{}, false},
		{"pure ASCII is not binary", []byte("hello world"), false},
		{"valid multibyte UTF-8 is not binary", []byte("héllo, wörld"), false},
		{"contains NUL byte is binary", []byte("abc\x00def"), true},
		{"leading NUL is binary", []byte{0x00, 0x01, 0x02}, true},
		{"invalid UTF-8 is binary", []byte{0xff, 0xfe, 0xfd}, true},
		{"isolated continuation byte is binary", []byte{0x80, 0x80}, true},
		{"truncated multibyte sequence is binary", []byte{0xe4, 0xbd}, true},
		{"PNG magic is binary", []byte{0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a}, true},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := isBinaryWindowsContent(tc.data); got != tc.want {
				t.Fatalf("isBinaryWindowsContent(%q) = %v, expected %v", tc.data, got, tc.want)
			}
		})
	}
}

// TestIsBinaryWindowsContentDoesNotMutate confirms that the detection process does not modify the input slice.
func TestIsBinaryWindowsContentDoesNotMutate(t *testing.T) {
	original := []byte("hello\x00world")
	snapshot := append([]byte(nil), original...)

	_ = isBinaryWindowsContent(original)

	if !bytes.Equal(original, snapshot) {
		t.Fatalf("input was modified: original %q, current %q", snapshot, original)
	}
}

// TestResolveWindowsFSEncodingErrorMessage confirms that the error message is friendly for troubleshooting (contains the invalid value).
func TestResolveWindowsFSEncodingErrorMessage(t *testing.T) {
	_, err := resolveWindowsFSEncoding(map[string]any{"encoding": "latin1"}, "utf-8")
	if err == nil {
		t.Fatal("expected an error, actual nil")
	}
	if !strings.Contains(err.Error(), "latin1") {
		t.Fatalf("the error message should contain the invalid value latin1, actual: %v", err)
	}
	if !strings.Contains(err.Error(), "base64") {
		t.Fatalf("the error message should mention the allowed value base64, actual: %v", err)
	}
}
