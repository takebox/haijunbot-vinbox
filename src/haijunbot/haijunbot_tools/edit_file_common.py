"""Common logic for file editing tools: encoding detection, backup rollback, quote normalization matching, diff preview, etc.

This module only provides reusable functions and does not define tool classes (to avoid being mistakenly loaded by the tool registry).
"""

import os
import shutil
import sys
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.config import (
    detect_file_encoding,
    get_default_encoding,
    read_text_file,
    save_exception,
)


def get_preferred_encodings() -> List[str]:
    """Get the tool-level preferred encoding order. Windows prefers gbk, other platforms prefer utf-8."""
    if sys.platform == "win32":
        return ["gbk", "utf-8"]
    return ["utf-8", "gbk"]


def read_text_with_preferred_encoding(
    file_path: str,
) -> Tuple[str, Optional[str]]:
    """Use detect_file_encoding to directly detect the encoding and read the text file."""
    detected_encoding = detect_file_encoding(file_path)
    if detected_encoding:
        try:
            content = read_text_file(
                file_path,
                encoding=detected_encoding,
                detect_encoding=False,
                errors="strict",
            )
            return content, detected_encoding
        except (UnicodeDecodeError, LookupError):
            pass

    # Fall back to the default read method
    content = read_text_file(file_path)
    return content, detected_encoding


def read_file_with_backup(
    file_path: str,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Read a file and create a backup

    Args:
        file_path: File path

    Returns:
        (file content, backup file path or None, detected encoding or None)
    """
    abs_path = os.path.abspath(file_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    file_content = ""
    backup_path = None
    detected_encoding = None
    if os.path.exists(abs_path):
        file_content, detected_encoding = read_text_with_preferred_encoding(abs_path)
        # Create a backup file
        backup_path = abs_path + ".bak"
        try:
            shutil.copy2(abs_path, backup_path)
        except Exception:
            # A backup failure does not affect the main flow
            backup_path = None

    return file_content, backup_path, detected_encoding


def write_file_with_rollback(
    abs_path: str,
    content: str,
    backup_path: Optional[str],
    encoding: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Write a file, rolling back on failure

    Args:
        abs_path: Absolute file path
        content: The content to write
        backup_path: Backup file path or None
        encoding: Specify the encoding; if None, detect automatically

    Returns:
        (whether successful, error message or None)
    """
    enc = encoding or get_default_encoding()
    try:
        with open(abs_path, "w", encoding=enc, errors="replace") as f:
            f.write(content)
        return (True, None)
    except Exception as write_error:
        # Write failed, attempting rollback
        if backup_path and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, abs_path)
                os.remove(backup_path)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_tools.edit_file",
                    function="write_file_with_rollback",
                )
                pass
        error_msg = f"File write failed: {str(write_error)}"
        return (False, error_msg)


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to facilitate conservative equivalence matching."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_quotes(text: str) -> str:
    """Normalize common quote styles to facilitate locating the actual matched text in the file."""
    return text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


def find_actual_search_text(content: str, search_text: str) -> Optional[str]:
    """Find the actual matched text in the file.

    First try an exact match; if it fails, try locating it based on newline and quote normalization,
    and extract the actual matched fragment from the original file content.
    """
    if not search_text:
        return search_text

    if search_text in content:
        return search_text

    normalized_content = normalize_quotes(normalize_line_endings(content))
    normalized_search = normalize_quotes(normalize_line_endings(search_text))
    search_index = normalized_content.find(normalized_search)
    if search_index == -1:
        return None
    return content[search_index : search_index + len(search_text)]


def is_opening_quote_context(characters: List[str], index: int) -> bool:
    """Determine whether the quote at the current position is in an opening-quote context."""
    if index == 0:
        return True
    previous_character = characters[index - 1]
    return previous_character in {" ", "\t", "\n", "\r", "(", "[", "{", "—", "–"}


def apply_curly_double_quotes(text: str) -> str:
    """Convert straight double quotes to curly double quotes."""
    characters = list(text)
    result: List[str] = []
    for index, character in enumerate(characters):
        if character == '"':
            result.append("“" if is_opening_quote_context(characters, index) else "”")
        else:
            result.append(character)
    return "".join(result)


def apply_curly_single_quotes(text: str) -> str:
    """Convert straight single quotes to curly single quotes, while preserving apostrophes in common contractions."""
    characters = list(text)
    result: List[str] = []
    for index, character in enumerate(characters):
        if character != "'":
            result.append(character)
            continue

        previous_character = characters[index - 1] if index > 0 else ""
        next_character = characters[index + 1] if index < len(characters) - 1 else ""
        if previous_character.isalpha() and next_character.isalpha():
            result.append("’")
            continue

        result.append("‘" if is_opening_quote_context(characters, index) else "’")
    return "".join(result)


def preserve_quote_style(
    search_text: str, actual_search_text: str, replace_text: str
) -> str:
    """When search matches the actual text due to quote normalization, keep the curly-quote style of the actual text as much as possible."""
    if search_text == actual_search_text:
        return replace_text

    has_curly_double_quotes = "“" in actual_search_text or "”" in actual_search_text
    has_curly_single_quotes = "‘" in actual_search_text or "’" in actual_search_text

    styled_replace_text = replace_text
    if has_curly_double_quotes:
        styled_replace_text = apply_curly_double_quotes(styled_replace_text)
    if has_curly_single_quotes:
        styled_replace_text = apply_curly_single_quotes(styled_replace_text)
    return styled_replace_text


def count_matches(content: str, search_text: str) -> int:
    """Count the number of matches of the text in the content

    Args:
        content: File content
        search_text: The text to search for

    Returns:
        Number of matches
    """
    if not search_text:
        return 0
    return content.count(search_text)


def is_file_in_workspace_subdir(file_path: str) -> bool:
    """Check whether the file is under a subdirectory of the current working directory

    Args:
        file_path: File path (may be absolute or relative)

    Returns:
        True if the file is under a subdirectory of the current working directory, False otherwise
    """
    try:
        abs_file_path = os.path.abspath(file_path)
        abs_workspace_path = os.path.abspath(os.getcwd())

        # Check whether the file path starts with the working directory path
        # Use os.path.commonpath to handle paths correctly
        try:
            common_path = os.path.commonpath([abs_file_path, abs_workspace_path])
            # If the common path equals the working directory path, the file is under the working directory or its subdirectories
            return os.path.abspath(common_path) == abs_workspace_path
        except ValueError:
            # If the paths are not on the same drive (Windows), commonpath raises ValueError
            return False
    except Exception:
        # If any exception occurs, return False by default
        return False


def generate_diff_preview(
    original_content: str,
    modified_content: str,
    file_path: str,
) -> str:
    """Generate a preview diff after modification

    Args:
        original_content: Original file content
        modified_content: Modified file content
        file_path: File path

    Returns:
        Preview diff string
    """
    import difflib

    # Generate a unified diff format
    original_lines = original_content.splitlines(keepends=True)
    modified_lines = modified_content.splitlines(keepends=True)

    # Use difflib to generate a unified diff
    diff = list(
        difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )

    diff_preview = "".join(diff)
    return diff_preview
