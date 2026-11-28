//go:build linux

package capability

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestLinuxFSReadWriteRoundTrip verifies that the content read back after writing is consistent.
func TestLinuxFSReadWriteRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "hello.txt")
	const content = "hello, HaijunBot\nsecond line\n"

	res, err := handleLinuxFSWrite(map[string]any{
		"path":    path,
		"content": content,
	})
	if err != nil {
		t.Fatalf("write failed: %v", err)
	}
	m := res.(map[string]any)
	if m["created"] != true {
		t.Errorf("the first write should have created=true, actual %v", m["created"])
	}
	if m["written_bytes"].(int) != len(content) {
		t.Errorf("written_bytes should be %d, actual %v", len(content), m["written_bytes"])
	}

	readRes, err := handleLinuxFSRead(map[string]any{"path": path})
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	rm := readRes.(map[string]any)
	if rm["content"].(string) != content {
		t.Errorf("the content read back is inconsistent:\nwant %q\nactual %q", content, rm["content"])
	}
	if rm["is_binary"] != false {
		t.Errorf("a text file should not be detected as binary, actual %v", rm["is_binary"])
	}
	if rm["truncated"] != false {
		t.Errorf("a small file should not be truncated, actual %v", rm["truncated"])
	}
	if rm["read_bytes"].(int) != len(content) {
		t.Errorf("read_bytes should be %d, actual %v", len(content), rm["read_bytes"])
	}
	if rm["size"].(int64) != int64(len(content)) {
		t.Errorf("size should be %d, actual %v", len(content), rm["size"])
	}
}

// TestLinuxFSWriteAppend verifies the append write behavior.
func TestLinuxFSWriteAppend(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "append.txt")

	if _, err := handleLinuxFSWrite(map[string]any{
		"path":    path,
		"content": "AAA",
	}); err != nil {
		t.Fatalf("the first write failed: %v", err)
	}

	res, err := handleLinuxFSWrite(map[string]any{
		"path":    path,
		"content": "BBB",
		"append":  true,
	})
	if err != nil {
		t.Fatalf("the append write failed: %v", err)
	}
	m := res.(map[string]any)
	if m["created"] != false {
		t.Errorf("appending to an existing file should have created=false, actual %v", m["created"])
	}
	if m["appended"] != true {
		t.Errorf("appended should be true, actual %v", m["appended"])
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read the file: %v", err)
	}
	if string(raw) != "AAABBB" {
		t.Errorf("the append result should be AAABBB, actual %q", string(raw))
	}
}

// TestLinuxFSWriteOverwriteByDefault verifies that the default is overwrite rather than append.
func TestLinuxFSWriteOverwriteByDefault(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "overwrite.txt")

	if _, err := handleLinuxFSWrite(map[string]any{"path": path, "content": "first"}); err != nil {
		t.Fatalf("the first write failed: %v", err)
	}
	if _, err := handleLinuxFSWrite(map[string]any{"path": path, "content": "second"}); err != nil {
		t.Fatalf("the second write failed: %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read the file: %v", err)
	}
	if string(raw) != "second" {
		t.Errorf("the default should overwrite, want second, actual %q", string(raw))
	}
}

// TestLinuxFSWriteCreateDirs verifies that create_dirs automatically creates parent directories.
func TestLinuxFSWriteCreateDirs(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "a", "b", "c", "deep.txt")

	// It should fail when create_dirs is not enabled.
	if _, err := handleLinuxFSWrite(map[string]any{"path": path, "content": "x"}); err == nil {
		t.Fatal("the parent directory does not exist and create_dirs is not enabled, it should return an error")
	}

	if _, err := handleLinuxFSWrite(map[string]any{
		"path":        path,
		"content":     "deep",
		"create_dirs": true,
	}); err != nil {
		t.Fatalf("the write failed after enabling create_dirs: %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read the deep file: %v", err)
	}
	if string(raw) != "deep" {
		t.Errorf("the content should be deep, actual %q", string(raw))
	}
}

