//go:build linux

package capability

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// linuxGUITimeout is the timeout for a single external GUI command call.
const linuxGUITimeout = 10 * time.Second

// linuxGUIMaxOutputBytes is the maximum number of bytes of external command output to keep.
const linuxGUIMaxOutputBytes = 1 << 20 // 1 MiB

// linuxGUIToolHints records installation hints for each tool, used to generate actionable error messages.
var linuxGUIToolHints = map[string]string{
	"xdotool": "sudo apt install xdotool",
	"wmctrl":  "sudo apt install wmctrl",
	"xclip":   "sudo apt install xclip",
	"xsel":    "sudo apt install xsel",
	"import":  "sudo apt install imagemagick",
	"scrot":   "sudo apt install scrot",
	"grim":    "sudo apt install grim",
}

// registerLinuxGUI registers the Linux graphical interface related capabilities.
//
// Design trade-off: this implementation **does not call X11 directly** (that would require cgo, which would break the CGO_ENABLED=0
// cross-compilation capability); instead it calls command-line tools already present on the system (xdotool / wmctrl /
// xclip / import, etc.). Therefore the availability of these capabilities depends on:
//  1. A graphical environment existing (DISPLAY or WAYLAND_DISPLAY non-empty);
//  2. The corresponding external command being installed.
//
// If either is not satisfied, the capability returns a clear error with installation/troubleshooting hints, rather than silently failing.
func registerLinuxGUI(reg *Registry) {
	_ = reg.Register(Capability{
		Name:        "linux.window.list",
		Description: "Lists the windows in the current graphical environment (prefers wmctrl, falls back to xdotool). Requires DISPLAY and wmctrl or xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"filter": map[string]any{
					"type":        "string",
					"description": "Filter by window title substring, optional.",
				},
			},
		},
		Handler: handleLinuxWindowList,
	})

	_ = reg.Register(Capability{
		Name:        "linux.window.focus",
		Description: "Activates (focuses) the specified window. Requires DISPLAY and wmctrl or xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x03400007; provide at least one of window_id and title.",
				},
				"title": map[string]any{
					"type":        "string",
					"description": "Window title (substring match), used when window_id is not provided.",
				},
			},
		},
		Handler: handleLinuxWindowFocus,
	})

	_ = reg.Register(Capability{
		Name:        "linux.window.close",
		Description: "Closes the specified window. Requires DISPLAY and wmctrl or xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"window_id": map[string]any{
					"type":        "string",
					"description": "Window ID, such as 0x03400007.",
				},
			},
			"required": []string{"window_id"},
		},
		Handler: handleLinuxWindowClose,
	})

	_ = reg.Register(Capability{
		Name:        "linux.input.click",
		Description: "Clicks the mouse at the specified screen coordinates. Requires DISPLAY and xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"x": map[string]any{
					"type":        "integer",
					"description": "Screen x coordinate (pixels).",
				},
				"y": map[string]any{
					"type":        "integer",
					"description": "Screen y coordinate (pixels).",
				},
				"button": map[string]any{
					"type":        "string",
					"description": "Mouse button, default left; supports left/right/middle.",
				},
				"count": map[string]any{
					"type":        "integer",
					"description": "Number of clicks, default 1.",
				},
			},
			"required": []string{"x", "y"},
		},
		Handler: handleLinuxInputClick,
	})

	_ = reg.Register(Capability{
		Name:        "linux.input.type",
		Description: "Types text into the currently focused window. Requires DISPLAY and xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"text": map[string]any{
					"type":        "string",
					"description": "The text to type.",
				},
				"delay_ms": map[string]any{
					"type":        "integer",
					"description": "Delay in milliseconds between each keystroke, optional.",
				},
			},
			"required": []string{"text"},
		},
		Handler: handleLinuxInputType,
	})

	_ = reg.Register(Capability{
		Name:        "linux.input.keys",
		Description: "Sends a key combination to the currently focused window (xdotool key syntax, such as ctrl+c, Return). Requires DISPLAY and xdotool.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"keys": map[string]any{
					"type":        "string",
					"description": "Key sequence, such as ctrl+c, alt+Tab, Return.",
				},
			},
			"required": []string{"keys"},
		},
		Handler: handleLinuxInputKeys,
	})

	_ = reg.Register(Capability{
		Name:        "linux.clipboard.get",
		Description: "Reads the clipboard text (prefers xclip, falls back to xsel). Requires DISPLAY.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type":       "object",
			"properties": map[string]any{},
		},
		Handler: handleLinuxClipboardGet,
	})

	_ = reg.Register(Capability{
		Name:        "linux.clipboard.set",
		Description: "Writes clipboard text (prefers xclip, falls back to xsel). Requires DISPLAY.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"text": map[string]any{
					"type":        "string",
					"description": "The text to write to the clipboard.",
				},
			},
			"required": []string{"text"},
		},
		Handler: handleLinuxClipboardSet,
	})

	_ = reg.Register(Capability{
		Name:        "linux.screenshot",
		Description: "Captures the screen and saves it to the specified path (prefers import, falls back to scrot, and under Wayland falls back to grim). Requires DISPLAY or WAYLAND_DISPLAY.",
		Platform:    PlatformLinux,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The absolute path to save the screenshot.",
				},
				"window_id": map[string]any{
					"type":        "string",
					"description": "Capture only the specified window, optional; only import supports it.",
				},
				"format": map[string]any{
					"type":        "string",
					"description": "Image format, default png.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleLinuxScreenshot,
	})
}

