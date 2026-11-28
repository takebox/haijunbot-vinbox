"""Rule sharing management module"""

import glob
import os

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
import shutil
from typing import Any
from typing import Dict
from typing import List
from typing import Set

import typer

from haijunbot.haijunbot_agent import user_confirm
from haijunbot.haijunbot_agent.share_manager import ShareManager
from haijunbot.haijunbot_utils.config import get_central_rules_repo
from haijunbot.haijunbot_utils.config import get_data_dir


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
        return f"{resource['rule_name']} ({resource['filename']})"

    def get_existing_resources(self) -> Set[str]:
        """Get the rule file names already present in the central repository"""
        existing_rules = set()
        # Check the files in the rules directory
        rules_dir = os.path.join(self.repo_path, "rules")
        if os.path.exists(rules_dir):
            for filepath in glob.glob(os.path.join(rules_dir, "*")):
                if os.path.isfile(filepath):
                    existing_rules.add(os.path.basename(filepath))
        # Check the files in the root directory (treated as rule files)
        for filepath in glob.glob(os.path.join(self.repo_path, "*")):
            if os.path.isfile(filepath) and not filepath.endswith(".yaml"):
                existing_rules.add(os.path.basename(filepath))
        return existing_rules

    def get_local_resources(self) -> List[Dict[str, Any]]:
        """Get local rules

        Note: only rules in the default rules directory (get_data_dir()/rules) can be shared;
        rules in the configured rules directory and the project rules directory cannot be shared.
        """
        # Get the rule file names already present in the central repository
        existing_rules = self.get_existing_resources()

        # Only get rules from the rules directory of the default data directory (the configured directory and project rules cannot be shared)
        local_rules_dir = os.path.join(get_data_dir(), "rules")
        if not os.path.exists(local_rules_dir):
            PrettyOutput.auto_print(f"⚠️ Local rules directory does not exist: {local_rules_dir}")
            return []

        # Collect the local rule files (excluding existing ones)
        rule_files = []
        for filepath in glob.glob(os.path.join(local_rules_dir, "*")):
            if not os.path.isfile(filepath):
                continue
            filename = os.path.basename(filepath)
            # Skip files that already exist
            if filename in existing_rules:
                continue

            # The rule name is the file name
            rule_name = filename
            rule_files.append(
                {
                    "path": filepath,
                    "filename": filename,
                    "rule_name": rule_name,
                }
            )

        return rule_files

    def share_resources(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Share rules to the central repository"""
        # Confirm the operation
        share_list = ["\nThe following rules will be shared to the central repository (note: files will be moved, not copied):"]
        for rule in resources:
            share_list.append(f"- {rule['rule_name']} ({rule['filename']})")
        joined_list = "\n".join(share_list)
        PrettyOutput.auto_print(f"⚠️ {joined_list}")

        if not user_confirm("Confirm moving these rules to the central repository? (the original files will be deleted)"):
            return []

        # Ensure the central repository has a rules directory
        rules_dir = os.path.join(self.repo_path, "rules")
        if not os.path.exists(rules_dir):
            os.makedirs(rules_dir, exist_ok=True)

        # Move the selected rules to the central repository
        moved_list = []
        for rule in resources:
            src_file = rule["path"]
            dst_file = os.path.join(rules_dir, rule["filename"])
            shutil.move(src_file, dst_file)  # Use move instead of copy
            moved_list.append(f"Moved: {rule['rule_name']}")

        return moved_list

    def run(self) -> None:
        """Execute the rule sharing process"""
        try:
            # Update the central repository
            self.update_central_repo()

            # Get local resources
            local_resources = self.get_local_resources()
            if not local_resources:
                PrettyOutput.auto_print(
                    "⚠️ No new rule files were found (all rules may already exist in the central repository)"
                )
                return

            # Select the resources to share
            selected_resources = self.select_resources(local_resources)
            if not selected_resources:
                return

            # Share the resources
            moved_list = self.share_resources(selected_resources)
            if moved_list:
                # Show all movement results at once
                joined_moved = "\n".join(moved_list)
                PrettyOutput.auto_print(f"✅ {joined_moved}")

                # Commit and push
                self.commit_and_push(len(selected_resources))

                PrettyOutput.auto_print("✅ Rules have been successfully shared to the central repository!")
                PrettyOutput.auto_print(
                    f"ℹ️ The original files have been moved from {os.path.join(get_data_dir(), 'rules')} to the central repository"
                )

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error sharing rules: {str(e)}")
            raise typer.Exit(code=1)