// TestLinuxFSWriteMode verifies the parsing and effect of the mode parameter.
func TestLinuxFSWriteMode(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "mode.txt")

	if _, err := handleLinuxFSWrite(map[string]any{
		"path":    path,
		"content": "x",
		"mode":    "0600",
	}); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat failed: %v", err)
	}
	if got := info.Mode().Perm(); got != 0o600 {
		t.Errorf("the permission should be 0600, actual %o", got)
	}

	// An invalid mode must report an error.
	if _, err := handleLinuxFSWrite(map[string]any{
		"path":    filepath.Join(dir, "bad.txt"),
		"content": "x",
		"mode":    "abc",
	}); err == nil {
		t.Error("an invalid mode should return an error")
	}

	if _, err := handleLinuxFSWrite(map[string]any{
		"path":    filepath.Join(dir, "bad2.txt"),
		"content": "x",
		"mode":    "0999",
	}); err == nil {
		t.Error("a mode containing an invalid octal digit should return an error")
	}
}

// TestLinuxFSReadOffsetLimit verifies segmented reading by offset/limit and the truncation flag.
func TestLinuxFSReadOffsetLimit(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "seg.txt")
	const content = "0123456789"

	if _, err := handleLinuxFSWrite(map[string]any{"path": path, "content": content}); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	res, err := handleLinuxFSRead(map[string]any{
		"path":   path,
		"offset": 2,
		"limit":  3,
	})
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	m := res.(map[string]any)
	if m["content"].(string) != "234" {
		t.Errorf("offset=2 limit=3 should produce 234, actual %q", m["content"])
	}
	if m["truncated"] != true {
		t.Errorf("there is still remaining content, truncated should be true, actual %v", m["truncated"])
	}
	if m["read_bytes"].(int) != 3 {
		t.Errorf("read_bytes should be 3, actual %v", m["read_bytes"])
	}

	// Reading exactly to the end should not mark truncation.
	res2, err := handleLinuxFSRead(map[string]any{
		"path":   path,
		"offset": 7,
		"limit":  3,
	})
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	m2 := res2.(map[string]any)
	if m2["content"].(string) != "789" {
		t.Errorf("it should produce 789, actual %q", m2["content"])
	}
	if m2["truncated"] != false {
		t.Errorf("reading exactly to the end should not truncate, actual %v", m2["truncated"])
	}
}

// TestLinuxFSReadBinaryDetection verifies that binary content is automatically converted to base64.
func TestLinuxFSReadBinaryDetection(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bin.dat")
	payload := []byte{0x00, 0x01, 0x02, 0xFF, 0xFE}

	if err := os.WriteFile(path, payload, 0o644); err != nil {
		t.Fatalf("failed to prepare the binary file: %v", err)
	}

	res, err := handleLinuxFSRead(map[string]any{"path": path})
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	m := res.(map[string]any)
	if m["is_binary"] != true {
		t.Errorf("content containing NUL bytes should be detected as binary, actual %v", m["is_binary"])
	}
	if m["encoding"].(string) != "base64" {
		t.Errorf("binary content should report base64 encoding, actual %v", m["encoding"])
	}
	decoded, err := base64.StdEncoding.DecodeString(m["content"].(string))
	if err != nil {
		t.Fatalf("the returned content is not valid base64: %v", err)
	}
	if string(decoded) != string(payload) {
		t.Errorf("the content after base64 decoding is inconsistent:\nwant %v\nactual %v", payload, decoded)
	}
}

// TestLinuxFSReadBase64Encoding verifies explicitly specifying base64 encoding.
func TestLinuxFSReadBase64Encoding(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "text.txt")
	if _, err := handleLinuxFSWrite(map[string]any{"path": path, "content": "hi"}); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	res, err := handleLinuxFSRead(map[string]any{"path": path, "encoding": "base64"})
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	m := res.(map[string]any)
	if m["content"].(string) != base64.StdEncoding.EncodeToString([]byte("hi")) {
		t.Errorf("the base64 content does not match, actual %q", m["content"])
	}
	if m["is_binary"] != false {
		t.Errorf("for text content is_binary should be false, actual %v", m["is_binary"])
	}
}

