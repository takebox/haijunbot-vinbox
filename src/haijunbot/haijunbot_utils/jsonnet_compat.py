# -*- coding: utf-8 -*-
"""Jsonnet compatibility layer - provides an interface similar to json5.loads()"""

import json
from typing import Any
from typing import Dict
from typing import Match

import _jsonnet


def _fix_jsonnet_multiline_strings(s: str) -> tuple[str, Dict[str, str]]:
    """
    Fix the indentation problem of jsonnet ||| multiline strings.

    jsonnet requires that the first line of content after ||| must be indented (at least one space),
    otherwise it reports "text block's first line must start with whitespace".

    This function automatically detects and fixes this problem.

    Parameters:
        s: The input string

    Returns:
        (The fixed string, a dictionary of the first line's original indentation information)
        The keys of the indentation information dictionary are the markers of ||| multiline strings in the fixed string,
        and the values are the original indentation level of the first line (if the first line originally had indentation but subsequent lines did not)
    """

    import re

    # Match the ||| multiline string pattern
    # Format: ||| followed by optional whitespace and newline, then the content, and finally |||
    # Use non-greedy matching to ensure matching the nearest |||
    pattern = r"(\|\|\|)(\s*\n)(.*?)(\n\s*\|\|\|)"

    def fix_match(match: Match[str]) -> tuple[str, Dict[str, str]]:
        start_marker = match.group(1)  # |||
        whitespace_after = match.group(2)  # whitespace and newline
        content = match.group(3)  # multiline content
        end_marker = match.group(4)  # newline, whitespace, and |||

        # jsonnet requires that the end marker ||| must be on its own line without indentation (starting from the beginning of the line)
        # Regardless of the original format, uniformly fix it to '\n|||'
        end_marker = "\n|||"

        # If the content is empty, return the fixed end marker
        if not content.strip():
            return start_marker + whitespace_after + content + end_marker, {}

        # Split the content by lines

        lines = content.split("\n")

        # Determine the indentation level:
        # 1. If the first line is indented, use the first line's indentation level
        # 2. If the first line is empty, find the indentation level of the first non-empty line
        # 3. If the first line is not indented, use the default single space
        # 4. If all lines are empty, use the default single space
        indent_level = 1  # Default indentation level
        first_line_has_indent = False
        first_line_indent = 0

        if lines:
            first_line = lines[0]
            if first_line.strip() and first_line.startswith((" ", "\t")):
                # The first line already has indentation; record its indentation level
                first_line_indent = len(first_line) - len(first_line.lstrip())
                first_line_has_indent = True
                indent_level = first_line_indent
                # Ensure there is at least one space
                if indent_level == 0:
                    indent_level = 1
            elif not first_line.strip():
                # The first line is empty; find the indentation level of the first non-empty line
                for line in lines[1:]:
                    if line.strip():
                        if line.startswith((" ", "\t")):
                            # Found the first non-empty line; use its indentation level
                            indent_level = len(line) - len(line.lstrip())
                            # Ensure there is at least one space
                            if indent_level == 0:
                                indent_level = 1
                        else:
                            # The first non-empty line has no indentation; use the default single space
                            indent_level = 1
                        break

        # Uniformly set the indentation level for every line
        # jsonnet's ||| requires all lines to have the same indentation level, and strips the smallest common indentation prefix of all lines
        # To preserve the first line's indentation, we need to:
        # 1. Give all lines the same indentation (satisfying jsonnet's requirement)
        # 2. Record the first line's original indentation level, to restore it after parsing
        # 3. After parsing, add the original indentation to the first line

        # Check whether there are subsequent lines without indentation (which need fixing)
        has_unindented_lines = False
        if first_line_has_indent:
            for line in lines[1:]:
                if line.strip() and not line.startswith((" ", "\t")):
                    has_unindented_lines = True
                    break

        # Record the original indentation information of all lines (for restoration)
        # If there are lines with different indentation levels, we need to record each line's original indentation
        original_indents = {}  # key: line content (after removing indentation), value: original indentation level
        has_mixed_indents = False

        # Record the original indentation information of all lines (regardless of whether indentation is mixed, it needs to be recorded for restoration)
        # Save the original indentation string rather than its length, to preserve special characters such as Tab
        if lines:
            seen_indents = set()
            for line in lines:
                if line.strip():
                    line_indent = len(line) - len(line.lstrip())
                    seen_indents.add(line_indent)
                    line_content = line.lstrip()
                    # Record the original indentation string (preserving characters such as Tab)
                    original_indents[line_content] = line[:line_indent]

            # If there are multiple different indentation levels, the indentation is mixed
            if len(seen_indents) > 1:
                has_mixed_indents = True

        # If the first line is indented but subsequent lines are not, we also need to record it
        if first_line_has_indent and has_unindented_lines:
            has_mixed_indents = True
            # Record the original indentation string of the first line
            first_line_content = lines[0].lstrip()
            original_indents[first_line_content] = lines[0][:first_line_indent]

        # jsonnet's text block rule: all lines must be indented >= the first line's indentation
        # Therefore we unify all lines to the same base indentation, and restore the original indentation via the restoration logic
        base_indent = 1  # Uniformly use 1-space indentation

        # Unify the indentation of all lines to the base indentation (satisfying jsonnet's requirement)

        for i in range(len(lines)):
            line = lines[i]
            if line.strip():  # Only process non-empty lines
                line_content = line.lstrip()
                lines[i] = " " * base_indent + line_content

        # Reassemble the content
        fixed_content = "\n".join(lines)

        # Return the fixed content and the original indentation information
        # As long as there is mixed indentation, return the indentation information for restoration
        indent_info = original_indents if has_mixed_indents else {}

        return start_marker + whitespace_after + fixed_content + end_marker, indent_info

    # Use the DOTALL flag so that . matches newlines
    # Collect all fixed content and indentation information
    all_indent_info = {}
    fixed_parts = []
    last_end = 0

    for match in re.finditer(pattern, s, flags=re.DOTALL):
        # Add the part before the match
        fixed_parts.append(s[last_end : match.start()])

        # Fix the matched part
        fixed_content, indent_info = fix_match(match)
        fixed_parts.append(fixed_content)

        # Merge the indentation information
        all_indent_info.update(indent_info)

        last_end = match.end()

    # Add the remaining part
    fixed_parts.append(s[last_end:])
    fixed = "".join(fixed_parts)

    return fixed, all_indent_info


