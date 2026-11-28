//go:build linux

package capability

import (
	"encoding/base64"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

// Default and maximum constraints for the file system capabilities.
const (
	// linuxFSDefaultReadLimit is the default number of bytes to read for linux.fs.read when limit is not specified.
	linuxFSDefaultReadLimit = 1 << 20 // 1 MiB
	// linuxFSMaxReadLimit is the maximum number of bytes allowed for linux.fs.read, to prevent a single read from blowing up memory.
	linuxFSMaxReadLimit = 8 << 20 // 8 MiB
	// linuxFSDefaultListLimit is the default upper bound on the number of entries for linux.fs.list when limit is not specified.
	linuxFSDefaultListLimit = 500
	// linuxFSMaxListLimit is the maximum upper bound on the number of entries allowed for linux.fs.list.
	linuxFSMaxListLimit = 10000
	// linuxFSDefaultMode is the default file permission (octal string) for linux.fs.write when mode is not specified.
	linuxFSDefaultMode = "0644"
)

// registerLinuxFS registers the Linux file system capabilities.
func registerLinuxFS(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "linux.fs.read",
		Description: "Reads file content on Linux. Supports segmented reading via offset/limit; " +
			"when the content contains NUL bytes, it is automatically returned as base64 with is_binary=true.",
		Platform: PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The file path to read (an absolute path or relative to the daemon working directory).",
				},
				"offset": map[string]any{
					"type":        "integer",
					"description": "Starting offset in bytes, default 0.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Maximum number of bytes to read, default 1048576 (1 MiB), maximum 8388608 (8 MiB).",
				},
				"encoding": map[string]any{
					"type":        "string",
					"description": "The encoding of the returned content, supporting utf-8 (default) and base64.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleLinuxFSRead,
	})

	_ = reg.Register(Capability{
		Name:        "linux.fs.write",
		Description: "Writes file content on Linux. Supports overwrite/append, automatic creation of parent directories, and custom permissions.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The file path to write.",
				},
				"content": map[string]any{
					"type":        "string",
					"description": "The content to write; when encoding=base64, it is base64-decoded and then written.",
				},
				"encoding": map[string]any{
					"type":        "string",
					"description": "The encoding of content, supporting utf-8 (default) and base64.",
				},
				"append": map[string]any{
					"type":        "boolean",
					"description": "Whether to append, default false (overwrite).",
				},
				"create_dirs": map[string]any{
					"type":        "boolean",
					"description": "Whether to automatically create parent directories, default false.",
				},
				"mode": map[string]any{
					"type":        "string",
					"description": "The octal string for file permissions, default 0644; only takes effect when creating a new file.",
				},
			},
			"required": []string{"path", "content"},
		},
		Handler: handleLinuxFSWrite,
	})

	_ = reg.Register(Capability{
		Name:        "linux.fs.list",
		Description: "Lists the contents of a directory on Linux, supporting recursion and depth limits.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The directory path to list.",
				},
				"recursive": map[string]any{
					"type":        "boolean",
					"description": "Whether to list subdirectories recursively, default false.",
				},
				"max_depth": map[string]any{
					"type":        "integer",
					"description": "The maximum depth when recursing, default 1 (current level only); ignored when recursive=false.",
				},
				"show_hidden": map[string]any{
					"type":        "boolean",
					"description": "Whether to include hidden items starting with a dot, default true.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Upper bound on the number of returned entries, default 500, maximum 10000.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleLinuxFSList,
	})
}