// TestLinuxFSWriteBase64Content verifies writing base64 content.
func TestLinuxFSWriteBase64Content(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "from64.bin")
	payload := []byte{0xDE, 0xAD, 0xBE, 0xEF}

	if _, err := handleLinuxFSWrite(map[string]any{
		"path":     path,
		"content":  base64.StdEncoding.EncodeToString(payload),
		"encoding": "base64",
	}); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	if string(raw) != string(payload) {
		t.Errorf("the base64 write result is inconsistent:\nwant %v\nactual %v", payload, raw)
	}

	// Invalid base64 must report an error.
	if _, err := handleLinuxFSWrite(map[string]any{
		"path":     filepath.Join(dir, "bad.bin"),
		"content":  "!!!not-base64!!!",
		"encoding": "base64",
	}); err == nil {
		t.Error("invalid base64 content should return an error")
	}
}

// TestLinuxFSListBasic verifies directory listing.
func TestLinuxFSListBasic(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "a.txt"), []byte("a"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "b.txt"), []byte("bb"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(dir, "sub"), 0o755); err != nil {
		t.Fatal(err)
	}

	res, err := handleLinuxFSList(map[string]any{"path": dir})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	m := res.(map[string]any)
	if m["count"].(int) != 3 {
		t.Errorf("there should be 3 entries, actual %d", m["count"])
	}
	if m["truncated"] != false {
		t.Errorf("it should not be truncated, actual %v", m["truncated"])
	}

	entries := m["entries"].([]map[string]any)
	names := map[string]bool{}
	for _, e := range entries {
		names[e["name"].(string)] = true
		if e["mode"].(string) == "" {
			t.Errorf("entry %v is missing mode", e["name"])
		}
		if e["mod_time"].(string) == "" {
			t.Errorf("entry %v is missing mod_time", e["name"])
		}
	}
	for _, want := range []string{"a.txt", "b.txt", "sub"} {
		if !names[want] {
			t.Errorf("missing entry %s", want)
		}
	}

	// Verify that sub is recognized as a directory.
	for _, e := range entries {
		if e["name"].(string) == "sub" && e["is_dir"] != true {
			t.Error("sub should be recognized as a directory")
		}
	}
}

// TestLinuxFSListHidden verifies the show_hidden switch.
func TestLinuxFSListHidden(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, ".hidden"), []byte("h"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "visible"), []byte("v"), 0o644); err != nil {
		t.Fatal(err)
	}

	// By default hidden items are included.
	res, err := handleLinuxFSList(map[string]any{"path": dir})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	if res.(map[string]any)["count"].(int) != 2 {
		t.Errorf("hidden items should be included by default, actual %d", res.(map[string]any)["count"])
	}

	// After disabling it, only 1 should remain.
	res2, err := handleLinuxFSList(map[string]any{"path": dir, "show_hidden": false})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	if res2.(map[string]any)["count"].(int) != 1 {
		t.Errorf("with show_hidden=false only 1 should remain, actual %d", res2.(map[string]any)["count"])
	}
}

