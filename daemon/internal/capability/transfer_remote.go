// This file implements the common core of the "cross-machine direct file transfer" capability: pushing a local file (or directory) to a remote node,
// or pulling one back to the local machine from a remote node. Key differences from the existing fs.transfer.read/write:
//
//   - fs.transfer.read/write are "building blocks": one chunk at a time, with the bytes passing through the caller (Agent) context;
//   - fs.transfer.push/pull are "whole-machine transfer": the daemon loops over chunks internally, and the bytes only flow between the daemon and
//     the gateway, so the caller (Agent) only gets a summary (path, size, sha256),
//     and therefore transferring a 512 MiB file will not blow up the context.
//
// Data path:
//
//	local daemon --(HTTP, with the gateway Token)--> gateway /api/node/{node_id}/file-transfer/{upload|download}
//	                                        --(WebSocket)--> target node writes to disk / packages
//
// Important: this file has **no build tag** and is compiled into all platforms, so it may only use the standard library,
// and must not reference platform-specific symbols (requiredString, etc.). Parameter reading uniformly uses
// transferParamString / transferParamInt64 from transfer.go.
package capability

import (
	"archive/tar"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"haijunbot-daemon/internal/proxy"
)

// transferRemoteTimeout is the timeout for a single chunked HTTP request.
//
// Rationale: the max single chunk is 8 MiB (about 10.7 MiB after base64), which should complete within 60s even across
// the public internet; too short a timeout would wrongly kill slow links, and too long would stall the entire push/pull loop.
const transferRemoteTimeout = 60 * time.Second

// transferRemoteMaxFileSize is the maximum number of bytes allowed for a single direct transfer (512 MiB), consistent with the existing
// TransferMaxFileSize, to avoid the two sets of semantics drifting.
const transferRemoteMaxFileSize = TransferMaxFileSize

// transferRemoteResult is the summary structure that push/pull returns to the caller.
//
// It deliberately contains only metadata, with no file content bytes, guaranteeing that the Agent context is not polluted.
type transferRemoteResult struct {
	Direction  string `json:"direction"`   // "push" or "pull"
	Gateway    string `json:"gateway"`     // gateway address
	NodeID     string `json:"node_id"`     // target node ID
	Mode       string `json:"mode"`        // "file" or "dir"
	LocalPath  string `json:"local_path"`  // local path
	RemotePath string `json:"remote_path"` // remote (node-side converged) path
	Size       int64  `json:"size"`        // number of transferred bytes (for a directory, the tar package size)
	SHA256     string `json:"sha256"`      // whole-package SHA-256 (lowercase hex)
	Chunks     int    `json:"chunks"`      // number of chunks
	ChunkSize  int    `json:"chunk_size"`  // bytes per chunk
}

// transferRemoteParams are the normalized input parameters parsed from the capability parameters.
type transferRemoteParams struct {
	Gateway    string
	NodeID     string
	LocalPath  string
	RemotePath string
	Mode       string
	ChunkSize  int
}

// parseTransferRemoteParams parses and validates the common parameters of push/pull.
//
// Required: gateway, node_id, local_path, remote_path.
// Optional: mode (file|dir; when absent it is auto-inferred by whether local_path is a directory), chunk_size.
func parseTransferRemoteParams(params map[string]any) (*transferRemoteParams, error) {
	gateway, err := transferParamString(params, "gateway")
	if err != nil {
		return nil, err
	}
	gateway = strings.TrimRight(gateway, "/")
	if !strings.HasPrefix(gateway, "http://") && !strings.HasPrefix(gateway, "https://") {
		return nil, fmt.Errorf("parameter gateway must start with http:// or https://, actual %s", gateway)
	}

	nodeID, err := transferParamString(params, "node_id")
	if err != nil {
		return nil, err
	}

	localPath, err := transferParamString(params, "local_path")
	if err != nil {
		return nil, err
	}

	remotePath, err := transferParamString(params, "remote_path")
	if err != nil {
		return nil, err
	}

	mode := strings.ToLower(strings.TrimSpace(stringOrEmpty(params, "mode")))
	if mode == "" {
		// When not explicitly specified, infer by the local path type; in the push scenario the local machine is the authoritative source.
		info, statErr := os.Stat(localPath)
		if statErr == nil && info.IsDir() {
			mode = "dir"
		} else {
			mode = "file"
		}
	}
	if mode != "file" && mode != "dir" {
		return nil, fmt.Errorf("parameter mode can only be file or dir, actual %s", mode)
	}

	chunkSize, err := transferParamInt64(params, "chunk_size", int64(TransferDefaultChunkSize))
	if err != nil {
		return nil, err
	}
	normalized, err := NormalizeTransferChunkSize(int(chunkSize))
	if err != nil {
		return nil, err
	}

	return &transferRemoteParams{
		Gateway:    gateway,
		NodeID:     nodeID,
		LocalPath:  localPath,
		RemotePath: remotePath,
		Mode:       mode,
		ChunkSize:  normalized,
	}, nil
}