// handleLinuxFSRead is the implementation of linux.fs.read.
func handleLinuxFSRead(params map[string]any) (any, error) {
	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	offset, err := optionalInt(params, "offset", 0)
	if err != nil {
		return nil, err
	}
	if offset < 0 {
		return nil, fmt.Errorf("parameter offset cannot be negative, actual %d", offset)
	}

	limit, err := optionalInt(params, "limit", linuxFSDefaultReadLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > linuxFSMaxReadLimit {
		return nil, fmt.Errorf("parameter limit exceeds the upper bound %d bytes, actual %d", linuxFSMaxReadLimit, limit)
	}

	encoding, err := resolveFSEncoding(params, "utf-8")
	if err != nil {
		return nil, err
	}

	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file %s: %w", path, err)
	}
	if info.IsDir() {
		return nil, fmt.Errorf("path %s is a directory and cannot be read with linux.fs.read; use linux.fs.list instead", path)
	}

	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open file %s: %w", path, err)
	}
	defer f.Close()

	if offset > 0 {
		if _, err := f.Seek(int64(offset), io.SeekStart); err != nil {
			return nil, fmt.Errorf("failed to seek to offset %d: %w", offset, err)
		}
	}

	// Read 1 extra byte to determine whether there is remaining content (i.e., whether truncation occurred).
	buf := make([]byte, limit+1)
	n, err := io.ReadFull(f, buf)
	if err != nil && err != io.EOF && err != io.ErrUnexpectedEOF {
		return nil, fmt.Errorf("failed to read file %s: %w", path, err)
	}

	truncated := false
	if n > limit {
		n = limit
		truncated = true
	}
	data := buf[:n]

	isBinary := isBinaryContent(data)
	content := string(data)
	if isBinary && encoding == "utf-8" {
		// Binary content cannot be safely represented as UTF-8, so automatically fall back to base64.
		content = base64.StdEncoding.EncodeToString(data)
	} else if encoding == "base64" {
		content = base64.StdEncoding.EncodeToString(data)
	}

	return map[string]any{
		"path":       path,
		"size":       info.Size(),
		"offset":     offset,
		"read_bytes": n,
		"content":    content,
		"truncated":  truncated,
		"is_binary":  isBinary,
		"encoding":   chooseReportedEncoding(encoding, isBinary),
	}, nil
}

// handleLinuxFSWrite is the implementation of linux.fs.write.
func handleLinuxFSWrite(params map[string]any) (any, error) {
	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	// content is allowed to be an empty string (e.g., creating an empty file), so requiredString is not used here.
	rawContent, ok := params["content"]
	if !ok || rawContent == nil {
		return nil, fmt.Errorf("missing required parameter content")
	}
	contentStr, ok := rawContent.(string)
	if !ok {
		return nil, fmt.Errorf("parameter content must be a string, actual %T", rawContent)
	}

	encoding, err := resolveFSEncoding(params, "utf-8")
	if err != nil {
		return nil, err
	}

	appendMode, err := optionalBool(params, "append", false)
	if err != nil {
		return nil, err
	}

	createDirs, err := optionalBool(params, "create_dirs", false)
	if err != nil {
		return nil, err
	}

	modeStr, err := optionalString(params, "mode")
	if err != nil {
		return nil, err
	}
	if modeStr == "" {
		modeStr = linuxFSDefaultMode
	}
	mode, err := parseFileMode(modeStr)
	if err != nil {
		return nil, err
	}

	var payload []byte
	if encoding == "base64" {
		decoded, err := base64.StdEncoding.DecodeString(strings.TrimSpace(contentStr))
		if err != nil {
			return nil, fmt.Errorf("parameter content is not valid base64: %w", err)
		}
		payload = decoded
	} else {
		payload = []byte(contentStr)
	}

	_, statErr := os.Stat(path)
	existed := statErr == nil

	if createDirs {
		dir := filepath.Dir(path)
		if dir != "" && dir != "." {
			if err := os.MkdirAll(dir, 0o755); err != nil {
				return nil, fmt.Errorf("failed to create parent directory %s: %w", dir, err)
			}
		}
	}

	flags := os.O_WRONLY | os.O_CREATE
	if appendMode {
		flags |= os.O_APPEND
	} else {
		flags |= os.O_TRUNC
	}

	f, err := os.OpenFile(path, flags, mode)
	if err != nil {
		return nil, fmt.Errorf("failed to open file %s: %w", path, err)
	}

	written, writeErr := f.Write(payload)
	closeErr := f.Close()
	if writeErr != nil {
		return nil, fmt.Errorf("failed to write file %s: %w", path, writeErr)
	}
	if closeErr != nil {
		return nil, fmt.Errorf("failed to close file %s: %w", path, closeErr)
	}

	return map[string]any{
		"path":          path,
		"written_bytes": written,
		"created":       !existed,
		"appended":      appendMode,
	}, nil
}

