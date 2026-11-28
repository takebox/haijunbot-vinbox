# -*- coding: utf-8 -*-
"""Tool sharing management module"""

import glob
import os
import shutil
from typing import Any
from typing import Dict
from typing import List
from typing import Set

import typer

from haijunbot.haijunbot_agent import user_confirm
from haijunbot.haijunbot_agent.share_manager import ShareManager
from haijunbot.haijunbot_utils.config import get_central_tool_repo
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.output import PrettyOutput


class ToolShareManager(ShareManager):
    """Tool sharing manager"""

    def __init__(self) -> None:
        central_repo = get_central_tool_repo()
        if not central_repo:
            PrettyOutput.auto_print("❌ Error: central tool repository (central_tool_repo) is not configured")
            PrettyOutput.auto_print("ℹ️ Please set the Git address of the central tool repository in the config file")
            raise typer.Exit(code=1)

        super().__init__(central_repo, "central_tool_repo")

    def get_resource_type(self) -> str:
        """Get the resource type name"""
        return "tool"

    def format_resource_display(self, resource: Dict[str, Any]) -> str:
        """Format the resource display"""
        return f"{resource['tool_name']} ({resource['filename']})"

    def get_existing_resources(self) -> Set[str]:
        """Get the tool file names already present in the central repository"""
        existing_tools = set()
        for filepath in glob.glob(os.path.join(self.repo_path, "*.py")):
            existing_tools.add(os.path.basename(filepath))
        return existing_tools

    def get_local_resources(self) -> List[Dict[str, Any]]:
        """Get local tools"""
        # Get the tool file names already present in the central repository
        existing_tools = self.get_existing_resources()

        # Only get tools from the tools directory of the data directory
        local_tools_dir = os.path.join(get_data_dir(), "tools")
        if not os.path.exists(local_tools_dir):
            PrettyOutput.auto_print(f"⚠️ Local tools directory does not exist: {local_tools_dir}")
            return []

        # Collect local tool files (excluding those already present)
        tool_files = []
        for filepath in glob.glob(os.path.join(local_tools_dir, "*.py")):
            filename = os.path.basename(filepath)
            # Skip __init__.py and files that already exist
            if filename == "__init__.py" or filename in existing_tools:
                continue

            # Try to get the tool name (via simple parsing)
            tool_name = filename[:-3]  # Remove the .py suffix
            tool_files.append(
                {
                    "path": filepath,
                    "filename": filename,
                    "tool_name": tool_name,
                }
            )

        return tool_files

    def share_resources(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Share tools to the central repository"""
        # Confirm the operation
        share_list = ["\nThe following tools will be shared to the central repository (note: files will be moved, not copied):"]
        for tool in resources:
            share_list.append(f"- {tool['tool_name']} ({tool['filename']})")
        joined_list = "\n".join(share_list)
        PrettyOutput.auto_print(f"⚠️ {joined_list}")

        if not user_confirm("Confirm moving these tools to the central repository? (the original files will be deleted)"):
            return []

        # Move the selected tools to the central repository
        moved_list = []
        for tool in resources:
            src_file = tool["path"]
            dst_file = os.path.join(self.repo_path, tool["filename"])
            shutil.move(src_file, dst_file)  # Use move instead of copy
            moved_list.append(f"Moved: {tool['tool_name']}")

        return moved_list

    def run(self) -> None:
        """Execute the tool sharing workflow"""
        try:
            # Update the central repository
            self.update_central_repo()

            # Get local resources
            local_resources = self.get_local_resources()
            if not local_resources:
                PrettyOutput.auto_print(
                    "⚠️ No new tool files found (all tools may already exist in the central repository)"
                )
                return

            # Select the resources to share
            selected_resources = self.select_resources(local_resources)
            if not selected_resources:
                return

            # Share the resources
            moved_list = self.share_resources(selected_resources)
            if moved_list:
                # Display all move results at once
                joined_moved = "\n".join(moved_list)
                PrettyOutput.auto_print(f"✅ {joined_moved}")

                # Commit and push
                self.commit_and_push(len(selected_resources))

                PrettyOutput.auto_print("✅ Tools shared to the central repository successfully!")
                PrettyOutput.auto_print(
                    f"ℹ️ The original files have been moved from {os.path.join(get_data_dir(), 'tools')} to the central repository"
                )

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error while sharing tools: {str(e)}")
            raise typer.Exit(code=1)
