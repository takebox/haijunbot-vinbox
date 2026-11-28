package service

// This file holds the pure logic on the Windows side for "external command output encoding". It deliberately has no //go:build windows
// tag so it compiles and unit-tests on Linux (the local dev environment is Linux, with no Windows runtime).
// This is consistent with the approach in internal/capability/windows_encoding.go.
//
// Background: why transcoding is needed
// ==========
// schtasks / taskkill / tasklist are native console programs that write text according to the **console output code page**--
// GBK/CP936 on Chinese Windows, not UTF-8. Go's os/exec only returns raw bytes, so a plain
// string(out) would interpret GBK as UTF-8, producing garbled text (mojibake) that is unreadable,
// and the user cannot understand the failure reason (this happens in real machines when install fails).
//
// Fix strategy: no GBK decoding table
// ==========
// The standard library has no GBK decoding capability, and the project forbids introducing golang.org/x/text.
// Therefore this file relies on PowerShell to do the "decode with the system default encoding → output as UTF-8"
// transcoding; the script is in buildPowerShellScript. The caller (runCmd in task_windows.go) passes
// the script with -EncodedCommand, avoiding non-ASCII characters in the script being corrupted when command-line arguments are parsed with the ANSI code page.

import (
	"encoding/base64"
	"strings"
	"unicode/utf16"
)

// buildPowerShellScript builds the PowerShell script that runs an external command and transcodes its output.
//
// Extracted separately so it can be unit-tested (this machine is Linux and cannot actually run powershell.exe):
// argument quoting correctness directly determines whether schtasks receives the expected /TR value.
//
// Script structure (the order must not change):
//
//	$ProgressPreference='SilentlyContinue';
//	$ErrorActionPreference='Continue';
//	$out = & <name> <args...> 2>&1 | Out-String;   # OutputEncoding is still the system default here, correctly decoding the child process output
//	$code = $LASTEXITCODE;                          # capture the external command exit code (a pipe does not change it)
//	[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
//	[Console]::Out.Write($out)                     # write out as UTF-8 for the Go side to read directly
//	exit $code                                      # pass the external command's exit code through to Go
//
// Notes:
//   - Step 1 must read the external command's output with the **system default** [Console]::OutputEncoding:
//     that is GBK on Chinese systems, matching the bytes schtasks writes, so PowerShell can decode it into an internal
//     string correctly. Setting it to UTF-8 first and then reading would decode GBK bytes as UTF-8 and get mojibake.
//   - Step 2 then changes the encoding to UTF-8 and writes out; a plain string(out) on the Go side is the correct text.
//   - `2>&1` merges stderr into stdout, so failure reasons (e.g. "access denied") can also be captured.
//   - `Out-String` serializes the external command's output objects into text, preserving the full content.
//   - Use [Console]::Out.Write rather than Write-Output, to avoid appending an extra newline.
//   - $ErrorActionPreference='Continue': prevents PowerShell from interrupting when the external command returns a non-zero exit code,
//     so its output text can still be read.
//   - **Must explicitly exit $code**: because $ErrorActionPreference='Continue', PowerShell still exits with 0 by default
//     when the external command fails, and Go's cmd.Output() would wrongly treat it as success (in a real machine: schtasks
//     creation failed yet "the scheduled task has been created" was printed). With $LASTEXITCODE captured and passed through,
//     the Go side can correctly detect the failure. Note $LASTEXITCODE must be captured right after the external command runs;
//     a pipe (| Out-String) does not change it.
//   - $ProgressPreference='SilentlyContinue': PowerShell by default also outputs progress records (the progress
//     stream), and after they are merged into stdout by `2>&1`, they are serialized into CLIXML (shaped like `#< CLIXML`
//     plus a piece of XML), burying the real failure reason (in a real machine, install failure is exactly this). After closing
//     the progress stream, stdout only contains the external command's real output; the fallback cleanup is stripPowerShellClixml.
func buildPowerShellScript(name string, args []string) string {
	var b strings.Builder
	b.WriteString("$ProgressPreference='SilentlyContinue'; ")
	b.WriteString("$ErrorActionPreference='Continue'; ")
	b.WriteString("$out = & ")
	b.WriteString(quotePowerShellArg(name))
	for _, a := range args {
		b.WriteString(" ")
		b.WriteString(quotePowerShellArg(a))
	}
	b.WriteString(" 2>&1 | Out-String; ")
	b.WriteString("$code = $LASTEXITCODE; ")
	b.WriteString("[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; ")
	b.WriteString("[Console]::Out.Write($out); ")
	b.WriteString("exit $code")
	return b.String()
}

