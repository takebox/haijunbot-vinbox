#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File-change post-processing tools configuration module

Provides file-change post-processing tool configuration and command generation (such as formatting, auto-fixing, etc.).
"""

import os
import shlex
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.config import get_after_change_tools_config

# File-change post-processing tool command template mapping (file extension/filename -> list of command templates)
# Placeholder description:
# - {file_path}: full path of a single file
# - {file_name}: filename (without path)
AFTER_CHANGE_COMMAND_TEMPLATES_BY_FILE: Dict[str, List[str]] = {
    # Python
    ".py": ["ruff format {file_path}"],
    ".pyw": ["ruff format {file_path}"],
    ".pyi": ["ruff format {file_path}"],
    ".pyx": ["ruff format {file_path}"],
    ".pxd": ["ruff format {file_path}"],
    # JavaScript/TypeScript
    ".js": ["prettier --write {file_path}"],
    ".mjs": ["prettier --write {file_path}"],
    ".cjs": ["prettier --write {file_path}"],
    ".jsx": ["prettier --write {file_path}"],
    ".ts": ["prettier --write {file_path}"],
    ".tsx": ["prettier --write {file_path}"],
    ".cts": ["prettier --write {file_path}"],
    ".mts": ["prettier --write {file_path}"],
    # Rust
    ".rs": ["rustfmt {file_path}"],
    # Go
    ".go": ["gofmt -w {file_path}"],
    # Java
    ".java": ["google-java-format -i {file_path}"],
    # C/C++
    ".c": ["clang-format -i {file_path}"],
    ".cpp": ["clang-format -i {file_path}"],
    ".cc": ["clang-format -i {file_path}"],
    ".cxx": ["clang-format -i {file_path}"],
    ".h": ["clang-format -i {file_path}"],
    ".hpp": ["clang-format -i {file_path}"],
    ".hxx": ["clang-format -i {file_path}"],
    ".inl": ["clang-format -i {file_path}"],
    ".ipp": ["clang-format -i {file_path}"],
    # HTML/CSS
    ".html": ["prettier --write {file_path}"],
    ".htm": ["prettier --write {file_path}"],
    ".xhtml": ["prettier --write {file_path}"],
    ".css": ["prettier --write {file_path}"],
    ".scss": ["prettier --write {file_path}"],
    ".sass": ["prettier --write {file_path}"],
    ".less": ["prettier --write {file_path}"],
    # JSON/YAML
    ".json": ["prettier --write {file_path}"],
    ".jsonl": ["prettier --write {file_path}"],
    ".json5": ["prettier --write {file_path}"],
    ".yaml": ["prettier --write {file_path}"],
    ".yml": ["prettier --write {file_path}"],
    # Markdown
    ".md": ["prettier --write {file_path}"],
    ".markdown": ["prettier --write {file_path}"],
    # SQL
    ".sql": ["sqlfluff format {file_path}"],
    # Shell/Bash
    ".sh": ["shfmt -w {file_path}"],
    ".bash": ["shfmt -w {file_path}"],
    # XML
    ".xml": [
        "xmllint --format {file_path} > {file_path}.tmp && mv {file_path}.tmp {file_path}"
    ],
    ".xsd": [
        "xmllint --format {file_path} > {file_path}.tmp && mv {file_path}.tmp {file_path}"
    ],
    ".dtd": [
        "xmllint --format {file_path} > {file_path}.tmp && mv {file_path}.tmp {file_path}"
    ],
}


def _format_after_change_command(
    template: str,
    file_path: str,
    project_root: Optional[str] = None,
) -> Optional[str]:
    """
    Format a command template (internal function)

    Args:
        template: command template string
        file_path: file path (relative or absolute)
        project_root: project root directory (optional, used to handle relative paths)

    Returns:
        The command string, or None if it cannot be generated
    """
    # If it is an absolute path, use it directly; otherwise convert to an absolute path
    if os.path.isabs(file_path):
        abs_file_path = file_path
    elif project_root:
        abs_file_path = os.path.join(project_root, file_path)
    else:
        abs_file_path = os.path.abspath(file_path)

    # Prepare the placeholder replacement dictionary
    placeholders = {
        "file_path": shlex.quote(abs_file_path),
        "file_name": shlex.quote(os.path.basename(abs_file_path)),
    }

    # Replace placeholders
    try:
        command = template.format(**placeholders)
    except KeyError:
        # If the template contains an undefined placeholder, return None
        return None

    return command


def get_after_change_commands_for_files(
    files: List[str], project_root: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Get the list of post-change processing commands for multiple files

    Args:
        files: list of file paths
        project_root: project root directory (optional), if provided loads project-level config

    Returns:
        A command list in the format [(file_path, command), ...]
    """
    # Merge built-in default commands with config.yaml configuration (config.yaml already includes global+project merge, project overrides global)
    config = AFTER_CHANGE_COMMAND_TEMPLATES_BY_FILE.copy()
    config.update(get_after_change_tools_config())

    commands = []

    for file_path in files:
        # Get the command template list directly from the file extension/filename
        filename = os.path.basename(file_path)
        filename_lower = filename.lower()

        # Try matching the full filename first
        templates = config.get(filename_lower, [])

        # If filename matching fails, try matching by extension
        if not templates:
            ext = os.path.splitext(filename)[1]
            if ext:
                templates = config.get(ext.lower(), [])

        for template in templates:
            command = _format_after_change_command(template, file_path, project_root)
            if command:
                commands.append((file_path, command))

    return commands
