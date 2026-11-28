package daemonlog

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestLogPathInHomeHaijunBotLogs verifies the log path is under ~/.haijunbot/logs.
func TestLogPathInHomeHaijunBotLogs(t *testing.T) {
	path, err := LogPath()
	if err != nil {
		t.Fatalf("LogPath failed: %v", err)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("failed to get home directory: %v", err)
	}
	want := filepath.Join(home, ".haijunbot", "logs", "daemon.log")
	if path != want {
		t.Fatalf("want %s, got %s", want, path)
	}
}

// TestRotateWriterWriteAndAppend verifies written content is correct and multiple writes are appended.
func TestRotateWriterWriteAndAppend(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "daemon.log")
	w, err := newRotateWriter(path)
	if err != nil {
		t.Fatalf("newRotateWriter failed: %v", err)
	}
	defer w.Close()

	if _, err := w.Write([]byte("first\n")); err != nil {
		t.Fatalf("write failed: %v", err)
	}
	if _, err := w.Write([]byte("second\n")); err != nil {
		t.Fatalf("append failed: %v", err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}
	if got := string(data); got != "first\nsecond\n" {
		t.Fatalf("content mismatch, got %q", got)
	}
}

// TestRotateWriterRotatesWhenExceedingMax verifies rotation and backup retention when the limit is exceeded.
func TestRotateWriterRotatesWhenExceedingMax(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "daemon.log")
	w, err := newRotateWriter(path)
	if err != nil {
		t.Fatalf("newRotateWriter failed: %v", err)
	}
	defer w.Close()

	// Pre-place a file close to the limit so the next write triggers rotation.
	big := strings.Repeat("x", maxBytes)
	if _, err := w.Write([]byte(big)); err != nil {
		t.Fatalf("failed to write big block: %v", err)
	}
	if _, err := w.Write([]byte("after-rotate\n")); err != nil {
		t.Fatalf("failed to write after rotation: %v", err)
	}

	backup := path + backupSuffix
	info, err := os.Stat(backup)
	if err != nil {
		t.Fatalf("expected backup file %s: %v", backup, err)
	}
	if info.Size() != int64(len(big)) {
		t.Fatalf("backup size want %d, got %d", len(big), info.Size())
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("failed to read current log: %v", err)
	}
	if string(data) != "after-rotate\n" {
		t.Fatalf("current log content after rotation mismatch, got %q", string(data))
	}
}

// TestRotateReplacesExistingBackup verifies repeated rotation overwrites the old backup without error.
func TestRotateReplacesExistingBackup(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "daemon.log")
	w, err := newRotateWriter(path)
	if err != nil {
		t.Fatalf("newRotateWriter failed: %v", err)
	}
	defer w.Close()

	for i := 0; i < 3; i++ {
		if _, err := w.Write([]byte(strings.Repeat("y", maxBytes))); err != nil {
			t.Fatalf("write %d failed: %v", i, err)
		}
	}
	if _, err := os.Stat(path + backupSuffix); err != nil {
		t.Fatalf("expected backup to exist: %v", err)
	}
}