// stringOrEmpty reads an optional string parameter; when missing or non-string it returns an empty string.
func stringOrEmpty(params map[string]any, key string) string {
	v, ok := params[key]
	if !ok || v == nil {
		return ""
	}
	s, ok := v.(string)
	if !ok {
		return ""
	}
	return s
}

// transferRemoteURL concatenates the node file direct-transfer endpoint address on the gateway.
func transferRemoteURL(gateway, nodeID, action string) string {
	return fmt.Sprintf("%s/api/node/%s/file-transfer/%s", gateway, nodeID, action)
}

// transferRemotePost makes a POST request with the Token to the gateway, returning the parsed response body.
//
// The gateway response is uniformly shaped like {"success":bool,"data":{...}} or {"success":false,"error":{...}};
// this function returns an error with context when the HTTP status is not 200 or success=false.
func transferRemotePost(gateway, token, url string, payload map[string]any) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to serialize the request body: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to construct the request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)

	client := &http.Client{Timeout: transferRemoteTimeout, Transport: proxy.Transport()}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request to %s failed: %w", url, err)
	}
	defer resp.Body.Close()

	// The response body may be large (a download chunk contains base64 content), but it is bounded by the single-chunk limit, so a 32 MiB margin is given here.
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 32<<20))
	if err != nil {
		return nil, fmt.Errorf("failed to read the response from %s: %w", url, err)
	}

	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, fmt.Errorf("failed to parse the response from %s (HTTP %d): %s",
			url, resp.StatusCode, strings.TrimSpace(string(raw)))
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("request to %s failed (HTTP %d): %v",
			url, resp.StatusCode, parsed["error"])
	}
	if ok, _ := parsed["success"].(bool); !ok {
		return nil, fmt.Errorf("request to %s was rejected: %v", url, parsed["error"])
	}
	return parsed, nil
}

// transferRemoteData extracts the data sub-object from the gateway response.
func transferRemoteData(resp map[string]any) (map[string]any, error) {
	data, ok := resp["data"].(map[string]any)
	if !ok {
		return nil, fmt.Errorf("the response is missing the data field: %v", resp)
	}
	return data, nil
}

// transferRemoteInt64 reads an integer field from data (JSON numbers are float64).
func transferRemoteInt64(data map[string]any, key string) (int64, error) {
	v, ok := data[key]
	if !ok || v == nil {
		return 0, fmt.Errorf("the response is missing field %s", key)
	}
	switch n := v.(type) {
	case float64:
		return int64(n), nil
	case int64:
		return n, nil
	case int:
		return int64(n), nil
	default:
		return 0, fmt.Errorf("field %s is not a number: %T", key, v)
	}
}

