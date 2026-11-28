"""Replace-by-line-number tool: replace the content of a specified line-number range in a file with content."""

import os
from typing import Any
from typing import Dict

from haijunbot.haijunbot_tools.edit_file_common import (
    generate_diff_preview,
    is_file_in_workspace_subdir,
    read_file_with_backup,
    write_file_with_rollback,
)
from haijunbot.haijunbot_utils.config import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput


class edit_file_by_line:
    """Replace-by-line-number tool, replacing the content of the closed interval [start_line, end_line] with content"""

    name = "edit_file_by_line"
    description = (
        "Replace the content of a specified line-number range in a file with content (closed interval [start_line, end_line])."
        "Suitable for scenarios where the target lines are known: first use read_code to confirm the line numbers, then specify the line range to replace."
        "If you want search-and-replace by content, use edit_file instead; if you want a whole-file rewrite, use write_file instead."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file to edit (supports absolute and relative paths)",
            },
            "start_line": {
                "type": "integer",
                "description": "Start line number (starting from 1, inclusive)",
            },
            "end_line": {
                "type": "integer",
                "description": "End line number (starting from 1, inclusive)",
            },
            "content": {
                "type": "string",
                "description": "New content used to replace that line-number range",
            },
        },
        "required": ["file_path", "start_line", "end_line", "content"],
    }

    def __init__(self) -> None:
        """Initialize the replace-by-line-number tool"""
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

        start_line = args.get("start_line")
        end_line = args.get("end_line")
        if not isinstance(start_line, int) or isinstance(start_line, bool):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The start_line argument must be an integer",
            }
        if not isinstance(end_line, int) or isinstance(end_line, bool):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The end_line argument must be an integer",
            }
        if start_line < 1:
            return {
                "success": False,
                "stdout": "",
                "stderr": "start_line must be greater than or equal to 1",
            }
        if end_line < start_line:
            return {
                "success": False,
                "stdout": "",
                "stderr": "end_line must be greater than or equal to start_line",
            }

        if "content" not in args:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required argument: content",
            }
        if not isinstance(args.get("content"), str):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The content argument must be a string",
            }
        return None

    @staticmethod
    def _replace_line_range(
        content: str, start_line: int, end_line: int, replace: str
    ) -> str:
        """Replace the content of the closed interval [start_line, end_line] in content with replace"""
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        before_lines = lines[: start_line - 1]
        after_lines = lines[end_line:] if end_line < total_lines else []

        # Ensure the replacement content ends with a newline (if there are lines after it)
        replace_content = replace
        if after_lines and not replace_content.endswith("\n"):
            replace_content += "\n"

        new_content_parts = []
        if before_lines:
            new_content_parts.append("".join(before_lines))
        new_content_parts.append(replace_content)
        if after_lines:
            if not replace_content.endswith("\n") and new_content_parts:
                new_content_parts.append("\n")
            new_content_parts.append("".join(after_lines))

        return "".join(new_content_parts)

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the content of the closed interval [start_line, end_line] in the file with content"""
        try:
            error_response = edit_file_by_line._validate_args(args)
            if error_response:
                return error_response

            file_path = args["file_path"]
            start_line = args["start_line"]
            end_line = args["end_line"]
            replace = args["content"]
            agent = args.get("agent")

            # Read the original content and create a backup (returns empty content if the file does not exist)
            (
                original_content,
                backup_path,
                detected_encoding,
            ) = read_file_with_backup(file_path)

            total_lines = len(original_content.splitlines(keepends=True))
            if start_line > total_lines:
                if backup_path and os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.edit_file_by_line",
                            function="execute",
                        )
                        pass
                error_msg = f"start_line ({start_line}) exceeds the total number of lines in the file ({total_lines})"
                PrettyOutput.auto_print(f"❌ {file_path}: {error_msg}")
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"{file_path}: {error_msg}",
                }

            new_content = edit_file_by_line._replace_line_range(
                original_content, start_line, end_line, replace
            )

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
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.edit_file_by_line",
                        function="execute",
                    )
                    pass

            encoding_info = detected_encoding or "utf-8"
            all_results = [
                f"✅ {file_path}: modified successfully (🔤 encoding: {encoding_info})",
                f"   Replaced lines {start_line}-{end_line}",
            ]

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


__all__ = ["edit_file_by_line"]
