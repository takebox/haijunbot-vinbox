// Package handler processes commands dispatched by the gateway.
//
// The action of a command is the capability name, executed by capability.Registry;
// when no registry is attached, it falls back to a placeholder implementation (returns not_implemented).
package handler

import (
	"encoding/json"
	"fmt"

	"haijunbot-daemon/internal/capability"
)

// Command is a command dispatched by the gateway.
type Command struct {
	ID        string          `json:"id"`
	Type      string          `json:"type"`
	Action    string          `json:"action"`
	Params    json.RawMessage `json:"params,omitempty"`
	TimeoutMS int             `json:"timeout_ms,omitempty"`
}

// Result is the command result returned to the gateway.
type Result struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
	Data    any    `json:"data,omitempty"`
}

// Dispatch processes a command and returns the result.
//
// Compatibility entry point: when no capability registry is attached, always returns not_implemented.
func Dispatch(cmd Command) Result {
	return Result{
		ID:      cmd.ID,
		Type:    "result",
		Success: false,
		Error:   "not_implemented",
	}
}

// DispatchWith processes a command using the capability registry and returns the result.
//
// The action of a command is the capability name; params are parsed into a map and passed to the capability handler.
// When reg is nil, a clear error is returned so callers can detect missing configuration.
func DispatchWith(reg *capability.Registry, cmd Command) Result {
	if reg == nil {
		return Result{
			ID:      cmd.ID,
			Type:    "result",
			Success: false,
			Error:   "capability registry is nil",
		}
	}
	params, err := parseParams(cmd.Params)
	if err != nil {
		return Result{
			ID:      cmd.ID,
			Type:    "result",
			Success: false,
			Error:   fmt.Sprintf("failed to parse params: %v", err),
		}
	}
	res := reg.Execute(cmd.Action, params)
	return Result{
		ID:      cmd.ID,
		Type:    "result",
		Success: res.Success,
		Error:   res.Error,
		Data:    res.Data,
	}
}

// parseParams parses the command params into a map; empty params return nil.
func parseParams(raw json.RawMessage) (map[string]any, error) {
	if len(raw) == 0 {
		return nil, nil
	}
	var params map[string]any
	if err := json.Unmarshal(raw, &params); err != nil {
		return nil, err
	}
	return params, nil
}