// transferPackDirToTar packs a directory into a tar byte stream, with the top-level directory name taken from the directory basename.
//
// Packing into memory rather than a temporary file: the single direct-transfer limit is 512 MiB, and it is only called once before push,
// in exchange for a simpler implementation and no leftover temporary files.
func transferPackDirToTar(dir string) ([]byte, error) {
	absDir, err := filepath.Abs(dir)
	if err != nil {
		return nil, fmt.Errorf("failed to resolve the directory's absolute path: %w", err)
	}
	base := filepath.Base(absDir)

	var buf bytes.Buffer
	tw := tar.NewWriter(&buf)

	walkErr := filepath.Walk(absDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(absDir, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}
		// Paths inside the tar uniformly use forward slashes, with the directory basename as the top level.
		name := base + "/" + filepath.ToSlash(rel)

		hdr, err := tar.FileInfoHeader(info, "")
		if err != nil {
			return err
		}
		hdr.Name = name
		if info.IsDir() {
			hdr.Name += "/"
		}
		if err := tw.WriteHeader(hdr); err != nil {
			return err
		}
		if info.IsDir() {
			return nil
		}

		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()
		if _, err := io.Copy(tw, f); err != nil {
			return err
		}
		return nil
	})
	if walkErr != nil {
		return nil, fmt.Errorf("failed to pack directory %s: %w", dir, walkErr)
	}
	if err := tw.Close(); err != nil {
		return nil, fmt.Errorf("failed to close the tar writer: %w", err)
	}
	return buf.Bytes(), nil
}

// transferUnpackTarToDir unpacks a tar byte stream into the target directory.
//
// Security: any member that escapes the target directory is rejected (to prevent tar traversal), equivalent to the gateway-side _safe_extract_tar.
func transferUnpackTarToDir(data []byte, destDir string) error {
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", destDir, err)
	}
	root, err := filepath.Abs(destDir)
	if err != nil {
		return fmt.Errorf("failed to resolve the directory's absolute path: %w", err)
	}

	tr := tar.NewReader(bytes.NewReader(data))
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("failed to read the tar: %w", err)
		}

		target := filepath.Join(root, filepath.FromSlash(hdr.Name))
		rel, err := filepath.Rel(root, target)
		if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
			return fmt.Errorf("tar member %s escapes the target directory %s", hdr.Name, destDir)
		}

		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0o755); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", target, err)
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return fmt.Errorf("failed to create directory %s: %w", filepath.Dir(target), err)
			}
			out, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, os.FileMode(hdr.Mode)&0o777)
			if err != nil {
				return fmt.Errorf("failed to create file %s: %w", target, err)
			}
			if _, err := io.Copy(out, tr); err != nil {
				out.Close()
				return fmt.Errorf("failed to write file %s: %w", target, err)
			}
			if err := out.Close(); err != nil {
				return fmt.Errorf("failed to close file %s: %w", target, err)
			}
		default:
			// Symbolic links, device files, etc. are all skipped: direct transfer only moves ordinary files and directories.
			continue
		}
	}
	return nil
}

// transferPushFile uploads a byte slice to the remote end in chunks.
//
// It returns the number of uploaded bytes and the number of chunks. The last chunk carries final=true (in dir mode this triggers remote unpacking).
func transferPushFile(
	gateway, token, nodeID, remotePath, mode string,
	data []byte, chunkSize int,
) (int, error) {
	total := len(data)
	if int64(total) > transferRemoteMaxFileSize {
		return 0, fmt.Errorf("the content to transfer %d bytes exceeds the limit of %d bytes (512 MiB)",
			total, transferRemoteMaxFileSize)
	}

	url := transferRemoteURL(gateway, nodeID, "upload")
	offset := 0
	chunks := 0
	for offset < total || (total == 0 && chunks == 0) {
		end := offset + chunkSize
		if end > total {
			end = total
		}
		chunk := data[offset:end]
		isLast := end >= total

		payload := map[string]any{
			"path":     remotePath,
			"data":     TransferEncodeBase64(chunk),
			"offset":   offset,
			"mode":     mode,
			"truncate": offset == 0,
			"final":    isLast,
		}
		if _, err := transferRemotePost(gateway, token, url, payload); err != nil {
			return chunks, err
		}

		chunks++
		offset = end
		if total == 0 {
			break
		}
	}
	return chunks, nil
}

