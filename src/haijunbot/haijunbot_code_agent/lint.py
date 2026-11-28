#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lint tool configuration module

Provides lint tool configuration and command generation functionality.
"""

import os
import shlex
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.config import get_lint_tools_config

# Mapping of lint tools to their auto-fix commands (lint tool name -> auto-fix command template)
# Used to suggest to the user the available auto-fix tools when lint warnings are found
LINT_AUTO_FIX_COMMANDS: Dict[str, List[str]] = {
    # Python
    "ruff": ["ruff check --fix {file_path}", "ruff format {file_path}"],
    "ty": [],  # ty has no auto-fix functionality
    "pylint": [],  # pylint has no auto-fix functionality
    "flake8": [],  # flake8 has no auto-fix functionality
    # JavaScript/TypeScript
    "eslint": ["eslint --fix {file_path}"],
    "prettier": ["prettier --write {file_path}"],
    # Rust
    "cargo": ["cargo clippy --fix --allow-dirty"],
    "clippy": ["cargo clippy --fix --allow-dirty"],
    # Go
    "go": ["go fmt {file_path}", "goimports -w {file_path}"],
    # C/C++
    "clang-tidy": ["clang-tidy --fix {file_path}"],
    # Shell
    "shellcheck": ["shfmt -w {file_path}"],
    # Ruby
    "rubocop": ["rubocop --auto-correct {file_path}"],
    # PHP
    "phpstan": [],  # phpstan has no auto-fix functionality
    # SQL
    "sqlfluff": ["sqlfluff fix {file_path}"],
    # Markdown/Documentation
    "markdownlint": ["markdownlint --fix {file_path}"],
    # CSS/SCSS/SASS/LESS
    "stylelint": ["stylelint --fix {file_path}"],
    # Swift
    "swiftlint": ["swiftlint --fix {file_path}"],
    # Kotlin
    "ktlint": ["ktlint -F {file_path}"],
}


# Lint tool command template mapping (file extension / file name -> list of command templates)
# Placeholder descriptions:
# - {file_path}: the full path of a single file
# - {file_name}: the file name (without path)
# - {config}: the config file path (optional)
LINT_COMMAND_TEMPLATES_BY_FILE: Dict[str, List[str]] = {
    # C/C++
    ".c": ["clang-tidy --checks=* {file_path}"],
    ".cpp": ["clang-tidy --checks=* {file_path}"],
    ".cc": ["clang-tidy --checks=* {file_path}"],
    ".cxx": ["clang-tidy --checks=* {file_path}"],
    ".h": ["clang-tidy --checks=* {file_path}"],
    ".hpp": ["clang-tidy --checks=* {file_path}"],
    ".hxx": ["clang-tidy --checks=* {file_path}"],
    ".inl": ["clang-tidy --checks=* {file_path}"],
    ".ipp": ["clang-tidy --checks=* {file_path}"],
    # Go
    ".go": ["go vet {file_path}"],
    # Python
    ".py": [
        "ruff check {file_path}",
        "ty check {file_path}",
    ],
    ".pyw": [
        "ruff check {file_path}",
        "ty check {file_path}",
    ],
    ".pyi": [
        "ruff check {file_path}",
        "ty check {file_path}",
    ],
    ".pyx": [
        "ruff check {file_path}",
        "ty check {file_path}",
    ],
    ".pxd": [
        "ruff check {file_path}",
        "ty check {file_path}",
    ],
    # Rust
    ".rs": ["cargo clippy --message-format=short"],
    ".rlib": ["cargo clippy --message-format=short"],
    # Java
    ".java": ["pmd check -d {file_path}"],
    ".class": ["pmd check -d {file_path}"],
    ".jar": ["pmd check -d {file_path}"],
    # JavaScript/TypeScript
    ".js": ["eslint {file_path}"],
    ".mjs": ["eslint {file_path}"],
    ".cjs": ["eslint {file_path}"],
    ".jsx": ["eslint {file_path}"],
    ".ts": [
        "eslint {file_path}",
        "tsc --noEmit {file_path}",
    ],
    ".tsx": [
        "eslint {file_path}",
        "tsc --noEmit {file_path}",
    ],
    ".cts": [
        "eslint {file_path}",
        "tsc --noEmit {file_path}",
    ],
    ".mts": [
        "eslint {file_path}",
        "tsc --noEmit {file_path}",
    ],
    # PHP
    ".php": ["phpstan analyse {file_path}"],
    ".phtml": ["phpstan analyse {file_path}"],
    ".php5": ["phpstan analyse {file_path}"],
    ".php7": ["phpstan analyse {file_path}"],
    ".phps": ["phpstan analyse {file_path}"],
    # Ruby
    ".rb": ["rubocop {file_path}"],
    ".rake": ["rubocop {file_path}"],
    ".gemspec": ["rubocop {file_path}"],
    # Swift
    ".swift": ["swiftlint lint {file_path}"],
    # Kotlin
    ".kt": ["ktlint {file_path}"],
    ".kts": ["ktlint {file_path}"],
    # C#
    ".cs": ["roslynator analyze {file_path}"],
    ".csx": ["roslynator analyze {file_path}"],
    # SQL
    ".sql": ["sqlfluff lint {file_path}"],
    # Shell/Bash
    ".sh": ["shellcheck {file_path}"],
    ".bash": ["shellcheck {file_path}"],
    # HTML/CSS
    ".html": ["htmlhint {file_path}"],
    ".htm": ["htmlhint {file_path}"],
    ".xhtml": ["htmlhint {file_path}"],
    ".css": ["stylelint {file_path}"],
    ".scss": ["stylelint {file_path}"],
    ".sass": ["stylelint {file_path}"],
    ".less": ["stylelint {file_path}"],
    # XML/JSON/YAML
    ".xml": ["xmllint --noout {file_path}"],
    ".xsd": ["xmllint --noout {file_path}"],
    ".dtd": ["xmllint --noout {file_path}"],
    ".tld": ["xmllint --noout {file_path}"],
    ".jsp": ["xmllint --noout {file_path}"],
    ".jspx": ["xmllint --noout {file_path}"],
    ".tag": ["xmllint --noout {file_path}"],
    ".tagx": ["xmllint --noout {file_path}"],
    ".json": ["jsonlint {file_path}"],
    ".jsonl": ["jsonlint {file_path}"],
    ".json5": ["jsonlint {file_path}"],
    ".yaml": ["yamllint {file_path}"],
    ".yml": ["yamllint {file_path}"],
    # Markdown/Documentation
    ".md": ["markdownlint {file_path}"],
    ".markdown": ["markdownlint {file_path}"],
    ".rst": ["rstcheck {file_path}"],
    ".adoc": ["asciidoctor-lint {file_path}"],
    # Extensionless files such as Docker/Terraform/Makefile
    "makefile": ["checkmake {file_path}"],
    "dockerfile": ["hadolint {file_path}"],
    "docker-compose.yml": ["hadolint {file_path}"],
    "docker-compose.yaml": ["hadolint {file_path}"],
    "jenkinsfile": ["jenkinsfile-linter {file_path}"],
    "build": ["buildifier {file_path}"],
    "workspace": ["buildifier {file_path}"],
    ".bashrc": ["shellcheck {file_path}"],
    ".bash_profile": ["shellcheck {file_path}"],
    ".zshrc": ["shellcheck {file_path}"],
    ".gitignore": ["git-lint {file_path}"],
    ".editorconfig": ["editorconfig-checker {file_path}"],
    ".eslintrc": ["eslint {file_path}"],
    ".prettierrc": ["prettier --check {file_path}"],
}


def _format_lint_command(
    template: str,
    file_path: str,
    project_root: Optional[str] = None,
) -> Optional[str]:
    """
    Format a lint command template (internal function)

    Args:
        template: the command template string
        file_path: the file path (relative or absolute)
        project_root: the project root directory (optional, used for resolving relative paths)

    Returns:
        The command string, or None if it cannot be generated
    """
    # Special handling: some tools do not need a file path (such as cargo clippy)
    if "{file_path}" not in template and "{file_name}" not in template:
        # No file path needed, return the template directly
        return template

    # If it is an absolute path, use it directly; otherwise convert it to an absolute path
    if os.path.isabs(file_path):
        abs_file_path = file_path
    elif project_root:
        abs_file_path = os.path.join(project_root, file_path)
    else:
        abs_file_path = os.path.abspath(file_path)

    # Prepare the placeholder replacement dictionary
    # Use shlex.quote to safely shell-escape the path, handling paths containing spaces
    placeholders = {
        "file_path": shlex.quote(abs_file_path),
        "file_name": shlex.quote(os.path.basename(abs_file_path)),
    }

    # If the template contains a {config} placeholder, it means a config file is needed
    # Config files should now be written directly into the template; automatic lookup is not supported
    if "{config}" in template:
        # If the template contains {config} but none was provided, return None
        # The user should specify the config file path directly in the template, or use another placeholder
        return None

    # Replace the placeholders
    try:
        command = template.format(**placeholders)
    except KeyError:
        # If the template contains an undefined placeholder, return None
        return None

    return command


def get_lint_commands_for_files(
    files: List[str], project_root: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Get the list of lint commands for multiple files

    Args:
        files: the list of file paths
        project_root: the project root directory (optional); if provided, loads project-level config

    Returns:
        A command list in the format [(file_path, command), ...]
    """
    # Merge the built-in default commands with the config.yaml configuration (config.yaml already contains global+project merged, with project overriding global)
    config = LINT_COMMAND_TEMPLATES_BY_FILE.copy()
    config.update(get_lint_tools_config())

    commands = []
    # Record tool templates that do not need a file path (such as cargo clippy) to avoid duplicate execution
    project_level_templates = set()

    for file_path in files:
        # Get the command template list directly from the file extension / file name
        filename = os.path.basename(file_path)
        filename_lower = filename.lower()

        # Try a full file name match first
        templates = config.get(filename_lower, [])

        # If the file name match fails, try the extension match
        if not templates:
            ext = os.path.splitext(filename)[1]
            if ext:
                templates = config.get(ext.lower(), [])

        for template in templates:
            # Check whether it is a project-level tool (does not need a file path)
            if "{file_path}" not in template and "{file_name}" not in template:
                # Project-level tool, executed only once per project
                if template not in project_level_templates:
                    project_level_templates.add(template)
                    command = _format_lint_command(template, file_path, project_root)
                    if command:
                        # Use the first file as the identifier
                        commands.append((file_path, command))
            else:
                # File-level tool, executed for every file
                command = _format_lint_command(template, file_path, project_root)
                if command:
                    commands.append((file_path, command))

    return commands


def group_commands_by_template(
    commands: List[Tuple[str, str]],
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Group commands by command template (identified by the first word of the command)

    Args:
        commands: a command list in the format [(file_path, command), ...]

    Returns:
        A dictionary in the format {template_key: [(file_path, command), ...]}
        template_key is the first word of the command
    """
    grouped: Dict[str, List[Tuple[str, str]]] = {}
    for file_path, command in commands:
        # Use the first word of the command as the grouping key
        template_key = command.split()[0] if command.split() else "unknown"
        if template_key not in grouped:
            grouped[template_key] = []
        grouped[template_key].append((file_path, command))
    return grouped
