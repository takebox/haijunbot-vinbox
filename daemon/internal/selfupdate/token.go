package selfupdate

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// TokenState is a credential snapshot temporarily written to disk before an update, used to restore the login state after "update → restart".
//
// Why it is needed: the daemon's Token is by default kept in memory only and not persisted (see internal/auth/store.go),
// so it is lost on process restart. Auto-update restarts the service; without a temporary save, the daemon would stay
// unauthenticated after the restart until the user opens the web page and pushes again.
//
// Security boundary: this file **only exists during the self-update window**; after a restart the daemon reads it once at
// startup and **immediately deletes it**, so it does not constitute long-term credential persistence; the file permission is 0600 (readable/writable by the owner only).
type TokenState struct {
	// Gateway is the gateway address (the raw value before normalization).
	Gateway string `json:"gateway"`
	// Token is the gateway JWT.
	Token string `json:"token"`
	// Name is the terminal name (may be empty).
	Name string `json:"name"`
	// SavedAtUnix is the persistence time (Unix seconds), for troubleshooting.
	SavedAtUnix int64 `json:"saved_at_unix"`
	// ExpiresAtUnix is the credential expiry time (Unix seconds); 0 means it never expires.
	//
	// Corresponds to expires_at in the design doc: if the gateway JWT carries exp, it can be filled here so the startup logic can judge whether it is still usable.
	ExpiresAtUnix int64 `json:"expires_at"`
}

// TokenStatePath returns the path of the temporary credential file: ~/.haijunbot/daemon/update-token.json.
//
// It is in the same directory as the config file (config.DefaultPath), for easy troubleshooting by users.
func TokenStatePath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("failed to obtain the user home directory: %w", err)
	}
	return filepath.Join(home, ".haijunbot", "daemon", "update-token.json"), nil
}

// SaveTokenState writes the credential snapshot to the temporary file (0600).
//
// The directory is created automatically if missing. A write failure returns an error; the caller should log it
// but not block the update flow (the worst case is only that credentials must be pushed again after the restart).
func SaveTokenState(state TokenState) error {
	path, err := TokenStatePath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("failed to create the credential directory: %w", err)
	}
	blob, err := json.Marshal(state)
	if err != nil {
		return fmt.Errorf("failed to serialize the credentials: %w", err)
	}
	// Write to a temp file first and then rename, avoiding a half-written file; permission 0600.
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, blob, 0o600); err != nil {
		return fmt.Errorf("failed to write the credential temp file: %w", err)
	}
	_ = os.Chmod(tmp, 0o600)
	if err := os.Rename(tmp, path); err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("failed to save the credential file: %w", err)
	}
	return nil
}

// LoadAndClearTokenState reads and **immediately deletes** the temporary credential file.
//
// Returns:
//   - state, true: a valid credential was read successfully (the file has been deleted);
//   - zero, false: the file does not exist or parsing failed (no error is reported; the caller skips silently).
//
// Why delete immediately after reading: the file is a one-time relay, avoiding credential-leak risk from long-term residence on disk.
func LoadAndClearTokenState() (TokenState, bool) {
	path, err := TokenStatePath()
	if err != nil {
		return TokenState{}, false
	}
	blob, err := os.ReadFile(path)
	if err != nil {
		return TokenState{}, false
	}
	// Delete the file regardless of whether parsing succeeds (one-time semantics).
	defer func() { _ = os.Remove(path) }()

	var state TokenState
	if err := json.Unmarshal(blob, &state); err != nil {
		return TokenState{}, false
	}
	if state.Gateway == "" || state.Token == "" {
		return TokenState{}, false
	}
	// Expiry check: ExpiresAtUnix 0 means no check; otherwise it must be later than the current time.
	if state.ExpiresAtUnix > 0 && state.ExpiresAtUnix <= time.Now().Unix() {
		return TokenState{}, false
	}
	return state, true
}
