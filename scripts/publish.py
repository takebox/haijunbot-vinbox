#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to automatically update the version number and publish to PyPI
Usage:
    python scripts/publish.py [major|minor|patch]
"""

import re
import sys
import subprocess
from pathlib import Path
from typing import Tuple, List


def get_current_version() -> Tuple[int, int, int]:
    """Get the current version number"""
    init_file = Path("src/haijunbot/__init__.py")
    # Read the version number from __init__.py
    init_content = init_file.read_text()
    version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
    if not version_match:
        raise ValueError("Version not found in __init__.py")
    version_str = version_match.group(1)
    major, minor, patch = map(int, version_str.split("."))
    return major, minor, patch


def update_version(version_type: str) -> str:
    """Update the version number"""
    major, minor, patch = get_current_version()
    if version_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif version_type == "minor":
        minor += 1
        patch = 0
    elif version_type == "patch":
        patch += 1
    else:
        raise ValueError("Invalid version type. Use 'major', 'minor', or 'patch'")
    new_version = f"{major}.{minor}.{patch}"
    # Update the version number in the files
    files_to_update = {
        "src/haijunbot/__init__.py": (
            r'__version__\s*=\s*["\']([^"\']+)["\']',
            f'__version__ = "{new_version}"',
        ),
        "setup.py": (r'version\s*=\s*["\']([^"\']+)["\']', f'version="{new_version}"'),
        "pyproject.toml": (
            r'version\s*=\s*["\']([^"\']+)["\']',
            f'version = "{new_version}"',
        ),
        # Keep the browser extension version in sync with the main version (the extension is distributed via gateway download)
        "browser_extension/manifest.json": (
            r'"version"\s*:\s*"([^"]+)"',
            f'"version": "{new_version}"',
        ),
        # Keep the frontend version in sync with the main version (the frontend is distributed via the gateway)
        "src/haijunbot/haijunbot_service/frontend/package.json": (
            r'"version"\s*:\s*"([^"]+)"',
            f'"version": "{new_version}"',
        ),
    }
    for file_path, (pattern, replacement) in files_to_update.items():
        path = Path(file_path)
        if path.exists():
            content = path.read_text()
            new_content = re.sub(pattern, replacement, content)
            path.write_text(new_content)

    return new_version


def run_command(cmd: List[str], error_msg: str) -> None:
    """Run a command"""
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {error_msg}")
        print(f"❌ Stderr: {e.stderr}")
        sys.exit(1)


def run_command_ignore_errors(cmd: List[str], error_msg: str) -> bool:
    """Run a command, ignore errors and return False on failure"""
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: {error_msg}")
        print(f"⚠️  Stderr: {e.stderr}")
        return False


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ["major", "minor", "patch"]:
        print("ℹ️ Usage: python scripts/publish.py [major|minor|patch]")
        sys.exit(1)
    version_type = sys.argv[1]
    try:
        # Update the version number
        new_version = update_version(version_type)
        print(f"✅ Updated version to {new_version}")

        # Commit the version update
        print("📝 Committing version update...")
        run_command(["git", "add", "."], "Failed to stage files")
        run_command(
            [
                "git",
                "commit",
                "--author",
                "skyfire <haijunbot@outlook.co.id>",
                "-m",
                f"Bump version to {new_version}",
            ],
            "Failed to commit version update",
        )
        # Create tag
        print("🏷️ Creating git tag...")
        run_command(["git", "tag", f"v{new_version}"], "Failed to create tag")
        # Push to remote repositories
        print("🚀 Pushing to all remotes...")
        # Get all remotes
        remotes_result = subprocess.run(
            ["git", "remote"],
            capture_output=True,
            text=True,
            check=True,
        )
        remotes = remotes_result.stdout.strip().split("\n")

        success_count = 0
        for remote in remotes:
            if not remote:
                continue
            print(f"  Pushing to {remote}...")
            # Push main branch
            if run_command_ignore_errors(
                ["git", "push", remote, "main"], f"Failed to push main to {remote}"
            ):
                # Push tags
                if run_command_ignore_errors(
                    ["git", "push", remote, "--tags"],
                    f"Failed to push tags to {remote}",
                ):
                    success_count += 1

        if success_count > 0:
            print(
                f"✅ Successfully pushed to {success_count}/{len(remotes)} remotes. The GitHub Action will now handle publishing to PyPI."
            )
        else:
            print(
                "⚠️  Warning: Failed to push to any remote. Please check the errors above."
            )
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
