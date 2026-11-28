// This file provides the common core of the "chunked file transfer" capability: constants, range computation, checksums, and encoding helpers.
//
// Design goal: let fs.transfer.push / fs.transfer.pull (cross-machine direct file transfer) share the same
// semantics and boundary validation, avoiding drift between the two implementations.
//
// Important: this file has **no build tag** and is compiled into all platforms, therefore:
//   - only the standard library may be used;
//   - it must never reference symbols that exist only in platform-specific files (such as requiredString / optionalBool /
//     resolveFSEncoding, which are defined in linux_*.go or windows_*.go respectively);
//   - top-level function names defined in this file must carry the Transfer prefix, to avoid clashing with same-named functions
//     in the platform files (for example optionalBool is defined on both the Linux and Windows sides).
package capability

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"strings"
)

// Common constraint constants for chunked transfer.
const (
	// TransferMaxFileSize is the maximum number of bytes allowed for a single file transfer (512 MiB).
	//
	// Rationale: the content is carried via JSON + base64, and base64 expands it by about 4/3. A 512 MiB file
	// requires 512 round trips when chunked at 1 MiB, a compromise between "enough" and "the upper-layer loop not running out of control";
	// anything larger should use a dedicated binary channel rather than this capability.
	TransferMaxFileSize int64 = 512 << 20 // 512 MiB

	// TransferDefaultChunkSize is the default chunk byte size used when no chunk size is specified (1 MiB).
	//
	// Rationale: 1 MiB becomes about 1.33 MiB after base64, so the single-frame JSON size is controllable;
	// it neither causes too many round trips from chunks being too small, nor blows up a single frame from chunks being too large.
	TransferDefaultChunkSize = 1 << 20 // 1 MiB

	// TransferMaxChunkSize is the maximum number of bytes for a single chunked read/write (8 MiB).
	//
	// Rationale: consistent with the existing single-read limit of fs.read (8 MiB),
	// guaranteeing that "one chunk" does not exceed the resource usage of one ordinary read.
	TransferMaxChunkSize = 8 << 20 // 8 MiB
)

// NormalizeTransferChunkSize normalizes the requested chunk size.
//
// Rule: when requested <= 0, returns the default chunk size; when it exceeds TransferMaxChunkSize, it errors.
func NormalizeTransferChunkSize(requested int) (int, error) {
	if requested <= 0 {
		return TransferDefaultChunkSize, nil
	}
	if requested > TransferMaxChunkSize {
		return 0, fmt.Errorf("parameter length exceeds the single-chunk limit of %d bytes, actual %d",
			TransferMaxChunkSize, requested)
	}
	return requested, nil
}

// ResolveTransferRange computes the actual range of one chunked read.
//
// Parameters:
//   - offset: start offset, must be >= 0;
//   - length: desired read length, <= 0 means "read to end of file";
//   - fileSize: total file size, must be >= 0.
//
// Returns:
//   - start: the actual start offset;
//   - count: the actual number of bytes read;
//   - eof: whether this read has reached (or passed) the end of file.
//
// Boundary semantics:
//   - offset < 0 or fileSize < 0 -> error;
//   - offset > fileSize -> start=fileSize, count=0, eof=true (out of bounds is treated as end of file, no error);
//   - offset == fileSize -> count=0, eof=true;
//   - length <= 0 or offset+length > fileSize -> take the remaining bytes, eof=true.
func ResolveTransferRange(offset, length, fileSize int64) (start, count int64, eof bool, err error) {
	if offset < 0 {
		return 0, 0, false, fmt.Errorf("parameter offset cannot be negative, actual %d", offset)
	}
	if fileSize < 0 {
		return 0, 0, false, fmt.Errorf("the file size cannot be negative, actual %d", fileSize)
	}

	// The offset has passed the end of file: treat it as "reached the end", returning an empty chunk rather than an error, so the upper-layer loop converges naturally.
	if offset >= fileSize {
		return fileSize, 0, true, nil
	}

	remaining := fileSize - offset
	if length <= 0 || length > remaining {
		// No length specified, or the requested length exceeds the remaining: always take the remaining part, which necessarily reaches the end of file.
		if length > TransferMaxChunkSize {
			return 0, 0, false, fmt.Errorf("parameter length exceeds the single-chunk limit of %d bytes, actual %d",
				TransferMaxChunkSize, length)
		}
		return offset, remaining, true, nil
	}

	if length > TransferMaxChunkSize {
		return 0, 0, false, fmt.Errorf("parameter length exceeds the single-chunk limit of %d bytes, actual %d",
			TransferMaxChunkSize, length)
	}

	// Read to offset+length, and whether it is exactly at the end of file.
	return offset, length, offset+length == fileSize, nil
}

