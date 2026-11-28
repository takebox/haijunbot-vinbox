//go:build windows

package capability

// This file implements the Windows platform file system capabilities (windows.fs.read / write / list).
//
// The design mirrors the Linux side linux_fs_linux.go, keeping parameters and return structures consistent:
//   - read: path/offset/limit/encoding → content/truncated/is_binary/encoding…
//   - write: path/content/encoding/append/create_dirs/mode → written_bytes/created/appended
//   - list: path/recursive/max_depth/show_hidden/limit → entries/count/truncated
//
// Differences from Linux:
//   - mode (Unix permission octal) is meaningless on Windows: the parameter is accepted but ignored, and the return
//     result marks mode_ignored=true, so the caller does not mistakenly think the permissions were set.
//   - Hidden-item detection: Windows uses the FILE_ATTRIBUTE_HIDDEN attribute rather than "starts with a dot".
//     Both count as hidden here (a leading dot is a cross-platform convention, the attribute is native Windows semantics).
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success path has not been verified end-to-end.

import (
	"encoding/base64"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"
)

// Default and maximum constraints for the Windows file system capabilities (kept in the same order of magnitude as the Linux side).
const (
	// windowsFSDefaultReadLimit is the default number of bytes to read for windows.fs.read when limit is not specified.
	windowsFSDefaultReadLimit = 1 << 20 // 1 MiB
	// windowsFSMaxReadLimit is the maximum number of bytes allowed for windows.fs.read, to prevent a single read from blowing up memory.
	windowsFSMaxReadLimit = 8 << 20 // 8 MiB
	// windowsFSDefaultListLimit is the default upper bound on the number of entries for windows.fs.list when limit is not specified.
	windowsFSDefaultListLimit = 500
	// windowsFSMaxListLimit is the maximum upper bound on the number of entries allowed for windows.fs.list.
	windowsFSMaxListLimit = 10000
)

// registerWindowsFS registers the Windows file system capabilities.
func registerWindowsFS(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.fs.read",
		Description: "Reads file content on Windows. Supports segmented reading via offset/limit; " +
			"when the content contains NUL bytes or is not valid UTF-8, it is automatically returned as base64 with is_binary=true.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The file path to read (an absolute path or relative to the daemon working directory), such as C:\\Users\\me\\a.txt.",
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
		Handler: handleWindowsFSRead,
	})

	_ = reg.Register(Capability{
		Name: "windows.fs.write",
		Description: "Writes file content on Windows. Supports overwrite/append and automatic creation of parent directories. " +
			"Note: the mode parameter is meaningless on Windows and is ignored (the result marks mode_ignored=true).",
		Platform: PlatformWindows,
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
					"description": "File permission octal string (only to align with the Linux side's parameters; ignored on Windows).",
				},
			},
			"required": []string{"path", "content"},
		},
		Handler: handleWindowsFSWrite,
	})

	_ = reg.Register(Capability{
		Name:        "windows.fs.list",
		Description: "Lists the contents of a directory on Windows, supporting recursion and depth limits. Hidden items are determined by a leading dot or the FILE_ATTRIBUTE_HIDDEN attribute.",
		Platform:    PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The directory path to list, such as C:\\Users\\me.",
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
					"description": "Whether to include hidden items (leading dot or with the hidden attribute), default true.",
				},
				"limit": map[string]any{
					"type":        "integer",
					"description": "Upper bound on the number of returned entries, default 500, maximum 10000.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleWindowsFSList,
	})
}

// handleWindowsFSRead is the implementation of windows.fs.read.
func handleWindowsFSRead(params map[string]any) (any, error) {
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

	limit, err := optionalInt(params, "limit", windowsFSDefaultReadLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > windowsFSMaxReadLimit {
		return nil, fmt.Errorf("parameter limit exceeds the upper bound %d bytes, actual %d", windowsFSMaxReadLimit, limit)
	}

	encoding, err := resolveWindowsFSEncoding(params, "utf-8")
	if err != nil {
		return nil, err
	}

	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file %s: %w", path, err)
	}
	if info.IsDir() {
		return nil, fmt.Errorf("path %s is a directory and cannot be read with windows.fs.read; use windows.fs.list instead", path)
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

	isBinary := isBinaryWindowsContent(data)
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
		"encoding":   chooseWindowsReportedEncoding(encoding, isBinary),
	}, nil
}

// handleWindowsFSWrite is the implementation of windows.fs.write.
func handleWindowsFSWrite(params map[string]any) (any, error) {
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

	encoding, err := resolveWindowsFSEncoding(params, "utf-8")
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

	// mode is kept only to align with the Linux side's parameters: Windows has no Unix permission bits, so its value is ignored.
	modeStr, err := optionalString(params, "mode")
	if err != nil {
		return nil, err
	}
	modeIgnored := modeStr != ""

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

	// Windows ignores the permission bits; passing 0o666 here defers to the system default (affected by umask/ACL).
	f, err := os.OpenFile(path, flags, 0o666)
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
		"mode_ignored":  modeIgnored,
	}, nil
}

// handleWindowsFSList is the implementation of windows.fs.list.
func handleWindowsFSList(params map[string]any) (any, error) {
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

	limit, err := optionalInt(params, "limit", windowsFSDefaultListLimit)
	if err != nil {
		return nil, err
	}
	if limit <= 0 {
		return nil, fmt.Errorf("parameter limit must be a positive integer, actual %d", limit)
	}
	if limit > windowsFSMaxListLimit {
		return nil, fmt.Errorf("parameter limit exceeds the upper bound %d, actual %d", windowsFSMaxListLimit, limit)
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

	truncated, err := collectWindowsFSEntries(path, 1, maxDepth, showHidden, limit, &entries)
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

// collectWindowsFSEntries recursively collects directory entries, returning early with truncated set when the limit is reached.
//
// depth is the current level depth (starting from 1), and maxDepth is the maximum allowed depth.
func collectWindowsFSEntries(dir string, depth, maxDepth int, showHidden bool, limit int, out *[]map[string]any) (bool, error) {
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

		// Use Lstat to identify the symbolic link itself rather than its target.
		fullPath := filepath.Join(dir, name)
		li, statErr := os.Lstat(fullPath)

		hidden := strings.HasPrefix(name, ".")
		if statErr == nil && isWindowsHidden(li) {
			hidden = true
		}
		if !showHidden && hidden {
			continue
		}

		entry := map[string]any{
			"name":     name,
			"path":     fullPath,
			"is_dir":   item.IsDir(),
			"hidden":   hidden,
			"mod_time": "",
			"size":     int64(0),
			"mode":     "",
		}

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
			truncated, err := collectWindowsFSEntries(fullPath, depth+1, maxDepth, showHidden, limit, out)
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

// isWindowsHidden determines whether a file has the Windows hidden attribute (FILE_ATTRIBUTE_HIDDEN).
//
// It uses only the standard library syscall (kernel32!GetFileAttributesW), without introducing golang.org/x/sys.
// On Windows, fs.FileInfo's Sys() returns *syscall.Win32FileAttributeData,
// whose FileAttributes field contains the hidden attribute bit. It returns false when the type assertion fails,
// falling back to the caller's "leading dot" check.
func isWindowsHidden(info fs.FileInfo) bool {
	if info == nil {
		return false
	}
	data, ok := info.Sys().(*syscall.Win32FileAttributeData)
	if !ok {
		return false
	}
	return data.FileAttributes&syscall.FILE_ATTRIBUTE_HIDDEN != 0
}
