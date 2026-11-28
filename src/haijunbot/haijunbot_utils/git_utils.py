"""
Git Utility Module
This module provides tools for interacting with Git repositories.
Includes the following features:
- Find the root directory of a Git repository
- Check for uncommitted changes
- Get commit history between two hash values
- Get the hash value of the latest commit
- Extract modified line ranges from Git diffs
"""

import datetime
import os

# -*- coding: utf-8 -*-
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from haijunbot.haijunbot_utils.config import (
    get_data_dir,
    is_confirm_before_apply_patch,
    save_exception,
)
from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output

# Global flag: records whether confirm_add_new_files has been called in the current process
# Used to avoid repeatedly asking the user whether to add new files/binary files/large code in the same process
_confirm_add_new_files_called = False

# Records the specific reason for rejection when handle_commit_workflow last returned False,
# For upper layers (e.g., code_agent._on_after_tool_call) to display in the "modification rejected" prompt,
# to prevent users/Agents from repeatedly retrying without seeing the reason.
_last_commit_reject_reason: str = ""


def get_last_commit_reject_reason() -> str:
    """Return the specific reason why handle_commit_workflow rejected the commit last time (may be an empty string)."""
    return _last_commit_reject_reason


def reset_confirm_add_new_files_flag() -> None:
    """Reset the global flag for confirm_add_new_files

    Used to reset the flag at the start of a new process, allowing file confirmation again
    """
    global _confirm_add_new_files_called
    _confirm_add_new_files_called = False


def find_git_root_and_cd(start_dir: str = ".", allow_init: bool = False) -> str:
    """
    Switch to the Git root directory of the given path.

    Parameters:
        start_dir (str): Starting directory to search from, defaults to current directory.
        allow_init (bool): Whether to allow initializing a new Git repository if not in a Git repo. Defaults to False.

    Returns:
        str: Path to the Git repository root directory.

    Raises:
        subprocess.CalledProcessError: If not in a Git repository and initialization is not allowed.
    """
    os.chdir(start_dir)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=False,
            check=True,
        )
        git_root = decode_output(result.stdout).strip()
        if not git_root:
            if allow_init:
                subprocess.run(["git", "init"], check=True, capture_output=True)
                git_root = os.path.abspath(".")
            else:
                raise subprocess.CalledProcessError(
                    1, ["git", "rev-parse", "--show-toplevel"]
                )
    except subprocess.CalledProcessError:
        # If not a Git repository
        if allow_init:
            subprocess.run(["git", "init"], check=True, capture_output=True)
            git_root = os.path.abspath(".")
        else:
            raise
    os.chdir(git_root)
    return git_root


def find_git_root(start_dir: str = ".", allow_init: bool = False) -> str:
    """
    Find the Git root directory for the given path (without changing working directory).

    Parameters:
        start_dir (str): Starting directory to search from, defaults to current directory.
        allow_init (bool): Whether to allow initializing a new Git repository if not in a Git repo. Defaults to False.

    Returns:
        str: Path to the Git repository root directory.

    Raises:
        subprocess.CalledProcessError: If not in a Git repository and initialization is not allowed.
    """
    abs_start_dir = os.path.abspath(start_dir)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=abs_start_dir,
            capture_output=True,
            text=False,
            check=True,
        )
        git_root = decode_output(result.stdout).strip()
        if not git_root:
            if allow_init:
                subprocess.run(
                    ["git", "init"], cwd=abs_start_dir, check=True, capture_output=True
                )
                git_root = abs_start_dir
            else:
                raise subprocess.CalledProcessError(
                    1, ["git", "rev-parse", "--show-toplevel"]
                )
    except subprocess.CalledProcessError:
        # If not a Git repository
        if allow_init:
            subprocess.run(
                ["git", "init"], cwd=abs_start_dir, check=True, capture_output=True
            )
            git_root = abs_start_dir
        else:
            raise
    return git_root


