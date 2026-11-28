"""CodeAgent Git operations module"""

import os
import subprocess

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output

# -*- coding: utf-8 -*-
import sys
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_git_utils.git_commiter import GitCommitTool
from haijunbot.haijunbot_utils.git_utils import confirm_add_new_files
from haijunbot.haijunbot_utils.git_utils import find_git_root_and_cd
from haijunbot.haijunbot_utils.git_utils import get_commits_between
from haijunbot.haijunbot_utils.git_utils import has_uncommitted_changes
from haijunbot.haijunbot_utils.git_utils import reset_confirm_add_new_files_flag
from haijunbot.haijunbot_utils.config import get_llm_group
from haijunbot.haijunbot_utils.input import user_confirm


class GitManager:
    """Git operations manager"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def check_git_config(self) -> None:
        """Check whether git username and email are set; if not, prompt and exit"""
        try:
            # Check git user.name
            result = subprocess.run(
                ["git", "config", "--get", "user.name"],
                capture_output=True,
                text=False,
                check=False,
            )
            username = decode_output(result.stdout).strip()

            # Check git user.email
            result = subprocess.run(
                ["git", "config", "--get", "user.email"],
                capture_output=True,
                text=False,
                check=False,
            )
            email = decode_output(result.stdout).strip()

            # If either config is not set, prompt and exit
            if not username or not email:
                missing_configs = []
                if not username:
                    missing_configs.append(
                        '  git config --global user.name "Your Name"'
                    )
                if not email:
                    missing_configs.append(
                        '  git config --global user.email "your.email@example.com"'
                    )

                message = "❌ Git configuration is incomplete\n\nPlease run the following commands to configure Git:\n" + "\n".join(
                    missing_configs
                )
                PrettyOutput.auto_print(f"❌ {message}")
                sys.exit(1)

        except FileNotFoundError:
            PrettyOutput.auto_print("❌ git command not found, please install Git first")
            sys.exit(1)
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error while checking Git configuration: {str(e)}")
            sys.exit(1)

    def find_git_root(self) -> str:
        """Find and switch to the git root directory

        Returns:
            str: git root directory path
        """
        curr_dir = os.getcwd()
        git_dir = find_git_root_and_cd(curr_dir)
        self.root_dir = git_dir
        return git_dir

    def update_gitignore(self, git_dir: str) -> None:
        """Check and update the .gitignore file

        - If .gitignore does not exist, create it and write the default ignore rules for each language
        - If .gitignore exists but has no .haijunbot, only append .haijunbot/

        Args:
            git_dir: git root directory path
        """
        # Lazy import to avoid circular dependency
        from haijunbot.haijunbot_utils.git_utils import get_default_gitignore_templates

        gitignore_path = os.path.join(git_dir, ".gitignore")

        existing_content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
                existing_content = f.read()

        # Check whether it already contains .haijunbot (used to determine whether default rules have been added)
        if ".haijunbot" in existing_content:
            return

        if not os.path.exists(gitignore_path):
            # Create a new .gitignore and write the default ignore rules for each language
            default_templates = get_default_gitignore_templates()
            with open(gitignore_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(default_templates + "\n")
            PrettyOutput.auto_print("✅ Created .gitignore and added default ignore rules for each language")
        else:
            # .gitignore exists but has no .haijunbot, only append .haijunbot/
            with open(gitignore_path, "a", encoding="utf-8", newline="\n") as f:
                # If the original file does not end with a newline, add one first
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write("\n.haijunbot/\n")
            PrettyOutput.auto_print("✅ Updated .gitignore, added .haijunbot/ ignore rule")

    def handle_git_changes(self, prefix: str, suffix: str, agent: Any) -> None:
        """Handle uncommitted changes in the git repository"""
        if has_uncommitted_changes():
            git_commiter = GitCommitTool()
            git_commiter.execute(
                {
                    "prefix": prefix,
                    "suffix": suffix,
                    "agent": agent,
                    # Use the current model group (no longer inherited from agent)
                    "llm_group": get_llm_group(),
                }
            )

    def init_env(self, prefix: str, suffix: str, agent: Any) -> None:
        """Initialize the environment, combining the following features:
        1. Find the git root directory
        2. Check and update the .gitignore file
        3. Handle uncommitted changes
        4. Configure git to be insensitive to line ending changes
        """
        git_dir = self.find_git_root()
        self.update_gitignore(git_dir)
        self.handle_git_changes(prefix, suffix, agent)
        # Configure git to be insensitive to line ending changes
        self.configure_line_ending_settings()

    def configure_line_ending_settings(self) -> None:
        """Configure git to be insensitive to line ending changes, only modifying when current settings differ from target settings"""
        target_settings = {
            "core.autocrlf": "false",
            "core.safecrlf": "false",
            "core.whitespace": "cr-at-eol",  # Ignore the CR at end of line
        }

        # Get the current settings and check whether changes are needed
        need_change = False
        current_settings = {}
        for key, target_value in target_settings.items():
            result = subprocess.run(
                ["git", "config", "--get", key],
                capture_output=True,
                text=False,
                check=False,
            )
            current_value = decode_output(result.stdout).strip()
            current_settings[key] = current_value
            if current_value != target_value:
                need_change = True

        if not need_change:
            return

        PrettyOutput.auto_print(
            "⚠️ Modifying git line-ending sensitivity settings, this will affect how line endings are handled for all files"
        )
        # Avoid printing one by one in a loop, concatenate first and then print together
        lines = ["The following settings will be applied:"]
        for key, value in target_settings.items():
            current = current_settings.get(key, "not set")
            lines.append(f"{key}: {current} -> {value}")
        joined_lines = "\n".join(lines)
        PrettyOutput.auto_print(f"ℹ️ {joined_lines}")

        # Apply the settings directly, no user confirmation needed
        for key, value in target_settings.items():
            subprocess.run(["git", "config", key, value], check=True)

        # For Windows systems, prompt the user that they can create a .gitattributes file
        if sys.platform.startswith("win"):
            self.handle_windows_line_endings()

        PrettyOutput.auto_print("✅ git line-ending sensitivity settings updated")

    def handle_windows_line_endings(self) -> None:
        """Handle line ending issues on Windows systems, providing suggestions rather than forcing changes"""
        gitattributes_path = os.path.join(self.root_dir, ".gitattributes")

        # Check whether a .gitattributes file already exists
        if os.path.exists(gitattributes_path):
            with open(gitattributes_path, "r", encoding="utf-8") as f:
                content = f.read()
            # If there is already line-ending-related configuration, do not prompt again
            if any(keyword in content for keyword in ["text=", "eol=", "binary"]):
                return

        PrettyOutput.auto_print(
            "ℹ️ Tip: On Windows systems, it is recommended to configure a .gitattributes file to avoid line ending issues."
        )
        PrettyOutput.auto_print(
            "ℹ️ This prevents an entire file from being marked as modified merely due to different line endings."
        )

        if user_confirm("Do you want to create a minimal .gitattributes file?", False):
            # Minimal content, only affecting specific file types
            minimal_content = """# HaijunBot-recommended minimal line ending configuration