// TransferFileSHA256 computes the file's SHA-256 in a streaming manner, returning a lowercase hex string.
//
// The implementation uses io.Copy to feed the file contents to the hasher without reading the whole file into memory,
// so it is safe even for large files.
func TransferFileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", fmt.Errorf("failed to open file %s: %w", path, err)
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", fmt.Errorf("failed to read file %s to compute the checksum: %w", path, err)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// TransferBytesSHA256 computes the SHA-256 of a byte slice, returning a lowercase hex string.
func TransferBytesSHA256(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// TransferEqualSHA256 compares whether two SHA-256 strings are equal.
//
// Leading and trailing whitespace is trimmed and case is ignored before comparison, so the caller can pass user input directly.
// An empty string is always treated as unequal (to avoid "neither was provided" being misjudged as a match).
func TransferEqualSHA256(a, b string) bool {
	left := strings.TrimSpace(a)
	right := strings.TrimSpace(b)
	if left == "" || right == "" {
		return false
	}
	return strings.EqualFold(left, right)
}

// TransferDecodeBase64 decodes a base64 string (trimming leading and trailing whitespace first).
func TransferDecodeBase64(s string) ([]byte, error) {
	trimmed := strings.TrimSpace(s)
	data, err := base64.StdEncoding.DecodeString(trimmed)
	if err != nil {
		return nil, fmt.Errorf("data is not valid base64 content: %w", err)
	}
	return data, nil
}

// TransferEncodeBase64 encodes bytes into a base64 string.
func TransferEncodeBase64(data []byte) string {
	return base64.StdEncoding.EncodeToString(data)
}

// transferParamString reads a required string parameter (self-contained in this file, not depending on platform-specific helpers).
func transferParamString(params map[string]any, key string) (string, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return "", fmt.Errorf("missing required parameter %s", key)
	}
	s, ok := v.(string)
	if !ok {
		return "", fmt.Errorf("parameter %s must be a string, actual %T", key, v)
	}
	s = strings.TrimSpace(s)
	if s == "" {
		return "", fmt.Errorf("parameter %s cannot be empty", key)
	}
	return s, nil
}

// transferParamInt64 reads an optional integer parameter, supporting three sources: int / int64 / float64.
//
// The reason for accommodating float64: after JSON deserialization an integer becomes a float64.
func transferParamInt64(params map[string]any, key string, def int64) (int64, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return def, nil
	}
	switch n := v.(type) {
	case int:
		return int64(n), nil
	case int32:
		return int64(n), nil
	case int64:
		return n, nil
	case float64:
		// JSON numbers are uniformly float64; it is required to be an integer value here, to avoid silent truncation.
		if n != float64(int64(n)) {
			return 0, fmt.Errorf("parameter %s must be an integer, actual %v", key, n)
		}
		return int64(n), nil
	default:
		return 0, fmt.Errorf("parameter %s must be an integer, actual %T", key, v)
	}
}

// transferParamBool reads an optional boolean parameter; when missing or nil it returns the default value.
func transferParamBool(params map[string]any, key string, def bool) (bool, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return def, nil
	}
	b, ok := v.(bool)
	if !ok {
		return false, fmt.Errorf("parameter %s must be a boolean, actual %T", key, v)
	}
	return b, nil
}