// TestLinuxFSListRecursive verifies recursion and max_depth.
func TestLinuxFSListRecursive(t *testing.T) {
	dir := t.TempDir()
	sub := filepath.Join(dir, "sub")
	deep := filepath.Join(sub, "deep")
	if err := os.MkdirAll(deep, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "top.txt"), []byte("t"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(sub, "mid.txt"), []byte("m"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(deep, "bottom.txt"), []byte("b"), 0o644); err != nil {
		t.Fatal(err)
	}

	// Non-recursive: only top.txt and sub.
	res, err := handleLinuxFSList(map[string]any{"path": dir})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	if got := res.(map[string]any)["count"].(int); got != 2 {
		t.Errorf("non-recursive should have 2 entries, actual %d", got)
	}

	// Recursion depth 2: the dir level (top.txt, sub) + the sub level (deep, mid.txt).
	// Note that the deep directory itself is at level 2 and should be listed; bottom.txt inside deep is at level 3 and is not listed.
	res2, err := handleLinuxFSList(map[string]any{
		"path":      dir,
		"recursive": true,
		"max_depth": 2,
	})
	if err != nil {
		t.Fatalf("recursive listing failed: %v", err)
	}
	if got := res2.(map[string]any)["count"].(int); got != 4 {
		t.Errorf("with max_depth=2 there should be 4 entries, actual %d", got)
	}

	// Recursion depth 3: plus bottom.txt at the deep level, for 5 entries total.
	res3, err := handleLinuxFSList(map[string]any{
		"path":      dir,
		"recursive": true,
		"max_depth": 3,
	})
	if err != nil {
		t.Fatalf("recursive listing failed: %v", err)
	}
	if got := res3.(map[string]any)["count"].(int); got != 5 {
		t.Errorf("with max_depth=3 there should be 5 entries, actual %d", got)
	}
}

// TestLinuxFSListLimit verifies limit truncation and the truncated flag.
func TestLinuxFSListLimit(t *testing.T) {
	dir := t.TempDir()
	for _, n := range []string{"1.txt", "2.txt", "3.txt", "4.txt", "5.txt"} {
		if err := os.WriteFile(filepath.Join(dir, n), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}

	res, err := handleLinuxFSList(map[string]any{"path": dir, "limit": 2})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	m := res.(map[string]any)
	if m["count"].(int) != 2 {
		t.Errorf("with limit=2 it should return 2 entries, actual %d", m["count"])
	}
	if m["truncated"] != true {
		t.Errorf("when truncated, truncated should be true, actual %v", m["truncated"])
	}
}

// TestLinuxFSListSymlink verifies the symbolic link information.
func TestLinuxFSListSymlink(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "target.txt")
	link := filepath.Join(dir, "link.txt")
	if err := os.WriteFile(target, []byte("t"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("the current environment does not support creating symbolic links: %v", err)
	}

	res, err := handleLinuxFSList(map[string]any{"path": dir})
	if err != nil {
		t.Fatalf("listing failed: %v", err)
	}
	entries := res.(map[string]any)["entries"].([]map[string]any)
	found := false
	for _, e := range entries {
		if e["name"].(string) == "link.txt" {
			found = true
			if e["symlink_target"] != target {
				t.Errorf("symlink_target should be %s, actual %v", target, e["symlink_target"])
			}
		}
	}
	if !found {
		t.Error("the symbolic link entry was not found")
	}
}

// TestLinuxFSParameterValidation covers parameter validation and error paths.
func TestLinuxFSParameterValidation(t *testing.T) {
	dir := t.TempDir()
	existing := filepath.Join(dir, "exists.txt")
	if err := os.WriteFile(existing, []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}

	cases := []struct {
		name   string
		fn     func(map[string]any) (any, error)
		params map[string]any
	}{
		{"read missing path", handleLinuxFSRead, map[string]any{}},
		{"read path has the wrong type", handleLinuxFSRead, map[string]any{"path": 123}},
		{"read path is empty", handleLinuxFSRead, map[string]any{"path": "   "}},
		{"read offset is negative", handleLinuxFSRead, map[string]any{"path": existing, "offset": -1}},
		{"read limit is 0", handleLinuxFSRead, map[string]any{"path": existing, "limit": 0}},
		{"read limit exceeds the upper bound", handleLinuxFSRead, map[string]any{"path": existing, "limit": 9 << 20}},
		{"read encoding is invalid", handleLinuxFSRead, map[string]any{"path": existing, "encoding": "gbk"}},
		{"read path does not exist", handleLinuxFSRead, map[string]any{"path": filepath.Join(dir, "nope.txt")}},
		{"read target is a directory", handleLinuxFSRead, map[string]any{"path": dir}},
		{"write missing path", handleLinuxFSWrite, map[string]any{"content": "x"}},
		{"write missing content", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "w.txt")}},
		{"write content has the wrong type", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "w.txt"), "content": 1}},
		{"write append has the wrong type", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "w.txt"), "content": "x", "append": "yes"}},
		{"write create_dirs has the wrong type", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "w.txt"), "content": "x", "create_dirs": 1}},
		{"write mode is invalid", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "w.txt"), "content": "x", "mode": "xyz"}},
		{"write parent directory does not exist", handleLinuxFSWrite, map[string]any{"path": filepath.Join(dir, "no", "dir", "f.txt"), "content": "x"}},
		{"list missing path", handleLinuxFSList, map[string]any{}},
		{"list path does not exist", handleLinuxFSList, map[string]any{"path": filepath.Join(dir, "nope")}},
		{"list target is a file", handleLinuxFSList, map[string]any{"path": existing}},
		{"list max_depth is 0", handleLinuxFSList, map[string]any{"path": dir, "max_depth": 0}},
		{"list limit is 0", handleLinuxFSList, map[string]any{"path": dir, "limit": 0}},
		{"list limit exceeds the upper bound", handleLinuxFSList, map[string]any{"path": dir, "limit": 20000}},
		{"list recursive has the wrong type", handleLinuxFSList, map[string]any{"path": dir, "recursive": "true"}},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := tc.fn(tc.params)
			if err == nil {
				t.Fatalf("expected an error but actually succeeded")
			}
			if !strings.Contains(err.Error(), "parameter") && !strings.Contains(err.Error(), "failed") &&
				!strings.Contains(err.Error(), "path") && !strings.Contains(err.Error(), "missing") {
				t.Errorf("the error message is not clear enough: %v", err)
			}
		})
	}
}

