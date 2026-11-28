// Package daemonlog writes the daemon's logs to both standard error and a local log file.
//
// Why it is needed: on Windows the daemon is started by a scheduled task, so standard
// output/error has no receiver and all logs are lost, making issues impossible to
// diagnose. This writes a copy to ~/.haijunbot/logs/daemon.log while keeping stderr
// output, so foreground runs (haijunbot-daemon run) behave unchanged.
//
// It depends only on the standard library; no logging framework is introduced, keeping
// it fully compatible with existing log.Printf calls.
package daemonlog

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sync"
)

const (
	// maxBytes is the size limit of a single log file; it rotates when exceeded.
	maxBytes = 5 << 20 // 5 MiB

	// backupSuffix is the backup file name suffix after rotation (daemon.log → daemon.log.1).
	backupSuffix = ".1"
)

// LogDir returns the log directory: ~/.haijunbot/logs.
func LogDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to get user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", "logs"), nil
}

// LogPath returns the log file path: ~/.haijunbot/logs/daemon.log.
func LogPath() (string, error) {
	dir, err := LogDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "daemon.log"), nil
}

// rotateWriter is a file writer with size-based rotation.
//
// Rotation strategy: before writing, check the current file size; when it exceeds
// maxBytes, rename daemon.log to daemon.log.1 (overwriting the old backup), then
// recreate daemon.log. Only one backup is kept to avoid unbounded disk usage.
type rotateWriter struct {
	mu   sync.Mutex
	path string
	file *os.File
	size int64
}

// newRotateWriter opens (creating if necessary) the log file and returns the writer.
func newRotateWriter(path string) (*rotateWriter, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return nil, err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return nil, err
	}
	info, err := f.Stat()
	if err != nil {
		_ = f.Close()
		return nil, err
	}
	return &rotateWriter{path: path, file: f, size: info.Size()}, nil
}

// Write rotates first if necessary, then writes the data.
func (w *rotateWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.size+int64(len(p)) > maxBytes {
		if err := w.rotate(); err != nil {
			// A rotation failure does not block writing: keep appending to the current file to avoid losing logs.
			_ = err
		}
	}
	n, err := w.file.Write(p)
	w.size += int64(n)
	return n, err
}

// rotate closes the current file, backs up the old file, and recreates it.
func (w *rotateWriter) rotate() error {
	if err := w.file.Close(); err != nil {
		return err
	}
	backup := w.path + backupSuffix
	// On Windows, renaming to an existing target fails, so delete the old backup first.
	_ = os.Remove(backup)
	if err := os.Rename(w.path, backup); err != nil {
		return err
	}
	f, err := os.OpenFile(w.path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	w.file = f
	w.size = 0
	return nil
}

// Close closes the underlying file.
func (w *rotateWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.file == nil {
		return nil
	}
	err := w.file.Close()
	w.file = nil
	return err
}

// Setup changes the standard library log output to "stderr + log file".
//
// It returns the log file path (empty string on failure). Any creation failure only
// degrades to pure stderr output and returns no error nor interrupts startup:
// unavailable logging should not prevent the daemon from working.
func Setup() string {
	path, err := LogPath()
	if err != nil {
		log.Printf("[daemonlog] cannot determine log path, outputting to stderr only: %v", err)
		return ""
	}
	w, err := newRotateWriter(path)
	if err != nil {
		log.Printf("[daemonlog] failed to open log file (%s), outputting to stderr only: %v", path, err)
		return ""
	}
	log.SetOutput(io.MultiWriter(os.Stderr, w))
	return path
}