def _restore_first_line_indent(obj: Any, indent_info: Dict[str, str]) -> Any:
    """
    Restore the first line's original indentation.

    Parameters:
        obj: The parsed object
        indent_info: The indentation information dictionary

    Returns:
        The object with the indentation restored
    """
    if not indent_info:
        return obj

    if isinstance(obj, dict):
        return {k: _restore_first_line_indent(v, indent_info) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_restore_first_line_indent(item, indent_info) for item in obj]
    elif isinstance(obj, str):
        # Check whether each line of the string originally had indentation
        # If original indentation information exists, restore each line's original indentation
        if indent_info:
            lines = obj.split("\n")
            restored_lines = []
            for line in lines:
                if line.strip():
                    # Remove the current line's indentation to get the content
                    line_content = line.lstrip()
                    # Check whether there is corresponding original indentation information
                    if line_content in indent_info:
                        # Restore the original indentation (directly use the saved indentation string, preserving characters such as Tab)
                        original_indent = indent_info[line_content]
                        restored_lines.append(original_indent + line_content)
                    else:
                        # No original indentation information; keep it as-is
                        restored_lines.append(line)
                else:
                    # Keep empty lines as-is
                    restored_lines.append(line)
            return "\n".join(restored_lines)
        return obj
    else:
        return obj


def _convert_backtick_multiline_strings(s: str) -> str:
    """
    Convert ``` multiline string markers in JSON values to |||.

    This function recognizes the ``` markers at JSON value positions (such as "key": ```) and converts them to |||,
    for compatibility with jsonnet's ||| multiline string syntax.

    Recognition rules:
    - A ``` at a JSON value position (after a colon) will be converted to |||
    - After removing the markdown code block markers, any remaining ``` is usually a multiline string marker

    Parameters:
        s: The input string (markdown code block markers should already be removed)

    Returns:
        The converted string (``` converted to |||)
    """

    import re

    # Match the ``` multiline strings in JSON values
    # Format: ": ``` or ":``` followed by optional whitespace and newline, then the content, and finally a newline and ```
    # Use non-greedy matching to ensure matching the nearest ```
    # Note: this pattern matches the ``` at JSON value positions (after a colon)
    pattern = r"(:\s*)(```)(\s*\n)(.*?)(\n\s*```)"

    def convert_match(match: Match[str]) -> str:
        colon = match.group(1)  # colon and optional whitespace
        match.group(2)  # ``` (kept for matching, but not used)
        whitespace_after = match.group(3)  # whitespace and newline
        content = match.group(4)  # multiline content
        match.group(5)  # newline, whitespace, and ``` (kept for matching, but not used)

        # Convert ``` to |||
        return colon + "|||" + whitespace_after + content + "\n|||"

    # Replace all matched patterns
    result = re.sub(pattern, convert_match, s, flags=re.DOTALL)

    return result