// stripPowerShellClixml removes CLIXML noise from PowerShell output, keeping only readable text.
//
// Background: when PowerShell's output is redirected to a pipe, it serializes certain streams (progress / verbose / warning
// etc.) into CLIXML--starting with `#< CLIXML` followed by a `<Objs ...>...</Objs>` XML block.
// In a real machine, when install fails, what is mixed into stdout is exactly the CLIXML of a progress record, burying
// real error text like "access denied" (and the Chinese in the XML is written out as GBK, still mojibake after transcoding).
//
// Processing strategy (plain text, no XML parsing, to avoid introducing dependencies):
//  1. Remove the content from `#< CLIXML` to the end of that line (the CLIXML header);
//  2. Remove all `<Objs ...>...</Objs>` blocks (multi-line matching);
//  3. Remove leftover orphan XML tag lines and extra blank lines.
//
// Why this fallback is kept: $ProgressPreference='SilentlyContinue' only turns off the progress stream;
// if other streams (such as warning) still produce CLIXML, this keeps the error message readable.
func stripPowerShellClixml(s string) string {
	if !strings.Contains(s, "#< CLIXML") && !strings.Contains(s, "<Objs") {
		return s
	}
	// 1. Remove `#< CLIXML` to the end of the line.
	if i := strings.Index(s, "#< CLIXML"); i >= 0 {
		lineEnd := strings.IndexByte(s[i:], '\n')
		if lineEnd < 0 {
			s = s[:i]
		} else {
			s = s[:i] + s[i+lineEnd+1:]
		}
	}
	// 2. Remove <Objs ...>...</Objs> blocks (non-greedy, multi-line).
	for {
		start := strings.Index(s, "<Objs")
		if start < 0 {
			break
		}
		end := strings.Index(s[start:], "</Objs>")
		if end < 0 {
			// No closing tag; truncate to the end directly.
			s = s[:start]
			break
		}
		s = s[:start] + s[start+end+len("</Objs>"):]
	}
	// 3. Clean up leftover orphan tag lines and extra blank lines.
	var lines []string
	for _, ln := range strings.Split(s, "\n") {
		t := strings.TrimSpace(ln)
		if strings.HasPrefix(t, "<") && strings.HasSuffix(t, ">") {
			continue
		}
		lines = append(lines, ln)
	}
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

// quotePowerShellArg adds the necessary quotes and escapes for a single argument per PowerShell rules.
//
// Rules: when an argument contains whitespace or PowerShell special characters, wrap it in single quotes; a single quote
// inside the argument is represented by two consecutive single quotes per PowerShell convention.
// No variable expansion happens inside single-quoted strings, so characters like $ need no extra handling.
func quotePowerShellArg(s string) string {
	if s == "" {
		return "''"
	}
	if !strings.ContainsAny(s, " \t'\"$`&|<>;(){}[],") {
		return s
	}
	return "'" + strings.ReplaceAll(s, "'", "''") + "'"
}

// encodePowerShellCommand encodes the script into the base64(UTF-16LE) required by -EncodedCommand.
//
// Consistent with the implementation in internal/capability/windows_encoding.go: base64 is pure ASCII,
// fully bypassing the non-ASCII character corruption caused by "command-line arguments being parsed with the ANSI code page".
// No BOM is added (-EncodedCommand expects BOM-less base64).
func encodePowerShellCommand(script string) string {
	units := utf16.Encode([]rune(script))
	buf := make([]byte, 0, len(units)*2)
	for _, u := range units {
		// UTF-16 code units are written little-endian: low byte first, then high byte.
		buf = append(buf, byte(u&0xFF), byte(u>>8))
	}
	return base64.StdEncoding.EncodeToString(buf)
}
