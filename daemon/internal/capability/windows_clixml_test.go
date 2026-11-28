package capability

// This file unit-tests the CLIXML decoding functions in windows_clixml.go.
//
// No build tags: the decoder only depends on the standard library and can run tests directly on Linux.
// The test samples are taken from real-machine (Windows 10 Pro 25H2 / PowerShell 5.1) measured output,
// ensuring the decoding rules match the real CLIXML format.

import (
	"strings"
	"testing"
)

// Real-machine measured sample: the CLIXML stderr produced by Write-Error.
const realCLIXMLErrorSample = "#< CLIXML\r\n" +
	"<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\">" +
	"<S S=\"Error\">Write-Error 'plain error test' : plain error test_x000D__x000A_</S>" +
	"<S S=\"Error\">    + CategoryInfo          : NotSpecified: (:) [Write-Error], WriteErrorException_x000D__x000A_</S>" +
	"<S S=\"Error\">    + FullyQualifiedErrorId : Microsoft.PowerShell.Commands.WriteErrorException_x000D__x000A_</S>" +
	"<S S=\"Error\"> _x000D__x000A_</S>" +
	"</Objs>"

// TestDecodePowerShellStderrRealSample verifies decoding with the real-machine sample.
func TestDecodePowerShellStderrRealSample(t *testing.T) {
	got := decodePowerShellStderr(realCLIXMLErrorSample, "")

	if strings.Contains(got, "CLIXML") || strings.Contains(got, "<Objs") || strings.Contains(got, "_x000D_") {
		t.Fatalf("the decoded result still contains CLIXML residue:\n%q", got)
	}
	if !strings.Contains(got, "plain error test") {
		t.Errorf("the error text was not restored:\n%q", got)
	}
	if !strings.Contains(got, "WriteErrorException") {
		t.Errorf("FullyQualifiedErrorId was not restored:\n%q", got)
	}
	// _x000D__x000A_ should be restored to a newline (\r\n).
	if !strings.Contains(got, "\r\n") {
		t.Errorf("_x000D__x000A_ was not restored to a newline:\n%q", got)
	}
}

// TestDecodePowerShellStderrNonCLIXML verifies that plain-text stderr is returned as-is.
func TestDecodePowerShellStderrNonCLIXML(t *testing.T) {
	plain := "error: file not found\nsecond line\n"
	if got := decodePowerShellStderr(plain, ""); got != plain {
		t.Errorf("non-CLIXML input should be returned as-is:\nexpected %q\ngot %q", plain, got)
	}
}

// TestDecodePowerShellStderrProgressOnly verifies that CLIXML containing only progress nodes returns an empty string.
//
// Real-machine measurement: the first module load produces <Obj S="progress">...<AV>Preparing modules for
// first use.</AV>...</Obj>, which is noise with no substantive error information and should be discarded rather than surfaced.
func TestDecodePowerShellStderrProgressOnly(t *testing.T) {
	progressOnly := "#< CLIXML\r\n" +
		"<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\">" +
		"<Obj S=\"progress\" RefId=\"0\"><TN RefId=\"0\"><T>System.Management.Automation.PSCustomObject</T><T>System.Object</T></TN>" +
		"<MS><I64 N=\"SourceId\">1</I64><PR N=\"Record\"><AV>Preparing modules for first use.</AV><AI>0</AI><Nil /><PI>-1</PI><PC>-1</PC><T>Completed</T><SR>-1</SR><SD> </SD></PR></MS></Obj>" +
		"</Objs>"

	if got := decodePowerShellStderr(progressOnly, ""); got != "" {
		t.Errorf("CLIXML containing only progress should return an empty string, got %q", got)
	}
}

// TestDecodePowerShellStderrMixedProgressAndError verifies that when progress + error are mixed, only the error is kept.
func TestDecodePowerShellStderrMixedProgressAndError(t *testing.T) {
	mixed := "#< CLIXML\r\n" +
		"<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\">" +
		"<Obj S=\"progress\" RefId=\"0\"><MS><PR N=\"Record\"><AV>Preparing modules for first use.</AV></PR></MS></Obj>" +
		"<S S=\"Error\">real error message_x000D__x000A_</S>" +
		"</Objs>"

	got := decodePowerShellStderr(mixed, "")
	if strings.Contains(got, "Preparing modules") {
		t.Errorf("progress noise should not appear in the result:\n%q", got)
	}
	if !strings.Contains(got, "real error message") {
		t.Errorf("the error text was not restored:\n%q", got)
	}
}

// TestDecodePowerShellStderrHTMLEntities verifies XML entity unescaping.
func TestDecodePowerShellStderrHTMLEntities(t *testing.T) {
	sample := "#< CLIXML\r\n" +
		"<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\">" +
		"<S S=\"Error\">a &lt; b &amp;&amp; c &gt; d &quot;quoted&quot; &apos;single&apos;</S>" +
		"</Objs>"

	got := decodePowerShellStderr(sample, "")
	want := `a < b && c > d "quoted" 'single'`
	if got != want {
		t.Errorf("XML entity unescaping error:\nexpected %q\ngot %q", want, got)
	}
}

