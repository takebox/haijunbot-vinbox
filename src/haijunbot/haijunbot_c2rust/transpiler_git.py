# -*- coding: utf-8 -*-
"""
Git operations module
"""

import subprocess
from typing import Optional

from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash


class GitManager:
    """Git operations manager"""

    def __init__(self, crate_dir: str) -> None:
        self.crate_dir = crate_dir

    def get_crate_commit_hash(self) -> Optional[str]:
        """Get the current commit id of the crate directory"""
        try:
            # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
            commit_hash = get_latest_commit_hash()
            return commit_hash if commit_hash else None
        except Exception:
            return None

    def get_git_diff(self, base_commit: Optional[str] = None) -> str:
        """
        Get the git diff showing changes from base_commit to the current working tree

        Args:
            base_commit: Baseline commit hash; if None, use HEAD

        Returns:
            str: git diff content; return an empty string if retrieval fails
        """
        try:
            # Check whether this is a git repository
            check_git_result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.crate_dir,
            )
            if check_git_result.returncode != 0:
                # Not a git repository; cannot obtain diff
                return ""

            if base_commit:
                # First check whether base_commit exists
                check_result = subprocess.run(
                    ["git", "rev-parse", "--verify", base_commit],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=self.crate_dir,
                )
                if check_result.returncode != 0:
                    # base_commit does not exist; use HEAD as the baseline
                    base_commit = None

            # Check whether HEAD exists
            head_check = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.crate_dir,
            )
            has_head = head_check.returncode == 0

            # Temporarily stage new files to obtain a complete diff
            subprocess.run(
                ["git", "add", "-N", "."],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.crate_dir,
            )

            try:
                if base_commit:
                    # Get the diff from base_commit to the current working tree
                    result = subprocess.run(
                        ["git", "diff", base_commit],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                        cwd=self.crate_dir,
                    )
                elif has_head:
                    # Get the diff from HEAD to the current working tree
                    result = subprocess.run(
                        ["git", "diff", "HEAD"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                        cwd=self.crate_dir,
                    )
                else:
                    # Empty repository; get the working tree diff
                    result = subprocess.run(
                        ["git", "diff"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        check=False,
                        cwd=self.crate_dir,
                    )

                return result.stdout or "" if result.returncode == 0 else ""
            finally:
                # Reset the staging area
                subprocess.run(
                    ["git", "reset"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=self.crate_dir,
                )
        except Exception:
            return ""

    def reset_to_commit(self, commit_hash: str) -> bool:
        """Reset the crate directory to the specified commit"""
        try:
            # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
            # Check whether this is a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                # Not a git repository; cannot reset
                return False

            # Perform a hard reset
            result = subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # Clean untracked files
                subprocess.run(
                    ["git", "clean", "-fd"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return True
            return False
        except Exception:
            return False
