# -*- coding: utf-8 -*-
"""Rule sharing management module"""

import glob
import os
import shutil
from typing import Any
from typing import Dict
from typing import List

import typer

from haijunbot.haijunbot_agent import user_confirm
from haijunbot.haijunbot_agent.share_manager import ShareManager
from haijunbot.haijunbot_utils.config import get_central_rules_repo
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import get_rules_load_dirs
from haijunbot.haijunbot_utils.output import PrettyOutput


class RuleShareManager(ShareManager):
    """Rule sharing manager"""

    def __init__(self) -> None:
        central_repo = get_central_rules_repo()
        if not central_repo:
            PrettyOutput.auto_print("❌ Error: central rules repository (central_rules_repo) is not configured")
            PrettyOutput.auto_print("ℹ️ Please set the Git address of the central rules repository in the config file")
            raise typer.Exit(code=1)

        super().__init__(central_repo, "central_rules_repo")

    def get_resource_type(self) -> str:
        """Get the resource type name"""
        return "rule"

    def format_resource_display(self, resource: Dict[str, Any]) -> str:
        """Format the resource display"""
        dir_name = os.path.basename(resource["directory"])
        return f"{resource['rule_name']} (from: {dir_name})"

    def get_existing_resources(self) -> Dict[str, str]:
        """Get the rules already present in the central repository"""
        existing_rules = {}  # Stores a rule_name -> content mapping
        for filepath in glob.glob(
            os.path.join(self.repo_path, "**", "*.md"), recursive=True
        ):
            try:
                # Use the path relative to repo_path as the rule identifier
                rel_path = os.path.relpath(filepath, self.repo_path)
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if content:
                        existing_rules[rel_path] = content
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.rule_share_manager",
                    function="get_existing_resources",
                )
                pass
        return existing_rules

    def get_local_resources(self) -> List[Dict[str, Any]]:
        """Get local rules"""
        # Get the rules already present in the central repository
        existing_rules = self.get_existing_resources()

        # Get all rule directories
        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir, get_git_root

        git_root = get_git_root()
        rule_dirs = [
            os.path.join(git_root, ".haijunbot", "rules"),
        ] + get_rules_load_dirs()

        # Add the builtin directory (if it exists)
        builtin_dir = _get_builtin_dir()
        if builtin_dir is not None:
            builtin_rules_dir = builtin_dir / "rules"
            if builtin_rules_dir.exists() and builtin_rules_dir.is_dir():
                rule_dirs.append(str(builtin_rules_dir))

        # Collect all rule files (excluding the central repository directory and rules already present)
        rule_files = []
        seen_rule_names = set()  # Used for deduplication

        for directory in set(rule_dirs):
            # Skip the central repository directory
            if os.path.abspath(directory) == os.path.abspath(self.repo_path):
                continue

            if not os.path.isdir(directory):
                continue

            for filepath in glob.glob(
                os.path.join(directory, "**", "*.md"), recursive=True
            ):
                try:
                    # Use the path relative to directory as the rule identifier
                    rel_path = os.path.relpath(filepath, directory)

                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Determine whether it already exists in the central repository based on the content
                    is_duplicate = False
                    if rel_path in existing_rules:
                        # If the paths are the same, compare the content
                        if content.strip() == existing_rules[rel_path].strip():
                            is_duplicate = True

                    # Exclude rules already present in the central repository (based on content), as well as locally duplicated rules
                    if content and not is_duplicate and rel_path not in seen_rule_names:
                        rule_files.append(
                            {
                                "path": filepath,
                                "rule_name": rel_path,
                                "directory": directory,
                            }
                        )
                        seen_rule_names.add(rel_path)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_agent.rule_share_manager",
                        function="get_local_resources",
                    )
                    pass

        return rule_files

    def share_resources(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Share rules to the central repository"""
        # Confirm the operation
        share_list = ["\nThe following rules will be shared to the central repository:"]
        for rule in resources:
            share_list.append(f"- {rule['rule_name']}")
        joined_list = "\n".join(share_list)
        PrettyOutput.auto_print(f"ℹ️ {joined_list}")

        if not user_confirm("Confirm sharing these rules?"):
            return []

        # Copy the selected rules to the central repository
        copied_list = []
        for rule in resources:
            src_file = rule["path"]
            # Preserve the relative path structure
            dst_file = os.path.join(self.repo_path, rule["rule_name"])
            dst_dir = os.path.dirname(dst_file)

            # Create the target directory (if it does not exist)
            os.makedirs(dst_dir, exist_ok=True)

            shutil.copy2(src_file, dst_file)
            copied_list.append(f"Copied: {rule['rule_name']}")

        return copied_list

    def run(self) -> None:
        """Execute the rule sharing workflow"""
        try:
            # Update the central repository
            self.update_central_repo()

            # Get local resources
            local_resources = self.get_local_resources()
            if not local_resources:
                PrettyOutput.auto_print(
                    "⚠️ No new rule files found (all rules may already exist in the central repository)"
                )
                return

            # Select the resources to share
            selected_resources = self.select_resources(local_resources)
            if not selected_resources:
                return

            # Share the resources
            copied_list = self.share_resources(selected_resources)
            if copied_list:
                # Display all copy results at once
                joined_copied = "\n".join(copied_list)
                PrettyOutput.auto_print(f"✅ {joined_copied}")

                # Commit and push
                self.commit_and_push(len(selected_resources))

                PrettyOutput.auto_print("✅ Rules shared to the central repository successfully!")

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error while sharing rules: {str(e)}")
            raise typer.Exit(code=1)
