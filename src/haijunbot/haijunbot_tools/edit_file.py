"""Search-and-replace tool: find the search text in a file and replace it with replace."""

import os
from typing import Any
from typing import Dict

from haijunbot.haijunbot_tools.edit_file_common import (
    count_matches,
    find_actual_search_text,
    generate_diff_preview,
    is_file_in_workspace_subdir,
    preserve_quote_style,
    read_file_with_backup,
    write_file_with_rollback,
)
from haijunbot.haijunbot_utils.config import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput


class edit_file:
    """Search-and-replace tool, finding the search text in a file and replacing it with replace"""

    name = "edit_file"
    description = (
        "Find the search text in a file and replace it with replace (exact match)."
        "search needs to include enough context to uniquely locate the target position; if it matches multiple places, by default it does not replace and reports an error,"
        "and you can explicitly set replace_all=true to replace all matches."
        "If you want a whole-file rewrite, use write_file instead; if you want to replace by line number, use edit_file_by_line instead."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file to edit (supports absolute and relative paths)",
            },
            "search": {
                "type": "string",
                "description": "The original text to find (requires exact matching; it is recommended to include enough context to uniquely locate it)",
            },
            "replace": {
                "type": "string",
                "description": "New text used to replace search (an empty string means deletion)",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Whether to replace all matches, defaults to false (replace only when the match is unique)",
            },
        },
        "required": ["file_path", "search", "replace"],
    }

    def __init__(self) -> None:
        """Initialize the search-and-replace tool"""
        pass

    @staticmethod
    def _validate_args(args: Dict[str, Any]) -> Dict[str, Any] | None:
        """Validate the arguments; return an error response on failure, otherwise return None"""
        file_path = args.get("file_path")
        if not file_path or not isinstance(file_path, str):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required string argument: file_path",
            }

        if "search" not in args or not isinstance(args.get("search"), str):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required string argument: search",
            }
        if "replace" not in args or not isinstance(args.get("replace"), str):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required string argument: replace",
            }

        replace_all = args.get("replace_all", False)
        if not isinstance(replace_all, bool):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The replace_all argument must be a boolean",
            }
        return None

    @staticmethod
    def _build_not_found_error(search: str, file_path: str) -> str:
        """Build detailed error information when no matching text is found"""
        error_info = "No matching text was found"
        if search:
            error_info += f"\nSearch text: {search[:200]}..."
            error_info += (
                "\n💡 Tip: If the search text exists in the file but no match is found, it may be because:"
            )
            error_info += (
                "\n   1. The search text contains invisible characters or a format mismatch (check spaces, newlines, etc.)"
            )
            error_info += "\n   2. The actual text in the file differs from search in quote or newline style"
            error_info += "\n   3. **The file may have been updated**: if the file was modified elsewhere, the search text may no longer exist or may have changed"
            error_info += f"\n   💡 Suggestion: use the `read_code` tool to re-read the file `{file_path}` and view its current content,"
            error_info += (
                "\n      confirm whether the file has been updated, then adjust the search text according to the actual content"
            )
        return error_info

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Find the search text in a file and replace it with replace"""
        try:
            error_response = edit_file._validate_args(args)
            if error_response:
                return error_response

            file_path = args["file_path"]
            search = args["search"]
            replace = args["replace"]
            replace_all = args.get("replace_all", False)
            agent = args.get("agent")

            if search == "":
                error_msg = (
                    "search cannot be an empty string. If you want to rewrite the entire file, use the write_file tool."
                )
                PrettyOutput.auto_print(f"❌ {file_path}: {error_msg}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {error_msg}",
                }

            # Check whether search and replace are exactly the same (invalid operation)
            if search == replace:
                error_msg = (
                    "search and replace have exactly the same content; this is an invalid operation (no actual modification)"
                )
                PrettyOutput.auto_print(f"❌ {file_path}: {error_msg}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {error_msg}",
                }

            # Read the original content and create a backup (returns empty content if the file does not exist)
            (
                original_content,
                backup_path,
                detected_encoding,
            ) = read_file_with_backup(file_path)

            def _cleanup_backup() -> None:
                if backup_path and os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                    except Exception as e:
                        save_exception(
                            e, module="haijunbot_tools.edit_file", function="execute"
                        )
                        pass

            actual_search = find_actual_search_text(original_content, search)
            if actual_search is None:
                _cleanup_backup()
                error_msg = edit_file._build_not_found_error(search, file_path)
                PrettyOutput.auto_print(f"❌ {file_path}: {error_msg}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {error_msg}",
                }

            styled_replace = preserve_quote_style(search, actual_search, replace)
            match_count = count_matches(original_content, actual_search)

            if match_count == 1:
                new_content = original_content.replace(actual_search, styled_replace, 1)
            elif replace_all:
                new_content = original_content.replace(actual_search, styled_replace)
            else:
                _cleanup_backup()
                error_msg = (
                    f"The search text matched {match_count} places, but replace_all=false, so all matches will not be replaced automatically."
                    "\n💡 Suggestion: provide more precise context to uniquely locate the target position, or explicitly set replace_all=true."
                )
                PrettyOutput.auto_print(f"❌ {file_path}: {error_msg}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {error_msg}",
                }

            abs_path = os.path.abspath(file_path)
            write_success, write_error = write_file_with_rollback(
                abs_path, new_content, backup_path, detected_encoding
            )
            if not write_success:
                PrettyOutput.auto_print(f"❌ {file_path}: {write_error}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {write_error}",
                }

            # Write succeeded, delete the backup file
            _cleanup_backup()

            encoding_info = detected_encoding or "utf-8"
            all_results = [f"✅ {file_path}: modified successfully (🔤 encoding: {encoding_info})"]

            # When the file is not under a subdirectory of the current working directory (or is not code_agent), print a diff preview
            in_workspace = is_file_in_workspace_subdir(abs_path)
            if not (agent and agent.agent_type() == "code_agent" and in_workspace):
                try:
                    diff_text = generate_diff_preview(
                        original_content, new_content, file_path
                    )
                    from haijunbot.haijunbot_code_agent.diff_visualizer import (
                        visualize_diff_enhanced,
                    )

                    visualize_diff_enhanced(
                        diff_text,
                        file_path=file_path,
                        mode="side_by_side",
                        show_line_numbers=True,
                        context_lines=3,
                    )
                    all_results.append(
                        f"\n📝 diff for {file_path} (file is not under a subdirectory of the current working directory):"
                    )
                    all_results.append(diff_text)
                except Exception as diff_error:
                    # A failure to generate or print the diff does not affect the main flow
                    PrettyOutput.auto_print(f"⚠️ Error generating diff: {str(diff_error)}")

            return {
                "success": True,
                "stdout": "\n".join(all_results),
                "stderr": "",
            }

        except Exception as e:
            error_msg = f"File edit failed: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}


__all__ = ["edit_file"]
