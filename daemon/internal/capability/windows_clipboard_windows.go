//go:build windows

package capability

// This file implements the Windows platform clipboard and screenshot capabilities (windows.clipboard.*, windows.screenshot).
//
// Unlike the window/input capabilities (windows_gui_windows.go, windows_input_windows.go), which call user32.dll directly,
// clipboard and screenshot go through PowerShell:
//   - Clipboard: user32's clipboard API requires a whole set of OpenClipboard/GlobalLock/GlobalAlloc
//     memory handle management, which is a lot of code and prone to leaks; PowerShell ships with Get-Clipboard/Set-Clipboard,
//     available on both Windows PowerShell 5.1 and PowerShell 7+, with clear semantics.
//   - Screenshot: requires the bitmap encoding capability of GDI+/System.Drawing, and hand-writing GDI+ COM
//     interfaces (GdipSaveImageToFile, etc.) with pure syscall is extremely tedious; PowerShell does it in one line.
//
// Therefore this file reuses requireTool from windows_common_windows.go to detect powershell.exe,
// and executes uniformly with a timeout via runWindowsPowerShellCommand.
//
// Security note: **never concatenate user text directly into a PowerShell command string**.
// The text of windows.clipboard.set is encoded by encodePowerShellText into a single-quoted literal
// (see windows_gui_parse.go), where single quotes are doubled per PowerShell rules,
// and $, backticks, semicolons, newlines, etc. are not interpreted, thus eliminating command injection.
//
// Note: the local development environment is Linux, with no Windows runtime environment, so this file can only guarantee
// "compilation under GOOS=windows"; the success paths of each capability have not been verified end-to-end.

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// windowsClipboardTimeout is the timeout for executing the PowerShell clipboard command.
//
// It stays consistent with the Linux side's linuxGUITimeout (10s): clipboard reads/writes are millisecond operations,
// and 10s is enough to cover a cold process start; a timeout means PowerShell is stuck and should fail quickly rather than hang the caller.
//
// Note: windows.clipboard.set includes a retry internally (see windowsClipboardSetScript);
// on real hardware, when the clipboard is briefly occupied by another process, it may need nearly 10 retries (about 10s) to succeed,
// so it is relaxed to 30s here to avoid being interrupted by a timeout before the retries complete.
const windowsClipboardTimeout = 30 * time.Second

// windowsScreenshotTimeout is the timeout for executing the PowerShell screenshot command.
//
// More relaxed than the clipboard: a screenshot must load the System.Drawing assembly, capture the full-screen bitmap, and encode it to
// PNG/JPEG (encoding a 4K screen may take several seconds), so it is given 30s.
const windowsScreenshotTimeout = 30 * time.Second

// windowsClipboardTool is the value of the tool field in the result returned by the clipboard capabilities.
//
// "powershell.exe" is used to align with the "xclip"/"xsel" form on the Linux side, so the caller can see at a glance
// which implementation is used underneath.
const windowsClipboardTool = "powershell.exe"

// registerWindowsClipboard registers the Windows clipboard and screenshot capabilities.
func registerWindowsClipboard(reg *Registry) {
	_ = reg.Register(Capability{
		Name: "windows.clipboard.get",
		Description: "Reads the text in the Windows clipboard. " +
			"Implemented via PowerShell's Get-Clipboard -Raw, preserving the original format such as newlines " +
			"(without -Raw, PowerShell splits it into an array by line and then concatenates, losing line endings). " +
			"When the clipboard does not contain text (such as only an image), an empty string is returned.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type":       "object",
			"properties": map[string]any{},
		},
		Handler: handleWindowsClipboardGet,
	})

	_ = reg.Register(Capability{
		Name: "windows.clipboard.set",
		Description: "Writes text to the Windows clipboard. " +
			"Implemented via PowerShell's Set-Clipboard; the text is passed after being escaped as a single-quoted literal, " +
			"so it will not cause command injection. An empty string may be passed to clear the clipboard.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"text": map[string]any{
					"type":        "string",
					"description": "The text to write to the clipboard; an empty string is allowed (meaning clear the clipboard).",
				},
			},
			"required": []string{"text"},
		},
		Handler: handleWindowsClipboardSet,
	})

	_ = reg.Register(Capability{
		Name: "windows.screenshot",
		Description: "Captures the Windows primary screen and saves it to the specified path. " +
			"Loads System.Drawing via PowerShell, captures the primary screen with Graphics.CopyFromScreen, " +
			"and encodes and saves it in the format specified by format. Supports png (default), jpg/jpeg. " +
			"Note: only the primary screen is captured; multi-monitor stitching and specifying a window are not supported.",
		Platform: PlatformWindows,
		Parameters: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"path": map[string]any{
					"type":        "string",
					"description": "The absolute path to save the screenshot, such as C:\\Users\\me\\shot.png.",
				},
				"format": map[string]any{
					"type":        "string",
					"description": "Image format, default png; supports png, jpg, jpeg.",
				},
			},
			"required": []string{"path"},
		},
		Handler: handleWindowsScreenshot,
	})
}

