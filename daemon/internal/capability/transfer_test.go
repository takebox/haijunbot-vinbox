package capability

// This file tests the common pure logic of chunked transfer (transfer.go), runnable cross-platform.
//
// It only tests the parts that do not depend on the file system: chunk size normalization, range computation, checksum helpers, and base64 round trips.

import (
	"strings"
	"testing"
)

func TestTransferNormalizeChunkSize(t *testing.T) {
	cases := []struct {
		name      string
		requested int
		want      int
		wantErr   bool
	}{
		{"zero takes the default", 0, TransferDefaultChunkSize, false},
		{"negative takes the default", -1, TransferDefaultChunkSize, false},
		{"a normal value is returned as-is", 4096, 4096, false},
		{"equal to the upper bound", TransferMaxChunkSize, TransferMaxChunkSize, false},
		{"above the upper bound errors", TransferMaxChunkSize + 1, 0, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, err := NormalizeTransferChunkSize(c.requested)
			if c.wantErr {
				if err == nil {
					t.Fatalf("expected an error, actual got=%d err=nil", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("did not expect an error: %v", err)
			}
			if got != c.want {
				t.Fatalf("expected %d, actual %d", c.want, got)
			}
		})
	}
}

func TestTransferResolveRange(t *testing.T) {
	const size = 1000

	cases := []struct {
		name      string
		offset    int64
		length    int64
		fileSize  int64
		wantStart int64
		wantCount int64
		wantEOF   bool
		wantErr   bool
	}{
		{"negative offset errors", -1, 100, size, 0, 0, false, true},
		{"negative fileSize errors", 0, 100, -1, 0, 0, false, true},
		{"read a specified length from the start, not to the end", 0, 100, size, 0, 100, false, false},
		{"read exactly to the end of file", 0, 1000, size, 0, 1000, true, false},
		{"length=0 reads to the end", 0, 0, size, 0, 1000, true, false},
		{"negative length reads to the end", 0, -5, size, 0, 1000, true, false},
		{"length exceeding the remaining takes the remaining", 100, 5000, size, 100, 900, true, false},
		{"offset past the end of file returns an empty chunk", 2000, 100, size, 1000, 0, true, false},
		{"offset equal to the end of file returns an empty chunk", 1000, 100, size, 1000, 0, true, false},
		{"mid-section read not to the end", 500, 100, size, 500, 100, false, false},
		{"mid-section read exactly to the end", 900, 100, size, 900, 100, true, false},
		{"length exceeding the single-chunk limit errors", 0, TransferMaxChunkSize + 1, size, 0, 0, false, true},
		{"empty file reads an empty chunk", 0, 100, 0, 0, 0, true, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			start, count, eof, err := ResolveTransferRange(c.offset, c.length, c.fileSize)
			if c.wantErr {
				if err == nil {
					t.Fatalf("expected an error, actual start=%d count=%d eof=%v", start, count, eof)
				}
				return
			}
			if err != nil {
				t.Fatalf("did not expect an error: %v", err)
			}
			if start != c.wantStart || count != c.wantCount || eof != c.wantEOF {
				t.Fatalf("expected (start=%d,count=%d,eof=%v), actual (start=%d,count=%d,eof=%v)",
					c.wantStart, c.wantCount, c.wantEOF, start, count, eof)
			}
		})
	}
}

func TestTransferBytesSHA256(t *testing.T) {
	// The SHA-256 of empty content is a fixed value, used to anchor the implementation's correctness.
	const emptySHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	if got := TransferBytesSHA256(nil); got != emptySHA {
		t.Fatalf("empty content SHA-256 expected %s, actual %s", emptySHA, got)
	}

	// The SHA-256 of "abc" is a well-known value.
	const abcSHA = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
	if got := TransferBytesSHA256([]byte("abc")); got != abcSHA {
		t.Fatalf("\"abc\" SHA-256 expected %s, actual %s", abcSHA, got)
	}

	// The output must be lowercase hex, length 64.
	got := TransferBytesSHA256([]byte("hello"))
	if len(got) != 64 {
		t.Fatalf("SHA-256 length expected 64, actual %d", len(got))
	}
	if got != strings.ToLower(got) {
		t.Fatalf("SHA-256 expected lowercase, actual %s", got)
	}
}

func TestTransferEqualSHA256(t *testing.T) {
	const sum = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

	cases := []struct {
		name string
		a    string
		b    string
		want bool
	}{
		{"exactly the same", sum, sum, true},
		{"different case is treated as equal", sum, strings.ToUpper(sum), true},
		{"leading and trailing whitespace ignored", "  " + sum + "\n", sum, true},
		{"different values are unequal", sum, strings.Repeat("0", 64), false},
		{"empty string on the left is unequal", "", sum, false},
		{"empty string on the right is unequal", sum, "", false},
		{"both empty is unequal", "", "", false},
		{"only whitespace is unequal", "   ", "   ", false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := TransferEqualSHA256(c.a, c.b); got != c.want {
				t.Fatalf("expected %v, actual %v", c.want, got)
			}
		})
	}
}