// requireDisplay checks whether a graphical environment exists.
func requireDisplay() error {
	if os.Getenv("DISPLAY") != "" || os.Getenv("WAYLAND_DISPLAY") != "" {
		return nil
	}
	return fmt.Errorf("no graphical environment detected (both DISPLAY/WAYLAND_DISPLAY are empty); GUI capabilities are unavailable; " +
		"if the daemon runs as a systemd user service, please confirm it can access the current graphical session")
}

// requireTool probes candidate commands in order and returns the absolute path of the first executable.
//
// When all are missing, it returns an error with installation hints, so the caller can follow them directly.
func requireTool(names ...string) (string, error) {
	for _, name := range names {
		if path, err := exec.LookPath(name); err == nil {
			return path, nil
		}
	}

	hints := make([]string, 0, len(names))
	for _, name := range names {
		if hint, ok := linuxGUIToolHints[name]; ok {
			hints = append(hints, fmt.Sprintf("%s (install: %s)", name, hint))
		} else {
			hints = append(hints, name)
		}
	}
	return "", fmt.Errorf("no available command found among %s, please install one of them", strings.Join(hints, " or "))
}

// runGUICommand executes an external GUI command and returns the standard output.
//
// Uniformly with a timeout; on failure the stderr content is included in the error message for easier troubleshooting.
func runGUICommand(stdin string, path string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), linuxGUITimeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, path, args...)
	if stdin != "" {
		cmd.Stdin = strings.NewReader(stdin)
	}

	out, err := cmd.Output()
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("executing %s timed out (%s)", path, linuxGUITimeout)
		}
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			stderr := strings.TrimSpace(string(exitErr.Stderr))
			if stderr != "" {
				return "", fmt.Errorf("failed to execute %s: %s", path, stderr)
			}
		}
		return "", fmt.Errorf("failed to execute %s: %w", path, err)
	}

	if len(out) > linuxGUIMaxOutputBytes {
		out = out[:linuxGUIMaxOutputBytes]
	}
	return string(out), nil
}

// handleLinuxWindowList is the implementation of linux.window.list.
func handleLinuxWindowList(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	filter, err := optionalString(params, "filter")
	if err != nil {
		return nil, err
	}

	tool, err := requireTool("wmctrl", "xdotool")
	if err != nil {
		return nil, err
	}

	var windows []map[string]any
	if strings.HasSuffix(tool, "wmctrl") {
		out, err := runGUICommand("", tool, "-lp")
		if err != nil {
			return nil, err
		}
		windows = parseWmctrlWindowList(out)
	} else {
		out, err := runGUICommand("", tool, "search", "--name", filter)
		if err != nil {
			// xdotool returns a non-zero exit code when there are no matching windows; treat it as an empty result rather than an error.
			if strings.Contains(err.Error(), "failed") && filter != "" {
				windows = nil
			} else {
				return nil, err
			}
		} else {
			windows = parseXdotoolWindowList(out, tool)
		}
	}

	if filter != "" {
		filtered := make([]map[string]any, 0, len(windows))
		lower := strings.ToLower(filter)
		for _, w := range windows {
			title, _ := w["title"].(string)
			if strings.Contains(strings.ToLower(title), lower) {
				filtered = append(filtered, w)
			}
		}
		windows = filtered
	}

	return map[string]any{
		"windows": windows,
		"count":   len(windows),
		"tool":    tool,
	}, nil
}

