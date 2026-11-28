"""Core functionality for rules index CLI.

This module provides functions to retrieve and format rules index data.
"""

import os

from haijunbot.haijunbot_agent.rules_manager import RulesManager
from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule_path
from haijunbot.haijunbot_utils.output import PrettyOutput


def get_rules_index() -> dict:
    """Get all available rules index.

    Returns:
        A dictionary containing all rules grouped by source, or empty dict if failed.
    """
    try:
        # Use the current working directory as the project root so project rules are identified correctly
        root_dir = os.getcwd()
        manager = RulesManager(root_dir=root_dir)
        all_rules = manager.get_all_available_rule_names()
        return all_rules
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Failed to get rules index: {e}")
        return {}


def get_rules_index_formatted(as_json: bool = False) -> str:
    """Get formatted rules index.

    Args:
        as_json: Whether to format as JSON.

    Returns:
        Formatted output string.
    """
    try:
        root_dir = os.getcwd()
        manager = RulesManager(root_dir=root_dir)
        result = manager._get_all_rules_index()
        return result if result else "❌ No rules found"
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Failed to get rules index: {e}")
        return "❌ Failed to get rules index"


def _extract_rule_description(rule_path: str) -> str:
    """Extract description from a rule file's YAML Front Matter.

    Args:
        rule_path: Absolute path to the rule file.

    Returns:
        Description string, or empty string if not found.
    """
    try:
        if not os.path.exists(rule_path):
            return ""
        with open(rule_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Extract description from YAML Front Matter
        if content.startswith("---"):
            lines = content.split("\n")
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    break
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip()
                    return description
        return ""
    except Exception:
        return ""


def format_rules_index(index: dict, as_json: bool = False) -> str:
    """Format the rules index for output.

    Args:
        index: The rules index dictionary (from get_rules_index).
        as_json: Whether to format as JSON.

    Returns:
        Formatted output string.
    """
    if not index:
        return "❌ No rules found"

    if as_json:
        import json

        return json.dumps(index, ensure_ascii=False, indent=2)

    # Format as Markdown output
    output_lines = ["# HaijunBot rules index\n"]

    # Built-in rules
    if index.get("builtin"):
        output_lines.append("## 📦 Built-in rules (builtin)\n")
        for rule_name in index["builtin"]:
            # Strip the builtin: prefix
            name = rule_name.split(":", 1)[1] if ":" in rule_name else rule_name
            # Get the built-in rule path
            rule_path = get_builtin_rule_path(name)
            description = _extract_rule_description(rule_path) if rule_path else ""
            if description:
                output_lines.append(f"- [{description}]({rule_path})")
            else:
                # Even without a description, show the path or name
                if rule_path:
                    output_lines.append(f"- {rule_path}")
                else:
                    # If getting the path fails, show the rule name
                    output_lines.append(f"- builtin:{name}")
        output_lines.append("")

    # File rules (project, global, central repository, etc.)
    if index.get("files"):
        output_lines.append("## 📁 Rule files (files)\n")
        # Group by source while storing the full path
        by_source: dict[str, list[tuple[str, str]]] = {}
        for rule_name in index["files"]:
            if ":" in rule_name:
                prefix = rule_name.split(":", 1)[0]
                name = rule_name.split(":", 1)[1]
            else:
                prefix = "unknown"
                name = rule_name

            source_labels = {
                "project": "Project",
                "global": "Global",
                "central": "Central Repository",
            }
            # configN prefix is uniformly categorized as "config directory"
            label = (
                "Config Directory"
                if prefix.startswith("config")
                else source_labels.get(prefix, prefix)
            )
            if label not in by_source:
                by_source[label] = []
            # Store the full path to extract the description
            by_source[label].append((rule_name, name))

        # Output by source
        for source, rules_list in sorted(by_source.items()):
            output_lines.append(f"### {source}\n")
            for full_name, rel_name in sorted(rules_list, key=lambda x: x[1]):
                # Determine the actual file path based on the prefix
                rule_path = ""
                if full_name.startswith("project:"):
                    rule_path = os.path.join(os.getcwd(), ".haijunbot", "rules", rel_name)
                elif full_name.startswith("global:"):
                    rule_path = os.path.join(
                        os.path.expanduser("~"), ".haijunbot", "rules", rel_name
                    )
                elif full_name.startswith("central:"):
                    # Central repository path, not handled for now
                    rule_path = ""
                else:
                    # Resolve configN prefix uniformly via RulesManager (to avoid index misalignment)
                    rule_path = RulesManager(root_dir=os.getcwd()).get_rule_file_path(
                        full_name
                    )

                description = _extract_rule_description(rule_path) if rule_path else ""
                if description:
                    output_lines.append(f"- [{description}]({rule_path})")
                else:
                    # Even without a description, show the absolute path
                    output_lines.append(f"- {rule_path}")
            output_lines.append("")

    # YAML rules
    if index.get("yaml"):
        output_lines.append("## 📝 YAML rules\n")
        # Group by source
        by_source_yaml: dict[str, list[str]] = {}
        for rule_name in index["yaml"]:
            if ":" in rule_name:
                prefix = rule_name.split(":", 1)[0]
                name = rule_name.split(":", 1)[1]
            else:
                prefix = "unknown"
                name = rule_name

            source_labels = {
                "central_yaml": "Central Repository",
                "project_yaml": "Project",
                "global_yaml": "Global",
            }
            label = source_labels.get(prefix, prefix)
            if label not in by_source_yaml:
                by_source_yaml[label] = []
            by_source_yaml[label].append(name)

        # Output by source
        for source, rules in sorted(by_source_yaml.items()):
            output_lines.append(f"### {source}\n")
            for rule in sorted(rules):
                output_lines.append(f"- `{rule}`")
            output_lines.append("")

    return "\n".join(output_lines)