func TestTransferBase64RoundTrip(t *testing.T) {
	// Content containing binary bytes (NUL, 0xFF), verifying that the base64 round trip is lossless.
	original := []byte{0x00, 0x01, 0xFF, 0xFE, 'h', 'i', 0x00}
	encoded := TransferEncodeBase64(original)
	decoded, err := TransferDecodeBase64(encoded)
	if err != nil {
		t.Fatalf("decoding failed: %v", err)
	}
	if string(decoded) != string(original) {
		t.Fatalf("round trip inconsistent: original %v, decoded %v", original, decoded)
	}

	// Empty content round trip.
	emptyDecoded, err := TransferDecodeBase64(TransferEncodeBase64(nil))
	if err != nil {
		t.Fatalf("empty content decoding failed: %v", err)
	}
	if len(emptyDecoded) != 0 {
		t.Fatalf("empty content decoded length expected 0, actual %d", len(emptyDecoded))
	}

	// base64 with leading and trailing whitespace should decode normally.
	decoded2, err := TransferDecodeBase64("  " + encoded + "\n")
	if err != nil {
		t.Fatalf("decoding with whitespace failed: %v", err)
	}
	if string(decoded2) != string(original) {
		t.Fatalf("the decoding result with whitespace is inconsistent")
	}

	// Invalid base64 must report an error.
	if _, err := TransferDecodeBase64("!!!not-base64!!!"); err == nil {
		t.Fatalf("invalid base64 expected an error, actual nil")
	}
}

func TestTransferParamHelpers(t *testing.T) {
	// transferParamString: missing/empty/non-string should all report errors.
	if _, err := transferParamString(map[string]any{}, "path"); err == nil {
		t.Fatalf("a missing parameter should report an error")
	}
	if _, err := transferParamString(map[string]any{"path": "  "}, "path"); err == nil {
		t.Fatalf("a whitespace parameter should report an error")
	}
	if _, err := transferParamString(map[string]any{"path": 123}, "path"); err == nil {
		t.Fatalf("a non-string should report an error")
	}
	got, err := transferParamString(map[string]any{"path": " /tmp/a "}, "path")
	if err != nil || got != "/tmp/a" {
		t.Fatalf("expected \"/tmp/a\", actual %q err=%v", got, err)
	}

	// transferParamInt64: accommodates int/int32/int64/float64, rejects decimals.
	cases := []struct {
		name    string
		value   any
		want    int64
		wantErr bool
	}{
		{"int", 42, 42, false},
		{"int32", int32(42), 42, false},
		{"int64", int64(42), 42, false},
		{"float64 integer value", float64(42), 42, false},
		{"float64 decimal errors", 42.5, 0, true},
		{"string errors", "42", 0, true},
	}
	for _, c := range cases {
		t.Run("int64/"+c.name, func(t *testing.T) {
			v, err := transferParamInt64(map[string]any{"n": c.value}, "n", 0)
			if c.wantErr {
				if err == nil {
					t.Fatalf("expected an error, actual %d", v)
				}
				return
			}
			if err != nil {
				t.Fatalf("did not expect an error: %v", err)
			}
			if v != c.want {
				t.Fatalf("expected %d, actual %d", c.want, v)
			}
		})
	}

	// When missing, it returns the default value.
	def, err := transferParamInt64(map[string]any{}, "n", 7)
	if err != nil || def != 7 {
		t.Fatalf("when missing, expected the default 7, actual %d err=%v", def, err)
	}

	// transferParamBool: missing takes the default, non-boolean errors.
	b, err := transferParamBool(map[string]any{}, "truncate", true)
	if err != nil || !b {
		t.Fatalf("when missing, expected the default true, actual %v err=%v", b, err)
	}
	if _, err := transferParamBool(map[string]any{"truncate": "yes"}, "truncate", false); err == nil {
		t.Fatalf("a non-boolean should report an error")
	}
	got2, err := transferParamBool(map[string]any{"truncate": false}, "truncate", true)
	if err != nil || got2 {
		t.Fatalf("expected false, actual %v err=%v", got2, err)
	}
}

func TestTransferConstants(t *testing.T) {
	// The magnitude relationships between the constants must be self-consistent, to avoid accidental later changes.
	if TransferDefaultChunkSize > TransferMaxChunkSize {
		t.Fatalf("the default chunk %d should not be greater than the max chunk %d", TransferDefaultChunkSize, TransferMaxChunkSize)
	}
	if TransferMaxChunkSize > TransferMaxFileSize {
		t.Fatalf("the max chunk %d should not be greater than the single-file limit %d", TransferMaxChunkSize, TransferMaxFileSize)
	}
	if TransferMaxFileSize != 512<<20 {
		t.Fatalf("the single-file limit expected 512 MiB, actual %d", TransferMaxFileSize)
	}
	if TransferDefaultChunkSize != 1<<20 {
		t.Fatalf("the default chunk expected 1 MiB, actual %d", TransferDefaultChunkSize)
	}
	if TransferMaxChunkSize != 8<<20 {
		t.Fatalf("the max chunk expected 8 MiB, actual %d", TransferMaxChunkSize)
	}
}