// handleLinuxWindowFocus is the implementation of linux.window.focus.
func handleLinuxWindowFocus(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}
	title, err := optionalString(params, "title")
	if err != nil {
		return nil, err
	}
	if windowID == "" && title == "" {
		return nil, fmt.Errorf("at least one of the parameters window_id and title must be provided")
	}

	tool, err := requireTool("wmctrl", "xdotool")
	if err != nil {
		return nil, err
	}

	var out string
	if strings.HasSuffix(tool, "wmctrl") {
		if windowID != "" {
			out, err = runGUICommand("", tool, "-i", "-a", windowID)
		} else {
			out, err = runGUICommand("", tool, "-a", title)
		}
	} else {
		if windowID == "" {
			res, searchErr := runGUICommand("", tool, "search", "--name", title)
			if searchErr != nil {
				return nil, fmt.Errorf("failed to find a window by title %q: %w", title, searchErr)
			}
			ids := strings.Fields(strings.TrimSpace(res))
			if len(ids) == 0 {
				return nil, fmt.Errorf("no window with a title matching %q was found", title)
			}
			windowID = ids[0]
		}
		out, err = runGUICommand("", tool, "windowactivate", windowID)
	}
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"window_id": windowID,
		"title":     title,
		"focused":   true,
		"output":    strings.TrimSpace(out),
		"tool":      tool,
	}, nil
}

// handleLinuxWindowClose is the implementation of linux.window.close.
func handleLinuxWindowClose(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	windowID, err := requiredString(params, "window_id")
	if err != nil {
		return nil, err
	}

	tool, err := requireTool("wmctrl", "xdotool")
	if err != nil {
		return nil, err
	}

	var out string
	if strings.HasSuffix(tool, "wmctrl") {
		out, err = runGUICommand("", tool, "-i", "-c", windowID)
	} else {
		out, err = runGUICommand("", tool, "windowclose", windowID)
	}
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"window_id": windowID,
		"closed":    true,
		"output":    strings.TrimSpace(out),
		"tool":      tool,
	}, nil
}

// handleLinuxInputClick is the implementation of linux.input.click.
func handleLinuxInputClick(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	// x/y are allowed to be 0 (the top-left corner of the screen), so the default-value semantics of optionalInt cannot be reused;
	// whether the parameter is provided must be determined explicitly.
	x, err := requiredInt(params, "x")
	if err != nil {
		return nil, err
	}
	y, err := requiredInt(params, "y")
	if err != nil {
		return nil, err
	}

	button, err := optionalString(params, "button")
	if err != nil {
		return nil, err
	}
	if button == "" {
		button = "left"
	}
	switch button {
	case "left", "right", "middle":
	default:
		return nil, fmt.Errorf("parameter button does not support %q, allowed values: left, right, middle", button)
	}

	count, err := optionalInt(params, "count", 1)
	if err != nil {
		return nil, err
	}
	if count <= 0 {
		return nil, fmt.Errorf("parameter count must be a positive integer, actual %d", count)
	}

	tool, err := requireTool("xdotool")
	if err != nil {
		return nil, err
	}

	if _, err := runGUICommand("", tool, "mousemove", strconv.Itoa(x), strconv.Itoa(y)); err != nil {
		return nil, err
	}
	out, err := runGUICommand("", tool, "click", "--repeat", strconv.Itoa(count), button)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"x":      x,
		"y":      y,
		"button": button,
		"count":  count,
		"output": strings.TrimSpace(out),
		"tool":   tool,
	}, nil
}

// handleLinuxInputType is the implementation of linux.input.type.
func handleLinuxInputType(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	text, err := requiredString(params, "text")
	if err != nil {
		return nil, err
	}

	delayMS, err := optionalInt(params, "delay_ms", 0)
	if err != nil {
		return nil, err
	}
	if delayMS < 0 {
		return nil, fmt.Errorf("parameter delay_ms cannot be negative, actual %d", delayMS)
	}

	tool, err := requireTool("xdotool")
	if err != nil {
		return nil, err
	}

	args := []string{"type"}
	if delayMS > 0 {
		args = append(args, "--delay", strconv.Itoa(delayMS))
	}
	// Separate with -- to prevent text starting with "-" from being treated as an option by xdotool.
	args = append(args, "--", text)

	out, err := runGUICommand("", tool, args...)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"typed":  text,
		"output": strings.TrimSpace(out),
		"tool":   tool,
	}, nil
}

// handleLinuxInputKeys is the implementation of linux.input.keys.
func handleLinuxInputKeys(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	keys, err := requiredString(params, "keys")
	if err != nil {
		return nil, err
	}

	tool, err := requireTool("xdotool")
	if err != nil {
		return nil, err
	}

	out, err := runGUICommand("", tool, "key", "--", keys)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"keys":   keys,
		"output": strings.TrimSpace(out),
		"tool":   tool,
	}, nil
}

// handleLinuxClipboardGet is the implementation of linux.clipboard.get.
func handleLinuxClipboardGet(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	tool, err := requireTool("xclip", "xsel")
	if err != nil {
		return nil, err
	}

	var out string
	if strings.HasSuffix(tool, "xclip") {
		out, err = runGUICommand("", tool, "-selection", "clipboard", "-o")
	} else {
		out, err = runGUICommand("", tool, "-b", "-o")
	}
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"text": out,
		"tool": tool,
	}, nil
}

