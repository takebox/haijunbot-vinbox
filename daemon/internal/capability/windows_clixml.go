package capability

// This file implements decoding of PowerShell's CLIXML output.
//
// Background: why stderr is CLIXML
// ==============================
// When Windows PowerShell 5.1 finds that **standard error is not a terminal** (the daemon capturing stderr through a
// pipe is exactly this case), it serializes the error stream and progress stream into CLIXML (an XML dialect) rather
// than plain text. The real-machine measured windows.script.exec stderr looks like:
//
//	#< CLIXML
//	<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">
//	  <Obj S="progress" RefId="0">...<AV>Preparing modules for first use.</AV>...</Obj>
//	  <S S="Error">Write-Error 'x' : x_x000D__x000A_</S>
//	</Objs>
//
// This hands the caller a pile of XML noise instead of readable error text.
//
// Why not turn it off on the PowerShell side
// ==========================================
// Approaches already tried and ruled out:
//
//  1. $ProgressPreference = 'SilentlyContinue': only suppresses the **content of the progress stream**,
//     but in -EncodedCommand mode progress records are still serialized into CLIXML
//     (real-machine measurement: <Obj S="progress"> nodes still appear). And it has no effect on the error stream at all.
//
//  2. -OutputFormat Text: works when -Command is used alone, but is **incompatible with -EncodedCommand**
//     (-EncodedCommand implies -OutputFormat XML, so the latter is ignored); real-machine measurement still outputs CLIXML.
//     And -Command would corrupt non-ASCII text due to the ANSI code page, so it cannot be used either.
//
//  3. -Command - (pass the script via stdin) + -OutputFormat Text: works, but the reading encoding of stdin
//     is affected by [Console]::InputEncoding, and the statement that sets that encoding must itself be passed via stdin,
//     creating a chicken-and-egg problem; and it loses the UTF-16LE non-ASCII guarantee of -EncodedCommand.
//
// So the choice is to decode CLIXML on the Go side: retain the non-ASCII guarantee of -EncodedCommand while restoring
// stderr to readable plain text. This is the only approach that does not sacrifice correctness.
//
// Decoding rules
// ==============
//   - CLIXML uses <S S="Error">text</S> to represent a segment of error text (the S attribute is the stream name);
//   - newlines in the text are encoded as the literal "_x000D__x000A_" (the hexadecimal escape of CR LF),
//     which must be restored to "\r\n"; other _xHHHH_ forms are similarly restored to the corresponding Unicode code point;
//   - XML entities (&amp; &lt; &gt; &quot; &apos;) must be unescaped;
//   - non-CLIXML input is returned as-is (maintaining compatibility with plain-text stderr).
//
// Only the standard library is depended on (encoding/xml or a hand-written scan); no third-party dependencies are introduced.

import (
	"strconv"
	"strings"
	"unicode/utf16"
)

// clixmlHeader is the fixed start marker of CLIXML output.
// It is used to determine whether a segment of stderr is CLIXML, avoiding needless parsing of ordinary text.
const clixmlHeader = "#< CLIXML"

// decodePowerShellStderr restores PowerShell's stderr output to readable plain text.
//
// If the input does not contain the CLIXML marker, it is returned as-is (ordinary plain-text stderr is unaffected).
// If it contains CLIXML, all <S S="...">text</S> nodes are extracted and joined by line,
// restoring _xHHHH_ escapes and XML entities at the same time.
//
// The reason for not introducing encoding/xml: the <S> nodes in CLIXML may contain unescaped bare text,
// and we only care about the text content, so a hand-written scan is simpler and more tolerant (an XML parser fails
// entirely on malformed input, whereas here "best-effort restoration" is desired).
//
// The preamble parameter is the script preamble (windowsPowerShellPreamble), used to strip echo noise:
// PowerShell echoes the full source of the offending statement for a **non-terminating error** (such as Write-Error),
// and since the preamble is prepended at the very front of the script, it is echoed along with it (exposed by real-machine
// measurement). This is pure noise and should be stripped. An empty string means no stripping.
func decodePowerShellStderr(raw, preamble string) string {
	if !strings.Contains(raw, clixmlHeader) {
		return stripPowerShellPreambleEcho(raw, preamble)
	}

	// Strip the "#< CLIXML" line, keeping only the XML body.
	body := raw
	if idx := strings.Index(body, clixmlHeader); idx >= 0 {
		body = body[idx+len(clixmlHeader):]
	}

	var segments []string
	rest := body
	for {
		// Locate the next <S ...> start tag.
		open := strings.Index(rest, "<S ")
		if open < 0 {
			break
		}
		// Find the '>' that ends the start tag.
		openEnd := strings.Index(rest[open:], ">")
		if openEnd < 0 {
			break
		}
		openEnd += open
		// Locate the corresponding </S>.
		closeIdx := strings.Index(rest[openEnd:], "</S>")
		if closeIdx < 0 {
			break
		}
		closeIdx += openEnd

		text := rest[openEnd+1 : closeIdx]
		segments = append(segments, decodeCLIXMLText(text))
		rest = rest[closeIdx+len("</S>"):]
	}

	if len(segments) == 0 {
		// There is a CLIXML header but no extractable <S> node (such as a progress-only <Obj>):
		// return an empty string — at this point stderr has no substantive error information, and the XML noise should not be surfaced.
		return ""
	}

	// Each <S> segment already contains newlines (after restoration), so they are joined directly.
	// After joining, strip the preamble echo noise (the CLIXML <S S="Error"> also echoes the preamble statement).
	return stripPowerShellPreambleEcho(strings.TrimRight(strings.Join(segments, ""), "\r\n"), preamble)
}

