package selfupdate

import (
	"os"
	"testing"
)

// TestTokenStateRoundTrip verifies that after saving one can read it back, and reading deletes the file (one-time semantics).
func TestTokenStateRoundTrip(t *testing.T) {
	// Use a temp HOME for isolation, avoiding pollution of the real user directory.
	t.Setenv("HOME", t.TempDir())

	path, err := TokenStatePath()
	if err != nil {
		t.Fatalf("TokenStatePath failed: %v", err)
	}

	state := TokenState{
		Gateway:     "https://example.com",
		Token:       "jwt-token",
		Name:        "my-terminal",
		SavedAtUnix: NowUnix(),
	}
	if err := SaveTokenState(state); err != nil {
		t.Fatalf("SaveTokenState failed: %v", err)
	}

	// The file should exist with permission 0600 (readable/writable by the owner only).
	fi, err := os.Stat(path)
	if err != nil {
		t.Fatalf("the credential file does not exist: %v", err)
	}
	if perm := fi.Mode().Perm(); perm != 0o600 {
		t.Fatalf("the credential file permission should be 0600, got %o", perm)
	}

	got, ok := LoadAndClearTokenState()
	if !ok {
		t.Fatal("the credentials should be read successfully")
	}
	if got.Gateway != state.Gateway || got.Token != state.Token || got.Name != state.Name {
		t.Fatalf("read back content mismatch: %+v", got)
	}

	// The file must be deleted after reading.
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("the credential file should be deleted after reading: %v", err)
	}
	// A second read should return false.
	if _, ok := LoadAndClearTokenState(); ok {
		t.Fatal("should not read the credentials again after the file was deleted")
	}
}

// TestLoadAndClearTokenState_Missing verifies that a missing file returns false without an error.
func TestLoadAndClearTokenState_Missing(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	if _, ok := LoadAndClearTokenState(); ok {
		t.Fatal("a missing file should return false")
	}
}

// TestLoadAndClearTokenState_Invalid verifies that invalid content returns false and deletes the file.
func TestLoadAndClearTokenState_Invalid(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	path, err := TokenStatePath()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(path[:len(path)-len("/update-token.json")], 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("not-json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, ok := LoadAndClearTokenState(); ok {
		t.Fatal("invalid content should return false")
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("the file should also be deleted after reading invalid content: %v", err)
	}
}

// TestLoadAndClearTokenState_Expired verifies that an expired credential (expires_at earlier than now) is invalid.
func TestLoadAndClearTokenState_Expired(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	if err := SaveTokenState(TokenState{
		Gateway:       "https://example.com",
		Token:         "jwt",
		ExpiresAtUnix: NowUnix() - 10,
	}); err != nil {
		t.Fatal(err)
	}
	if _, ok := LoadAndClearTokenState(); ok {
		t.Fatal("an expired credential should be invalid")
	}
}

// TestLoadAndClearTokenState_NotExpired verifies that a credential with expires_at in the future is valid.
func TestLoadAndClearTokenState_NotExpired(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	if err := SaveTokenState(TokenState{
		Gateway:       "https://example.com",
		Token:         "jwt",
		ExpiresAtUnix: NowUnix() + 3600,
	}); err != nil {
		t.Fatal(err)
	}
	if _, ok := LoadAndClearTokenState(); !ok {
		t.Fatal("a non-expired credential should be valid")
	}
}

// TestLoadAndClearTokenState_EmptyFields verifies that missing gateway/token is invalid.
func TestLoadAndClearTokenState_EmptyFields(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	// Write a JSON containing only name directly (bypassing SaveTokenState's field validation).
	path, err := TokenStatePath()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(path[:len(path)-len("/update-token.json")], 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(`{"name":"x"}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, ok := LoadAndClearTokenState(); ok {
		t.Fatal("missing gateway/token should return false")
	}
}
