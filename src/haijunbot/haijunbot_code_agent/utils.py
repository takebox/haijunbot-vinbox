# -*- coding: utf-8 -*-
"""CodeAgent utility function module.

Provides utility functions such as the project overview.
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import subprocess
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.git_utils import get_recent_commits_with_files
from haijunbot.haijunbot_utils.utils import decode_output, get_loc_stats


def get_git_tracked_files_info(
    project_root: str, max_files: int = 100, max_tree_lines: int = 200
) -> Optional[str]:
    """Get the list of git-tracked files or the directory structure

    If the number of files exceeds max_files, returns the directory structure (without files)

    Args:
        project_root: the project root directory
        max_files: the file count threshold; above this value the directory structure is returned
        max_tree_lines: the maximum number of lines in the directory tree, to prevent it from being too large and exceeding the LLM context limit

    Returns:
        str: the string representation of the file list or directory structure, or None on failure
    """
    try:
        # Get all git-tracked files
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=False,
            check=True,
            cwd=project_root,
        )
        stdout = decode_output(result.stdout)

        if result.returncode != 0 or not stdout.strip():
            return None

        files = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
        file_count = len(files)

        if file_count == 0:
            return None

        # If the file count exceeds the threshold, return the directory structure
        if file_count > max_files:
            # Extract all directory paths
            dirs = set()
            for file_path in files:
                # Get all parent directories of the file
                parts = file_path.split("/")
                for i in range(1, len(parts)):
                    dir_path = "/".join(parts[:i])
                    if dir_path:
                        dirs.add(dir_path)

            # Build the tree directory structure
            dir_tree: Dict[str, Any] = {}
            for dir_path in sorted(dirs):
                parts = dir_path.split("/")
                current = dir_tree
                for part in parts:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

            def format_tree(
                tree: dict,
                prefix: str = "",
                is_last: bool = True,
                current_lines: int = 0,
            ) -> List[str]:
                """Format the directory tree (with a line count limit)"""
                lines: List[str] = []
                items = sorted(tree.items())
                for i, (name, subtree) in enumerate(items):
                    # Check the line count limit
                    if current_lines + len(lines) >= max_tree_lines:
                        break
                    is_last_item = i == len(items) - 1
                    connector = "└── " if is_last_item else "├── "
                    lines.append(f"{prefix}{connector}{name}/")

                    extension = "    " if is_last_item else "│   "
                    if subtree and current_lines + len(lines) < max_tree_lines:
                        subtree_lines = format_tree(
                            subtree,
                            prefix + extension,
                            is_last_item,
                            current_lines + len(lines),
                        )
                        lines.extend(subtree_lines)
                        # If the subtree was truncated, stop processing
                        if len(subtree_lines) == 0 and subtree:
                            break
                return lines

            tree_lines = format_tree(dir_tree)
            truncated_msg = (
                "\n... (directory structure truncated, use tools to view the full structure)"
                if len(tree_lines) >= max_tree_lines
                else ""
            )
            return (
                f"Git-tracked directory structure ({file_count} files in total):\n"
                + "\n".join(tree_lines)
                + truncated_msg
            )
        else:
            # Not many files, return the file list directly
            files_str = "\n".join(f"  - {file}" for file in sorted(files))
            return f"Git-tracked file list ({file_count} files in total):\n{files_str}"

    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    except Exception:
        # Other exceptions, fail silently
        return None


def get_project_overview(project_root: str) -> str:
    """Get project overview information

    Args:
        project_root: the project root directory

    Returns:
        The project overview string
    """
    project_info = []

    # Get code statistics
    try:
        loc_stats = get_loc_stats()
        if loc_stats:
            project_info.append(f"Code statistics:\n{loc_stats}")
    except Exception as e:
        save_exception(
            e, module="haijunbot_code_agent.utils", function="get_project_overview"
        )
        pass

    # Get git-tracked file information
    try:
        git_files_info = get_git_tracked_files_info(project_root)
        if git_files_info:
            project_info.append(git_files_info)
    except Exception as e:
        save_exception(
            e, module="haijunbot_code_agent.utils", function="get_project_overview"
        )
        pass

    # Get recent commit information
    try:
        commits_info = get_recent_commits_with_files()
        if commits_info:
            commits_str = "\n".join(
                f"Commit {i + 1}: {commit['hash'][:7]} - {commit['message']} ({len(commit['files'])} files)\n"
                + "\n".join(f"    - {file}" for file in commit["files"][:5])
                + ("\n    ..." if len(commit["files"]) > 5 else "")
                for i, commit in enumerate(commits_info[:5])
            )
            project_info.append(f"Recent commits:\n{commits_str}")
    except Exception as e:
        save_exception(
            e, module="haijunbot_code_agent.utils", function="get_project_overview"
        )
        pass

    if project_info:
        return "Project overview:\n" + "\n\n".join(project_info)
    return ""
