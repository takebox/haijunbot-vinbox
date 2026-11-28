# -*- coding: utf-8 -*-
"""Sharing management module, responsible for the sharing functionality of tools and methodologies"""

import os
import subprocess
from abc import ABC
from abc import abstractmethod
from typing import Any

from prompt_toolkit import prompt

from haijunbot.haijunbot_agent import user_confirm
from haijunbot.haijunbot_agent.share_secret_scanner import format_findings
from haijunbot.haijunbot_agent.share_secret_scanner import scan_files
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output


def parse_selection(selection_str: str, max_value: int) -> list[int]:
    """Parse the user-input selection string, supporting comma separation and range selection

    For example: "1,2,3,4-9,20" -> [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]
    """
    selected: set[int] = set()
    parts = selection_str.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            # Handle range selection
            try:
                start_str, end_str = part.split("-")
                start_num = int(start_str.strip())
                end_num = int(end_str.strip())
                if 1 <= start_num <= max_value and 1 <= end_num <= max_value:
                    selected.update(range(start_num, end_num + 1))
            except ValueError:
                continue
        else:
            # Handle a single number
            try:
                num = int(part)
                if 1 <= num <= max_value:
                    selected.add(num)
            except ValueError:
                continue

    return sorted(list(selected))


class ShareManager(ABC):
    """Sharing manager base class"""

    def __init__(self, central_repo_url: str, repo_name: str):
        self.central_repo_url = central_repo_url
        self.repo_name = repo_name
        # Supports configuring the central repository as a local directory (including a git subpath)
        expanded = os.path.expanduser(os.path.expandvars(central_repo_url))
        if os.path.isdir(expanded):
            # Use the local directory directly as the central repository path (supports git repository subdirectories)
            self.repo_path = expanded
        else:
            # Still use the clone path in the data directory per the original logic
            self.repo_path = os.path.join(get_data_dir(), repo_name)

    def update_central_repo(self) -> None:
        """Clone or update the central repository"""
        if not os.path.exists(self.repo_path):
            PrettyOutput.auto_print(f"ℹ️ Cloning the central {self.get_resource_type()} repository...")
            subprocess.run(
                ["git", "clone", self.central_repo_url, self.repo_path], check=True
            )
            # Check and add a .gitignore file
            gitignore_path = os.path.join(self.repo_path, ".gitignore")
            modified = False
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w") as f:
                    f.write("__pycache__/\n")
                modified = True
            else:
                with open(gitignore_path, "r+") as f:
                    content = f.read()
                    if "__pycache__" not in content:
                        f.write("\n__pycache__/\n")
                        modified = True

            if modified:
                subprocess.run(
                    ["git", "add", ".gitignore"], cwd=self.repo_path, check=True
                )
                subprocess.run(
                    ["git", "commit", "-m", "chore: add __pycache__ to .gitignore"],
                    cwd=self.repo_path,
                    check=True,
                )
                subprocess.run(["git", "push"], cwd=self.repo_path, check=True)
        else:
            PrettyOutput.auto_print(f"ℹ️ Updating the central {self.get_resource_type()} repository...")
            # Check whether it is an empty repository
            try:
                # First try to get the remote branch information
                result = subprocess.run(
                    ["git", "ls-remote", "--heads", "origin"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=False,
                    check=True,
                )
                # If there is a remote branch, perform pull
                if decode_output(result.stdout).strip():
                    # Check whether there are uncommitted changes
                    status_result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=False,
                        check=True,
                    )
                    if decode_output(status_result.stdout):
                        if user_confirm(
                            f"Uncommitted changes were detected in the central {self.get_resource_type()} repository '{self.repo_name}'. Discard these changes and update?"
                        ):
                            subprocess.run(
                                ["git", "checkout", "."], cwd=self.repo_path, check=True
                            )
                        else:
                            PrettyOutput.auto_print(
                                f"ℹ️ Skipping update of '{self.repo_name}' to preserve uncommitted changes."
                            )
                            return
                    subprocess.run(["git", "pull"], cwd=self.repo_path, check=True)
                else:
                    PrettyOutput.auto_print(
                        f"ℹ️ The central {self.get_resource_type()} repository is empty; it will be initialized as a new repository"
                    )
            except subprocess.CalledProcessError:
                # If the command fails, it may be a network problem or another error
                PrettyOutput.auto_print("⚠️ Unable to connect to the remote repository; skipping update")

    def _scan_staged_for_secrets(self) -> bool:
        """Scan the changed files to be committed this time, to intercept suspected real credentials.

        Returns True to pass (commit may continue), False if sensitive information is hit and must be aborted.
        The scan scope is limited to the files changed this time (git status --porcelain), not the whole history.
        Can be explicitly bypassed with the environment variable HAIJUNBOT_ALLOW_SECRETS=1 (semantically aligned with git pre-commit hooks).
        """
        if os.environ.get("HAIJUNBOT_ALLOW_SECRETS", "0") == "1":
            PrettyOutput.auto_print("⚠️ HAIJUNBOT_ALLOW_SECRETS=1; skipping the pre-share credential scan.")
            return True

        # Enumerate the files changed this time (relative to the central repository root)
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_path,
            capture_output=True,
            text=False,
            check=True,
        )
        changed_files: list[str] = []
        for raw_line in decode_output(status_result.stdout).splitlines():
            if len(raw_line) < 4:
                continue
            # porcelain format: XY <path>; a rename line looks like "R  old -> new"; take the new path
            path = raw_line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            # Strip possible quote wrapping
            path = path.strip('"')
            if path:
                changed_files.append(os.path.join(self.repo_path, path))

        if not changed_files:
            return True

        findings = scan_files(changed_files)
        if not findings:
            return True

        PrettyOutput.auto_print(
            f"❌ Suspected real credentials detected; sharing aborted ({self.get_resource_type()})."
        )
        PrettyOutput.auto_print("Detailed report (masked):")
        PrettyOutput.auto_print(format_findings(findings))
        PrettyOutput.auto_print("How to handle:")
        PrettyOutput.auto_print(
            "  1. If confirmed to be real credentials → remove them from the content to be shared and use environment variables/config files instead"
        )
        PrettyOutput.auto_print(
            "  2. If confirmed to be test samples/placeholders → add them to the whitelist in share_secret_scanner.py"
        )
        PrettyOutput.auto_print(
            "  3. If sharing is truly required (such as security test data) → re-run with HAIJUNBOT_ALLOW_SECRETS=1"
        )
        return False

    def commit_and_push(self, count: int) -> None:
        """Commit and push the changes"""
        PrettyOutput.auto_print("ℹ️ Committing changes...")
        subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True)

        # Pre-share gate: scan the content to be committed; abort if sensitive credentials are hit (no commit, no push)
        if not self._scan_staged_for_secrets():
            raise RuntimeError(
                f"Sharing aborted: suspected real credentials detected ({self.get_resource_type()})"
            )

        commit_msg = f"Add {count} {self.get_resource_type()}(s) from local collection"
        subprocess.run(
            ["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True
        )

        PrettyOutput.auto_print("ℹ️ Pushing to the remote repository...")
        # Check whether an upstream branch needs to be set (the case of an empty repository)
        try:
            # First try a normal push
            subprocess.run(["git", "push"], cwd=self.repo_path, check=True)
        except subprocess.CalledProcessError:
            # If it fails, it may be an empty repository; try setting the upstream branch
            try:
                subprocess.run(
                    ["git", "push", "-u", "origin", "main"],
                    cwd=self.repo_path,
                    check=True,
                )
            except subprocess.CalledProcessError:
                # If the main branch does not exist, try the master branch
                subprocess.run(
                    ["git", "push", "-u", "origin", "master"],
                    cwd=self.repo_path,
                    check=True,
                )

    def select_resources(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Let the user select the resources to share"""
        # Display the selectable resources
        resource_list = [
            f"\nShareable {self.get_resource_type()}(s) (those already in the central repository are excluded):"
        ]
        for i, resource in enumerate(resources, 1):
            resource_list.append(f"[{i}] {self.format_resource_display(resource)}")

        # Print all resources at once
        joined_resources = "\n".join(resource_list)
        PrettyOutput.auto_print(f"ℹ️ {joined_resources}")

        # Let the user choose
        while True:
            try:
                choice_str = prompt(
                    f"\nPlease select the {self.get_resource_type()} number(s) to share (supported format: 1,2,3,4-9,20 or all): "
                ).strip()
                if choice_str == "0":
                    return []

                if choice_str.lower() == "all":
                    return resources
                else:
                    selected_indices = parse_selection(choice_str, len(resources))
                    if not selected_indices:
                        PrettyOutput.auto_print("⚠️ Invalid selection")
                        continue
                    return [resources[i - 1] for i in selected_indices]

            except ValueError:
                PrettyOutput.auto_print("⚠️ Please enter a valid number")

    @abstractmethod
    def get_resource_type(self) -> str:
        """Get the resource type name"""
        pass

    @abstractmethod
    def format_resource_display(self, resource: dict[str, Any]) -> str:
        """Format the resource display"""
        pass

    @abstractmethod
    def get_existing_resources(self) -> Any:
        """Get the resources already present in the central repository"""
        pass

    @abstractmethod
    def get_local_resources(self) -> list[dict[str, Any]]:
        """Get local resources"""
        pass

    @abstractmethod
    def share_resources(self, resources: list[dict[str, Any]]) -> list[str]:
        """Share resources to the central repository"""
        pass
