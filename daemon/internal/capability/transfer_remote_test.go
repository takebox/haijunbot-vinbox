// This file unit-tests the "cross-machine direct file transfer" capability (fs.transfer.push / fs.transfer.pull).
//
// Test strategy: use httptest to start a fake gateway that simulates the /api/node/{id}/file-transfer/{upload|download}
// endpoints, assembling chunks by offset into an in-memory file (simulating remote disk writes), then verify:
//  1. push: after a local file is uploaded in chunks, the remote assembled content matches the source, and the returned summary contains no content;
//  2. push directory: automatically tar-packed, and the remote tar can unpack the original files;
//  3. pull: pull content from the fake gateway in chunks and write it to disk, matching the source;
//  4. pull directory: the remote tar unpacks successfully on the local machine;
//  5. an explicit error when credentials are missing;
//  6. parameter validation (missing gateway / invalid mode / non-http prefix).
//
// Note: this file has no build tag and compiles on both Linux and Windows; it depends only on the standard library.

package capability

import (
	"archive/tar"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeGateway is a fake gateway that simulates the node file direct-transfer endpoints.
//
// It assembles uploaded chunks by offset into the remote buffer (simulating remote disk writes),
// and supports downloading that buffer in chunks by offset/length.
type fakeGateway struct {
	remote   []byte // remote "file" content (in dir mode, the tar bytes)
	mode     string
	uploads  int // number of upload chunks received
	download int // number of download chunks received
}

func (f *fakeGateway) handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Validate the Token header, ensuring the capability really carries credentials.
		if r.Header.Get("Authorization") != "Bearer test-token" {
			http.Error(w, `{"success":false,"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			http.Error(w, `{"success":false,"error":"bad json"}`, http.StatusBadRequest)
			return
		}

		switch {
		case strings.HasSuffix(r.URL.Path, "/file-transfer/upload"):
			f.handleUpload(w, payload)
		case strings.HasSuffix(r.URL.Path, "/file-transfer/download"):
			f.handleDownload(w, payload)
		default:
			http.Error(w, `{"success":false,"error":"not found"}`, http.StatusNotFound)
		}
	}
}

func (f *fakeGateway) handleUpload(w http.ResponseWriter, payload map[string]any) {
	rawData, _ := payload["data"].(string)
	chunk, err := base64.StdEncoding.DecodeString(rawData)
	if err != nil {
		http.Error(w, `{"success":false,"error":"bad base64"}`, http.StatusBadRequest)
		return
	}
	offset := int(toInt64(payload["offset"]))

	// The first chunk (truncate=true) clears the remote buffer, simulating the gateway-side truncate semantics.
	if trunc, _ := payload["truncate"].(bool); trunc {
		f.remote = nil
	}
	// Extend by offset and write.
	if need := offset + len(chunk); need > len(f.remote) {
		grown := make([]byte, need)
		copy(grown, f.remote)
		f.remote = grown
	}
	copy(f.remote[offset:], chunk)

	f.uploads++
	writeJSON(w, map[string]any{
		"success": true,
		"data": map[string]any{
			"path":   payload["path"],
			"offset": offset,
			"size":   len(f.remote),
		},
	})
}

func (f *fakeGateway) handleDownload(w http.ResponseWriter, payload map[string]any) {
	offset := int(toInt64(payload["offset"]))
	length := int(toInt64(payload["length"]))
	if offset > len(f.remote) {
		offset = len(f.remote)
	}
	end := offset + length
	if end > len(f.remote) {
		end = len(f.remote)
	}
	chunk := f.remote[offset:end]
	eof := end >= len(f.remote)

	f.download++
	writeJSON(w, map[string]any{
		"success": true,
		"data": map[string]any{
			"path":   payload["path"],
			"offset": offset,
			"size":   len(f.remote),
			"eof":    eof,
			"data":   base64.StdEncoding.EncodeToString(chunk),
		},
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

// toInt64 converts a JSON number (float64) into an int64.
func toInt64(v any) int64 {
	if n, ok := v.(float64); ok {
		return int64(n)
	}
	return 0
}

// setupFakeGateway starts the fake gateway and points the credential provider at test-token, restoring it automatically at the end of the test.
func setupFakeGateway(t *testing.T, f *fakeGateway) string {
	t.Helper()
	srv := httptest.NewServer(f.handler())
	t.Cleanup(srv.Close)

	SetBrowserExtCredentialProvider(func(gateway string) (string, bool) {
		return "test-token", true
	})
	t.Cleanup(func() { SetBrowserExtCredentialProvider(nil) })
	return srv.URL
}

// TestTransferPushFileChunked verifies a single-file push: after chunked upload the remote content matches the source,
// and the returned summary contains only metadata, no content bytes.
func TestTransferPushFileChunked(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "src.bin")
	// 3.5 chunks of content, covering both the "divisible" and "tail chunk" boundaries.
	content := bytes.Repeat([]byte("abcdefgh"), 1000) // 8000 bytes
	if err := os.WriteFile(src, content, 0o644); err != nil {
		t.Fatal(err)
	}

	f := &fakeGateway{}
	gateway := setupFakeGateway(t, f)

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.push", map[string]any{
		"gateway":     gateway,
		"node_id":     "node-1",
		"local_path":  src,
		"remote_path": "/data/src.bin",
		"chunk_size":  float64(3000), // 3 chunks: 3000+3000+2000
	})
	if !res.Success {
		t.Fatalf("push failed: %s", res.Error)
	}

	if !bytes.Equal(f.remote, content) {
		t.Fatalf("remote content differs from source: expected %d bytes, actual %d bytes", len(content), len(f.remote))
	}
	if f.uploads != 3 {
		t.Fatalf("expected 3 upload chunks, actual %d", f.uploads)
	}

	// Summary validation: contains sha256 and size, and no content.
	summary, ok := res.Data.(*transferRemoteResult)
	if !ok {
		t.Fatalf("unexpected return type: %T", res.Data)
	}
	if summary.SHA256 != TransferBytesSHA256(content) {
		t.Fatalf("sha256 differs: %s", summary.SHA256)
	}
	if summary.Size != int64(len(content)) {
		t.Fatalf("size differs: %d", summary.Size)
	}
	if summary.Direction != "push" || summary.Mode != "file" {
		t.Fatalf("summary direction/mode unexpected: %+v", summary)
	}
}

// TestTransferPushEmptyFile verifies that an empty file can also be pushed normally (at least one chunk is sent).
func TestTransferPushEmptyFile(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "empty.bin")
	if err := os.WriteFile(src, nil, 0o644); err != nil {
		t.Fatal(err)
	}

	f := &fakeGateway{}
	gateway := setupFakeGateway(t, f)

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.push", map[string]any{
		"gateway":     gateway,
		"node_id":     "node-1",
		"local_path":  src,
		"remote_path": "empty.bin",
	})
	if !res.Success {
		t.Fatalf("pushing the empty file failed: %s", res.Error)
	}
	if len(f.remote) != 0 {
		t.Fatalf("the remote end should be 0 bytes for an empty file, actual %d", len(f.remote))
	}
	if f.uploads != 1 {
		t.Fatalf("expected 1 upload for an empty file, actual %d", f.uploads)
	}
}

// TestTransferPushDirectoryPacksTar verifies a directory push: automatically tar-packed and the remote can unpack the original files.
func TestTransferPushDirectoryPacksTar(t *testing.T) {
	dir := t.TempDir()
	srcDir := filepath.Join(dir, "mydir")
	if err := os.MkdirAll(filepath.Join(srcDir, "sub"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "a.txt"), []byte("alpha"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "sub", "b.txt"), []byte("beta"), 0o644); err != nil {
		t.Fatal(err)
	}

	f := &fakeGateway{}
	gateway := setupFakeGateway(t, f)

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.push", map[string]any{
		"gateway":     gateway,
		"node_id":     "node-1",
		"local_path":  srcDir,
		"remote_path": "mydir",
		"chunk_size":  float64(512), // force multiple chunks, to verify tar chunk reassembly
	})
	if !res.Success {
		t.Fatalf("pushing the directory failed: %s", res.Error)
	}

	// What the remote receives should be a complete tar, from which two files can be read after unpacking.
	got := map[string]string{}
	tr := tar.NewReader(bytes.NewReader(f.remote))
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("failed to parse the remote tar: %v", err)
		}
		if hdr.Typeflag != tar.TypeReg {
			continue
		}
		b, _ := io.ReadAll(tr)
		got[filepath.Base(hdr.Name)] = string(b)
	}
	if got["a.txt"] != "alpha" || got["b.txt"] != "beta" {
		t.Fatalf("remote tar content unexpected: %+v", got)
	}

	summary := res.Data.(*transferRemoteResult)
	if summary.Mode != "dir" {
		t.Fatalf("expected mode=dir, actual %s", summary.Mode)
	}
}

// TestTransferPullFileChunked verifies a single-file pull: chunked pull written to disk with matching content.
func TestTransferPullFileChunked(t *testing.T) {
	content := bytes.Repeat([]byte("0123456789"), 500) // 5000 bytes
	f := &fakeGateway{remote: content}
	gateway := setupFakeGateway(t, f)

	dir := t.TempDir()
	dst := filepath.Join(dir, "out.bin")

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.pull", map[string]any{
		"gateway":     gateway,
		"node_id":     "node-1",
		"local_path":  dst,
		"remote_path": "src.bin",
		"chunk_size":  float64(2000), // 3 chunks
	})
	if !res.Success {
		t.Fatalf("pull failed: %s", res.Error)
	}

	got, err := os.ReadFile(dst)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, content) {
		t.Fatalf("content written to disk differs from remote: expected %d bytes, actual %d bytes", len(content), len(got))
	}
	if f.download != 3 {
		t.Fatalf("expected 3 download chunks, actual %d", f.download)
	}

	summary := res.Data.(*transferRemoteResult)
	if summary.SHA256 != TransferBytesSHA256(content) {
		t.Fatalf("summary sha256 differs: %s", summary.SHA256)
	}
}

// TestTransferPullDirectoryUnpacksTar verifies a directory pull: the remote tar unpacks successfully on the local machine.
func TestTransferPullDirectoryUnpacksTar(t *testing.T) {
	// First build a tar as the "remote directory".
	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)
	payload := []byte("remote-content")
	hdr := &tar.Header{
		Name:     "remote/hello.txt",
		Mode:     0o644,
		Size:     int64(len(payload)),
		Typeflag: tar.TypeReg,
	}
	if err := tw.WriteHeader(hdr); err != nil {
		t.Fatal(err)
	}
	if _, err := tw.Write(payload); err != nil {
		t.Fatal(err)
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}

	f := &fakeGateway{remote: buf.Bytes()}
	gateway := setupFakeGateway(t, f)

	dir := t.TempDir()
	dst := filepath.Join(dir, "unpacked")

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.pull", map[string]any{
		"gateway":     gateway,
		"node_id":     "node-1",
		"local_path":  dst,
		"remote_path": "remote",
		"mode":        "dir",
	})
	if !res.Success {
		t.Fatalf("pulling the directory failed: %s", res.Error)
	}

	got, err := os.ReadFile(filepath.Join(dst, "remote", "hello.txt"))
	if err != nil {
		t.Fatalf("failed to read the unpacked file: %v", err)
	}
	if string(got) != "remote-content" {
		t.Fatalf("unpacked content unexpected: %s", got)
	}
}

// TestTransferRequiresCredential verifies that without credentials it must report an explicit error.
func TestTransferRequiresCredential(t *testing.T) {
	SetBrowserExtCredentialProvider(nil)
	t.Cleanup(func() { SetBrowserExtCredentialProvider(nil) })

	reg := NewRegistry()
	res := reg.Execute("fs.transfer.push", map[string]any{
		"gateway":     "http://127.0.0.1:8000",
		"node_id":     "node-1",
		"local_path":  "/tmp/x",
		"remote_path": "x",
	})
	if res.Success {
		t.Fatalf("it should not succeed without credentials")
	}
	if !strings.Contains(res.Error, "credential") {
		t.Fatalf("the error message should indicate missing credentials, actual: %s", res.Error)
	}
}

// TestTransferParamValidation verifies parameter validation: missing gateway, invalid mode, non-http prefix.
func TestTransferParamValidation(t *testing.T) {
	SetBrowserExtCredentialProvider(func(string) (string, bool) { return "t", true })
	t.Cleanup(func() { SetBrowserExtCredentialProvider(nil) })

	reg := NewRegistry()

	cases := []struct {
		name   string
		params map[string]any
		want   string
	}{
		{
			name: "missing gateway",
			params: map[string]any{
				"node_id": "n", "local_path": "/tmp/x", "remote_path": "x",
			},
			want: "gateway",
		},
		{
			name: "gateway with a non-http prefix",
			params: map[string]any{
				"gateway": "127.0.0.1:8000", "node_id": "n",
				"local_path": "/tmp/x", "remote_path": "x",
			},
			want: "http://",
		},
		{
			name: "invalid mode",
			params: map[string]any{
				"gateway": "http://127.0.0.1:8000", "node_id": "n",
				"local_path": "/tmp/x", "remote_path": "x", "mode": "weird",
			},
			want: "mode",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := reg.Execute("fs.transfer.push", tc.params)
			if res.Success {
				t.Fatalf("expected failure, actual success: %+v", res.Data)
			}
			if !strings.Contains(res.Error, tc.want) {
				t.Fatalf("the error message should contain %q, actual: %s", tc.want, res.Error)
			}
		})
	}
}
