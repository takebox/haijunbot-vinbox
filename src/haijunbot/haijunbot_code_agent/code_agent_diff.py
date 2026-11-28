# -*- coding: utf-8 -*-
"""CodeAgent code change preview and statistics module"""

import os
import subprocess
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.config import get_diff_large_file_threshold
from haijunbot.haijunbot_utils.config import get_diff_show_line_numbers
from haijunbot.haijunbot_utils.config import get_diff_visualization_mode
from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash
from haijunbot.haijunbot_utils.utils import decode_output


class DiffManager:
    """Code change preview and statistics manager"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        # Lazy import to avoid circular dependency
        self._visualizer = None

    def build_name_status_map(self) -> Dict[str, str]:
        """Build a per-file status map and diff text; deleted files are not shown a diff, only a deletion notice"""
        status_map = {}
        try:
            head_exists = bool(get_latest_commit_hash())
            # Temporarily use -N to include diff detection for untracked files
            subprocess.run(
                ["git", "add", "-N", "."],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cmd = ["git", "diff", "--name-status"] + (["HEAD"] if head_exists else [])
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                check=False,
            )
            stdout = decode_output(res.stdout) if res.stdout else ""
        finally:
            subprocess.run(
                ["git", "reset"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if res.returncode == 0 and stdout:
            for line in stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                if not parts:
                    continue
                status = parts[0]
                if status.startswith("R") or status.startswith("C"):
                    # Rename/copy: use the new path as the key
                    if len(parts) >= 3:
                        old_path, new_path = parts[1], parts[2]
                        status_map[new_path] = status
                        # Also record the old path, to facilitate matching the name-only result
                        status_map[old_path] = status
                    elif len(parts) >= 2:
                        status_map[parts[-1]] = status
                else:
                    if len(parts) >= 2:
                        status_map[parts[1]] = status
        return status_map

    def get_file_diff(self, file_path: str) -> str:
        """Get the diff of a single file, including new file content; returns an empty string on failure"""
        head_exists = bool(get_latest_commit_hash())
        try:
            # To allow untracked files to also show a diff, temporarily use -N on that file
            subprocess.run(
                ["git", "add", "-N", "--", file_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cmd = (
                ["git", "diff"] + (["HEAD"] if head_exists else []) + ["--", file_path]
            )
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=False,
                check=False,
            )
            stdout = decode_output(res.stdout) if res.stdout else ""
            if res.returncode == 0:
                return stdout
            return ""
        finally:
            subprocess.run(
                ["git", "reset", "--", file_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _get_visualizer(self) -> Optional[Any]:
        """Get the visualizer instance (lazy initialization)"""
        if self._visualizer is None:
            try:
                from haijunbot.haijunbot_code_agent.diff_visualizer import DiffVisualizer

                self._visualizer = DiffVisualizer()
            except ImportError:
                # If the import fails, return None
                self._visualizer = False
        return self._visualizer if self._visualizer is not False else None

    def build_per_file_patch_preview(
        self, modified_files: List[str], use_enhanced_visualization: bool = True
    ) -> str:
        """Build a per-file patch preview

        Args:
            modified_files: list of modified files
            use_enhanced_visualization: whether to use enhanced visualization (default True)

        Returns:
            str: markdown text of the patch preview (used for logging, etc.)
        """
        status_map = self.build_name_status_map()
        lines: List[str] = []
        visualizer = self._get_visualizer() if use_enhanced_visualization else None
        visualization_mode = (
            get_diff_visualization_mode() if use_enhanced_visualization else "default"
        )
        show_line_numbers = get_diff_show_line_numbers()
        large_file_threshold = get_diff_large_file_threshold()

        def _get_file_numstat(file_path: str) -> Tuple[int, int]:
            """Get the added/deleted line counts of a single file, returning (0,0) on failure"""
            head_exists = bool(get_latest_commit_hash())
            try:
                # Allow untracked files to also have their added line counts counted
                subprocess.run(
                    ["git", "add", "-N", "--", file_path],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                cmd = (
                    ["git", "diff", "--numstat"]
                    + (["HEAD"] if head_exists else [])
                    + ["--", file_path]
                )
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    check=False,
                )
                stdout = decode_output(res.stdout) if res.stdout else ""
                if res.returncode == 0 and stdout:
                    for line in stdout.splitlines():
                        parts = line.strip().split("\t")
                        if len(parts) >= 3:
                            add_s, del_s = parts[0], parts[1]

                            def to_int(x: str) -> int:
                                try:
                                    return int(x)
                                except Exception:
                                    # Show as 0 for binary or unparsable values
                                    return 0

                            return to_int(add_s), to_int(del_s)
            finally:
                subprocess.run(
                    ["git", "reset", "--", file_path],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return (0, 0)

        for f in modified_files:
            status = status_map.get(f, "")
            adds, dels = _get_file_numstat(f)
            total_changes = adds + dels

            # .haijunbot file: only return statistics, without affecting the visualizer display
            if ".haijunbot" in f:
                # visualizer displays normally
                if visualizer:
                    file_diff = self.get_file_diff(f)
                    if file_diff.strip():
                        if visualization_mode == "unified":
                            visualizer.visualize_unified_diff(
                                file_diff, f, show_line_numbers=show_line_numbers
                            )
                        elif visualization_mode == "syntax":
                            visualizer.visualize_syntax_highlighted(file_diff, f)
                        elif visualization_mode == "compact":
                            visualizer.visualize_compact(file_diff, f)
                        else:
                            visualizer.visualize_unified_diff(
                                file_diff, f, show_line_numbers=show_line_numbers
                            )
                # The return value only contains the statistics summary
                lines.append(f"- {f} {adds} lines added / {dels} lines deleted")
                continue

            # Deleted file: do not show a diff, only a notice (with deleted line count info if available)
            if (status.startswith("D")) or (not os.path.exists(f)):
                if dels > 0:
                    lines.append(f"- {f} file deleted ({dels} lines deleted)")
                else:
                    lines.append(f"- {f} file deleted")
                # Use the visualizer to display statistics
                if visualizer:
                    visualizer.visualize_statistics(f, 0, dels)
                continue

            # Change too large: show statistics and a compact preview
            if total_changes > large_file_threshold:
                if visualizer:
                    # Display statistics
                    visualizer.visualize_statistics(f, adds, dels, total_changes)
                    # Display compact preview
                    file_diff = self.get_file_diff(f)
                    if file_diff.strip():
                        if visualization_mode == "compact":
                            visualizer.visualize_compact(file_diff, f, max_lines=100)
                        elif visualization_mode == "syntax":
                            visualizer.visualize_syntax_highlighted(file_diff, f)
                        else:
                            # unified mode also displays, but limits the number of lines
                            visualizer.visualize_compact(file_diff, f, max_lines=50)
                lines.append(f"- {f} {adds} lines added / {dels} lines deleted (change too large, preview omitted)")
                continue

            # Normal change: show the diff of this file
            file_diff = self.get_file_diff(f)
            if file_diff.strip():
                # Use enhanced visualization
                if visualizer:
                    if visualization_mode == "unified":
                        visualizer.visualize_unified_diff(
                            file_diff, f, show_line_numbers=show_line_numbers
                        )
                    elif visualization_mode == "syntax":
                        visualizer.visualize_syntax_highlighted(file_diff, f)
                    elif visualization_mode == "compact":
                        visualizer.visualize_compact(file_diff, f)
                    else:
                        # Default to unified
                        visualizer.visualize_unified_diff(
                            file_diff, f, show_line_numbers=show_line_numbers
                        )

                # Also keep the markdown format for logging
                lines.append(f"File: {f}\n```diff\n{file_diff}\n```")
            else:
                # When the diff cannot be obtained (e.g. renamed or special status), avoid empty output
                lines.append(f"- {f} change recorded (no displayable text diff)")
        return "\n".join(lines)