// handleLinuxClipboardSet is the implementation of linux.clipboard.set.
func handleLinuxClipboardSet(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	// Writing an empty string to clear the clipboard is allowed, so requiredString is not used.
	raw, ok := params["text"]
	if !ok || raw == nil {
		return nil, fmt.Errorf("missing required parameter text")
	}
	text, ok := raw.(string)
	if !ok {
		return nil, fmt.Errorf("parameter text must be a string, actual %T", raw)
	}

	tool, err := requireTool("xclip", "xsel")
	if err != nil {
		return nil, err
	}

	var out string
	if strings.HasSuffix(tool, "xclip") {
		out, err = runGUICommand(text, tool, "-selection", "clipboard")
	} else {
		out, err = runGUICommand(text, tool, "-b", "-i")
	}
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"written_bytes": len(text),
		"output":        strings.TrimSpace(out),
		"tool":          tool,
	}, nil
}

// handleLinuxScreenshot is the implementation of linux.screenshot.
func handleLinuxScreenshot(params map[string]any) (any, error) {
	if err := requireDisplay(); err != nil {
		return nil, err
	}

	path, err := requiredString(params, "path")
	if err != nil {
		return nil, err
	}

	windowID, err := optionalString(params, "window_id")
	if err != nil {
		return nil, err
	}

	format, err := optionalString(params, "format")
	if err != nil {
		return nil, err
	}
	if format == "" {
		format = "png"
	}
	switch format {
	case "png", "jpg", "jpeg":
	default:
		return nil, fmt.Errorf("parameter format does not support %q, allowed values: png, jpg, jpeg", format)
	}

	tool, err := requireTool("import", "scrot", "grim")
	if err != nil {
		return nil, err
	}

	var out string
	switch {
	case strings.HasSuffix(tool, "import"):
		args := []string{"-window", "root"}
		if windowID != "" {
			args = []string{"-window", windowID}
		}
		args = append(args, path)
		out, err = runGUICommand("", tool, args...)
	case strings.HasSuffix(tool, "scrot"):
		out, err = runGUICommand("", tool, path)
	default: // grim
		out, err = runGUICommand("", tool, path)
	}
	if err != nil {
		return nil, err
	}

	info, statErr := os.Stat(path)
	if statErr != nil {
		return nil, fmt.Errorf("the screenshot command executed but the output file %s was not found: %w", path, statErr)
	}

	return map[string]any{
		"path":       path,
		"size_bytes": info.Size(),
		"format":     format,
		"output":     strings.TrimSpace(out),
		"tool":       tool,
	}, nil
}

// requiredInt reads a required integer parameter.
//
// Difference from optionalInt: it returns an error rather than a default value when missing,
// for parameters like x/y where "0 is a legal value and cannot be confused with missing".
func requiredInt(params map[string]any, key string) (int, error) {
	v, ok := params[key]
	if !ok || v == nil {
		return 0, fmt.Errorf("missing required parameter %s", key)
	}
	switch n := v.(type) {
	case int:
		return n, nil
	case int64:
		return int(n), nil
	case float64:
		if n != float64(int(n)) {
			return 0, fmt.Errorf("parameter %s must be an integer, actual %v", key, n)
		}
		return int(n), nil
	default:
		return 0, fmt.Errorf("parameter %s must be an integer, actual %T", key, v)
	}
}

// parseWmctrlWindowList parses the output of `wmctrl -lp`.
//
// Each line looks like:
//
//	0x03400007  0 12345  hostname Window Title
//
// The fields are, in order: window ID, desktop number, PID, hostname, title (may contain spaces).
func parseWmctrlWindowList(out string) []map[string]any {
	windows := make([]map[string]any, 0, 16)
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 5 {
			continue
		}
		windows = append(windows, map[string]any{
			"window_id": fields[0],
			"desktop":   fields[1],
			"pid":       fields[2],
			"hostname":  fields[3],
			"title":     strings.Join(fields[4:], " "),
		})
	}
	return windows
}

// parseXdotoolWindowList parses the window ID list of `xdotool search` and fills in the titles.
func parseXdotoolWindowList(out string, tool string) []map[string]any {
	windows := make([]map[string]any, 0, 16)
	for _, id := range strings.Fields(strings.TrimSpace(out)) {
		entry := map[string]any{
			"window_id": id,
			"title":     "",
		}
		if title, err := runGUICommand("", tool, "getwindowname", id); err == nil {
			entry["title"] = strings.TrimSpace(title)
		}
		windows = append(windows, entry)
	}
	return windows
}