// TestDecodePowerShellStderrAmpersandBeforeEntity verifies that &amp;lt; is correctly restored to the literal "&lt;".
//
// This checks the replacement order: if &amp; is replaced before &lt;, "&amp;lt;" would be incorrectly restored to "<".
func TestDecodePowerShellStderrAmpersandBeforeEntity(t *testing.T) {
	sample := "#< CLIXML\r\n" +
		"<Objs Version=\"1.1.0.1\" xmlns=\"http://schemas.microsoft.com/powershell/2004/04\">" +
		"<S S=\"Error\">&amp;lt;</S>" +
		"</Objs>"

	got := decodePowerShellStderr(sample, "")
	if got != "&lt;" {
		t.Errorf("&amp;lt; should be restored to the literal %q, got %q", "&lt;", got)
	}
}

// TestDecodeCLIXMLHexEscapesNonBMP verifies that surrogate pairs (non-BMP characters) are correctly restored.
func TestDecodeCLIXMLHexEscapesNonBMP(t *testing.T) {
	// The UTF-16 surrogate pair for U+1F600 (😀) is D83D DE00.
	got := decodeCLIXMLHexEscapes("emoji:_xD83D__xDE00_")
	if got != "emoji:😀" {
		t.Errorf("surrogate pair restore error: expected %q, got %q", "emoji:😀", got)
	}
}

// TestDecodeCLIXMLHexEscapesPlain verifies that text without escapes is returned as-is.
func TestDecodeCLIXMLHexEscapesPlain(t *testing.T) {
	plain := "no escapes here"
	if got := decodeCLIXMLHexEscapes(plain); got != plain {
		t.Errorf("escape-free text should be returned as-is: expected %q, got %q", plain, got)
	}
}

// TestDecodePowerShellStderrEmpty verifies empty input.
func TestDecodePowerShellStderrEmpty(t *testing.T) {
	if got := decodePowerShellStderr("", ""); got != "" {
		t.Errorf("empty input should return an empty string, got %q", got)
	}
}

// realPreambleEchoStderr is a real-machine measured stderr sample: when Write-Error triggers a non-terminating error,
// PowerShell echoes the full source of the offending statement, and since windowsPowerShellPreamble is prepended at the
// very front of the script, it is itself echoed too (the newlines were rewritten by PowerShell; the const has none).
const realPreambleEchoStderr = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8;\r\n" +
	" [Console]::InputEncoding = [System.Text.Encoding]::UTF8; $ProgressPreference = 'SilentlyContinue'\r\n" +
	"Write-Error 'this is an error'; Write-Output 'after' : this is an error\r\n" +
	"    + CategoryInfo          : NotSpecified: (:) [Write-Error], WriteErrorException\r\n" +
	"    + FullyQualifiedErrorId : Microsoft.PowerShell.Commands.WriteErrorException\r\n "

// TestStripPowerShellPreambleEchoRealSample verifies, with the real-machine sample, that the preamble echo is stripped
// and that the user script's own error information is fully preserved.
func TestStripPowerShellPreambleEchoRealSample(t *testing.T) {
	got := decodePowerShellStderr(realPreambleEchoStderr, windowsPowerShellPreamble)

	if strings.Contains(got, "OutputEncoding") || strings.Contains(got, "ProgressPreference") {
		t.Errorf("the preamble echo was not stripped:\n%q", got)
	}
	// The user script's own error information must be preserved.
	for _, want := range []string{"this is an error", "CategoryInfo", "FullyQualifiedErrorId"} {
		if !strings.Contains(got, want) {
			t.Errorf("the user error information %q was mistakenly removed:\n%q", want, got)
		}
	}
}

// TestStripPowerShellPreambleEchoEmptyPreamble verifies that no stripping is done when the preamble is empty.
func TestStripPowerShellPreambleEchoEmptyPreamble(t *testing.T) {
	in := "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\r\nreal error\r\n"
	if got := decodePowerShellStderr(in, ""); got != in {
		t.Errorf("nothing should be stripped when the preamble is empty:\nexpected %q\ngot %q", in, got)
	}
}

// TestStripPowerShellPreambleEchoKeepsUserCode verifies that an identifier with the same name in the user script is
// filtered if it shares a line with the encoding-setting feature (a known trade-off), but other lines are unaffected.
func TestStripPowerShellPreambleEchoKeepsUserCode(t *testing.T) {
	in := "my OutputEncoding check failed\r\n" + // contains OutputEncoding but no UTF8 → kept
		"real error line\r\n"
	got := decodePowerShellStderr(in, windowsPowerShellPreamble)
	if !strings.Contains(got, "my OutputEncoding check failed") {
		t.Errorf("a line containing only OutputEncoding without UTF8 should not be removed:\n%q", got)
	}
	if !strings.Contains(got, "real error line") {
		t.Errorf("a normal error line was mistakenly removed:\n%q", got)
	}
}