// transferPullFile pulls content from the remote end in chunks, returning the complete bytes and the number of chunks.
func transferPullFile(
	gateway, token, nodeID, remotePath, mode string,
	chunkSize int,
) ([]byte, int, error) {
	url := transferRemoteURL(gateway, nodeID, "download")

	var buf bytes.Buffer
	offset := int64(0)
	chunks := 0
	for {
		payload := map[string]any{
			"path":   remotePath,
			"offset": offset,
			"length": chunkSize,
			"mode":   mode,
		}
		resp, err := transferRemotePost(gateway, token, url, payload)
		if err != nil {
			return nil, chunks, err
		}
		data, err := transferRemoteData(resp)
		if err != nil {
			return nil, chunks, err
		}

		b64, _ := data["data"].(string)
		chunk, err := TransferDecodeBase64(b64)
		if err != nil {
			return nil, chunks, err
		}
		if int64(buf.Len())+int64(len(chunk)) > transferRemoteMaxFileSize {
			return nil, chunks, fmt.Errorf("the pulled content exceeds the limit of %d bytes (512 MiB)",
				transferRemoteMaxFileSize)
		}
		buf.Write(chunk)
		chunks++

		eof, _ := data["eof"].(bool)
		if eof {
			break
		}
		offset += int64(len(chunk))
		if len(chunk) == 0 {
			// Defensive: the remote end did not mark eof but returned an empty chunk, to avoid an infinite loop.
			break
		}
	}
	return buf.Bytes(), chunks, nil
}

// handleTransferPush is the common implementation of fs.transfer.push: local -> remote node.
func handleTransferPush(params map[string]any) (any, error) {
	p, err := parseTransferRemoteParams(params)
	if err != nil {
		return nil, err
	}

	token, ok := browserExtToken(p.Gateway)
	if !ok || token == "" {
		return nil, fmt.Errorf("the gateway %s has no available credentials, cannot initiate a direct transfer; please log in and push the login information first", p.Gateway)
	}

	var payload []byte
	switch p.Mode {
	case "file":
		info, err := os.Stat(p.LocalPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read the local file %s: %w", p.LocalPath, err)
		}
		if info.IsDir() {
			return nil, fmt.Errorf("the local path %s is a directory, please set mode to dir", p.LocalPath)
		}
		if info.Size() > transferRemoteMaxFileSize {
			return nil, fmt.Errorf("file %s size %d bytes exceeds the limit of %d bytes (512 MiB)",
				p.LocalPath, info.Size(), transferRemoteMaxFileSize)
		}
		payload, err = os.ReadFile(p.LocalPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read the local file %s: %w", p.LocalPath, err)
		}
	case "dir":
		info, err := os.Stat(p.LocalPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read the local directory %s: %w", p.LocalPath, err)
		}
		if !info.IsDir() {
			return nil, fmt.Errorf("the local path %s is not a directory, please set mode to file", p.LocalPath)
		}
		payload, err = transferPackDirToTar(p.LocalPath)
		if err != nil {
			return nil, err
		}
		if int64(len(payload)) > transferRemoteMaxFileSize {
			return nil, fmt.Errorf("after packing, the directory is %d bytes, exceeding the limit of %d bytes (512 MiB)",
				len(payload), transferRemoteMaxFileSize)
		}
	}

	chunks, err := transferPushFile(
		p.Gateway, token, p.NodeID, p.RemotePath, p.Mode, payload, p.ChunkSize,
	)
	if err != nil {
		return nil, err
	}

	return &transferRemoteResult{
		Direction:  "push",
		Gateway:    p.Gateway,
		NodeID:     p.NodeID,
		Mode:       p.Mode,
		LocalPath:  p.LocalPath,
		RemotePath: p.RemotePath,
		Size:       int64(len(payload)),
		SHA256:     TransferBytesSHA256(payload),
		Chunks:     chunks,
		ChunkSize:  p.ChunkSize,
	}, nil
}

// handleTransferPull is the common implementation of fs.transfer.pull: remote node -> local.
func handleTransferPull(params map[string]any) (any, error) {
	p, err := parseTransferRemoteParams(params)
	if err != nil {
		return nil, err
	}

	token, ok := browserExtToken(p.Gateway)
	if !ok || token == "" {
		return nil, fmt.Errorf("the gateway %s has no available credentials, cannot initiate a direct transfer; please log in and push the login information first", p.Gateway)
	}

	payload, chunks, err := transferPullFile(
		p.Gateway, token, p.NodeID, p.RemotePath, p.Mode, p.ChunkSize,
	)
	if err != nil {
		return nil, err
	}

	// Write to disk: in file mode, write the file directly; in dir mode, unpack into the local_path directory.
	if p.Mode == "dir" {
		if err := transferUnpackTarToDir(payload, p.LocalPath); err != nil {
			return nil, err
		}
	} else {
		if err := os.MkdirAll(filepath.Dir(p.LocalPath), 0o755); err != nil {
			return nil, fmt.Errorf("failed to create directory %s: %w", filepath.Dir(p.LocalPath), err)
		}
		if err := os.WriteFile(p.LocalPath, payload, 0o644); err != nil {
			return nil, fmt.Errorf("failed to write the local file %s: %w", p.LocalPath, err)
		}
	}

	return &transferRemoteResult{
		Direction:  "pull",
		Gateway:    p.Gateway,
		NodeID:     p.NodeID,
		Mode:       p.Mode,
		LocalPath:  p.LocalPath,
		RemotePath: p.RemotePath,
		Size:       int64(len(payload)),
		SHA256:     TransferBytesSHA256(payload),
		Chunks:     chunks,
		ChunkSize:  p.ChunkSize,
	}, nil
}