// requirePowerShell detects whether powershell.exe is available and returns its absolute path.
//
// Windows ships with Windows PowerShell 5.1 (powershell.exe), so it necessarily exists under normal circumstances;
// the detection is only to give a readable error message in extreme environments (trimmed images, abnormal PATH).
func requirePowerShell() (string, error) {
	return requireTool("powershell.exe", "Windows ships with Windows PowerShell 5.1; please confirm the system PATH is not broken")
}

// runWindowsPowerShellCommand executes a PowerShell script and returns the standard output (UTF-8).
//
// Parameters:
//   - script: the complete PowerShell script text. **The caller must ensure that the user input within it
//     has been escaped** (see encodePowerShellText); this function does not do any escaping.
//   - timeout: the timeout duration.
//
// Encoding scheme (this is the core of this function, which fixes the garbled Chinese on real machines):
//
//  1. Pass the script with -EncodedCommand rather than -Command. Reason: the -Command script text is passed
//     through command-line arguments, and Windows PowerShell 5.1 parses that argument according to the ANSI code page (GBK on Chinese systems),
//     while Go's exec passes it as UTF-8 bytes, corrupting the Chinese inside the script.
//     -EncodedCommand accepts base64(UTF-16LE), which is pure ASCII, completely bypassing the problem.
//     See the encodePowerShellCommand implementation in windows_encoding.go.
//
//  2. Prepend windowsPowerShellPreamble to the script, setting PowerShell's output encoding to
//     UTF-8. This way the stdout bytes read on the Go side are UTF-8, and string(out) can be used directly,
//     without introducing a GBK decoding table (the standard library lacks this capability, and third-party packages are forbidden by project constraints).
//
// Other switches:
//   - -NoProfile: skip the user profile (to avoid a custom profile slowing down startup or changing behavior).
//   - -NonInteractive: disallow interactive prompts (otherwise an accidentally popped confirmation box would hang until timeout).
//   - -ExecutionPolicy Bypass: bypass the script execution policy restriction.
//
// On failure, the stderr content is included in the error message for easier troubleshooting (such as a System.Drawing load failure).
func runWindowsPowerShellCommand(script string, timeout time.Duration) (string, error) {
	ps, err := requirePowerShell()
	if err != nil {
		return "", err
	}

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	// The preamble must execute before any output is produced, so it is prepended to the script.
	fullScript := windowsPowerShellPreamble + "\n" + script

	cmd := exec.CommandContext(ctx, ps,
		"-NoProfile",
		"-NonInteractive",
		"-ExecutionPolicy", "Bypass",
		"-EncodedCommand", encodePowerShellCommand(fullScript),
	)
	// The daemon itself has no console; without this attribute a new console window (flashing black box) is created for PowerShell.
	cmd.SysProcAttr = hideWindow()

	out, err := cmd.Output()
	if err != nil {
		if ctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("PowerShell execution timed out (%s)", timeout)
		}
		if exitErr, ok := err.(*exec.ExitError); ok {
			stderr := strings.TrimSpace(string(exitErr.Stderr))
			if stderr != "" {
				return "", fmt.Errorf("PowerShell execution failed: %s", stderr)
			}
		}
		return "", fmt.Errorf("PowerShell execution failed: %w", err)
	}

	// Under normal circumstances PowerShell has output UTF-8, so it can be converted directly.
	// If an abnormal environment still outputs GBK, the byte stream is not valid UTF-8; give a clear error in that case,
	// rather than silently returning a bunch of U+FFFD and confusing the caller about "why is it all question marks".
	if !looksLikeUTF8(out) {
		return "", fmt.Errorf("PowerShell output is not valid UTF-8 (appears to still output according to the console code page); "+
			"please confirm the system does not forcibly override the console output encoding; raw byte length %d", len(out))
	}
	return string(out), nil
}

// handleWindowsClipboardGet is the implementation of windows.clipboard.get.
func handleWindowsClipboardGet(params map[string]any) (any, error) {
	// -Raw ensures the complete text (including newlines) is returned rather than an array split by line.
	// Appending [Console]::Out.Write rather than Write-Output is to avoid PowerShell
	// automatically appending a newline at the end of the output — otherwise the text read back would have one extra "\n" compared to the original.
	//
	// When the clipboard is empty (or not text), Get-Clipboard returns empty, and the argument piped to [Console]::Out.Write
	// is then $null, which PowerShell converts to an empty string output, matching the expectation of "return an empty string".
	const script = "[Console]::Out.Write((Get-Clipboard -Raw))"

	out, err := runWindowsPowerShellCommand(script, windowsClipboardTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"text": out,
		"tool": windowsClipboardTool,
	}, nil
}

