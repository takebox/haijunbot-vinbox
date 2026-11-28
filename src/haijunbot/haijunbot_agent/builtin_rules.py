# -*- coding: utf-8 -*-
"""HaijunBot Agent builtin rules module

Provides excellent development practice rules such as TDD, code review, refactoring, etc.
Supports using jinja2 template syntax with built-in variables in rule files.
This module is available for all agents.
"""

import os
import re

from pathlib import Path

from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir, render_rule_template


# Builtin rules dictionary: rule name -> rule content
# This dictionary is dynamically populated at module load time via _load_builtin_rules()
BUILTIN_RULES: dict[str, str] = {}


def _load_rules_from_directory(directory: Path, base_dir: Path) -> None:
    """Load rule files from specified directory, supports jinja2 template rendering

    Args:
        directory: Directory containing rule files
        base_dir: Base directory (used for computing relative paths)
    """
    if not directory.exists():
        return

    for rule_file in directory.rglob("*.md"):
        # Compute relative path from base directory
        # E.g.: architecture_design/clean_code.md -> architecture_design/clean_code.md
        try:
            relative_path = rule_file.relative_to(base_dir)
        except ValueError:
            # If file is not under base directory, use filename
            rule_name = rule_file.name
        else:
            # Use relative path directly, keeping slash format
            rule_name = str(relative_path)

        try:
            with open(rule_file, "r", encoding="utf-8") as f:
                rule_content = f.read()

                # Strip YAML Front Matter header, consistent with file-based rules
                if rule_content.startswith("---"):
                    lines = rule_content.split("\n")
                    found_first = False
                    found_second = False
                    new_lines = []
                    for line in lines:
                        if not found_second:
                            if line.strip() == "---":
                                if not found_first:
                                    found_first = True
                                else:
                                    found_second = True
                            continue
                        new_lines.append(line)
                    rule_content = "\n".join(new_lines).strip()
                else:
                    rule_content = rule_content.strip()

                # Use the common rendering function
                rendered_content = render_rule_template(
                    rule_content, rule_file.parent.as_posix()
                )
                if rendered_content:
                    BUILTIN_RULES[rule_name] = rendered_content
        except Exception:
            # Ignore files that fail to load, do not affect other rules
            continue


def _load_builtin_rules() -> None:
    """Load all builtin rules"""
    # Use helper function to find builtin directory
    # Supports finding from both installed and source locations
    builtin_dir = _get_builtin_dir()
    if builtin_dir is None:
        # If builtin directory not found, return silently (may be dev environment or incomplete install)
        return

    # Base directory (used for computing relative paths)
    rules_base_dir = builtin_dir / "rules"

    # Load general rules (rules directory)
    _load_rules_from_directory(rules_base_dir, rules_base_dir)

    # Load testing rules (testing directory)
    _load_rules_from_directory(rules_base_dir / "testing", rules_base_dir)


# Automatically load all rules at module load time
_load_builtin_rules()


def get_builtin_rule(rule_name: str) -> str | None:
    """Get builtin rule

    Args:
        rule_name: Rule name (case insensitive)

    Returns:
        str: Rule content, or None if not found
    """
    return BUILTIN_RULES.get(rule_name.lower())


def list_builtin_rules() -> list[str]:
    """List all available builtin rule names

    Returns:
        list[str]: List of rule names
    """
    return list(BUILTIN_RULES.keys())


def list_builtin_rule_entries() -> list[str]:
    """List builtin rule entry names that can be 'auto-selected'.

    Consistent with file-based rule scanning: if a directory contains ``track.md`` (case insensitive),
    only that entry file is treated as an option without recursing into subdirectories; references/scripts and
    companion .md files for TRACK.md are treated as resources only, not participating in auto-selection
    (can still be loaded by path via load_rule).
    """
    builtin_dir = _get_builtin_dir()
    if builtin_dir is None:
        return []
    base_dir = builtin_dir / "rules"
    if not base_dir.exists():
        return []

    def _entry_md(path: Path) -> bool:
        # Only .md files with name + description front matter can be auto-selected as rules;
        # references/section docs and other companion files without descriptions can still be loaded by path via load_rule, but do not participate in auto-selection.
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return False
        if not text.startswith("---"):
            return False
        fm = re.search(r"^---\n(.*?)\n---", text, re.S)
        if not fm:
            return False
        head = fm.group(1)
        return bool(
            re.search(r"^name\s*:", head, re.M)
            and re.search(r"^description\s*:", head, re.M)
        )

    entries: list[str] = []
    for root, dirs, files in os.walk(base_dir, topdown=True):
        root_path = Path(root)
        track_file = next(
            (f for f in files if f.lower() == "track.md"), None
        )
        if track_file is not None:
            rel = (root_path / track_file).relative_to(base_dir).as_posix()
            if (rel in BUILTIN_RULES or rel.lower() in BUILTIN_RULES) and _entry_md(
                root_path / track_file
            ):
                entries.append(rel)
            dirs.clear()
            continue
        for filename in files:
            if filename.lower().endswith(".md"):
                rel = (root_path / filename).relative_to(base_dir).as_posix()
                if (rel in BUILTIN_RULES or rel.lower() in BUILTIN_RULES) and _entry_md(
                    root_path / filename
                ):
                    entries.append(rel)
    return sorted(set(entries))


def get_builtin_rule_path(rule_name: str) -> str | None:
    """Get the file path of a builtin rule

    Args:
        rule_name: Rule name (new format, e.g. architecture_design:clean_code.md)

    Returns:
        str | None: Absolute path of the rule file, or None if not found
    """
    builtin_dir = _get_builtin_dir()
    if builtin_dir is None:
        return None

    # Parse path from rule name (preserving original case)
    # architecture_design/clean_code.md -> architecture_design/clean_code.md
    path_parts = rule_name

    # Search in the general rules directory
    general_rules_dir = builtin_dir / "rules"
    rule_file = general_rules_dir / path_parts
    if rule_file.exists() and rule_file.is_file():
        return str(rule_file.absolute())

    # Not found
    return None
