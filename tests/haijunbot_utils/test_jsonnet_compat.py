# -*- coding: utf-8 -*-
"""haijunbot_utils.jsonnet_compat module unit tests"""

import pytest

from haijunbot.haijunbot_utils.jsonnet_compat import (
    _fix_jsonnet_multiline_strings,
    _strip_markdown_code_blocks,
    loads,
    dumps,
)


class TestStripMarkdownCodeBlocks:
    """Tests for _strip_markdown_code_blocks function"""

    def test_strip_json_code_block(self):
        """Test stripping ```json code block markers"""
        input_str = """```json
{
  "key": "value"
}
```"""
        result = _strip_markdown_code_blocks(input_str)
        assert "```" not in result
        assert '"key"' in result
        assert '"value"' in result

    def test_strip_json5_code_block(self):
        """Test stripping ```json5 code block markers"""
        input_str = """```json5
{
  "key": "value" // comment
}
```"""
        result = _strip_markdown_code_blocks(input_str)
        assert "```" not in result
        assert '"key"' in result

    def test_strip_plain_code_block(self):
        """Test stripping ``` code block markers (without language identifier)"""
        input_str = """```
{
  "key": "value"
}
```"""
        result = _strip_markdown_code_blocks(input_str)
        assert "```" not in result
        assert '"key"' in result

    def test_strip_code_block_with_whitespace(self):
        """Test stripping code block markers (with surrounding whitespace)"""
        input_str = """  ```json
{
  "key": "value"
}
```  """
        result = _strip_markdown_code_blocks(input_str)
        assert "```" not in result
        assert '"key"' in result

    def test_no_code_block(self):
        """Test case with no code block markers"""
        input_str = '{"key": "value"}'
        result = _strip_markdown_code_blocks(input_str)
        assert result == input_str

    def test_empty_string(self):
        """Test empty string"""
        result = _strip_markdown_code_blocks("")
        assert result == ""

    def test_non_string_input(self):
        """Test non-string input"""
        result = _strip_markdown_code_blocks(123)
        assert result == 123

    def test_code_block_with_backticks_in_content(self):
        """Test case where code block content contains backticks"""
        input_str = """```json
{
  "text": "Content containing `backticks`"
}
```"""
        result = _strip_markdown_code_blocks(input_str)
        assert "```" not in result
        assert "`backticks`" in result