def has_uncommitted_changes(cwd: Optional[str] = None) -> bool:
    """Check if there are uncommitted changes in the Git repository

    Parameters:
        cwd: Working directory path, uses current directory if None

    Returns:
        bool: Returns True if there are uncommitted changes, False otherwise
    """
    # Compatible with empty repos: use git status --porcelain to detect all uncommitted changes
    # git diff does not work in empty repos (no HEAD commit as base), will incorrectly return no diff
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        # If status output is non-empty, there are uncommitted changes (including untracked files, modified files, staged files, etc.)
        if status_result.stdout.strip():
            return True
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.git_utils", function="has_uncommitted_changes"
        )
        pass

    # Before executing git add ., record files currently staged (possibly user-added files ignored by gitignore)
    process = subprocess.Popen(
        ["git", "diff", "--cached", "--name-only"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    stdout_bytes, _ = process.communicate()
    staged_files_before_add = decode_output(stdout_bytes)
    manually_staged_files = [
        f.strip() for f in staged_files_before_add.split("\n") if f.strip()
    ]

    # Silently add all changes
    subprocess.run(
        ["git", "add", "-A"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # Check working directory changes
    working_changes = (
        subprocess.run(
            ["git", "diff", "--exit-code"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    )

    # Check staging area changes
    staged_changes = (
        subprocess.run(
            ["git", "diff", "--cached", "--exit-code"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    )

    # Silently reset changes
    subprocess.run(
        ["git", "reset"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # After reset, re-add files that were manually staged and might be ignored by gitignore
    for file_path in manually_staged_files:
        if os.path.exists(file_path):
            # Use -f flag to force add files ignored by .gitignore
            subprocess.run(
                ["git", "add", "-f", file_path], check=False, capture_output=True
            )

    return working_changes or staged_changes


def find_recent_non_checkout_commit() -> str:
    """Find the most recent non-automatic commit (non-CheckPoint) hash going backwards from HEAD

    Scenario: the initial commit recorded by the task becomes invalid due to history rewriting (reset/rebase/squash, etc.),
    causing git log <start>..<end> to report Invalid revision range. In this case, fall back to the most recent
    non-temporary commit (i.e., user manual commit or formal commit from GitCommitTool) as the new starting point.

    Returns:
        str: Most recent non-automatic commit hash; returns empty string if not found or on error
    """
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%H|%s", "-n", "200"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        if result.returncode != 0:
            return ""
        output = decode_output(result.stdout)
        for line in output.splitlines():
            if "|" in line:
                commit_hash, message = line.split("|", 1)
                if not is_auto_commit_message(message):
                    return commit_hash
    except Exception:
        pass
    return ""


def get_commits_between(start_hash: str, end_hash: str) -> List[Tuple[str, str]]:
    """Get list of commits between two commit hashes

    Parameters:
        start_hash: Starting commit hash (exclusive)
        end_hash: Ending commit hash (inclusive)

    Returns:
        List[Tuple[str, str]]: List of tuples (commit hash, commit message)
    """
    try:
        # Use git log with pretty format to get hash and message
        result = subprocess.run(
            ["git", "log", f"{start_hash}..{end_hash}", "--pretty=format:%H|%s"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # Disable automatic text decoding
        )
        if result.returncode != 0:
            error_msg = decode_output(result.stderr)
            # On failure (e.g., Invalid revision range, meaning start_hash is no longer in current history):
            # Correct start commit to the most recent non-automatic (non-CheckPoint) commit and retry,
            # to avoid failure to get commit history due to history rewrite invalidating the initial commit.
            fallback_start = find_recent_non_checkout_commit()
            if fallback_start and fallback_start != start_hash:
                result = subprocess.run(
                    [
                        "git",
                        "log",
                        f"{fallback_start}..{end_hash}",
                        "--pretty=format:%H|%s",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=False,
                )
                if result.returncode == 0:
                    output = decode_output(result.stdout)
                    commits = []
                    for line in output.splitlines():
                        if "|" in line:
                            commit_hash, message = line.split("|", 1)
                            commits.append((commit_hash, message))
                    return commits
            PrettyOutput.auto_print(f"❌ Failed to get commit history: {error_msg}")
            return []

        output = decode_output(result.stdout)
        commits = []
        for line in output.splitlines():
            if "|" in line:
                commit_hash, message = line.split("|", 1)
                commits.append((commit_hash, message))
        return commits

    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to get commit historyRaises: {str(e)}")
        return []


# Modified function to get diff


def get_diff() -> str:
    """Use git to get working directory diff, including modified and newly added file contents

    Returns:
        str: Diff content or error message
    """
    try:
        # Check if it is an empty repository
        head_check = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        confirm_add_new_files()
        if head_check.returncode != 0:
            # For empty repo, directly get working directory diff
            result = subprocess.run(
                ["git", "diff"], capture_output=True, text=False, check=True
            )
        else:
            # Stage new files
            subprocess.run(["git", "add", "-N", "."], check=True, capture_output=True)

            # Get all diffs (including new files)
            result = subprocess.run(
                ["git", "diff", "HEAD"], capture_output=True, text=False, check=True
            )

            # Reset staging area
            subprocess.run(["git", "reset"], check=True, capture_output=True)

        return decode_output(result.stdout)

    except subprocess.CalledProcessError as e:
        return f"Failed to get diff: {str(e)}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


def get_diff_stat_between_commits(
    start_hash: str, end_hash: Optional[str] = None
) -> str:
    """Get diff statistics between two commits

    Parameters:
        start_hash: Starting commit hash (exclusive)
        end_hash: Ending commit hash (inclusive), use HEAD if None

    Returns:
        str: Diff statistics or error message
    """
    try:
        if end_hash is None:
            end_hash = "HEAD"

        # Check if start_hash exists
        start_check = subprocess.run(
            ["git", "rev-parse", "--verify", start_hash],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if start_check.returncode != 0:
            return f"Starting commit does not exist: {start_hash}"

        # Check if end_hash exists
        end_check = subprocess.run(
            ["git", "rev-parse", "--verify", end_hash],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if end_check.returncode != 0:
            return f"Ending commit does not exist: {end_hash}"

        # Get diff statistics between two commits
        result = subprocess.run(
            ["git", "diff", "--stat", f"{start_hash}..{end_hash}"],
            capture_output=True,
            text=False,
            check=True,
        )

        try:
            return decode_output(result.stdout)
        except Exception as e:
            return f"Failed to decode output: {str(e)}"

    except subprocess.CalledProcessError as e:
        error_msg = decode_output(e.stderr) if e.stderr else str(e)
        return f"Failed to get commit diff statistics: {error_msg}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


def get_diff_between_commits(start_hash: str, end_hash: Optional[str] = None) -> str:
    """Get diff between two commits

    Parameters:
        start_hash: Starting commit hash (exclusive)
        end_hash: Ending commit hash (inclusive), use HEAD if None

    Returns:
        str: Diff content or error message
    """
    try:
        if end_hash is None:
            # If end_hash is None, use HEAD
            end_hash = "HEAD"

        # Check if start_hash exists
        start_check = subprocess.run(
            ["git", "rev-parse", "--verify", start_hash],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if start_check.returncode != 0:
            return f"Starting commit does not exist: {start_hash}"

        # Check if end_hash exists
        end_check = subprocess.run(
            ["git", "rev-parse", "--verify", end_hash],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if end_check.returncode != 0:
            return f"Ending commit does not exist: {end_hash}"

        # Get diff between two commits
        result = subprocess.run(
            ["git", "diff", f"{start_hash}..{end_hash}"],
            capture_output=True,
            text=False,
            check=True,
        )

        try:
            return decode_output(result.stdout)
        except Exception as e:
            return f"Failed to decode output: {str(e)}"

    except subprocess.CalledProcessError as e:
        error_msg = decode_output(e.stderr) if e.stderr else str(e)
        return f"Failed to get commit diff: {error_msg}"
    except Exception as e:
        return f"Unexpected error occurred: {str(e)}"


def revert_file(filepath: str) -> None:
    """Enhanced git restore, handles new files"""
    import subprocess

    try:
        # Check if file is under version control
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", filepath],
            stderr=subprocess.PIPE,
            text=False,  # Disable automatic text decoding
        )
        if result.returncode == 0:
            subprocess.run(
                ["git", "checkout", "HEAD", "--", filepath],
                check=True,
                capture_output=True,
            )
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
        subprocess.run(
            ["git", "clean", "-f", "--", filepath], check=True, capture_output=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = decode_output(e.stderr) if e.stderr else str(e)
        PrettyOutput.auto_print(f"❌ Failed to restore file: {error_msg}")


# Modified restore function


def revert_change() -> None:
    """Restore all uncommitted changes to HEAD state"""
    import subprocess

    try:
        # Check if it is an empty repository
        head_check = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if head_check.returncode == 0:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"], check=True, capture_output=True
            )
        subprocess.run(["git", "clean", "-fd"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(f"❌ Failed to restore changes: {str(e)}")


def detect_large_code_deletion(threshold: int = 200) -> Optional[Dict[str, int]]:
    """Detect if there is large-scale code deletion

    Parameters:
        threshold: Net deletion line count threshold, default 200 lines

    Returns:
        Optional[Dict[str, int]]: If a large amount of deletion is detected, returns a dictionary containing statistics:
            {
                'insertions': int,  # Number of added lines
                'deletions': int,   # Number of deleted lines
                'net_deletions': int  # Net number of deleted lines
            }
            If there is no large amount of deletion or an error occurs, returns None
    """
    try:
        # Temporarily stage all files to get the complete diff statistics
        subprocess.run(
            ["git", "add", "-N", "."],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Check whether there is a HEAD
        head_check = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

        if head_check.returncode == 0:
            # Has HEAD, get diff statistics relative to HEAD
            diff_result = subprocess.run(
                ["git", "diff", "HEAD", "--shortstat"],
                capture_output=True,
                check=False,
            )
        else:
            # Empty repository, get working tree diff statistics
            diff_result = subprocess.run(
                ["git", "diff", "--shortstat"],
                capture_output=True,
                check=False,
            )

        # Reset the staging area
        subprocess.run(
            ["git", "reset"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Parse the number of inserted and deleted lines
        if diff_result.returncode == 0 and diff_result.stdout:
            output = decode_output(diff_result.stdout)
            insertions = 0
            deletions = 0
            insertions_match = re.search(r"(\d+)\s+insertions?\(\+\)", output)
            deletions_match = re.search(r"(\d+)\s+deletions?\(\-\)", output)
            if insertions_match:
                insertions = int(insertions_match.group(1))
            if deletions_match:
                deletions = int(deletions_match.group(1))

            # Check whether there is a large amount of code deletion (net deletion exceeds the threshold)
            net_deletions = deletions - insertions
            if net_deletions > threshold:
                return {
                    "insertions": insertions,
                    "deletions": deletions,
                    "net_deletions": net_deletions,
                }
        return None
    except Exception:
        # If an error occurs during the check, return None
        return None


# The confirm_large_code_deletion function is deprecated; uniformly use the large model query


def check_large_code_deletion(threshold: int = 200) -> bool:
    """Check whether there is a large amount of code deletion

    Parameters:
        threshold: Net deletion line threshold, defaults to 200 lines

    Returns:
        bool: Always returns True; the large model query is handled uniformly by the caller
    """
    # The detection feature is now handled uniformly by the caller
    return True


def handle_commit_workflow(start_commit: Optional[str] = None) -> bool:
    """Handle the git commit workflow and return the commit details.

    Args:
        start_commit: Starting commit hash, used for the squash workflow

    Returns:
        bool: Whether the commit was successful
    """
    global _last_commit_reject_reason
    _last_commit_reject_reason = ""

    if is_confirm_before_apply_patch() and not user_confirm(
        "Do you want to commit the code?", default=True
    ):
        _last_commit_reject_reason = "User cancelled the commit confirmation"
        revert_change()
        return False

    import subprocess

    try:
        confirm_add_new_files()

        # Get the current HEAD
        current_head = get_latest_commit_hash()

        # Check whether squash is needed: there is a start_commit and it differs from the current HEAD
        if start_commit and start_commit != current_head:
            # Perform squash operation: compress all commits after start_commit into one
            subprocess.run(
                ["git", "reset", "--soft", start_commit],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Commit code"], check=True, capture_output=True
            )
            return True

        # Original logic: check whether the working tree has uncommitted changes
        if not has_uncommitted_changes():
            _last_commit_reject_reason = "The working tree has no uncommitted changes"
            return False

        # Check for a large amount of code deletion before committing
        if not check_large_code_deletion():
            _last_commit_reject_reason = "A large amount of code deletion was detected; commit rejected"
            return False

        # Get the total number of commits on the current branch
        commit_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=False,
        )
        if commit_result.returncode != 0:
            _last_commit_reject_reason = (
                "Unable to get the total commit count (git rev-list --count HEAD failed)"
            )
            return False

        commit_count = int(decode_output(commit_result.stdout).strip())

        # Stage all modifications
        subprocess.run(["git", "add", "."], check=True, capture_output=True)

        # Commit the changes
        subprocess.run(
            ["git", "commit", "-m", f"CheckPoint #{commit_count + 1}"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        # Capture the specific error output of the git command failure (e.g. secret scanner / hook rejection reason)
        stderr = decode_output(e.stderr) if e.stderr else ""
        stdout = decode_output(e.stdout) if e.stdout else ""
        detail = (stderr or stdout or str(e)).strip()
        _last_commit_reject_reason = (
            f"git commit failed ({e.cmd}): {detail}" if detail else f"git commit failed: {e}"
        )
        return False


def get_latest_commit_hash() -> str:
    """Get the latest commit hash of the current Git repository

    Returns:
        str: Commit hash, returns an empty string if not in a Git repository, the repository is empty, or an error occurs
    """
    try:
        # First check whether a HEAD reference exists
        head_check = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        if head_check.returncode != 0:
            return ""  # Empty repository or invalid HEAD

        # Get the full hash of HEAD
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        return decode_output(result.stdout).strip() if result.returncode == 0 else ""
    except Exception:
        return ""


# Commit message prefix for automatic commits (temporary checkpoints).
# Only commits with this prefix are considered temporary commits automatically produced by CodeAgent and can be squashed and merged;
# All other commits (including user manual commits and formal commits generated by GitCommitTool) are
# treated as manual commits and retained as the starting point of a new task.
AUTO_COMMIT_PREFIX = "CheckPoint #"


def is_auto_commit_message(message: str) -> bool:
    """Determine whether the commit message is a temporary commit automatically produced by CodeAgent

    Parameters:
        message: Commit message (the subject line of git log)

    Returns:
        bool: Returns True if it starts with "CheckPoint #" (temporary commit), otherwise returns False
    """
    return (message or "").strip().startswith(AUTO_COMMIT_PREFIX)


def advance_start_commit(start_commit: Optional[str]) -> Optional[str]:
    """Move the task starting commit forward to the latest manual commit

    Scenario: During CodeAgent execution, the user may have manually run git commit (or produced
    formal commits generated by GitCommitTool). These commits are not the output of "this task",
    and if the old start_commit is still used as the starting point, subsequent squash / reset would mistakenly affect them.

    Therefore, scan from start_commit (exclusive) to HEAD in chronological order (old to new),
    and once a non-temporary commit (i.e. a manual commit) is encountered, move the starting point forward to that commit; take the last
    manual commit, and the temporary checkpoints after it are still counted as the output of this task.

    Parameters:
        start_commit: The currently recorded starting commit hash, may be None

    Returns:
        Optional[str]: The starting commit hash after moving forward; returned as-is when no move is needed
    """
    if not start_commit:
        return start_commit

    latest = get_latest_commit_hash()
    if not latest or latest == start_commit:
        return start_commit

    # git log outputs in reverse chronological order by default; after reversal it becomes the order from old to new
    commits = get_commits_between(start_commit, latest)
    if not commits:
        return start_commit

    new_start = start_commit
    for commit_hash, message in reversed(commits):
        if not is_auto_commit_message(message):
            new_start = commit_hash
    return new_start


def get_modified_line_ranges() -> Dict[str, List[Tuple[int, int]]]:
    """Get the modified line ranges of all changed files from the Git diff

    Returns:
        A dictionary mapping file paths to (start line, end line) range tuples containing the modified parts.
        Line numbers start from 1.
    """
    # Get the Git diff of all files
    # Used only to parse modified line ranges, reducing context to lower output size and parsing cost
    proc = subprocess.run(
        ["git", "show", "--no-color"],
        capture_output=True,
    )
    diff_output = decode_output(proc.stdout)

    # Parse the diff to get the modified files and their line ranges
    result: Dict[str, List[Tuple[int, int]]] = {}
    current_file = None

    for line in diff_output.splitlines():
        # Match lines like "+++ b/path/to/file"
        file_match = re.match(r"^\+\+\+ b/(.*)", line)
        if file_match:
            current_file = file_match.group(1)
            continue

        # Match lines like "@@ -100,5 +100,7 @@", where the + part shows the new lines
        range_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if range_match and current_file:
            start_line = int(range_match.group(1))  # Keep starting from 1
            line_count = int(range_match.group(2)) if range_match.group(2) else 1
            end_line = start_line + line_count - 1
            if current_file not in result:
                result[current_file] = []
            result[current_file].append((start_line, end_line))

    return result


def is_file_in_git_repo(filepath: str) -> bool:
    """Check whether the file is in the current Git repository"""
    import subprocess

    try:
        # Get the Git repository root directory
        repo_root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True
        )
        repo_root = (
            decode_output(repo_root_result.stdout).strip()
            if repo_root_result.returncode == 0
            else ""
        )

        # Check whether the file path is under the repository root directory
        return os.path.abspath(filepath).startswith(os.path.abspath(repo_root))
    except Exception:
        return False


def check_and_update_git_repo_background(repo_path: str) -> None:
    """Check and update the git repository in a background thread (without user interaction)

    This function is used for update checks executed by a background thread:
    - Minor version update: automatically run git checkout and pip install
    - Major version update: only write a marker file, do not perform the update
    - No user confirmation, no restart required

    Parameters:
        repo_path: Repository path
    """
    # Check the last check date
    last_check_file = os.path.join(get_data_dir(), "last_git_check")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists(last_check_file):
        with open(last_check_file, "r") as f:
            last_check_date = f.read().strip()
        if last_check_date == today_str:
            return

    try:
        git_root = find_git_root(repo_path)
    except Exception:
        return

    try:
        # Check whether there are uncommitted modifications
        if has_uncommitted_changes(cwd=git_root):
            return

        # Get remote tag updates
        try:
            subprocess.run(
                ["git", "fetch", "--tags"],
                cwd=git_root,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            # Handle fetch failures silently to avoid showing errors on every launch
            return
        # Get the latest local tag
        local_tag_result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=git_root,
            capture_output=True,
        )
        # Get the latest remote tag
        remote_tag_result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", "origin"],
            cwd=git_root,
            capture_output=True,
        )
        remote_tag = ""
        if remote_tag_result.returncode == 0:
            # Extract the latest tag name
            tags = [
                ref.split("/")[-1]
                for ref in decode_output(remote_tag_result.stdout).splitlines()
            ]
            tags = sorted(
                tags,
                key=lambda x: [
                    int(i) if i.isdigit() else i for i in re.split(r"([0-9]+)", x)
                ],
            )
            remote_tag = tags[-1] if tags else ""

        if (
            local_tag_result.returncode == 0
            and remote_tag_result.returncode == 0
            and decode_output(local_tag_result.stdout).strip() != remote_tag
        ):
            # Check whether it is a major version upgrade (different major version number)
            local_tag = decode_output(local_tag_result.stdout).strip()
            try:
                from packaging import version

                # Compare after removing the tag prefix 'v'
                local_ver = version.parse(local_tag.lstrip("v"))
                remote_ver = version.parse(remote_tag.lstrip("v"))
                is_major_upgrade = remote_ver.major != local_ver.major

                if is_major_upgrade:
                    PrettyOutput.auto_print(
                        f"⚠️ Major version upgrade detected: v{local_ver} -> v{remote_ver}"
                    )
                    PrettyOutput.auto_print(
                        "A major version upgrade may contain incompatible API changes; an update marker will be recorded in the background."
                    )
                    PrettyOutput.auto_print("ℹ️ On the next launch you will be asked whether to perform the major version upgrade.")
                    # Write the major version update marker
                    from haijunbot.haijunbot_utils.utils import _set_major_update_pending

                    _set_major_update_pending(remote_tag)
                    # Update the check date to avoid repeated prompts
                    with open(last_check_file, "w") as f:
                        f.write(today_str)
                    return
            except Exception:
                # If version parsing fails, keep the original behavior and continue the upgrade
                pass

            # Perform minor version update: first ensure the target tag's commit object exists (compatible with shallow clones), then git checkout
            try:
                subprocess.run(
                    ["git", "fetch", "--depth", "1", "origin", "tag", remote_tag],
                    cwd=git_root,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                # Handle fetch failures silently, try to checkout directly
                pass
            subprocess.run(
                ["git", "checkout", remote_tag],
                cwd=git_root,
                check=True,
                stderr=subprocess.PIPE,
            )
            PrettyOutput.auto_print(f"✅ HaijunBot has been updated to tag {remote_tag}")

            # Perform pip installation to update the code
            try:
                PrettyOutput.auto_print("ℹ️ Installing the updated code...")

                # Check whether in a virtual environment
                in_venv = hasattr(sys, "real_prefix") or (
                    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
                )

                # Detect uv availability
                from shutil import which as _which

                uv_executable = None
                if sys.platform == "win32":
                    venv_uv = os.path.join(sys.prefix, "Scripts", "uv.exe")
                else:
                    venv_uv = os.path.join(sys.prefix, "bin", "uv")
                if os.path.exists(venv_uv):
                    uv_executable = venv_uv
                else:
                    path_uv = _which("uv")
                    if path_uv:
                        uv_executable = path_uv

                # Choose the install command according to the environment
                if uv_executable:
                    install_cmd = [uv_executable, "pip", "install", "-e", "."]
                else:
                    install_cmd = [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-e",
                        ".",
                    ]

                # Try to install
                result = subprocess.run(install_cmd, cwd=git_root, capture_output=True)

                if result.returncode == 0:
                    PrettyOutput.auto_print("✅ Code update installed successfully")
                    PrettyOutput.auto_print(
                        "ℹ️ The update will take effect on the next launch; this run will continue to use the current version."
                    )
                    # Write the restart marker so the user is prompted to restart on the next launch
                    from haijunbot.haijunbot_utils.utils import _set_update_reboot_flag

                    _set_update_reboot_flag()
                    # Update the check date
                    with open(last_check_file, "w") as f:
                        f.write(today_str)
                    return

                # Handle permission errors
                error_msg = decode_output(result.stderr).strip()
                if not in_venv and (
                    "Permission denied" in error_msg or "not writeable" in error_msg
                ):
                    # The background thread does not perform user interaction; directly try a user-level install
                    user_result = subprocess.run(
                        install_cmd + ["--user"],
                        cwd=git_root,
                        capture_output=True,
                    )
                    if user_result.returncode == 0:
                        PrettyOutput.auto_print("✅ User-level code installed successfully")
                        PrettyOutput.auto_print(
                            "ℹ️ The update will take effect on the next launch; this run will continue to use the current version."
                        )
                        # Write the restart marker
                        from haijunbot.haijunbot_utils.utils import _set_update_reboot_flag

                        _set_update_reboot_flag()
                        # Update the check date
                        with open(last_check_file, "w") as f:
                            f.write(today_str)
                        return

                PrettyOutput.auto_print(f"❌ Code installation failed: {error_msg}")
            except Exception as e:
                PrettyOutput.auto_print(f"❌ An unexpected error occurred during installation: {str(e)}")

        # Update check date file
        with open(last_check_file, "w") as f:
            f.write(today_str)
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Update check failed: {str(e)}")
    finally:
        pass


def check_and_update_git_repo(repo_path: str) -> bool:
    """Check and update the git repository (with user interaction)

    Args:
        repo_path: repository path

    Returns:
        bool: whether the update was performed
    """
    # Check the last check date
    last_check_file = os.path.join(get_data_dir(), "last_git_check")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists(last_check_file):
        with open(last_check_file, "r") as f:
            last_check_date = f.read().strip()
        if last_check_date == today_str:
            return False

    try:
        git_root = find_git_root(repo_path)
    except Exception:
        return False

    try:
        # Check for uncommitted changes
        if has_uncommitted_changes(cwd=git_root):
            return False

        # Fetch remote tag updates
        subprocess.run(
            ["git", "fetch", "--tags"], cwd=git_root, check=True, capture_output=True
        )
        # Get the latest local tag
        local_tag_result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=git_root,
            capture_output=True,
        )
        # Get the latest remote tag
        remote_tag_result = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", "origin"],
            cwd=git_root,
            capture_output=True,
        )
        remote_tag = ""
        if remote_tag_result.returncode == 0:
            # Extract the latest tag name
            tags = [
                ref.split("/")[-1]
                for ref in decode_output(remote_tag_result.stdout).splitlines()
            ]
            tags = sorted(
                tags,
                key=lambda x: [
                    int(i) if i.isdigit() else i for i in re.split(r"([0-9]+)", x)
                ],
            )
            remote_tag = tags[-1] if tags else ""

        if (
            local_tag_result.returncode == 0
            and remote_tag_result.returncode == 0
            and decode_output(local_tag_result.stdout).strip() != remote_tag
        ):
            PrettyOutput.auto_print(
                f"ℹ️ Detected new version tag {remote_tag}, updating HaijunBot..."
            )

            # Check whether it is a major version upgrade (different major version number)
            local_tag = decode_output(local_tag_result.stdout).strip()
            try:
                from packaging import version

                # Compare after removing the tag prefix 'v'
                local_ver = version.parse(local_tag.lstrip("v"))
                remote_ver = version.parse(remote_tag.lstrip("v"))
                is_major_upgrade = remote_ver.major != local_ver.major

                if is_major_upgrade:
                    PrettyOutput.auto_print(
                        f"⚠️ Major version upgrade detected: v{local_ver} -> v{remote_ver}"
                    )
                    PrettyOutput.auto_print(
                        "A major version upgrade may contain incompatible API changes; an update flag will be recorded in the background."
                    )
                    PrettyOutput.auto_print("ℹ️ On the next startup you will be asked whether to perform the major version upgrade.")
                    # Write the major version update flag
                    from haijunbot.haijunbot_utils.utils import _set_major_update_pending

                    _set_major_update_pending(remote_tag)
                    # Update the check date to avoid repeated prompts
                    with open(last_check_file, "w") as f:
                        f.write(today_str)
                    return False
            except Exception:
                # If version parsing fails, keep the original behavior and continue the upgrade
                pass
            # First ensure the commit object of the target tag exists (for shallow clones), then git checkout
            try:
                subprocess.run(
                    ["git", "fetch", "--depth", "1", "origin", "tag", remote_tag],
                    cwd=git_root,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                # Handle fetch failure silently, then try checkout directly
                pass
            subprocess.run(
                ["git", "checkout", remote_tag],
                cwd=git_root,
                check=True,
                stderr=subprocess.PIPE,
            )
            PrettyOutput.auto_print(f"✅ HaijunBot has been updated to tag {remote_tag}")

            # Run pip install to update the code
            try:
                PrettyOutput.auto_print("ℹ️ Installing the updated code...")

                # Check whether inside a virtual environment
                in_venv = hasattr(sys, "real_prefix") or (
                    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
                )

                # Detect uv availability: prefer uv inside the virtual environment, then uv in PATH
                from shutil import which as _which

                uv_executable = None
                if sys.platform == "win32":
                    venv_uv = os.path.join(sys.prefix, "Scripts", "uv.exe")
                else:
                    venv_uv = os.path.join(sys.prefix, "bin", "uv")
                if os.path.exists(venv_uv):
                    uv_executable = venv_uv
                else:
                    path_uv = _which("uv")
                    if path_uv:
                        uv_executable = path_uv

                # Choose the install command based on the environment
                # Choose the install command based on uv availability (prefer uv)
                if uv_executable:
                    install_cmd = [uv_executable, "pip", "install", "-e", "."]
                else:
                    install_cmd = [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-e",
                        ".",
                    ]

                # Try to install
                result = subprocess.run(install_cmd, cwd=git_root, capture_output=True)

                if result.returncode == 0:
                    PrettyOutput.auto_print("✅ Code update installed successfully")
                    PrettyOutput.auto_print(
                        "ℹ️ The update will take effect on the next startup; this run will continue using the current version."
                    )
                    # Write the restart flag to prompt the user to restart on the next startup
                    from haijunbot.haijunbot_utils.utils import _set_update_reboot_flag

                    _set_update_reboot_flag()
                    return False

                # Handle permission errors
                error_msg = decode_output(result.stderr).strip()
                if not in_venv and (
                    "Permission denied" in error_msg or "not writeable" in error_msg
                ):
                    if user_confirm(
                        "Permission issue detected, try a user-level install (--user)?", True
                    ):
                        user_result = subprocess.run(
                            install_cmd + ["--user"],
                            cwd=git_root,
                            capture_output=True,
                        )
                        if user_result.returncode == 0:
                            PrettyOutput.auto_print("✅ User-level code installation succeeded")
                            PrettyOutput.auto_print(
                                "ℹ️ The update will take effect on the next startup; this run will continue using the current version."
                            )
                            # Write the restart flag to prompt the user to restart on the next startup
                            from haijunbot.haijunbot_utils.utils import (
                                _set_update_reboot_flag,
                            )

                            _set_update_reboot_flag()
                            return False
                        error_msg = decode_output(user_result.stderr).strip()

                PrettyOutput.auto_print(f"❌ Code installation failed: {error_msg}")
                return False
            except Exception as e:
                PrettyOutput.auto_print(f"❌ An unexpected error occurred during installation: {str(e)}")
                return False
        # Update check date file
        with open(last_check_file, "w") as f:
            f.write(today_str)
        return False
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Git repository update check failed: {e}")
        return False
    finally:
        pass


def get_diff_file_list() -> List[str]:
    """Get the list of files changed from HEAD to the current state, including modified and added files

    Returns:
        List[str]: list of modified and added file paths
    """
    try:
        confirm_add_new_files()

        # Stage newly added files
        subprocess.run(["git", "add", "-N", "."], check=True, capture_output=True)

        # Get all diff files (including newly added files)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], capture_output=True
        )

        # Reset the staging area
        subprocess.run(["git", "reset"], check=True, capture_output=True)

        if result.returncode != 0:
            PrettyOutput.auto_print(
                f"❌ Failed to get diff file list: {decode_output(result.stderr)}"
            )
            return []

        return [f for f in decode_output(result.stdout).splitlines() if f]

    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(f"❌ Failed to get diff file list: {str(e)}")
        return []
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Exception while getting diff file list: {str(e)}")
        return []


def get_recent_commits_with_files() -> List[Dict[str, Any]]:
    """Get the commit info and file list of the last 5 commits

    Returns:
        List[Dict[str, Any]]: list of dictionaries containing commit info and file list, in the format:
            [
                {
                    'hash': str,
                    'message': str,
                    'author': str,
                    'date': str,
                    'files': List[str]  # list of modified files (up to 20 files)
                },
                ...
            ]
            Returns an empty list on failure
    """
    try:
        # Get the current git username
        current_author_result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
        )
        current_author = (
            decode_output(current_author_result.stdout).strip()
            if current_author_result.returncode == 0
            else ""
        )

        # Get basic info of the current user's last 5 commits
        result = subprocess.run(
            [
                "git",
                "log",
                "-5",
                "--author=" + current_author,
                "--pretty=format:%H%n%s%n%an%n%ad",
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            return []

        # Parse commit info
        commits: List[Dict[str, Any]] = []
        lines = decode_output(result.stdout).splitlines()
        for i in range(0, len(lines), 4):
            if i + 3 >= len(lines):
                break
            commit: Dict[str, Any] = {
                "hash": lines[i],
                "message": lines[i + 1],
                "author": lines[i + 2],
                "date": lines[i + 3],
                "files": [],
            }
            commits.append(commit)

        # Get the file modification list for each commit
        for commit in commits:
            files_result = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:", commit["hash"]],
                capture_output=True,
            )
            if files_result.returncode == 0:
                file_lines = decode_output(files_result.stdout).splitlines()
                unique_files: Set[str] = set(filter(None, file_lines))
                commit["files"] = list(unique_files)[:20]  # Limit to a maximum of 20 files

        return commits

    except subprocess.CalledProcessError:
        return []


def _get_new_files() -> List[str]:
    """Get the list of newly added files"""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
    )
    return decode_output(result.stdout).splitlines()


def get_default_gitignore_templates() -> str:
    """Get the default .gitignore template for each language

    Returns:
        str: formatted .gitignore content, grouped by language
    """
    # Lazy import to avoid circular dependency
    from haijunbot.haijunbot_code_agent.code_analyzer.file_ignore import FileIgnorePatterns

    templates = []

    # Python
    if FileIgnorePatterns.PYTHON_DIRS or FileIgnorePatterns.PYTHON_VENV_DIRS:
        templates.append("# Python")
        templates.extend(sorted(FileIgnorePatterns.PYTHON_DIRS))
        templates.extend(sorted(FileIgnorePatterns.PYTHON_VENV_DIRS))
        templates.append("")

    # Rust
    if FileIgnorePatterns.RUST_DIRS:
        templates.append("# Rust")
        templates.extend(sorted(FileIgnorePatterns.RUST_DIRS))
        templates.append("")

    # Go
    if FileIgnorePatterns.GO_DIRS:
        templates.append("# Go")
        templates.extend(sorted(FileIgnorePatterns.GO_DIRS))
        templates.append("")

    # Node.js
    if FileIgnorePatterns.NODE_DIRS:
        templates.append("# Node.js")
        templates.extend(sorted(FileIgnorePatterns.NODE_DIRS))
        templates.append("")

    # Java
    if FileIgnorePatterns.JAVA_DIRS:
        templates.append("# Java")
        templates.extend(sorted(FileIgnorePatterns.JAVA_DIRS))
        templates.append("")

    # C/C++
    if FileIgnorePatterns.C_CPP_DIRS:
        templates.append("# C/C++")
        templates.extend(sorted(FileIgnorePatterns.C_CPP_DIRS))
        templates.append("")

    # .NET
    if FileIgnorePatterns.DOTNET_DIRS:
        templates.append("# .NET")
        templates.extend(sorted(FileIgnorePatterns.DOTNET_DIRS))
        templates.append("")

    # Common build artifacts
    if FileIgnorePatterns.BUILD_DIRS:
        templates.append("# Build artifacts")
        templates.extend(sorted(FileIgnorePatterns.BUILD_DIRS))
        templates.append("")

    # Dependency directories
    if FileIgnorePatterns.DEPENDENCY_DIRS:
        templates.append("# Dependencies")
        templates.extend(sorted(FileIgnorePatterns.DEPENDENCY_DIRS))
        templates.append("")

    # IDEs and editors
    if FileIgnorePatterns.OTHER_DIRS:
        templates.append("# IDE & Editors")
        templates.extend(sorted(FileIgnorePatterns.OTHER_DIRS))
        templates.append("")

    # HaijunBot-specific
    templates.append("# HaijunBot")
    templates.extend(sorted(FileIgnorePatterns.dirs))

    return "\n".join(templates)


def confirm_add_new_files() -> None:
    """Confirm newly added files, lines of code, and binary files"""
    global _confirm_add_new_files_called

    # If already confirmed, return directly to avoid repeated prompts
    if _confirm_add_new_files_called:
        return

    _confirm_add_new_files_called = True

    def _get_added_lines() -> int:
        """Get the number of newly added lines of code"""
        diff_stats_result = subprocess.run(
            ["git", "diff", "--numstat"],
            capture_output=True,
            check=True,
        )
        diff_stats = decode_output(diff_stats_result.stdout).splitlines()

        added_lines = 0
        for stat in diff_stats:
            parts = stat.split()
            if len(parts) >= 1:
                try:
                    added_lines += int(parts[0])
                except ValueError:
                    pass
        return added_lines

    def _get_binary_files(files: List[str]) -> List[str]:
        """Identify binary files from the file list"""
        binary_files = []
        for file in files:
            try:
                with open(file, "rb") as f:
                    if b"\x00" in f.read(1024):
                        binary_files.append(file)
            except (IOError, PermissionError):
                continue
        return binary_files

    def _check_conditions(
        new_files: List[str], added_lines: int, binary_files: List[str]
    ) -> bool:
        """Check various conditions and print prompt information"""
        need_confirm = False
        output_lines = []

        if len(new_files) > 20:
            output_lines.append(f"Detected {len(new_files)} newly added files (select N to re-detect)")
            output_lines.append("New file list:")
            output_lines.extend(f"  - {file}" for file in new_files)
            need_confirm = True

        if added_lines > 500:
            output_lines.append(f"Detected {added_lines} newly added lines of code (select N to re-detect)")
            need_confirm = True

        if binary_files:
            output_lines.append(
                f"Detected {len(binary_files)} binary files (select N to re-detect)"
            )
            output_lines.append("Binary file list:")
            output_lines.extend(f"  - {file}" for file in binary_files)
            need_confirm = True

        if output_lines:
            emoji = "⚠️ " if need_confirm else "ℹ️ "
            PrettyOutput.auto_print(emoji + ("\n" + emoji).join(output_lines))

        return need_confirm

    while True:
        new_files = _get_new_files()
        added_lines = _get_added_lines()
        binary_files = _get_binary_files(new_files)

        if not _check_conditions(new_files, added_lines, binary_files):
            break

        if not user_confirm(
            "Do you want to add these changes (if not, please modify the .gitignore file to ignore unwanted files)?",
            True,
        ):
            # User selected N: handle .gitignore
            try:
                repo_root_result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    check=True,
                )
                repo_root = decode_output(repo_root_result.stdout).strip() or "."
            except Exception:
                repo_root = "."
            gitignore_path = os.path.join(repo_root, ".gitignore")

            # Check whether .gitignore content needs to be added
            if os.path.exists(gitignore_path):
                # .gitignore already exists: only append .haijunbot (if not already included)
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if ".haijunbot" not in content:
                    try:
                        needs_newline = content and not content.endswith("\n")
                        with open(
                            gitignore_path, "a", encoding="utf-8", newline="\n"
                        ) as f:
                            if needs_newline:
                                f.write("\n")
                            f.write("\n.haijunbot/\n")
                        PrettyOutput.auto_print("✅ Added .haijunbot/ to .gitignore")
                    except Exception as e:
                        PrettyOutput.auto_print(
                            f"⚠ Failed to add .haijunbot/ to .gitignore: {e}"
                        )
            else:
                # .gitignore does not exist: generate the full default template for each language
                PrettyOutput.auto_print("ℹ No .gitignore file found")
                if user_confirm("Add the default .gitignore rules for each language?", True):
                    default_templates = get_default_gitignore_templates()
                    try:
                        with open(
                            gitignore_path, "w", encoding="utf-8", newline="\n"
                        ) as f:
                            f.write(default_templates + "\n")
                        PrettyOutput.auto_print("✅ Added default .gitignore rules for each language")
                    except Exception as e:
                        PrettyOutput.auto_print(f"⚠ Failed to add .gitignore: {e}")

            # Only ignore untracked new files (tracked files cannot be ignored via .gitignore)
            files_to_ignore = sorted(set(new_files))

            # Read the existing .gitignore to avoid duplicate additions
            existing_lines: Set[str] = set()
            try:
                if os.path.exists(gitignore_path):
                    with open(gitignore_path, "r", encoding="utf-8") as f:
                        existing_lines = set(line.strip() for line in f if line.strip())
            except Exception:
                existing_lines = set()

            # Append non-existent file paths to .gitignore (using paths relative to the repository root)
            try:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    for file in files_to_ignore:
                        abs_path = os.path.abspath(file)
                        rel_path = os.path.relpath(abs_path, repo_root)
                        # Avoid invalid relative paths (a .. prefix should not appear); fall back to the original value if present
                        entry = rel_path if not rel_path.startswith("..") else file
                        if entry not in existing_lines:
                            f.write(entry + "\n")
                PrettyOutput.auto_print(
                    "ℹ️ Untracked files have been added to .gitignore, re-detecting..."
                )
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️ Failed to update .gitignore: {str(e)}")

            continue

        break