// handleLinuxFSList is the implementation of linux.fs.list.
func handleLinuxFSList(params map[string]any) (any, error) {
	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	recursive, err := optionalBool(params, "recursive", false)
	if err != nil {
		return nil, err
	}

	maxDepth, err := optionalInt(params, "max_depth", 1)
	if err != nil {
		return nil, err
	}
	if maxDepth <= 0 {
		return nil, fmt.Errorf("parameter max_depth must be a positive integer, actual %d", maxDepth)
	}

	showHidden, err := optionalBool(params, "show_hidden", true)
	if err != nil {
		return nil, err
	}

	limit, err := optionalInt(params, "limit", linuxFSDefaultListLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > linuxFSMaxListLimit {
		return nil, fmt.Errorf("parameter limit exceeds the upper bound %d, actual %d", linuxFSMaxListLimit, limit)
	}

	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to access path %s: %w", path, err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("path %s is not a directory", path)
	}

	// When not recursive, the depth is fixed at 1, meaning only the current level is listed.
	if !recursive {
		maxDepth = 1
	}

	entries := make([]map[string]any, 0, 16)

	truncated, err := collectFSEntries(path, 1, maxDepth, showHidden, limit, &entries)
	if err != nil {
		return nil, err
	}

	sort.Slice(entries, func(i, j int) bool {
		return entries[i]["path"].(string) < entries[j]["path"].(string)
	})

	return map[string]any{
		"path":      path,
		"entries":   entries,
		"count":     len(entries),
		"truncated": truncated,
	}, nil
}

// collectFSEntries recursively collects directory entries, returning early with truncated set when the limit is reached.
//
// depth is the current level depth (starting from 1), and maxDepth is the maximum allowed depth.
func collectFSEntries(dir string, depth, maxDepth int, showHidden bool, limit int, out *[]map[string]any) (bool, error) {
	if depth > maxDepth {
		return false, nil
	}

	items, err := os.ReadDir(dir)
	if err != nil {
		// Skip when a subdirectory cannot be read (permissions, etc.), without interrupting the overall listing.
		if depth == 1 {
			return false, fmt.Errorf("failed to read directory %s: %w", dir, err)
		}
		return false, nil
	}

	for _, item := range items {
		if len(*out) >= limit {
			return true, nil
		}

		name := item.Name()
		if !showHidden && strings.HasPrefix(name, ".") {
			continue
		}

		fullPath := filepath.Join(dir, name)
		entry := map[string]any{
			"name":     name,
			"path":     fullPath,
			"is_dir":   item.IsDir(),
			"mod_time": "",
			"size":     int64(0),
			"mode":     "",
		}

		// Use Lstat to identify the symbolic link itself rather than its target.
		li, statErr := os.Lstat(fullPath)
		if statErr == nil {
			entry["size"] = li.Size()
			entry["mode"] = li.Mode().String()
			entry["mod_time"] = li.ModTime().Format(time.RFC3339)
			if li.Mode()&os.ModeSymlink != 0 {
				entry["is_dir"] = false
				if target, err := os.Readlink(fullPath); err == nil {
					entry["symlink_target"] = target
				}
			}
		}

		*out = append(*out, entry)

		if item.IsDir() && depth < maxDepth {
			truncated, err := collectFSEntries(fullPath, depth+1, maxDepth, showHidden, limit, out)
			if err != nil {
				return false, err
			}
			if truncated {
				return true, nil
			}
		}
	}

	return false, nil
}

// resolveFSEncoding parses and validates the encoding parameter, only allowing utf-8 and base64.
func resolveFSEncoding(params map[string]any, def string) (string, error) {
	raw, err := optionalString(params, "encoding")
	if err != nil {
		return "", err
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

// chooseReportedEncoding returns the encoding actually used to represent content.
func chooseReportedEncoding(requested string, isBinary bool) string {
	if isBinary && requested == "utf-8" {
		return "base64"
	}
	return requested
}

// parseFileMode parses an octal permission string, such as "0644", "755".
func parseFileMode(s string) (fs.FileMode, error) {
	trimmed := strings.TrimSpace(s)
	trimmed = strings.TrimPrefix(trimmed, "0o")
	trimmed = strings.TrimPrefix(trimmed, "0O")

	parsed, err := strconv.ParseUint(trimmed, 8, 32)
	if err != nil {
		return 0, fmt.Errorf("parameter mode is not a valid octal permission value: %q", s)
	}
	if parsed > 0o7777 {
		return 0, fmt.Errorf("parameter mode is out of range (maximum 07777): %q", s)
	}
	return fs.FileMode(parsed), nil
}

// isBinaryContent determines whether the content is binary.
//
// The criterion: it contains NUL bytes, or is not valid UTF-8.
func isBinaryContent(data []byte) bool {
	if len(data) == 0 {
		return false
	}
	if strings.IndexByte(string(data), 0) >= 0 {
		return true
	}
	return !utf8.Valid(data)
}

// optionalBool reads an optional boolean parameter; returns the default value when missing or nil.
func optionalBool(params map[string]any, key string, def bool) (bool, error) {
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