def _strip_markdown_code_blocks(s: Any) -> Any:
    """
    Remove markdown code block markers (such as ```json5, ```json, ``` etc.) from a string

    Supports the following scenarios:
    - Whitespace/newlines before and after the code block: \n```json\n{...}\n```
    - The code block is not at the start of the string: prefix\n```json\n{...}\n```
    - Standard format: ```json\n{...}\n```

    Parameters:
        s: The input string

    Returns:
        The cleaned string (if the input is not a string, it is returned as-is)
    """

    import re

    # If the input is not a string, return it as-is
    if not isinstance(s, str):
        return s

    # First strip leading and trailing whitespace, but keep the internal structure
    block = s.strip()

    # Use regular expressions to match and remove the code block markers
    # Try multiple patterns, from strict to lenient

    # Pattern 1: standard format, the code block is at the beginning and end
    # Match: ```language + optional whitespace + optional newline + content + optional newline + optional whitespace + ```
    pattern1 = r"^```[a-zA-Z0-9_+-]*\s*\n?(.*?)\n?\s*```\s*$"
    match = re.match(pattern1, block, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Pattern 2: there may be extra whitespace/newlines before and after the code block, but the code block is required to be at the start or end of the string
    # Only matches cases where the entire string is wrapped by a code block, not ``` inside JSON values
    # Match: start of string (optional whitespace) + ```language + optional whitespace + newline + content + newline + optional whitespace + ``` + end of string (optional whitespace)
    pattern2 = r"^\s*```[a-zA-Z0-9_+-]*\s*\n(.*?)\n\s*```\s*$"
    match = re.match(pattern2, block, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Pattern 3: a more lenient match that does not require newlines, but the code block is required to be at the start or end of the string
    # Only matches cases where the entire string is wrapped by a code block, not ``` inside JSON values
    # Match: start of string (optional whitespace) + ```language + optional whitespace + content + optional whitespace + ``` + end of string (optional whitespace)
    pattern3 = r"^\s*```[a-zA-Z0-9_+-]*\s*(.*?)\s*```\s*$"
    match = re.match(pattern3, block, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If none of the regexes match, try manual removal (backward compatible)
    # But only handle cases where the entire string is wrapped by a code block (the code block is at the beginning and there are also ``` at the end)
    block_stripped = block.strip()
    if block_stripped.startswith("```") and block_stripped.rstrip().endswith("```"):
        # Find the content after the leading ```
        after_start = 3  # Skip ```
        # Skip the language identifier (if present)
        while after_start < len(block_stripped) and block_stripped[after_start] not in (
            "\n",
            "\r",
            " ",
            "\t",
        ):
            after_start += 1
        # Skip whitespace characters
        while after_start < len(block_stripped) and block_stripped[after_start] in (
            " ",
            "\t",
        ):
            after_start += 1
        # Skip the newline character (if present)
        if after_start < len(block_stripped) and block_stripped[after_start] in (
            "\n",
            "\r",
        ):
            after_start += 1
            # Handle \r\n
            if (
                after_start < len(block_stripped)
                and block_stripped[after_start] == "\n"
                and block_stripped[after_start - 1] == "\r"
            ):
                after_start += 1

        # Find the position of the trailing ```
        before_end = block_stripped.rfind("```")
        if before_end > after_start:
            # Extract the content (removing the trailing ``` and the preceding whitespace)
            content = block_stripped[after_start:before_end].rstrip()
            return content

    return block.strip()


def loads(s: str) -> Any:
    """
    Parse a JSON/Jsonnet format string and return a Python object

    Uses jsonnet for parsing, supporting JSON5 features (comments, trailing commas, multiline strings, etc.)

    Automatically handles:
    - markdown code block markers: if the input contains code block markers such as ```json5, ```json, ``` etc.,
      these markers are automatically removed before parsing.
    - ``` multiline strings: supports using ``` instead of ||| as the multiline string marker (at JSON value positions).
    - ||| multiline string indentation: automatically adds the necessary indentation to the first line of ||| multiline strings,
      avoiding the "text block's first line must start with whitespace" error.

    Parameters:
        s: The string to parse (may contain markdown code block markers)

    Returns:
        The parsed Python object

    Raises:
        ValueError: If parsing fails
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError("The input string is empty")

    # Automatically remove markdown code block markers
    cleaned = _strip_markdown_code_blocks(s)

    # Validation: ensure there are no residual code block markers (at the start or end of the string)
    # ``` within the string content is legal and needs no handling
    cleaned_stripped = cleaned.strip()
    if cleaned_stripped.startswith("```") or cleaned_stripped.rstrip().endswith("```"):
        # If there are still code block markers, the manual removal logic may not have worked correctly
        # Try removing again (to guard against edge cases)
        cleaned = _strip_markdown_code_blocks(cleaned)
        cleaned_stripped = cleaned.strip()
        # If they are still present, it may be a formatting issue; log a warning but continue processing
        if cleaned_stripped.startswith("```") or cleaned_stripped.rstrip().endswith(
            "```"
        ):
            # Last attempt: manually remove the leading and trailing ```
            while cleaned_stripped.startswith("```"):
                # Find the first newline or end of string
                first_newline = cleaned_stripped.find("\n", 3)
                if first_newline >= 0:
                    cleaned_stripped = cleaned_stripped[first_newline + 1 :]
                else:
                    # No newline; it may be in ```language format
                    cleaned_stripped = cleaned_stripped[3:].lstrip()
                    # Skip the language identifier
                    while cleaned_stripped and cleaned_stripped[0] not in (
                        "\n",
                        "\r",
                        " ",
                        "\t",
                    ):
                        cleaned_stripped = cleaned_stripped[1:]
                    break
            while cleaned_stripped.rstrip().endswith("```"):
                last_backticks = cleaned_stripped.rfind("```")
                if last_backticks >= 0:
                    cleaned_stripped = cleaned_stripped[:last_backticks].rstrip()
                else:
                    break
            cleaned = cleaned_stripped

    # Convert ``` multiline string markers in JSON values to |||
    cleaned = _convert_backtick_multiline_strings(cleaned)

    # Automatically fix the indentation problem of ||| multiline strings
    cleaned, indent_info = _fix_jsonnet_multiline_strings(cleaned)

    # Parse using jsonnet, supporting JSON5 and Jsonnet syntax
    try:
        result_json = _jsonnet.evaluate_snippet("<input>", cleaned)
    except RuntimeError as e:
        # Provide more detailed error information
        error_msg = str(e)
        if "Could not lex the character" in error_msg or "`" in error_msg:
            # Check whether there are residual code block markers
            if "```" in cleaned:
                # Find the positions of all ```
                import re

                matches = list(re.finditer(r"```", cleaned))
                for match in matches:
                    pos = match.start()
                    context = cleaned[max(0, pos - 30) : min(len(cleaned), pos + 50)]
                    # Check whether it is inside a string (surrounded by quotes)
                    before = cleaned[:pos]
                    # Simple check: if there is an odd number of quotes before it, it is inside a string
                    quote_count = before.count('"') - before.count('\\"')
                    if quote_count % 2 == 0:
                        # Not inside a string; it may be a residual code block marker
                        raise ValueError(
                            f"Residual code block marker ``` detected at position {pos}. "
                            f"Context: {repr(context)}. "
                            f"Original error: {error_msg}"
                        )
        raise ValueError(f"JSON parsing failed: {error_msg}")

    # jsonnet returns a JSON string, which needs to be parsed again
    result = json.loads(result_json)

    # If the first line originally had indentation, restore the first line's indentation
    if indent_info:
        result = _restore_first_line_indent(result, indent_info)

    return result


def dumps(obj: Any, **kwargs: Any) -> str:
    """
    Serialize a Python object to a JSON string

    Parameters:
        obj: The object to serialize
        **kwargs: Other parameters passed to json.dumps

    Returns:
        A JSON string
    """
    return json.dumps(obj, **kwargs)