// TestLinuxFSCapabilitiesRegistered verifies that all three capabilities are registered with complete metadata.
func TestLinuxFSCapabilitiesRegistered(t *testing.T) {
	reg := NewRegistry()
	for _, name := range []string{"linux.fs.read", "linux.fs.write", "linux.fs.list"} {
		cap, ok := reg.Get(name)
		if !ok {
			t.Fatalf("capability %s is not registered", name)
		}
		if cap.Platform != PlatformLinux {
			t.Errorf("the platform of capability %s should be linux, actual %s", name, cap.Platform)
		}
		if strings.TrimSpace(cap.Description) == "" {
			t.Errorf("capability %s is missing Description", name)
		}
		if cap.Parameters == nil {
			t.Errorf("capability %s is missing Parameters", name)
		}
		if cap.Handler == nil {
			t.Errorf("capability %s is missing Handler", name)
		}
	}
}

// TestParseFileMode verifies the pure logic of parsing octal permissions.
func TestParseFileMode(t *testing.T) {
	ok := map[string]os.FileMode{
		"0644":  0o644,
		"644":   0o644,
		"0755":  0o755,
		"0600":  0o600,
		"0o600": 0o600,
		"0777":  0o777,
	}
	for in, want := range ok {
		got, err := parseFileMode(in)
		if err != nil {
			t.Errorf("parseFileMode(%q) unexpectedly errored: %v", in, err)
			continue
		}
		if got != want {
			t.Errorf("parseFileMode(%q) = %o, want %o", in, got, want)
		}
	}

	for _, bad := range []string{"", "abc", "0999", "0x1ff", "99999"} {
		if _, err := parseFileMode(bad); err == nil {
			t.Errorf("parseFileMode(%q) should report an error", bad)
		}
	}
}

// TestIsBinaryContent verifies the pure logic of binary detection.
func TestIsBinaryContent(t *testing.T) {
	if isBinaryContent([]byte("")) {
		t.Error("empty content should not be detected as binary")
	}
	if isBinaryContent([]byte("hello world")) {
		t.Error("valid UTF-8 text should not be detected as binary")
	}
	if !isBinaryContent([]byte{0x00}) {
		t.Error("content containing NUL bytes should be detected as binary")
	}
	if !isBinaryContent([]byte{0xFF, 0xFE}) {
		t.Error("invalid UTF-8 should be detected as binary")
	}
}

// TestResolveFSEncoding verifies the parsing of the encoding parameter.
func TestResolveFSEncoding(t *testing.T) {
	cases := map[string]string{
		"":       "utf-8",
		"utf-8":  "utf-8",
		"UTF-8":  "utf-8",
		"utf8":   "utf-8",
		"base64": "base64",
		"BASE64": "base64",
	}
	for in, want := range cases {
		params := map[string]any{}
		if in != "" {
			params["encoding"] = in
		}
		got, err := resolveFSEncoding(params, "utf-8")
		if err != nil {
			t.Errorf("resolveFSEncoding(%q) unexpectedly errored: %v", in, err)
			continue
		}
		if got != want {
			t.Errorf("resolveFSEncoding(%q) = %q, want %q", in, got, want)
		}
	}

	if _, err := resolveFSEncoding(map[string]any{"encoding": "gbk"}, "utf-8"); err == nil {
		t.Error("an unsupported encoding should report an error")
	}
	if _, err := resolveFSEncoding(map[string]any{"encoding": 1}, "utf-8"); err == nil {
		t.Error("a wrong encoding type should report an error")
	}
}