# Use LF for all text files by default, only Windows-specific files use CRLF

# Use LF for all text files by default
* text=auto eol=lf

# Windows batch files need CRLF
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf
"""

            if not os.path.exists(gitattributes_path):
                with open(gitattributes_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(minimal_content)
                PrettyOutput.auto_print("✅ Created minimal .gitattributes file")
            else:
                PrettyOutput.auto_print("ℹ️ The following content will be appended to the existing .gitattributes file:")
                PrettyOutput.auto_print(
                    "📝 " + minimal_content, lang="text"
                )  # Keep syntax highlighting
                if user_confirm("Append to the existing file?", True):
                    with open(
                        gitattributes_path, "a", encoding="utf-8", newline="\n"
                    ) as f:
                        f.write("\n" + minimal_content)
                    PrettyOutput.auto_print("✅ Updated .gitattributes file")
        else:
            PrettyOutput.auto_print(
                "ℹ️ Skipped .gitattributes file creation. If you encounter line ending issues, you can create this file manually."
            )

    def handle_uncommitted_changes(self) -> None:
        """Handle uncommitted changes, including:
        1. Prompt the user to confirm whether to commit
        2. If confirmed, check the number of new files
        3. If more than 20 new files, ask the user to confirm whether to add them
        4. If the user refuses to add many files, prompt to modify .gitignore and re-detect
        5. Stage and commit all changes
        """
        # Reset the global flag to allow file confirmation again in this flow
        reset_confirm_add_new_files_flag()

        if has_uncommitted_changes():
            PrettyOutput.auto_print("⚠️ Uncommitted changes detected, commit them?")
            if not user_confirm("Commit now?", True):
                return

            try:
                confirm_add_new_files()

                if not has_uncommitted_changes():
                    return

                # Get the total number of commits on the current branch
                # Compatible with empty repositories or no HEAD: on failure, treat the commit count as 0 and continue the commit flow
                commit_count = 0
                try:
                    commit_result = subprocess.run(
                        ["git", "rev-list", "--count", "HEAD"],
                        capture_output=True,
                        text=False,
                        check=False,
                    )
                    if commit_result.returncode == 0:
                        out = decode_output(commit_result.stdout).strip()
                        if out.isdigit():
                            commit_count = int(out)
                except Exception:
                    commit_count = 0

                # Stage all changes
                subprocess.run(["git", "add", "."], check=True)

                # Commit changes
                subprocess.run(
                    ["git", "commit", "-m", f"CheckPoint #{commit_count + 1}"],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                PrettyOutput.auto_print(f"❌ Commit failed: {str(e)}")

    def show_commit_between(
        self, start_commit: Optional[str], end_commit: Optional[str]
    ) -> List[Tuple[str, str]]:
        """Show the commit history between two commits

        Args:
            start_commit: starting commit hash
            end_commit: ending commit hash

        Returns:
            A list of tuples containing (commit_hash, commit_message)
        """
        if start_commit and end_commit:
            commits = get_commits_between(start_commit, end_commit)
        else:
            commits = []

        if commits:
            commit_messages = "The following commit records were detected:\n" + "\n".join(
                f"- {commit_hash[:7]}: {message}" for commit_hash, message in commits
            )
            PrettyOutput.auto_print(f"ℹ️ {commit_messages}")
        return commits

    def handle_commit_confirmation(
        self,
        commits: List[Tuple[str, str]],
        start_commit: Optional[str],
        prefix: str,
        suffix: str,
        agent: Any,
        post_process_func: Any,
        skip_confirm: bool = False,
    ) -> None:
        """Handle commit confirmation and possible reset"""
        if commits and (skip_confirm or user_confirm("Accept the above commit records?", True)):
            subprocess.run(
                ["git", "reset", "--mixed", str(start_commit)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            # Detect changed files and format them
            from haijunbot.haijunbot_utils.git_utils import get_diff_file_list

            modified_files = get_diff_file_list()
            if modified_files:
                post_process_func(modified_files)

            git_commiter = GitCommitTool()
            git_commiter.execute(
                {
                    "prefix": prefix,
                    "suffix": suffix,
                    "agent": agent,
                    # Use the current model group (no longer inherited from agent)
                    "llm_group": get_llm_group(),
                }
            )

            # Update start_commit to the latest commit hash, so the correct starting point is used on the next commit
            from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

            agent.start_commit = get_latest_commit_hash()

            # After the user accepts the commit, decide whether to save memory based on configuration
            if getattr(agent, "force_save_memory", False):
                agent.memory_manager.prompt_memory_save()
        elif start_commit and commits:
            if user_confirm("Reset to the initial commit?", True):
                # Git operation: reset to the specified commit (already confirmed by the user, the commit ID comes from git)
                os.system(f"git reset --hard {str(start_commit)}")  # nosec B605
                PrettyOutput.auto_print("ℹ️ Reset to the initial commit")