// stripPowerShellPreambleEcho strips the PowerShell preamble statement echoed in stderr.
//
// Background: PowerShell echoes the full source of the offending statement for a **non-terminating error** (such as Write-Error).
// Since windowsPowerShellPreamble is prepended at the very front of the user script, it is echoed along with it, like:
//
//	[Console]::OutputEncoding = ...::UTF8; $OutputEncoding = ...::UTF8;
//	 [Console]::InputEncoding = ...::UTF8; $ProgressPreference = 'SilentlyContinue'
//	Write-Error 'x' : x
//
// In the echoed text, the preamble's newlines have been rewritten by PowerShell (the const has no newlines, yet the echo
// has extra newlines and indentation), so a verbatim match cannot be done. Instead, **feature-line filtering** is used
// here: a line that contains both "OutputEncoding" and "UTF8", or a line that contains both "ProgressPreference" and
// "SilentlyContinue", is regarded as a preamble echo line and discarded.
//
// This only removes noise lines and does not affect the user script's own error information (the probability that these
// identifiers appear together in user code is extremely low, and even if they do, only that line is lost).
func stripPowerShellPreambleEcho(s, preamble string) string {
	if preamble == "" || s == "" {
		return s
	}
	// Quick check: with no encoding-setting feature, there is no need to process line by line.
	if !strings.Contains(s, "OutputEncoding") && !strings.Contains(s, "ProgressPreference") {
		return s
	}

	lines := strings.Split(s, "\n")
	kept := lines[:0]
	for _, line := range lines {
		if isPowerShellPreambleEchoLine(line) {
			continue
		}
		kept = append(kept, line)
	}
	return strings.Join(kept, "\n")
}

// isPowerShellPreambleEchoLine determines whether a line is an echo of windowsPowerShellPreamble.
func isPowerShellPreambleEchoLine(line string) bool {
	if strings.Contains(line, "OutputEncoding") && strings.Contains(line, "UTF8") {
		return true
	}
	if strings.Contains(line, "ProgressPreference") && strings.Contains(line, "SilentlyContinue") {
		return true
	}
	return false
}

// decodeCLIXMLText restores the escapes in a CLIXML text node.
//
//   - _xHHHH_ → the character composed of the corresponding UTF-16 code unit (such as _x000D_ → '\r');
//   - XML entity unescaping.
func decodeCLIXMLText(s string) string {
	s = decodeCLIXMLHexEscapes(s)
	return unescapeXMLEntities(s)
}

// decodeCLIXMLHexEscapes restores escapes of the form _xHHHH_.
//
// CLIXML writes control characters and some special characters as _xHHHH_ (H is hexadecimal).
// Consecutive escapes are restored one by one (such as _x000D__x000A_ → "\r\n").
//
// Note: a surrogate pair appears as two consecutive _xHHHH_. Here consecutive escape sequences are collected and then
// uniformly processed with utf16.Decode, ensuring non-BMP characters (such as emoji) are correctly restored.
func decodeCLIXMLHexEscapes(s string) string {
	if !strings.Contains(s, "_x") {
		return s
	}

	var out strings.Builder
	out.Grow(len(s))

	// pending collects consecutive _xHHHH_ code units, decoded uniformly when non-escape content is encountered.
	var pending []uint16
	flush := func() {
		if len(pending) == 0 {
			return
		}
		out.WriteString(string(utf16.Decode(pending)))
		pending = pending[:0]
	}

	i := 0
	for i < len(s) {
		if s[i] == '_' && i+6 < len(s) && s[i+1] == 'x' && s[i+6] == '_' {
			if v, err := strconv.ParseUint(s[i+2:i+6], 16, 32); err == nil {
				pending = append(pending, uint16(v))
				i += 7
				continue
			}
		}
		flush()
		out.WriteByte(s[i])
		i++
	}
	flush()
	return out.String()
}

// unescapeXMLEntities unescapes the five predefined XML entities.
//
// Order matters: entities other than &amp; must be replaced first, and &amp; handled last,
// otherwise "&amp;lt;" would be incorrectly restored to "<" (it should be restored to the literal "&lt;").
func unescapeXMLEntities(s string) string {
	if !strings.Contains(s, "&") {
		return s
	}
	replacer := strings.NewReplacer(
		"&lt;", "<",
		"&gt;", ">",
		"&quot;", `"`,
		"&apos;", "'",
		"&amp;", "&",
	)
	return replacer.Replace(s)
}
