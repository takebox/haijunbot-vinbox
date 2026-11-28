"""Git Worktree management module

This module provides the WorktreeManager class for managing the creation, merging, and cleanup of git worktrees.
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import os
import shutil
import subprocess
from datetime import datetime
from typing import Optional

from haijunbot.haijunbot_git_utils.git_commiter import GitCommitTool
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output
from haijunbot.haijunbot_utils.git_utils import (
    has_uncommitted_changes,
)


class WorktreeManager:
    """Git Worktree manager

    Responsible for managing the creation, merging, and cleanup operations of git worktrees.
    """

    def __init__(self, repo_root: str):
        """Initialize WorktreeManager

        Args:
            repo_root: the git repository root directory
        """
        self.repo_root = repo_root
        self.worktree_path: Optional[str] = None
        self.worktree_branch: Optional[str] = None

    def _auto_commit_if_needed(self) -> None:
        """Detect and automatically commit uncommitted changes

        Before creating a worktree, ensure the main repository is in a clean state.
        If there are uncommitted changes, commit them automatically.
        """
        try:
            if has_uncommitted_changes():
                PrettyOutput.auto_print("⚠️  Uncommitted changes detected in the main repository")
                PrettyOutput.auto_print("🔄 Automatically committing main repository changes...")
                git_commiter = GitCommitTool()
                git_commiter.execute(
                    {
                        "root_dir": self.repo_root,
                    }
                )
                PrettyOutput.auto_print("✅ Main repository changes have been committed automatically")
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Error during automatic commit: {str(e)}")

    def _get_project_name(self) -> str:
        """Get the project name

        Try to extract the project name from the git remote URL; if there is no remote, use the directory name

        Returns:
            str: the project name
        """
        try:
            # Try to get the URL from the git remote
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                check=True,
                text=True,
            )
            url = result.stdout.strip()
            # Extract the project name from the URL: e.g. https://github.com/user/repo.git extracts repo
            if url:
                # Remove the .git suffix
                if url.endswith(".git"):
                    url = url[:-4]
                # Get the last part
                project_name = os.path.basename(url)
                if project_name:
                    return project_name
        except (subprocess.CalledProcessError, Exception):
            pass

        # Fallback strategy: use the current directory name
        return os.path.basename(self.repo_root)

    def _has_commits(self) -> bool:
        """Check whether the repository has at least one commit

        Returns:
            bool: True if there is a commit, otherwise False
        """
        try:
            # Use git rev-parse HEAD to detect whether there is a commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                check=False,
                cwd=self.repo_root,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _generate_branch_name(self) -> str:
        """Generate the worktree branch name

        Returns:
            str: in the format haijunbot-{project_name}-YYYYMMDD-HHMMSS-fff (fff is milliseconds)
        """
        project_name = self._get_project_name()
        # Generate a timestamp including milliseconds (the first 3 digits of the microseconds)
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d-%H%M%S") + f"-{now.microsecond // 1000:03d}"
        return f"haijunbot-{project_name}-{timestamp}"

    def get_current_branch(self) -> str:
        """Get the current branch name

        Returns:
            str: the current branch name

        Raises:
            RuntimeError: if getting the branch name fails
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                check=True,
            )
            branch = decode_output(result.stdout).strip()
            if not branch or branch == "HEAD":
                raise RuntimeError("Not currently on any branch (in detached HEAD state)")
            return branch
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get the current branch: {decode_output(e.stderr)}")
        except Exception as e:
            raise RuntimeError(f"Error while getting the current branch: {str(e)}")

    def _link_haijunbot_dir(self, worktree_path: str) -> None:
        """Set up a layered .haijunbot directory structure in the worktree

        Uses a layered symlink strategy:
        1. Create an independent .haijunbot directory (for config files tracked by Git)
        2. Create symlinks for runtime data directories (sharing the main repository data)

        The reasons for this design:
        - .haijunbot/rule.md and .haijunbot/rules/ need to be independent, to avoid modification conflicts between branches
        - Runtime data such as .haijunbot/memory/ needs to be shared, to avoid duplication and confusion

        Args:
            worktree_path: the worktree directory path

        Raises:
            RuntimeError: if creating the directory or symlink fails
        """
        original_haijunbot_dir = os.path.join(self.repo_root, ".haijunbot")
        worktree_haijunbot_dir = os.path.join(worktree_path, ".haijunbot")

        # Check whether the .haijunbot directory of the original repository exists
        if not os.path.exists(original_haijunbot_dir):
            PrettyOutput.auto_print("⚠️ The original repository has no .haijunbot directory, skipping setup")
            return

        # Define the Git-tracked files/directories that need to be copied independently
        # These files are independent in each worktree, to avoid modification conflicts between branches
        git_tracked_items = [
            "rule.md",  # .haijunbot/rule.md
            "rules",  # .haijunbot/rules/
        ]

        try:
            # Step 1: handle an existing .haijunbot directory
            if os.path.islink(worktree_haijunbot_dir):
                # If it is a symlink (old configuration), delete it
                PrettyOutput.auto_print("🔗 Old .haijunbot symlink detected, preparing to rebuild...")
                os.unlink(worktree_haijunbot_dir)
                need_create_dir = True
            elif os.path.exists(worktree_haijunbot_dir):
                # If the directory already exists (rule and rules auto-checked out by Git), no need to rebuild
                PrettyOutput.auto_print("✅ .haijunbot directory already exists (auto-checked out by Git)")
                need_create_dir = False
            else:
                # The directory does not exist, needs to be created
                need_create_dir = True

            # Step 2: create an independent .haijunbot directory (if needed)
            if need_create_dir:
                os.makedirs(worktree_haijunbot_dir, exist_ok=True)
                PrettyOutput.auto_print(
                    f"📁 Created independent .haijunbot directory: {worktree_haijunbot_dir}"
                )

                # Step 3: copy the Git-tracked files to the independent directory
                for item in git_tracked_items:
                    src_path = os.path.join(original_haijunbot_dir, item)
                    dst_path = os.path.join(worktree_haijunbot_dir, item)

                    if os.path.exists(src_path):
                        if os.path.isdir(src_path):
                            # Copy the directory
                            shutil.copytree(src_path, dst_path)
                            PrettyOutput.auto_print(f"📋 Copied Git directory: {item}")
                        else:
                            # Copy the file
                            shutil.copy2(src_path, dst_path)
                            PrettyOutput.auto_print(f"📄 Copied Git file: {item}")
                    else:
                        PrettyOutput.auto_print(f"⚠️ Git-tracked item does not exist: {item}")

            # Step 4: create symlinks for all other files and directories (except rule and rules)
            # Iterate over all items under the main repository's .haijunbot
            for item in os.listdir(original_haijunbot_dir):
                # Skip Git-tracked items (they should already exist or have been copied)
                if item in git_tracked_items:
                    continue

                src_path = os.path.join(original_haijunbot_dir, item)
                dst_path = os.path.join(worktree_haijunbot_dir, item)

                # If the symlink already exists, skip
                if os.path.exists(dst_path) or os.path.islink(dst_path):
                    continue

                # Create a symlink: worktree/.haijunbot/item -> original repo/.haijunbot/item
                try:
                    if os.name == "nt":
                        # Windows: use copy instead of symlink (requires admin privilege)
                        if os.path.isdir(src_path):
                            shutil.copytree(src_path, dst_path)
                        else:
                            shutil.copy2(src_path, dst_path)
                        item_type = "directory" if os.path.isdir(src_path) else "file"
                        PrettyOutput.auto_print(f"📋 Copied {item_type}: {item}")
                    else:
                        os.symlink(src_path, dst_path)
                        item_type = "directory" if os.path.isdir(src_path) else "file"
                        PrettyOutput.auto_print(f"🔗 Created {item_type} symlink: {item}")
                except Exception as e:
                    PrettyOutput.auto_print(f"⚠️ Failed to create symlink {item}: {str(e)}")

            PrettyOutput.auto_print("✅ .haijunbot directory setup complete (layered symlink mode)")

        except Exception as e:
            # On error, try to roll back: delete the created .haijunbot directory
            PrettyOutput.auto_print(f"❌ Error setting up the .haijunbot directory: {str(e)}")
            PrettyOutput.auto_print("🧹 Attempting rollback...")
            try:
                if os.path.exists(worktree_haijunbot_dir):
                    if os.path.islink(worktree_haijunbot_dir):
                        os.unlink(worktree_haijunbot_dir)
                    else:
                        shutil.rmtree(worktree_haijunbot_dir)
                PrettyOutput.auto_print("✅ Rollback successful")
            except Exception as rollback_error:
                PrettyOutput.auto_print(f"⚠️ Rollback failed: {str(rollback_error)}")
                PrettyOutput.auto_print(f"💡 Please clean up manually: {worktree_haijunbot_dir}")

            raise RuntimeError(f"Failed to set up the .haijunbot directory: {str(e)}")

    def create_worktree(self, branch_name: Optional[str] = None) -> str:
        """Create a git worktree branch and directory

        Args:
            branch_name: the branch name; if None, it is generated automatically

        Returns:
            str: the worktree directory path

        Raises:
            RuntimeError: if creating the worktree fails
        """
        # Detect and automatically commit uncommitted changes (ensure the main repository is clean)
        self._auto_commit_if_needed()

        # Check whether the repository has commits; if not, create an initial commit automatically
        if not self._has_commits():
            PrettyOutput.auto_print("⚠️ The repository has no commits, creating an initial commit automatically...")
            try:
                # Configure the git user info (to avoid commit failures)
                subprocess.run(
                    ["git", "config", "user.email", "haijunbot@localhost"],
                    capture_output=True,
                    check=True,
                    cwd=self.repo_root,
                )
                subprocess.run(
                    ["git", "config", "user.name", "HaijunBot AI Agent"],
                    capture_output=True,
                    check=True,
                    cwd=self.repo_root,
                )
                # Create an empty commit
                subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", "Initial commit"],
                    capture_output=True,
                    check=True,
                    cwd=self.repo_root,
                )
                PrettyOutput.auto_print("✅ Initial commit created automatically")
            except subprocess.CalledProcessError as e:
                error_msg = decode_output(e.stderr) if e.stderr else str(e)
                raise RuntimeError(
                    f"Failed to create the initial commit automatically: {error_msg}\n"
                    f"Please run manually: git commit --allow-empty -m 'Initial commit'"
                )

        if branch_name is None:
            branch_name = self._generate_branch_name()

        self.worktree_branch = branch_name

        PrettyOutput.auto_print(f"🌿 Creating git worktree: {branch_name}")

        try:
            # Create the worktree
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, f"../{branch_name}"],
                capture_output=True,
                check=True,
                text=True,
            )

            # Get the worktree directory path
            worktree_path = os.path.join(os.path.dirname(self.repo_root), branch_name)
            self.worktree_path = worktree_path

            PrettyOutput.auto_print(f"✅ Worktree created successfully: {worktree_path}")

            # Symlink the original repository's .haijunbot directory into the worktree
            self._link_haijunbot_dir(worktree_path)

            return worktree_path

        except subprocess.CalledProcessError as e:
            error_msg = decode_output(e.stderr) if e.stderr else str(e)
            raise RuntimeError(f"Failed to create the worktree: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"Error while creating the worktree: {str(e)}")

    def merge_back(self, original_branch: str, non_interactive: bool = False) -> bool:
        """Rebase the worktree branch and merge it back into the original branch

        Uses the rebase strategy: first rebase the worktree branch onto the original branch,
        then merge via fast-forward, keeping a linear history.

        Args:
            original_branch: the original branch name
            non_interactive: whether it is non-interactive mode

        Returns:
            bool: whether the merge succeeded
        """
        if not self.worktree_branch:
            PrettyOutput.auto_print("⚠️ There is no active worktree branch")
            return False

        PrettyOutput.auto_print(
            f"🔀 Rebasing and merging {self.worktree_branch} into {original_branch}"
        )

        # Check the main repository status, ensuring it is clean
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
                cwd=self.repo_root,
            )
            if status_result.stdout.strip():
                PrettyOutput.auto_print("⚠️ The main repository has uncommitted changes, cannot merge safely")
                PrettyOutput.auto_print("💡 Please commit or stash the main repository changes first")
                return False
        except subprocess.CalledProcessError:
            PrettyOutput.auto_print("⚠️ Unable to check the main repository status")
            return False

        try:
            # Step 1: perform the rebase in the worktree directory
            PrettyOutput.auto_print(
                f"🔄 Rebasing {self.worktree_branch} onto {original_branch} in the worktree..."
            )
            result = subprocess.run(
                ["git", "rebase", original_branch],
                capture_output=True,
                check=False,
                cwd=self.worktree_path,
            )

            if result.returncode != 0:
                error_msg = (
                    decode_output(result.stderr) if result.stderr else "Unknown error"
                )
                if "CONFLICT" in error_msg or "conflict" in error_msg.lower():
                    PrettyOutput.auto_print("⚠️ The rebase produced conflicts")
                    PrettyOutput.auto_print("📋 Conflict handling options:")
                    PrettyOutput.auto_print(
                        "   1. After resolving the conflicts manually, run: git rebase --continue"
                    )
                    PrettyOutput.auto_print(
                        "   2. Abandon this rebase, run: git rebase --abort"
                    )

                    # Automatically abort the rebase to clean up the state (keep the repository consistent)
                    PrettyOutput.auto_print("🧹 Automatically aborting the rebase to restore the state...")
                    abort_result = subprocess.run(
                        ["git", "rebase", "--abort"],
                        capture_output=True,
                        check=False,
                        timeout=5,
                        cwd=self.worktree_path,
                    )
                    if abort_result.returncode != 0:
                        abort_error = (
                            decode_output(abort_result.stderr)
                            if abort_result.stderr
                            else "Unknown error"
                        )
                        PrettyOutput.auto_print(f"⚠️ Failed to abort the rebase: {abort_error}")
                        PrettyOutput.auto_print("💡 Please run manually: git rebase --abort")
                    return False
                else:
                    raise RuntimeError(f"Rebase failed: {error_msg}")

            # Step 2: merge via fast-forward
            PrettyOutput.auto_print(
                f"🔀 Fast-forward merging {self.worktree_branch}..."
            )
            result = subprocess.run(
                ["git", "merge", "--ff-only", self.worktree_branch],
                capture_output=True,
                check=False,
                cwd=self.repo_root,
            )

            if result.returncode != 0:
                error_msg = (
                    decode_output(result.stderr) if result.stderr else "Unknown error"
                )
                raise RuntimeError(f"Fast-forward merge failed: {error_msg}")

            PrettyOutput.auto_print("✅ Rebase and merge succeeded")
            return True

        except subprocess.CalledProcessError as e:
            error_msg = decode_output(e.stderr) if e.stderr else str(e)
            PrettyOutput.auto_print(f"❌ Operation failed: {error_msg}")
            return False
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error during the operation: {str(e)}")
            return False
        finally:
            # Clean up the rebase state in the worktree (if the rebase failed)
            try:
                abort_result = subprocess.run(
                    ["git", "rebase", "--abort"],
                    capture_output=True,
                    check=False,
                    timeout=5,
                    cwd=self.worktree_path,
                )
                # If there is no rebase in progress, a non-zero return code is normal; ignore the error
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_code_agent.worktree_manager",
                    function="merge_back",
                )
                pass

            # Check the worktree status and provide recovery guidance
            try:
                status_result = subprocess.run(
                    ["git", "status", "--short", "--branch"],
                    capture_output=True,
                    check=True,
                    text=True,
                    timeout=5,
                    cwd=self.worktree_path,
                )
                # If there are unmerged files or conflicts, prompt the user
                if (
                    "rebasing" in status_result.stdout
                    or "conflict" in status_result.stdout.lower()
                ):
                    PrettyOutput.auto_print("⚠️ The worktree state is abnormal, there may be unresolved conflicts")
                    PrettyOutput.auto_print(f"💡 Worktree path: {self.worktree_path}")
                    PrettyOutput.auto_print("💡 Please check and handle it manually:")
                    PrettyOutput.auto_print(f"   cd {self.worktree_path}")
                    PrettyOutput.auto_print("   git status")
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_code_agent.worktree_manager",
                    function="merge_back",
                )
                pass

    def cleanup(self, worktree_path: Optional[str] = None) -> bool:
        """Clean up the worktree directory

        Args:
            worktree_path: the worktree directory path; if None, the current worktree_path is used

        Returns:
            bool: whether the cleanup succeeded
        """
        target_path = worktree_path or self.worktree_path
        if not target_path:
            PrettyOutput.auto_print("⚠️ There is no worktree to clean up")
            return False

        PrettyOutput.auto_print(f"🧹 Cleaning up worktree: {target_path}")

        try:
            # Get the branch name
            branch_name = os.path.basename(target_path)

            # Delete using git worktree remove
            result = subprocess.run(
                ["git", "worktree", "remove", branch_name],
                capture_output=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = (
                    decode_output(result.stderr) if result.stderr else "Unknown error"
                )
                PrettyOutput.auto_print(f"⚠️ Failed to remove the worktree: {error_msg}")
                return False

            PrettyOutput.auto_print("✅ Worktree cleaned up successfully")

            # Delete the corresponding branch
            if self.worktree_branch:
                PrettyOutput.auto_print(f"🗑️  Deleting branch: {self.worktree_branch}")
                try:
                    delete_result = subprocess.run(
                        ["git", "branch", "-D", self.worktree_branch],
                        capture_output=True,
                        check=False,
                        cwd=self.repo_root,
                    )
                    if delete_result.returncode == 0:
                        PrettyOutput.auto_print(
                            f"✅ Branch {self.worktree_branch} deleted"
                        )
                    else:
                        error_msg = (
                            decode_output(delete_result.stderr)
                            if delete_result.stderr
                            else "Unknown error"
                        )
                        PrettyOutput.auto_print(f"⚠️ Failed to delete the branch: {error_msg}")
                        PrettyOutput.auto_print(
                            f"💡 Please delete the branch manually: git branch -D {self.worktree_branch}"
                        )
                except Exception as e:
                    PrettyOutput.auto_print(f"⚠️ Error while deleting the branch: {str(e)}")

            return True

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Error while cleaning up the worktree: {str(e)}")
            return False

    def get_worktree_info(self) -> dict:
        """Get the current worktree information

        Returns:
            dict: a dictionary containing worktree_path and worktree_branch
        """
        return {
            "worktree_path": self.worktree_path,
            "worktree_branch": self.worktree_branch,
        }