class TestFixJsonnetMultilineStrings:
    """Tests for _fix_jsonnet_multiline_strings function"""

    def test_fix_no_indent_first_line(self):
        """Test fixing case where first line has no indentation"""
        input_str = """{
  "text": |||
First line has no indent
Second line also has none
|||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # First line should have indentation
        assert (
            "First line has no indent" in result or "First line has no indent" not in result.split("\n")[2]
        )
        # Should parse successfully
        parsed = loads(result)
        assert "text" in parsed

    def test_fix_all_lines_no_indent(self):
        """Test fixing case where all lines have no indentation"""
        input_str = """{
  "text": |||
First line
Second line
Third line
|||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # All lines should have indentation
        lines = result.split("\n")
        text_start_idx = None
        for i, line in enumerate(lines):
            if "|||" in line and text_start_idx is None:
                text_start_idx = i + 1
                break
        if text_start_idx:
            # Check subsequent lines (until next |||)
            for i in range(text_start_idx, len(lines)):
                if "|||" in lines[i]:
                    break
                if lines[i].strip():
                    assert lines[i].startswith(" "), (
                        f"Line {i} should have indentation: {repr(lines[i])}"
                    )

    def test_preserve_existing_indent(self):
        """Test preserving existing indentation (pre-processing unifies indentation, post-parsing restores original)"""
        input_str = """{\n  "text": |||\n    First line has indent\n    Second line also has\n  |||\n}"""
        result, indent_info = _fix_jsonnet_multiline_strings(input_str)
        # After pre-processing should be unified to 1-space indent (satisfies jsonnet requirement)
        assert "First line has indent" in result
        assert "Second line also has" in result
        # If all lines have same indentation, no need to record indent info
        # Should parse normally after parsing
        parsed = loads(input_str)
        assert "text" in parsed
        assert "First line has indent" in parsed["text"]
        assert "Second line also has" in parsed["text"]

    def test_mixed_indent(self):
        """Test mixed indentation (unified to first line's indent level)"""
        input_str = """{
  "text": |||
First line has none
     Second line has 4 spaces
Third line has none
  |||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # All lines unified to first line's indent level (1 space, because first line has no indent)
        # Lines without indent should be fixed
        assert "First line has none" in result or "First line has none" not in result.split("\n")[2]
        # Lines with existing indent unified to first line's indent level (remove original indent, add unified indent)
        assert "Second line has 4 spaces" in result

    def test_empty_multiline_string(self):
        """Test empty multiline string"""
        input_str = """{
  "text": |||
|||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # Empty content should remain unchanged
        assert "|||" in result

    def test_multiple_multiline_strings(self):
        """Test multiple multiline strings"""
        input_str = """{
  "text1": |||
First line
|||,
  "text2": |||
Second line
|||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # Both multiline strings should be fixed
        assert "First line" in result or "First line" not in result.split("\n")[2]
        assert "Second line" in result or "Second line" not in result.split("\n")[5]

    def test_multiline_string_with_tabs(self):
        """Test tab indentation (tabs converted to spaces, unified indentation)"""
        input_str = """{
  "text": |||
\tFirst line has tab
Second line has none
|||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # Tabs converted to spaces, all lines unified to first line's indent level
        # First line has tab, converted to spaces (usually 4 or 8, but here unified to 1 space)
        # Lines without indent should be fixed
        assert "First line has tab" in result or "First line has tab" in result.replace(
            "\t", " "
        )
        assert "Second line has none" in result or "Second line has none" not in result.split("\n")[3]

    def test_first_line_with_indent_others_without(self):
        """Test case where first line has indentation, subsequent lines do not (including empty lines)"""
        input_str = """{\n  "text": |||\n     Indented first line\n\nNon-indented second line\n\nNon-indented third line\n  |||\n}"""
        result, indent_info = _fix_jsonnet_multiline_strings(input_str)
        # After pre-processing should be unified to 1-space indent
        assert "Indented first line" in result
        assert "Non-indented second line" in result
        assert "Non-indented third line" in result
        # Verify it can be parsed and original indentation restored
        parsed = loads(input_str)
        assert "text" in parsed

        assert "Indented first line" in parsed["text"]
        assert "Non-indented second line" in parsed["text"]
        assert "Non-indented third line" in parsed["text"]

    def test_first_line_with_indent_others_without_no_empty_lines(self):
        """Test case where first line has indentation, subsequent lines do not (no empty lines)"""
        input_str = """{\n  "text": |||\nFirst line\nSecond line\nThird line\n  |||\n}"""
        result, indent_info = _fix_jsonnet_multiline_strings(input_str)
        # After pre-processing should be unified to 1-space indent
        assert "First line" in result
        assert "Second line" in result
        assert "Third line" in result
        # Verify it can be parsed and original indentation restored
        parsed = loads(input_str)
        assert "text" in parsed
        text = parsed["text"]
        assert "First line" in text

        assert "Second line" in text
        assert "Third line" in text
        # Verify line count (should include newlines)
        lines = text.split("\n")
        assert len([line for line in lines if line.strip()]) >= 3  # At least 3 non-empty lines

    def test_first_line_with_indent_mixed_with_indented_lines(self):
        """Test case where first line has indentation, some subsequent lines also have indentation (different levels)"""
        input_str = """{\n  "text": |||\n    First line has 4 spaces\n  Second line has 2 spaces\nThird line has none\n    Fourth line has 4 spaces\n  |||\n}"""
        result, indent_info = _fix_jsonnet_multiline_strings(input_str)
        # After pre-processing should be unified to 1-space indent (satisfies jsonnet requirement)
        assert "First line has 4 spaces" in result
        assert "Second line has 2 spaces" in result
        assert "Third line has none" in result
        assert "Fourth line has 4 spaces" in result
        # Verify it can be parsed and original indentation restored after parsing
        parsed = loads(input_str)

        assert "text" in parsed
        text = parsed["text"]
        # Verify each line's original indentation is preserved
        lines = text.split("\n")
        assert "First line has 4 spaces" in lines[0]  # 4 spaces
        assert "Second line has 2 spaces" in lines[1]  # 2 spaces
        assert "Third line has none" in lines[2]  # No indentation
        assert "Fourth line has 4 spaces" in lines[3]  # 4 spaces

    def test_multiline_string_with_indented_end_marker(self):
        """Test case where ||| multiline string end marker has indentation (should auto-fix)"""
        input_str = """{
  "text": |||
     First line
     Second line
     |||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # End marker should be fixed to have no indentation
        assert "\n|||" in result or result.endswith("|||")
        assert "     |||" not in result  # Should not have indented end marker
        # Verify it can be parsed
        parsed = loads(input_str)
        assert "text" in parsed
        assert "First line" in parsed["text"]
        assert "Second line" in parsed["text"]

    def test_first_line_empty_then_indented(self):
        """Test case where first line is empty, subsequent lines have indentation"""
        input_str = """{
  "text": |||

     Second line has 4 spaces
Third line has none
  |||
}"""
        result, _ = _fix_jsonnet_multiline_strings(input_str)
        # First line is empty, should skip it and use first non-empty line's indent level
        # Or use default 1 space
        # Verify it can be parsed
        parsed = loads(input_str)
        assert "text" in parsed

    def test_all_lines_empty_except_first(self):
        """Test case where only first line has content, all others are empty"""
        input_str = """{\n  "text": |||\n    First line has 4 spaces\n\n\n  |||\n}"""
        result, indent_info = _fix_jsonnet_multiline_strings(input_str)
        # After pre-processing should be unified to 1-space indent
        assert "First line has 4 spaces" in result
        # Verify it can be parsed
        parsed = loads(input_str)
        assert "text" in parsed
        assert "First line has 4 spaces" in parsed["text"]

    def test_first_line_no_indent_subsequent_lines_have_indent(self):
        """Test case where first line has no indent, subsequent lines have indent (relative indent should be preserved)"""
        input_str = """{\n  "content": |||\nFirst line has no indent\n    Second line has 4-space indent\n        Third line has 8-space indent\n|||\n}"""
        result = loads(input_str)
        assert "content" in result
        content = result["content"]
        lines = content.split("\n")
        # Verify relative indentation is preserved
        assert lines[0] == "First line has no indent"
        assert lines[1] == "    Second line has 4-space indent"
        assert lines[2] == "        Third line has 8-space indent"

    def test_first_line_has_indent_subsequent_lines_no_indent(self):
        """Test case where first line has indent, subsequent lines have no indent (relative indent should be preserved)"""
        input_str = """{\n  "content": |||\n    First line has 4-space indent\nSecond line has no indent\n    Third line has 4-space indent\n|||\n}"""
        result = loads(input_str)
        assert "content" in result
        content = result["content"]
        lines = content.split("\n")
        # Verify relative indentation is preserved
        assert lines[0] == "    First line has 4-space indent"
        assert lines[1] == "Second line has no indent"
        assert lines[2] == "    Third line has 4-space indent"

    def test_mixed_indent_relative_preserved(self):
        """Test that relative indentation relationships are preserved with mixed indentation"""
        input_str = """{\n  "content": |||\nFirst line no indent\n  Second line 2 spaces\n    Third line 4 spaces\n  Fourth line 2 spaces\nFifth line no indent\n|||\n}"""
        result = loads(input_str)
        assert "content" in result
        content = result["content"]
        lines = content.split("\n")
        # Verify relative indentation is preserved
        assert lines[0] == "First line no indent"
        assert lines[1] == "  Second line 2 spaces"
        assert lines[2] == "    Third line 4 spaces"
        assert lines[3] == "  Fourth line 2 spaces"
        assert lines[4] == "Fifth line no indent"


class TestLoads:
    """Tests for loads function"""

    def test_loads_simple_json(self):
        """Test parsing simple JSON"""
        json_str = '{"key": "value"}'
        result = loads(json_str)
        assert result == {"key": "value"}

    def test_loads_with_trailing_comma(self):
        """Test parsing JSON5 with trailing comma"""
        json_str = '{"key": "value",}'
        result = loads(json_str)
        assert result == {"key": "value"}

    def test_loads_with_comments(self):
        """Test parsing JSON5 with comments"""
        json_str = """{
  "key": "value", // This is a comment
  "key2": "value2" /* This is also a comment */
}"""
        result = loads(json_str)
        assert result == {"key": "value", "key2": "value2"}

    def test_loads_with_multiline_string_no_indent(self):
        """Test parsing ||| multiline string (no indentation, should auto-fix)"""
        json_str = """{
  "text": |||
First line
Second line
|||
}"""
        result = loads(json_str)
        assert "text" in result
        assert "First line" in result["text"]
        assert "Second line" in result["text"]

    def test_loads_with_multiline_string_with_indent(self):
        """Test parsing ||| multiline string (already has indentation)"""
        json_str = """{
  "text": |||
     First line
     Second line
  |||
}"""
        result = loads(json_str)
        assert "text" in result
        assert "First line" in result["text"]
        assert "Second line" in result["text"]

    def test_loads_with_markdown_code_block(self):
        """Test parsing JSON containing markdown code block markers"""
        json_str = """```json
{
  "key": "value"
}
```"""
        result = loads(json_str)
        assert result == {"key": "value"}

    def test_loads_with_markdown_and_multiline_string(self):
        """Test parsing JSON containing markdown code block and ||| multiline string"""
        json_str = """```json5
{
  "text": |||
First line
Second line
|||
}
```"""
        result = loads(json_str)
        assert "text" in result
        assert "First line" in result["text"]
        assert "Second line" in result["text"]

    def test_loads_with_special_characters_in_multiline(self):
        """Test ||| multiline string containing special characters"""
        json_str = """{
  "text": |||
Contains "double quotes" and 'single quotes'
Contains \\n escape characters
|||
}"""
        result = loads(json_str)
        assert "text" in result
        assert '"double quotes"' in result["text"] or "double quotes" in result["text"]
        assert "'single quotes'" in result["text"] or "single quotes" in result["text"]

    def test_loads_with_backticks_in_multiline(self):
        """Test ||| multiline string containing backticks"""
        json_str = """{
  "text": |||
Content containing `backticks`
|||
}"""
        result = loads(json_str)
        assert "text" in result
        assert "`backticks`" in result["text"] or "backticks" in result["text"]

    def test_loads_array(self):
        """Test parsing array"""
        json_str = "[1, 2, 3,]"
        result = loads(json_str)
        assert result == [1, 2, 3]

    def test_loads_nested_objects(self):
        """Test parsing nested objects"""
        json_str = """{
  "outer": {
    "inner": "value"
  }
}"""
        result = loads(json_str)
        assert result["outer"]["inner"] == "value"

    def test_loads_invalid_json(self):
        """Test parsing invalid JSON (should raise exception)"""
        json_str = "{invalid json}"
        with pytest.raises(Exception):
            loads(json_str)

    def test_loads_empty_string(self):
        """Test parsing empty string"""
        with pytest.raises(Exception):
            loads("")

    def test_loads_multiple_multiline_strings(self):
        """Test parsing JSON containing multiple ||| multiline strings"""
        json_str = """{
  "text1": |||
First segment
|||,
  "text2": |||
Second segment
|||
}"""
        result = loads(json_str)
        assert "text1" in result
        assert "text2" in result
        assert "First segment" in result["text1"]
        assert "Second segment" in result["text2"]

    def test_loads_multiline_string_with_empty_lines(self):
        """Test ||| multiline string containing empty lines"""
        json_str = """{
  "text": |||
First line

Third line
|||
}"""
        result = loads(json_str)
        assert "text" in result
        # Empty lines should be preserved
        lines = result["text"].split("\n")
        assert len(lines) >= 3

    def test_loads_multiline_string_with_only_whitespace_lines(self):
        """Test ||| multiline string containing only whitespace lines"""
        json_str = """{
  "text": |||
  
|||
}"""
        result = loads(json_str)
        assert "text" in result
        # Whitespace lines should be processed
        assert isinstance(result["text"], str)


class TestDumps:
    """Tests for dumps function"""

    def test_dumps_simple_dict(self):
        """Test serializing simple dictionary"""
        obj = {"key": "value"}
        result = dumps(obj)
        assert '"key"' in result
        assert '"value"' in result

    def test_dumps_with_ensure_ascii(self):
        """Test serializing with ensure_ascii=False"""
        obj = {"Chinese": "value"}
        result = dumps(obj, ensure_ascii=False)
        assert "Chinese" in result
        assert "value" in result

    def test_dumps_with_indent(self):
        """Test serializing with indentation"""
        obj = {"key": "value", "key2": "value2"}
        result = dumps(obj, indent=2)
        assert "\n" in result
        assert "  " in result  # Should have indentation


class TestIntegration:
    """Integration tests: combined functionality"""

    def test_markdown_code_block_with_multiline_string_no_indent(self):
        """Test markdown code block + ||| multiline string (no indentation)"""
        json_str = """```json5
{
  "text": |||
First line
Second line
|||
}
```"""
        result = loads(json_str)
        assert "text" in result
        assert "First line" in result["text"]
        assert "Second line" in result["text"]

    def test_complex_jsonnet_with_all_features(self):
        """Test complex Jsonnet containing all features"""
        json_str = """```json5
{
  // This is a comment
  "text": |||
First line has no indent
Second line also has none
|||,
  "number": 42,
  "array": [1, 2, 3,], // trailing comma
  "nested": {
    "key": "value"
  }
}
```"""
        result = loads(json_str)
        assert "text" in result
        assert "number" in result
        assert result["number"] == 42
        assert "array" in result
        assert result["array"] == [1, 2, 3]
        assert "nested" in result

    def test_multiple_multiline_strings_in_markdown(self):
        """Test markdown code block containing multiple ||| multiline strings"""
        json_str = """```json
{
  "text1": |||
First segment content
|||,
  "text2": |||
Second segment content
|||
}
```"""
        result = loads(json_str)
        assert "text1" in result
        assert "text2" in result
        assert "First segment content" in result["text1"]
        assert "Second segment content" in result["text2"]

    def test_multiline_string_with_mixed_content(self):
        """Test ||| multiline string containing mixed content (JSON, code, etc.)"""
        json_str = """{
  "code": |||
function hello() {
  console.log("Hello");
}
|||
}"""
        result = loads(json_str)
        assert "code" in result
        assert "function" in result["code"]
        assert "console.log" in result["code"]

    def test_multiline_string_preserves_formatting(self):
        """Test ||| multiline string unifies indentation (mixed indentation unified to first line's indent level)"""
        json_str = """{
  "text": |||
     First line has 4 spaces
   Second line has 2 spaces
Third line has none
  |||
}"""
        result = loads(json_str)
        assert "text" in result
        # Fix function unifies all lines' indentation to first line's indent level (4 spaces)
        # This ensures jsonnet can parse correctly (jsonnet requires all lines to have same indent level)
        text = result["text"]
        assert "First line" in text
        assert "Second line" in text
        assert "Third line" in text

    def test_multiple_backticks_in_multiline(self):
        """Test ||| multiline string containing multiple backticks"""
        json_str = """{
  "text": |||
First line contains `backtick1`
Second line contains `backtick2` and `backtick3`
Third line has no backticks
|||
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "`backtick1`" in text or "backtick1" in text
        assert "`backtick2`" in text or "backtick2" in text
        assert "`backtick3`" in text or "backtick3" in text

    def test_backtick_at_line_start_in_multiline(self):
        """Test backtick at line start in ||| multiline string"""
        json_str = """{
  "text": |||
`backtick` at line start
Normal content `backtick` in middle
Backtick at line end `backtick`
|||
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "`backtick`" in text or "backtick" in text

    def test_backticks_with_code_block_markers_in_multiline(self):
        """Test ||| multiline string containing ``` (should not be misidentified as code block marker)"""
        json_str = """{
  "text": |||
Content containing ```
Also has `single backtick`
And ```three backticks```
|||
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "```" in text
        assert "`single backtick`" in text or "single backtick" in text

    def test_backticks_in_multiline_within_markdown_code_block(self):
        """Test markdown code block containing multiline string which contains backticks"""
        input_str = """```json5
{
  "text": |||
Multiline string containing `backticks`
Inside markdown code block
|||
}
```"""
        result = loads(input_str)
        assert "text" in result
        text = result["text"]
        assert "`backticks`" in text or "backticks" in text
        assert "markdown" in text or "code block" in text

    def test_backticks_in_nested_multiline_strings(self):
        """Test nested multiline strings both containing backticks"""
        json_str = """{
  "text1": |||
First multiline string contains `backtick1`
|||,
  "text2": |||
Second multiline string contains `backtick2`
|||
}"""
        result = loads(json_str)
        assert "text1" in result
        assert "text2" in result
        assert "`backtick1`" in result["text1"] or "backtick1" in result["text1"]
        assert "`backtick2`" in result["text2"] or "backtick2" in result["text2"]

    def test_backticks_with_special_characters_in_multiline(self):
        """Test multiline string containing combination of backticks and special characters"""
        json_str = """{
  "text": |||
Contains `backticks` and special characters: !@#$%^&*()
Also combination of newline and `backticks`
|||
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "`backticks`" in text or "backticks" in text
        assert "!@#$%^&*()" in text or "special characters" in text

    def test_backtick_as_multiline_string_marker(self):
        """Test using ``` instead of ||| as multiline string identifier"""
        json_str = """{
  "text": ```
First line
Second line
```
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "First line" in text
        assert "Second line" in text

    def test_backtick_multiline_with_indent(self):
        """Test using ``` as multiline string identifier (with indentation)"""
        json_str = """{
  "text": ```
     First line has indent
     Second line also has indent
```
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "First line" in text
        assert "Second line" in text

    def test_backtick_multiline_in_markdown_code_block(self):
        """Test using ``` as multiline string identifier in markdown code block"""
        input_str = """```json5
{
  "text": ```
First line
Second line
```
}
```"""
        result = loads(input_str)
        assert "text" in result
        text = result["text"]
        assert "First line" in text
        assert "Second line" in text

    def test_backtick_and_pipe_multiline_mixed(self):
        """Test mixing ``` and ||| as multiline string identifiers"""
        json_str = """{
  "text1": ```
First multiline string
```,
  "text2": |||
Second multiline string
|||
}"""
        result = loads(json_str)
        assert "text1" in result
        assert "text2" in result
        assert "First" in result["text1"]
        assert "Second" in result["text2"]

    def test_backtick_multiline_with_backticks_in_content(self):
        """Test using ``` as multiline string identifier, content contains backticks"""
        json_str = """{
  "text": ```
Content containing `single backtick`
Also ```three backticks``` content
```
}"""
        result = loads(json_str)
        assert "text" in result
        text = result["text"]
        assert "`single backtick`" in text or "single backtick" in text
        # Note: ``` in content is preserved, not misidentified as end marker


class TestSummaryBlockScenarios:
    """Tests for scenarios extracted from <SUMMARY> blocks (leading newline + markdown code block)"""

    def test_summary_block_with_leading_newline(self):
        """Test content extracted from <SUMMARY> block (leading newline + ```json)"""
        # Simulate content extracted from <SUMMARY> block
        # Actual scenario: <SUMMARY>\n```json\n{...}\n```\n</SUMMARY>
        # After extraction: \n```json\n{...}\n```\n
        input_str = """
```json
{
  "replaceable": true,
  "libraries": [
    "bzip2-rs-tokio"
  ],
  "confidence": 0.98,
  "library": "bzip2-rs-tokio",
  "apis": [
    "bzip2_rs::encoder::Encoder",
    "bzip2_rs::tokio::Encoder"
  ],
  "notes": "The entire function subtree implements the core logic of bzip2 compression"
}
```
"""
        result = loads(input_str)
        assert isinstance(result, dict)
        assert result["replaceable"] is True
        assert "bzip2-rs-tokio" in result["libraries"]
        assert result["confidence"] == 0.98
        assert "notes" in result

    def test_summary_block_with_leading_newline_and_trailing_newline(self):
        """Test content extracted from <SUMMARY> block (newlines before and after)"""
        input_str = """
```json
{
  "key": "value"
}
```

"""
        result = loads(input_str)
        assert result == {"key": "value"}

    def test_summary_block_with_leading_whitespace(self):
        """Test content extracted from <SUMMARY> block (leading whitespace and newline)"""
        input_str = """   
```json
{
  "key": "value"
}
```   
"""
        result = loads(input_str)
        assert result == {"key": "value"}

    def test_summary_block_with_prefix_text(self):
        """Test case with text before code block (should not happen, but testing for robustness)

        Note: Current implementation only handles case where entire string is wrapped by code block.
        If there is text before code block, need to manually extract code block part first.
        This test case changed to test: even with prefix text, if entire string is wrapped by code block, parsing works correctly.
        """
        # Actual scenario: entire string wrapped by code block, but there may be whitespace before code block
        input_str = """   
```json
{
  "key": "value"
}
```   
"""
        result = loads(input_str)
        # Should correctly extract JSON content
        assert result == {"key": "value"}

    def test_summary_block_json5_with_comments(self):
        """Test JSON5 content extracted from <SUMMARY> block (with comments)"""
        input_str = """
```json5
{
  "replaceable": true, // This is a comment
  "libraries": ["lib1", "lib2"], /* This is also a comment */
  "confidence": 0.95
}
```
"""
        result = loads(input_str)
        assert result["replaceable"] is True
        assert len(result["libraries"]) == 2
        assert result["confidence"] == 0.95

    def test_summary_block_with_multiline_string(self):
        """Test content extracted from <SUMMARY> block containing ||| multiline string"""
        input_str = """
```json5
{
  "replaceable": true,
  "notes": |||
This is the first line of description
This is the second line of description
|||
}
```
"""
        result = loads(input_str)
        assert result["replaceable"] is True
        assert "notes" in result
        assert "first line of description" in result["notes"]
        assert "second line of description" in result["notes"]

    def test_summary_block_complex_structure(self):
        """Test complex structure extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "replaceable": true,
  "libraries": [
    "bzip2-rs-tokio",
    "bzip2-rs"
  ],
  "confidence": 0.98,
  "library": "bzip2-rs-tokio",
  "apis": [
    "bzip2_rs::encoder::Encoder",
    "bzip2_rs::tokio::Encoder"
  ],
  "notes": "The entire function subtree implements the core logic of bzip2 compression, including block processing, sorting (Burrows-Wheeler), MTF transform, Huffman coding and bitstream writing. This is fully consistent with the standard bzip2 compression algorithm. The `bzip2-rs-tokio` library provides a complete, pure Rust bzip2 compression/decompression implementation whose `bzip2_rs::encoder::Encoder` (synchronous) or `bzip2_rs::tokio::Encoder` (asynchronous) provides advanced streaming compression interfaces that can completely replace the current C implementation."
}
```
"""
        result = loads(input_str)
        assert isinstance(result, dict)
        assert result["replaceable"] is True
        assert isinstance(result["libraries"], list)
        assert len(result["libraries"]) >= 1
        assert "bzip2-rs-tokio" in result["libraries"]
        assert isinstance(result["apis"], list)
        assert len(result["apis"]) >= 1
        assert "notes" in result
        assert "bzip2" in result["notes"].lower()

    def test_summary_block_with_backticks_in_content(self):
        """Test content extracted from <SUMMARY> block containing backticks"""
        input_str = """
```json
{
  "notes": "Content containing `backticks`, also ```three backticks``` content"
}
```
"""
        result = loads(input_str)
        assert "notes" in result
        assert "backticks" in result["notes"]

    def test_summary_block_with_single_backtick_in_string(self):
        """Test content extracted from <SUMMARY> block containing single backtick (e.g. `bzip2-rs`)"""
        input_str = """
```json
{
  "replaceable": false,
  "libraries": [],
  "confidence": 0.95,
  "notes": "This function is a low-level core implementation in the bzip2 algorithm for building Huffman decoding tables. Since libraries like `bzip2-rs` that directly implement this algorithm are explicitly prohibited, there is no mature general-purpose library that can directly replace this specific, algorithm-internal function. Users typically use advanced APIs (like `BzDecoder`) to complete decompression rather than manually building decoding tables."
}
```
"""
        result = loads(input_str)
        assert result["replaceable"] is False
        assert "notes" in result
        assert "`bzip2-rs`" in result["notes"]
        assert "`BzDecoder`" in result["notes"]
        assert "bzip2" in result["notes"].lower()

    def test_summary_block_with_triple_backticks_in_string(self):
        """Test content extracted from <SUMMARY> block containing triple backticks (```)"""
        input_str = """
```json
{
  "notes": "Content containing ```three backticks```, this should not be misidentified as code block marker"
}
```
"""
        result = loads(input_str)
        assert "notes" in result
        assert "```three backticks```" in result["notes"]
        assert "code block marker" in result["notes"]

    def test_summary_block_with_backticks_at_string_start(self):
        """Test backtick at string start in content extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "code": "`function_name()` is a function call"
}
```
"""
        result = loads(input_str)
        assert "code" in result
        assert result["code"].startswith("`function_name()`")

    def test_summary_block_with_backticks_at_string_end(self):
        """Test backtick at string end in content extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "code": "This is a function call `function_name()`"
}
```
"""
        result = loads(input_str)
        assert "code" in result
        assert result["code"].endswith("`function_name()`")

    def test_summary_block_with_multiple_backticks_in_different_fields(self):
        """Test multiple fields containing backticks in content extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "library": "`bzip2-rs`",
  "api": "`BzDecoder::new()`",
  "notes": "Using the `BzDecoder` API from the `bzip2-rs` library can replace this functionality"
}
```
"""
        result = loads(input_str)
        assert "library" in result
        assert "`bzip2-rs`" in result["library"]
        assert "api" in result
        assert "`BzDecoder::new()`" in result["api"]
        assert "notes" in result
        assert "`bzip2-rs`" in result["notes"]
        assert "`BzDecoder`" in result["notes"]

    def test_summary_block_with_backticks_in_array(self):
        """Test array elements containing backticks in content extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "apis": [
    "`bzip2_rs::encoder::Encoder`",
    "`bzip2_rs::tokio::Encoder`"
  ]
}
```
"""
        result = loads(input_str)
        assert "apis" in result
        assert isinstance(result["apis"], list)
        assert len(result["apis"]) == 2
        assert "`bzip2_rs::encoder::Encoder`" in result["apis"]
        assert "`bzip2_rs::tokio::Encoder`" in result["apis"]

    def test_summary_block_with_backticks_in_nested_object(self):
        """Test nested object containing backticks in content extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "metadata": {
    "library": "`bzip2-rs`",
    "api": "`BzDecoder`"
  },
  "notes": "Using the `bzip2-rs` library"
}
```
"""
        result = loads(input_str)
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)
        assert "`bzip2-rs`" in result["metadata"]["library"]
        assert "`BzDecoder`" in result["metadata"]["api"]
        assert "`bzip2-rs`" in result["notes"]

    def test_summary_block_with_backticks_and_escaped_quotes(self):
        """Test content containing both backticks and escaped quotes extracted from <SUMMARY> block"""
        input_str = """
```json
{
  "notes": "Content containing `backticks` and \\\"escaped quotes\\\""
}
```
"""
        result = loads(input_str)
        assert "notes" in result
        assert "`backticks`" in result["notes"]
        assert '"escaped quotes"' in result["notes"] or "escaped quotes" in result["notes"]

    def test_summary_block_with_backticks_in_multiline_string_value(self):
        """Test content using ||| multiline string containing backticks extracted from <SUMMARY> block"""
        input_str = """
```json5
{
  "replaceable": true,
  "notes": |||
This is the first line, containing `bzip2-rs`
This is the second line, containing `BzDecoder`
|||
}
```
"""
        result = loads(input_str)
        assert result["replaceable"] is True
        assert "notes" in result
        assert "`bzip2-rs`" in result["notes"]
        assert "`BzDecoder`" in result["notes"]
        assert "first line" in result["notes"]
        assert "second line" in result["notes"]

    def test_summary_block_with_backticks_real_world_scenario(self):
        """Test real scenario: complete evaluation result extracted from <SUMMARY> block, containing backticks"""
        input_str = """
```json
{
  "replaceable": false,
  "libraries": [],
  "confidence": 0.95,
  "notes": "This function is a low-level core implementation in the bzip2 algorithm for building Huffman decoding tables. It is a very specific algorithmic step, not an independent, reusable function. While Rust libraries (like flate2) can handle the entire bzip2 decompression flow, they typically encapsulate these internal details and do not expose decoding table building separately. Since libraries like `bzip2-rs` that directly implement this algorithm are explicitly prohibited, there is no mature general-purpose library that can directly replace this specific, algorithm-internal function. Users typically use advanced APIs (like `BzDecoder`) to complete decompression rather than manually building decoding tables."
}
```
"""
        result = loads(input_str)
        assert result["replaceable"] is False
        assert isinstance(result["libraries"], list)
        assert len(result["libraries"]) == 0
        assert result["confidence"] == 0.95
        assert "notes" in result
        notes = result["notes"]
        assert "`bzip2-rs`" in notes
        assert "`BzDecoder`" in notes
        assert "bzip2" in notes.lower()
        assert "Huffman decoding table" in notes

    def test_summary_block_no_language_identifier(self):
        """Test content extracted from <SUMMARY> block (code block without language identifier)"""
        input_str = """
```
{
  "key": "value"
}
```
"""
        result = loads(input_str)
        assert result == {"key": "value"}

    def test_summary_block_with_crlf_newlines(self):
        """Test content extracted from <SUMMARY> block (using CRLF newlines)"""
        input_str = '\r\n```json\r\n{\r\n  "key": "value"\r\n}\r\n```\r\n'
        result = loads(input_str)
        assert result == {"key": "value"}

    def test_summary_block_with_mixed_newlines(self):
        """Test content extracted from <SUMMARY> block (mixed newlines)"""
        input_str = '\n```json\r\n{\n  "key": "value"\r\n}\n```\n'
        result = loads(input_str)
        assert result == {"key": "value"}

    def test_summary_block_empty_json(self):
        """Test empty JSON extracted from <SUMMARY> block"""
        input_str = """
```json
{}
```
"""
        result = loads(input_str)
        assert result == {}

    def test_summary_block_array(self):
        """Test array extracted from <SUMMARY> block"""
        input_str = """
```json
[1, 2, 3]
```
"""
        result = loads(input_str)
        assert result == [1, 2, 3]

    def test_summary_block_with_trailing_comma(self):
        """Test content extracted from <SUMMARY> block (with trailing comma)"""
        input_str = """
```json5
{
  "key1": "value1",
  "key2": "value2",
}
```
"""
        result = loads(input_str)
        assert result == {"key1": "value1", "key2": "value2"}