// registerTransferRemote registers the cross-machine direct file transfer capability (push/pull) for the specified platform.
//
// Platform differences appear only in the Platform field; the logic is fully shared, so registry_*.go passes in platform.
func registerTransferRemote(reg *Registry, platform Platform) {
	_ = reg.Register(Capability{
		Name: "fs.transfer.push",
		Description: "Directly transfer a local file (or directory) to a remote node: the daemon loops over chunks internally, " +
			"with the bytes not passing through the caller context, returning only a summary (path, size, sha256). " +
			"A directory is automatically packed into a tar and unpacked on the remote end. Single-transfer limit 512 MiB.",
		Platform: platform,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"gateway": map[string]any{
					"type":        "string",
					"description": "Gateway address (such as http://127.0.0.1:8000), which must start with http:// or https://.",
				},
				"node_id": map[string]any{
					"type":        "string",
					"description": "Target node ID (assigned by the gateway).",
				},
				"local_path": map[string]any{
					"type":        "string",
					"description": "Local source path (file or directory).",
				},
				"remote_path": map[string]any{
					"type": "string",
					"description": "Remote target path. It is converged by the node under ~/.haijunbot/transfers: " +
						"an absolute path keeps its structure with the root stripped, and a relative path is concatenated directly.",
				},
				"mode": map[string]any{
					"type":        "string",
					"description": "Transfer mode: file (single file) or dir (directory, automatically tar-packed). When absent, inferred from the local_path type.",
				},
				"chunk_size": map[string]any{
					"type":        "integer",
					"description": "Chunk byte size, default 1048576 (1 MiB), max 8388608 (8 MiB).",
				},
			},
			"required": []string{"gateway", "node_id", "local_path", "remote_path"},
		},
		Handler: handleTransferPush,
	})

	_ = reg.Register(Capability{
		Name: "fs.transfer.pull",
		Description: "Directly transfer a file (or directory) from a remote node back to the local machine: the daemon loops over chunks to pull, " +
			"with the bytes not passing through the caller context, returning only a summary (path, size, sha256). " +
			"A directory is packed into a tar on the remote end and unpacked on the local machine. Single-transfer limit 512 MiB.",
		Platform: platform,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"gateway": map[string]any{
					"type":        "string",
					"description": "Gateway address (such as http://127.0.0.1:8000), which must start with http:// or https://.",
				},
				"node_id": map[string]any{
					"type":        "string",
					"description": "Source node ID (assigned by the gateway).",
				},
				"local_path": map[string]any{
					"type":        "string",
					"description": "Local target path (in dir mode, the unpacking directory).",
				},
				"remote_path": map[string]any{
					"type": "string",
					"description": "Remote source path. It is converged by the node under ~/.haijunbot/transfers: " +
						"an absolute path keeps its structure with the root stripped, and a relative path is concatenated directly.",
				},
				"mode": map[string]any{
					"type":        "string",
					"description": "Transfer mode: file (single file) or dir (directory, automatically tar-packed on the remote end). When absent, inferred from the local_path type.",
				},
				"chunk_size": map[string]any{
					"type":        "integer",
					"description": "Chunk byte size, default 1048576 (1 MiB), max 8388608 (8 MiB).",
				},
			},
			"required": []string{"gateway", "node_id", "local_path", "remote_path"},
		},
		Handler: handleTransferPull,
	})
}
