package capability

// This file holds the pure logic functions of the Windows filesystem capability (windows.fs.*).
//
// These functions only depend on the standard library and do not reference any platform-specific types, so they **carry no build tags**:
// this way they can be compiled and unit tested directly on Linux / macOS, so that even without a Windows environment
// the correctness of core logic such as encoding parsing and binary detection can still be verified.
//
// The accompanying tests are in windows_fs_parse_test.go; windows_fs_windows.go, which carries the //go:build windows tag,
// is responsible for registering the capability and the actual file read/write.

import (
	"fmt"
	"strings"
	"unicode/utf8"
)

// resolveWindowsFSEncoding parses and validates the encoding parameter; only utf-8 and base64 are allowed.
//
// An empty value returns def (the default encoding passed in by the caller). It is case-insensitive and accepts "utf8" as an alias.
//
// Note: the raw value is read directly here instead of using optionalString, in order to keep this file
// "zero platform dependency" — optionalString is defined in a file carrying the //go:build windows tag
// and is unavailable on platforms such as darwin, so referencing it here would break cross-platform compilation.
func resolveWindowsFSEncoding(params map[string]any, def string) (string, error) {
	rawAny, ok := params["encoding"]
	if !ok || rawAny == nil {
		return def, nil
	}
	raw, ok := rawAny.(string)
	if !ok {
		return "", fmt.Errorf("parameter encoding must be a string, actual %T", rawAny)
	}
	if raw == "" {
		return def, nil
	}
	switch strings.ToLower(raw) {
	case "utf-8", "utf8":
		return "utf-8", nil
	case "base64":
		return "base64", nil
	default:
		return "", fmt.Errorf("parameter encoding does not support %q, allowed values: utf-8, base64", raw)
	}
}

// chooseWindowsReportedEncoding returns the encoding actually used to represent content.
//
// When utf-8 is requested but the content is judged to be binary, it is actually returned as base64, so base64 is reported,
// avoiding the caller getting garbled text when decoding as utf-8.
func chooseWindowsReportedEncoding(requested string, isBinary bool) string {
	if isBinary && requested == "utf-8" {
		return "base64"
	}
	return requested
}

// isBinaryWindowsContent determines whether the content is binary.
//
// The criterion: it contains a NUL byte, or is not valid UTF-8. Empty content is treated as non-binary.
func isBinaryWindowsContent(data []byte) bool {
	if len(data) == 0 {
		return false
	}
	if strings.IndexByte(string(data), 0) >= 0 {
		return true
	}
	return !utf8.Valid(data)
}
