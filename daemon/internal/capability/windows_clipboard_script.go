package capability

// This file implements the PowerShell script construction (with retry) for windows.clipboard.set.
//
// Why it is placed separately in a file without build tags
// =======================================================
// Script construction is pure string logic and is unrelated to the Windows runtime. Placing it in a file without build tags
// allows it to be unit tested directly on a Linux development machine (this machine has no Windows environment; the code in
// _windows.go can only be guaranteed to cross-compile, and its tests cannot be run).
//
// Why retrying is mandatory
// =========================
// The Windows clipboard can only be opened by one process at a time; any background program (IME, clipboard
// manager, browser, etc.) may briefly hold it, in which case Set-Clipboard throws
// "Requested Clipboard operation did not succeed" (ExternalException).
// Real-machine measurement: a single call failed, and in the worst case it took 9 retries to succeed (about 11s).
// Therefore retrying is mandatory; otherwise windows.clipboard.set is almost unusable on real machines.

import "fmt"

// windowsClipboardRetryAttempts is the maximum number of attempts for Set-Clipboard.
//
// Background (real-machine measurement): the Windows clipboard can only be opened by one process at a time; any background
// program (IME, clipboard manager, browser, etc.) may briefly hold it, in which case Set-Clipboard throws
// "Requested Clipboard operation did not succeed" (ExternalException).
// In the worst case measured on a real machine the 9th attempt was needed, so retrying is mandatory rather than failing on the first error.
const windowsClipboardRetryAttempts = 20

// windowsClipboardRetryDelayMs is the interval between two attempts (milliseconds).
const windowsClipboardRetryDelayMs = 100

// buildWindowsClipboardSetScript constructs a Set-Clipboard script with retries.
//
// valueLiteral must be the single-quoted literal produced by encodePowerShellText (to prevent injection).
// The retry logic is placed on the PowerShell side rather than the Go side: if each retry were to start a new powershell.exe,
// the cold-start overhead (hundreds of milliseconds) would far exceed the retry interval, and 20 retries would take several seconds; whereas
// retrying with Start-Sleep inside the same process has negligible overhead.
func buildWindowsClipboardSetScript(valueLiteral string) string {
	return fmt.Sprintf(
		"$ok = $false; "+
			"for ($i = 0; $i -lt %d; $i++) { "+
			"try { Set-Clipboard -Value %s; $ok = $true; break } "+
			"catch { Start-Sleep -Milliseconds %d } "+
			"}; "+
			"if (-not $ok) { Write-Error 'failed to set clipboard: the clipboard is continuously occupied by another program' ; exit 1 }",
		windowsClipboardRetryAttempts, valueLiteral, windowsClipboardRetryDelayMs)
}