// handleWindowsClipboardSet is the implementation of windows.clipboard.set.
func handleWindowsClipboardSet(params map[string]any) (any, error) {
	// Writing an empty string to clear the clipboard is allowed, so requiredString cannot be used
	// (it would judge an empty string as "cannot be empty"). Consistent with the Linux side's handleLinuxClipboardSet.
	raw, ok := params["text"]
	if !ok || raw == nil {
		return nil, fmt.Errorf("missing required parameter text")
	}
	text, ok := raw.(string)
	if !ok {
		return nil, fmt.Errorf("parameter text must be a string, actual %T", raw)
	}

	// Key security point: text is turned into a single-quoted literal by encodePowerShellText before being concatenated into the script.
	// That function doubles the single quotes in the text, and the remaining characters are not interpreted inside the single-quoted literal, eliminating injection.
	// The script includes a retry: the Windows clipboard is often briefly occupied by other processes, so a single call easily fails
	// (on real hardware at worst the 9th attempt succeeds); see buildWindowsClipboardSetScript.
	script := buildWindowsClipboardSetScript(encodePowerShellText(text))

	out, err := runWindowsPowerShellCommand(script, windowsClipboardTimeout)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"written_bytes": len(text),
		"output":        strings.TrimSpace(out),
		"tool":          windowsClipboardTool,
	}, nil
}

// handleWindowsScreenshot is the implementation of windows.screenshot.
func handleWindowsScreenshot(params map[string]any) (any, error) {
	path, err := requiredString(params, "path")
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
	// Normalize: jpeg and jpg are equivalent; unify to jpg for later mapping to ImageFormat.
	format = strings.ToLower(format)
	if format == "jpeg" {
		format = "jpg"
	}
	switch format {
	case "png", "jpg":
	default:
		return nil, fmt.Errorf("parameter format does not support %q, allowed values: png, jpg, jpeg", format)
	}

	// Select the System.Drawing ImageFormat static property.
	// png → [System.Drawing.Imaging.ImageFormat]::Png
	// jpg → [System.Drawing.Imaging.ImageFormat]::Jpeg
	imageFormat := "Png"
	if format == "jpg" {
		imageFormat = "Jpeg"
	}

	// Script key points:
	//  1. First Add-Type to load System.Drawing (Windows PowerShell 5.1 has this assembly built in;
	//     PowerShell 7 requires the corresponding Windows compatibility pack to be installed, and Add-Type errors if it is missing,
	//     with the error message passed through stderr to the caller).
	//  2. Use System.Windows.Forms.Screen's PrimaryScreen.Bounds to get the primary screen size,
	//     rather than Graphics.CopyFromScreen's default 0,0 to 0,0 (the latter captures nothing).
	//  3. Use try/finally to ensure the Bitmap and Graphics are always released, avoiding GDI handle leaks.
	//  4. The path is escaped via encodePowerShellText (Windows paths contain backslashes, and within a single-quoted literal
	//     a backslash is not an escape character, so no extra handling is needed; but the path may contain single quotes, so escaping is still required).
	script := strings.Join([]string{
		"Add-Type -AssemblyName System.Drawing",
		"Add-Type -AssemblyName System.Windows.Forms",
		"$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds",
		"$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height",
		"try {",
		"  $g = [System.Drawing.Graphics]::FromImage($bmp)",
		"  try {",
		"    $g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)",
		"  } finally { $g.Dispose() }",
		"  $bmp.Save(" + encodePowerShellText(path) +
			", [System.Drawing.Imaging.ImageFormat]::" + imageFormat + ")",
		"} finally { $bmp.Dispose() }",
	}, "\n")

	if _, err := runWindowsPowerShellCommand(script, windowsScreenshotTimeout); err != nil {
		return nil, err
	}

	// Consistent with the Linux side: after the command executes successfully, stat again to confirm the file is actually on disk.
	// This can expose the case of "the script silently failed but the exit code is 0".
	info, statErr := os.Stat(path)
	if statErr != nil {
		return nil, fmt.Errorf("the screenshot command executed but the output file %s was not found: %w", path, statErr)
	}

	return map[string]any{
		"path":       path,
		"size_bytes": info.Size(),
		"format":     format,
		"tool":       windowsClipboardTool,
	}, nil
}
