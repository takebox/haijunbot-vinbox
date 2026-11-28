"""Whole-file overwrite tool: overwrite the entire file with content."""

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


class write_file:
    """Whole-file overwrite tool, overwrite the entire file with content"""

    name = "write_file"
    description = (
        "Overwrite the entire file with content (whole-file rewrite)."
        "Suitable for creating new files or large-scale rewrites: just provide the file's complete new content, without providing search."
        "If you only want to modify a small part of the file, use edit_file (search-and-replace) or edit_file_by_line (replace by line number) instead."
    )

    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path of the file to write (supports absolute and relative paths)",
            },
            "content": {
                "type": "string",
                "description": "The file's complete new content (overwrites all original content; an empty string means clearing the file)",
            },
        },
        "required": ["file_path", "content"],
    }

    def __init__(self) -> None:
        """Initialize the whole-file overwrite tool"""
        pass

    @staticmethod
    def _validate_args(args: Dict[str, Any]) -> Dict[str, Any] | None:
        """Validate the arguments; return an error response on failure, otherwise return None"""
        file_path = args.get("file_path")
        if not file_path:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing required argument: file_path",
            }
        if not isinstance(file_path, str):
            return {
                "success": False,
                "stdout": "",
                "stderr": "The file_path argument must be a string",
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

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Overwrite the entire file with content"""
        try:
            error_response = write_file._validate_args(args)
            if error_response:
                return error_response

            file_path = args["file_path"]
            content = args["content"]
            agent = args.get("agent")

            # Read the original content and create a backup (returns empty content if the file does not exist)
            (
                original_content,
                backup_path,
                detected_encoding,
            ) = read_file_with_backup(file_path)

            abs_path = os.path.abspath(file_path)
            write_success, write_error = write_file_with_rollback(
                abs_path, content, backup_path, detected_encoding
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
                        e, module="haijunbot_tools.write_file", function="execute"
                    )
                    pass

            encoding_info = detected_encoding or "utf-8"
            all_results = [f"✅ {file_path}: written successfully (🔤 encoding: {encoding_info})"]

            # When the file is not under a subdirectory of the current working directory (or is not code_agent), print a diff preview
            in_workspace = is_file_in_workspace_subdir(abs_path)
            if not (agent and agent.agent_type() == "code_agent" and in_workspace):
                try:
                    diff_text = generate_diff_preview(
                        original_content, content, file_path
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
            error_msg = f"File write failed: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}


__all__ = ["write_file"]
