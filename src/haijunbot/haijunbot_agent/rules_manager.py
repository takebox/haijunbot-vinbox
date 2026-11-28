"""CodeAgent rules management module"""

import os
import re
import subprocess
import threading
from pathlib import Path

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule
from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule_path
from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry
from haijunbot.haijunbot_utils.template_utils import render_rule_template
from haijunbot.haijunbot_utils.config import get_central_rules_repo
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import get_rules_load_dirs
from haijunbot.haijunbot_utils.decision import decide_choice
from haijunbot.haijunbot_utils.utils import daily_check_git_updates

# Upper limit of a single rule body injected into context: if exceeded, truncate and prompt to fetch the full text via load_rule.
# The complete rule content is still fully retained in _loaded_rules, for load_rule/load_all_rules etc. to read on demand.
_RULE_INJECT_LIMIT = 4000


def _limit_rule_body(rule_name: str, body: str) -> str:
    """Truncate an overly long rule body into a context-friendly summary, avoiding blowing up the window in one injection.

    Keep the leading key points and structure; when the full content is needed, the model can read the original with load_rule.
    """
    if len(body) <= _RULE_INJECT_LIMIT:
        return body
    head = body[:_RULE_INJECT_LIMIT]
    newline = head.rfind("\n")
    if newline > _RULE_INJECT_LIMIT * 0.7:
        head = body[:newline]
    return (
        head + f"\n\n[Note: rule {rule_name} is long, the above is a partial summary;"
        "before going into specific execution details, first load its full text with the `load_rule` tool]"
    )


# Preselect candidate limit: avoid stuffing all rule names+descriptions into the LLM when there are thousands of rules; keep only the most relevant Top-N
_RULE_PRESELECT_TOP_N = 50

# Preselect stop words (single chars/meaningless words, filtered after jieba tokenization)
_RULE_PRESELECT_STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "to",
    "of",
    "and",
    "or",
    "for",
    "with",
    "in",
}


def _preselect_rules(
    task_description: str,
    rule_names: List[str],
    desc_by_name: Dict[str, str],
    top_n: int = _RULE_PRESELECT_TOP_N,
) -> List[str]:
    """Coarsely screen rules by task-description keywords, keeping only the most relevant Top-N candidates.

    Use jieba tokenization to extract keywords from the task description, score substring matches against each rule's "name + description",
    and take top_n in descending score order. This coarse screen reduces the candidate volume fed to the LLM during the selection stage;
    the final relevance is still decided by the LLM from the prescreened candidates.

    Returns:
        The prescreened list of rule names. If prescreening is impossible (no keywords / no matches / exception),
        fall back to returning the full set, to avoid missing the correct rule.
    """
    try:
        import jieba

        # Extract task-description keywords (filter stop words and single chars)
        keywords = [
            w.strip()
            for w in jieba.cut(task_description)
            if len(w.strip()) > 2
            and w.strip().lower() not in _RULE_PRESELECT_STOP_WORDS
        ]
        if not keywords:
            return rule_names

        # Score keyword matches for each rule (name + description)
        scored: List[Tuple[int, str]] = []
        for rule_name in rule_names:
            description = desc_by_name.get(rule_name, "")
            preview_match = re.match(
                r"^\(Content preview:\s*(.*?)\)$", description, re.S
            )
            if preview_match:
                description = preview_match.group(1)
            haystack = (rule_name + " " + description).lower()
            score = sum(1 for kw in keywords if kw.lower() in haystack)
            scored.append((score, rule_name))

        # Sort by score descending, then keep only candidates with matches
        scored.sort(key=lambda x: x[0], reverse=True)
        matched = [rule_name for score, rule_name in scored if score > 0]
        if not matched:
            return rule_names  # No matches at all, fall back to the full set

        # Take Top-N (matched is already sorted by score descending)
        return matched[:top_n]
    except Exception:
        return rule_names  # On exception fall back to the full set, ensuring existing behavior is unchanged


class RulesManager:
    """Rules manager, responsible for loading and managing various rules"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        # Initialize the rule directory list
        self._init_rules_dirs()
        # Track loaded rule names
        self.loaded_rules: Set[str] = set()

        # Private attributes: state management
        self._loaded_rules: Dict[
            str, str
        ] = {}  # {rule_name: rule_content} - cache of loaded rule contents
        self._merged_rules: str = ""  # merged rule string (loaded rule contents)

        # Automatically load the project .haijunbot/rule.md file (project overview)
        self._load_project_rule_file()
        # Register as the global rule revoker (reversible effect), for PluginRegistry.revoke_plugin to call
        PluginRegistry.instance().set_rules_revoker(self.unregister_rules_by_plugin)

    def _load_project_rule_file(self) -> None:
        """Automatically load project-level overview rules (project overview)

        Load in order:
        1. `.haijunbot/rules/rule.md` (project overview, highest priority)
        2. Repository root `AGENTS.md` (otherwise `HAIJUN.md`, common community convention, as a supplementary source)

        When both exist they do not conflict; they are merged and injected.
        """
        # Use the load_rule method to load, consistent with other rules
        self.load_rule("project:rule")
        # For community-convention compatibility: read repository root AGENTS.md / HAIJUN.md, as a project-overview supplement
        self.load_rule("project:agents")

    def _read_project_agents_file(self) -> Optional[str]:
        """Read repository root AGENTS.md (otherwise HAIJUN.md) as a project-overview supplement.

        Priority: AGENTS.md > HAIJUN.md. Content is truncated by a budget of 80% of the model's max input tokens,
        to avoid a huge file blowing up the context window in one injection.

        Returns:
            The processed content string, or None if the file does not exist or is empty.
        """
        for filename in ("AGENTS.md", "HAIJUN.md"):
            file_path = os.path.join(self.root_dir, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if not content:
                    return None
                # Token budget truncation: budget = 80% of the model's max input tokens
                try:
                    from haijunbot.haijunbot_utils.config import get_max_input_token_count
                    from haijunbot.haijunbot_utils.embedding import get_context_token_count

                    budget = int(get_max_input_token_count() * 0.8)
                    if get_context_token_count(content) > budget:
                        # Truncate to the nearest newline within budget, keeping the leading key points
                        head = content[: budget * 4]
                        newline = head.rfind("\n")
                        if newline > budget * 2:
                            head = content[:newline]
                        content = (
                            head
                            + f"\n\n[Note: {filename} content is long, truncated by token budget;"
                            " full content can be read with the `read_code` tool]"
                        )
                except Exception:
                    # Ignore truncation failures, keep the full content
                    pass
                return content
            except Exception:
                # Ignore read failures, do not affect the main flow
                return None
        return None

    def _add_path_comment(self, rule_name: str, rule_content: str) -> str:
        """Add a path comment before the rule content

        Args:
            rule_name: rule name
            rule_content: rule content

        Returns:
            str: the rule content with the path comment added
        """
        if not rule_content:
            return rule_content

        rule_file_path = self.get_rule_file_path(rule_name)
        if rule_file_path and rule_file_path != "--":
            path_comment = f"<!-- Rule file path: {rule_file_path} -->\n"
            return path_comment + rule_content
        return rule_content

    def _init_rules_dirs(self) -> None:
        """Initialize the rule directory list, including configured directories and the central repo"""
        # Base directory: the rules directory under the global data directory
        self.rules_dirs: List[str] = [os.path.join(get_data_dir(), "rules")]

        # Add the configured rule load directories
        self.rules_dirs.extend(get_rules_load_dirs())

        # Central rules repo path (stored separately, highest priority)
        self.central_repo_path: Optional[str] = None
        central_repo = get_central_rules_repo()
        if central_repo:
            # Support a local directory path or a Git repository URL
            expanded = os.path.expanduser(os.path.expandvars(central_repo))
            if os.path.isdir(expanded):
                # Use the local directory directly (supports a subdirectory of a Git repository)
                self.central_repo_path = expanded
            else:
                # The central rules repo is stored at a specific location under the data directory
                self.central_repo_path = os.path.join(
                    get_data_dir(), "central_rules_repo"
                )

                # Ensure the central rules repo is cloned/updated
                if not os.path.exists(self.central_repo_path):
                    try:
                        PrettyOutput.auto_print(
                            f"ℹ️ Cloning central rules repo: {central_repo}"
                        )
                        subprocess.run(
                            ["git", "clone", central_repo, self.central_repo_path],
                            check=True,
                        )
                    except Exception as e:
                        PrettyOutput.auto_print(f"❌ Failed to clone central rules repo: {str(e)}")

        # Run the daily update check (in a background thread, to avoid blocking)
        all_dirs_for_update = self.rules_dirs.copy()
        if self.central_repo_path:
            all_dirs_for_update.append(self.central_repo_path)

        def check_rules_updates() -> None:
            try:
                daily_check_git_updates(all_dirs_for_update, "rules")
            except Exception:
                # Fail silently, do not affect normal use
                pass

        threading.Thread(target=check_rules_updates, daemon=True).start()

    def _read_rule_from_dir(self, rules_dir: str, rule_name: str) -> Optional[str]:
        """Read a rule file with the specified name from the rules directory

        Args:
            rules_dir: the rules directory path
            rule_name: rule name (supports relative paths, e.g. deployment/version_release.md)

        Returns:
            str: the rule content, or None if not found
        """
        try:
            # Only files with the .md suffix are supported
            if not rule_name.endswith(".md"):
                rule_name = rule_name + ".md"
            # Support relative paths (e.g. deployment/version_release.md)
            rule_file_path = os.path.join(rules_dir, rule_name)
            if os.path.exists(rule_file_path) and os.path.isfile(rule_file_path):
                with open(rule_file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                # Strip the YAML Front Matter header
                if content.startswith("---"):
                    lines = content.split("\n")
                    found_first = False
                    found_second = False
                    new_lines = []
                    for line in lines:
                        if not found_second:
                            if line.strip() == "---":
                                if not found_first:
                                    # Found the first ---
                                    found_first = True
                                else:
                                    # Found the second ---, start collecting content
                                    found_second = True
                            continue
                        new_lines.append(line)
                    content = "\n".join(new_lines).strip()
                else:
                    content = content.strip()

                # Render the rule template with jinja2
                if content:
                    # Use the directory of the rule file as the context for template rendering
                    content = render_rule_template(
                        content, os.path.dirname(rule_file_path)
                    )
                return content if content else None
        except Exception:
            # Ignore rule read failures, do not affect the main flow
            pass
        return None

    def _get_all_rules_index(self) -> Optional[str]:
        """Get the index of all available rules

        Scan all rule sources (builtin, project, global, central repo, etc.),
        and generate index content containing descriptions and paths.

        Returns:
            str: the index content, or None if no rules are found
        """
        try:
            # Get all available rules
            all_rules = self.get_all_available_rule_names()

            if not all_rules:
                return None

            # Call the internal method to format the output
            return self._format_rules_index(all_rules)

        except Exception as e:
            # Ignore index generation failures, do not affect the main flow
            PrettyOutput.auto_print(f"⚠️ Failed to generate rules index: {e}")
            return None

    def _format_rules_index(self, index: dict) -> str:
        """Format the rules index into Markdown output

        Args:
            index: the rules index dict (from get_all_available_rule_names)

        Returns:
            the formatted Markdown string
        """

        if not index:
            return "❌ No rules found"

        # Format as Markdown output
        output_lines = ["# HaijunBot Rules Index\n"]

        # Builtin rules
        if index.get("builtin"):
            output_lines.append("## 📦 Builtin Rules (builtin)\n")
            for rule_name in index["builtin"]:
                # Strip the builtin: prefix
                name = rule_name.split(":", 1)[1] if ":" in rule_name else rule_name
                # Get the builtin rule path
                rule_path = get_builtin_rule_path(name)
                description = (
                    self._extract_rule_description(rule_path) if rule_path else ""
                )
                if description:
                    output_lines.append(f"- [{description}]({rule_path})")
            output_lines.append("")

        # File rules (project, global, central repo, etc.)
        if index.get("files"):
            output_lines.append("## 📁 Rule Files (files)\n")
            # Group by source
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
                    "central": "Central",
                }
                # configN prefixes are uniformly grouped as "config directory"
                label = (
                    "Config Directory"
                    if prefix.startswith("config")
                    else source_labels.get(prefix, prefix)
                )
                if label not in by_source:
                    by_source[label] = []
                by_source[label].append((rule_name, name))

            # Output by source
            for source, rules_list in sorted(by_source.items()):
                output_lines.append(f"### {source}\n")
                for full_name, rel_name in sorted(rules_list, key=lambda x: x[1]):
                    # Determine the actual file path based on the prefix
                    rule_path = ""
                    if full_name.startswith("project:"):
                        rule_path = os.path.join(
                            self.root_dir, ".haijunbot", "rules", rel_name
                        )
                    elif full_name.startswith("global:"):
                        rule_path = os.path.join(get_data_dir(), "rules", rel_name)
                    elif full_name.startswith("central:") and self.central_repo_path:
                        rule_path = os.path.join(
                            self.central_repo_path, "rules", rel_name
                        )
                    else:
                        # configN prefixes are uniformly resolved with get_rule_file_path (to avoid index misalignment)
                        rule_path = self.get_rule_file_path(full_name)

                    description = (
                        self._extract_rule_description(rule_path) if rule_path else ""
                    )
                    if description:
                        output_lines.append(f"- [{description}]({rule_path})")
                output_lines.append("")

        return "\n".join(output_lines)

    def _read_rule_head(self, rule_path: str, max_bytes: int = 4096) -> str:
        """Read only the head of a rule file (first max_bytes bytes), and extract the description

        Used for BM25 coarse screening, to avoid reading the full file content.

        Args:
            rule_path: the absolute path of the rule file
            max_bytes: the max number of bytes to read, default 4096

        Returns:
            the description string, or an empty string if not found
        """
        try:
            if not os.path.exists(rule_path):
                return ""
            with open(rule_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            # Extract the description from the YAML Front Matter
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

    def _extract_rule_description(self, rule_path: str) -> str:
        """Extract the description from a rule file

        Args:
            rule_path: the absolute path of the rule file

        Returns:
            the description string, or an empty string if not found
        """
        try:
            if not os.path.exists(rule_path):
                return ""
            with open(rule_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Extract the description from the YAML Front Matter
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

    def _get_builtin_rules_index(self) -> Optional[str]:
        """Automatically generate the index from rule files (rule name: description)

        Scan the builtin/rules/ directory, and extract the description field from
        the YAML Front Matter header of each .md file, generating the index content.

        Returns:
            str: the index content, or None if no rules are found
        """
        try:
            from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

            # Get the builtin directory path
            builtin_dir = _get_builtin_dir()
            if builtin_dir is None:
                return None

            builtin_rules_dir = builtin_dir / "rules"
            if not builtin_rules_dir.exists() or not builtin_rules_dir.is_dir():
                return None

            # Scan all .md files
            index_lines = []
            for root, dirs, files in os.walk(builtin_rules_dir):
                for filename in files:
                    if not filename.endswith(".md"):
                        continue

                    file_path = os.path.join(root, filename)

                    try:
                        with open(
                            file_path, "r", encoding="utf-8", errors="replace"
                        ) as f:
                            content = f.read()

                        # Extract the description from the YAML Front Matter
                        description = None
                        if content.startswith("---"):
                            lines = content.split("\n")
                            for i, line in enumerate(lines[1:], 1):
                                if line.strip() == "---":
                                    break
                                if line.startswith("description:"):
                                    description = line.split(":", 1)[1].strip()
                                    break

                        if not description:
                            # If there is no description, skip this rule
                            continue

                        # Use the actual absolute path
                        abs_path = os.path.abspath(file_path)

                        # Format: - [description](absolute_path)
                        index_lines.append(f"- [{description}]({abs_path})")
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_agent.rules_manager",
                            function="_get_builtin_rules_index",
                        )
                        continue

            if not index_lines:
                return None

            # Add the title and category
            index_content = "# HaijunBot Builtin Rules List\n\n"
            index_content += "\n".join(index_lines)

            return index_content

        except Exception as e:
            # Ignore index generation failures, do not affect the main flow
            PrettyOutput.auto_print(f"⚠️ Failed to generate rules index: {e}")
            return None

    def _get_rule_from_builtin_index(self, rule_name: str) -> Optional[str]:
        """Find and load a rule with the specified name from the builtin/rules/ directory

        Supports two lookup methods:
        1. Direct path: e.g. deployment/version_release.md
        2. Short name: e.g. solid, will search all rule file names for a match

        Args:
            rule_name: rule name (relative path or short name)

        Returns:
            str: the rule content, or None if not found
        """
        try:
            from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

            # Get the builtin directory path
            builtin_dir = _get_builtin_dir()
            if builtin_dir is None:
                return None

            builtin_rules_dir = builtin_dir / "rules"
            if not builtin_rules_dir.exists() or not builtin_rules_dir.is_dir():
                return None

            # Construct the rule file path
            if not rule_name.endswith(".md"):
                rule_name = rule_name + ".md"
            rule_file_path = builtin_rules_dir / rule_name

            # Check whether the rule file exists (supports a direct path)
            if not rule_file_path.exists() or not rule_file_path.is_file():
                # If the direct path does not exist, try searching for a filename match
                # Strip the .md suffix for matching
                search_name = rule_name.replace(".md", "")
                for root, dirs, files in os.walk(builtin_rules_dir):
                    for filename in files:
                        if not filename.endswith(".md"):
                            continue
                        # Check whether the filename matches (supports short names)
                        file_stem = os.path.splitext(filename)[0]
                        if search_name.lower() in file_stem.lower():
                            rule_file_path = Path(root) / filename
                            break
                    else:
                        continue
                    break
                else:
                    return None

            if not rule_file_path.exists() or not rule_file_path.is_file():
                return None

            # Read the rule file content
            with open(rule_file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Strip the YAML Front Matter header
            if content.startswith("---"):
                lines = content.split("\n")
                found_first = False
                found_second = False
                new_lines = []
                for line in lines:
                    if not found_second:
                        if line.strip() == "---":
                            if not found_first:
                                # Found the first ---
                                found_first = True
                            else:
                                # Found the second ---, start collecting content
                                found_second = True
                        continue
                    new_lines.append(line)
                content = "\n".join(new_lines).strip()
            else:
                content = content.strip()

            # Render the rule template with jinja2
            if content:
                content = render_rule_template(content, str(rule_file_path.parent))

            return content if content else None

        except Exception as e:
            # Ignore read failures, do not affect the main flow
            PrettyOutput.auto_print(f"⚠️ Failed to load rule from rules directory: {e}")
            return None

    def _get_all_rules_dirs(self) -> List[str]:
        """Get all rule directories (including the project directory and configured directories)

        Returns:
            List[str]: the rule directory list, sorted by priority (central repo > project > configured directories)
        """
        all_dirs = []
        # Priority 1: central rules repo (if a rule name collides, the central repo takes precedence)
        if (
            self.central_repo_path
            and os.path.exists(self.central_repo_path)
            and os.path.isdir(self.central_repo_path)
        ):
            # Check whether the central repo has a rules subdirectory
            central_rules_dir = os.path.join(self.central_repo_path, "rules")
            if os.path.exists(central_rules_dir) and os.path.isdir(central_rules_dir):
                all_dirs.append(central_rules_dir)
            else:
                # If there is no rules subdirectory, use the central repo root directory directly
                all_dirs.append(self.central_repo_path)
        # Priority 2: project rules directory
        project_rules_dir = os.path.join(self.root_dir, ".haijunbot", "rules")
        if os.path.exists(project_rules_dir) and os.path.isdir(project_rules_dir):
            all_dirs.append(project_rules_dir)
        # Priority 3-N: configured rule directories (excluding the central repo)
        all_dirs.extend(self.rules_dirs)
        return all_dirs

    def get_named_rule(self, rule_name: str) -> Optional[str]:
        """Get a rule with the specified name from the rules directory

        Rule name format: prefix:rule_name
        Prefix description:
        - builtin: - builtin rule directory (haijunbot source/builtin/rules)
        - project: - project .haijunbot/rules directory files
        - global: - global ~/.haijunbot/rules directory files
        - central: - central rules repo files
        - config1:, config2: - configured rule directory files
        - no prefix - builtin/rules/rule.md index or builtin rules

        Args:
            rule_name: rule name (may contain a prefix)

        Returns:
            str: the rule content, or None if not found
        """
        try:
            # Parse the prefix
            if ":" in rule_name:
                prefix, actual_name = rule_name.split(":", 1)
                if not actual_name:
                    return None

                # Handle the builtin prefix
                if prefix == "builtin":
                    try:
                        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

                        builtin_dir = _get_builtin_dir()
                        if builtin_dir is not None:
                            builtin_rules_dir = builtin_dir / "rules"
                            if (
                                builtin_rules_dir.exists()
                                and builtin_rules_dir.is_dir()
                            ):
                                rule_content = self._read_rule_from_dir(
                                    str(builtin_rules_dir), actual_name
                                )
                                if rule_content:
                                    return self._add_path_comment(
                                        rule_name, rule_content
                                    )
                                return None
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_agent.rules_manager",
                            function="get_named_rule",
                        )
                        pass
                    return None

                # Handle the project prefix
                if prefix == "project":
                    # Special rule: project:agents reads repository root AGENTS.md/HAIJUN.md
                    if actual_name == "agents":
                        agents_content = self._read_project_agents_file()
                        if agents_content:
                            return self._add_path_comment(rule_name, agents_content)
                        return None
                    project_rules_dir = os.path.join(self.root_dir, ".haijunbot", "rules")
                    if os.path.exists(project_rules_dir) and os.path.isdir(
                        project_rules_dir
                    ):
                        rule_content = self._read_rule_from_dir(
                            project_rules_dir, actual_name
                        )
                        if rule_content:
                            return self._add_path_comment(rule_name, rule_content)
                    return None

                # Handle the global prefix
                if prefix == "global":
                    global_rules_dir = os.path.join(get_data_dir(), "rules")
                    if os.path.exists(global_rules_dir) and os.path.isdir(
                        global_rules_dir
                    ):
                        rule_content = self._read_rule_from_dir(
                            global_rules_dir, actual_name
                        )
                        if rule_content:
                            return self._add_path_comment(rule_name, rule_content)
                    return None

                # Handle the central and config prefixes
                if prefix == "central" or prefix.startswith("config"):
                    all_rules_dirs = self._get_all_rules_dirs()
                    target_idx = -1
                    if prefix == "central" and len(all_rules_dirs) > 0:
                        target_idx = 0
                    elif prefix.startswith("config"):
                        try:
                            config_num = int(prefix[6:])
                            # configN corresponds to rules_dirs[N] (N>=1, rules_dirs[0] is the global directory)
                            if 1 <= config_num < len(self.rules_dirs):
                                target_idx = (
                                    len(all_rules_dirs) - len(self.rules_dirs)
                                ) + config_num
                        except ValueError:
                            pass

                    if 0 <= target_idx < len(all_rules_dirs):
                        rules_dir = all_rules_dirs[target_idx]
                        if os.path.exists(rules_dir) and os.path.isdir(rules_dir):
                            rule_content = self._read_rule_from_dir(
                                rules_dir, actual_name
                            )
                            if rule_content:
                                return self._add_path_comment(rule_name, rule_content)
                    return None

                # Unknown prefix
                return None

            # No prefix: look up by priority (rule.md index > builtin rules)
            # Priority 1: look up from the rule.md index file
            indexed_rule = self._get_rule_from_builtin_index(rule_name)
            if indexed_rule:
                return self._add_path_comment(rule_name, indexed_rule)

            # Priority 2: look up from builtin rules
            builtin_rule = get_builtin_rule(rule_name)
            if builtin_rule:
                return self._add_path_comment(rule_name, builtin_rule)

            return None
        except Exception as e:
            # Ignore rule read failures, do not affect the main flow
            PrettyOutput.auto_print(f"⚠️ Failed to read rule: {e}")
            return None

    def get_all_available_rule_names(self) -> dict[str, List[str]]:
        """Get all available rule names, categorized by source

        Returns:
            dict[str, List[str]]: a dict of rule names categorized by source
                - "builtin": builtin rule list
                - "files": file rule list in rule directories (with source prefix)
        """
        from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rule_entries

        # Auto-selection candidates only take "entry" rules (TRACK.md / top-level .md); companion docs are not independent selectable rules
        result = {
            "builtin": [f"builtin:{rule}" for rule in list_builtin_rule_entries()],
            "files": [],
        }

        # Collect file rules in rule directories (supports recursive traversal of subdirectories)
        all_rules_dirs = self._get_all_rules_dirs()
        for idx, rules_dir in enumerate(all_rules_dirs):
            if os.path.exists(rules_dir) and os.path.isdir(rules_dir):
                # Determine the source prefix (dynamically based on the actual source)
                # Check whether it is the central rules repo
                is_central = False
                if self.central_repo_path:
                    central_rules_dir = os.path.join(self.central_repo_path, "rules")
                    if (
                        rules_dir == central_rules_dir
                        or rules_dir == self.central_repo_path
                    ):
                        is_central = True

                # Check whether it is the project rules directory
                project_rules_dir = os.path.join(self.root_dir, ".haijunbot", "rules")
                is_project = rules_dir == project_rules_dir

                # Assign the prefix based on the actual source
                global_rules_dir = os.path.join(get_data_dir(), "rules")

                if is_central:
                    prefix = "central:"
                elif is_project:
                    prefix = "project:"
                elif rules_dir == global_rules_dir:
                    # Global rules directory
                    prefix = "global:"
                else:
                    # Configured rule directory: numbered by the actual index in rules_dirs
                    # (rules_dirs[0] is the global directory with the global: prefix, so config starts from 1)
                    try:
                        config_num = self.rules_dirs.index(rules_dir)
                    except ValueError:
                        config_num = -1
                    prefix = f"config{config_num}:" if config_num >= 1 else "config0:"

                try:
                    for root, dirs, files in os.walk(rules_dir, topdown=True):
                        # If the current directory contains track.md (case-insensitive), do not traverse deeper
                        if any(
                            f.lower() == "track.md"
                            for f in os.listdir(root)
                            if os.path.isfile(os.path.join(root, f))
                        ):
                            dirs.clear()
                        for filename in files:
                            if filename.endswith(".md"):
                                file_path = os.path.join(root, filename)
                                if os.path.isfile(file_path):
                                    # Compute the path relative to the rule directory as the rule name
                                    rel_path = os.path.relpath(file_path, rules_dir)
                                    # Rule name carries the source prefix (e.g. project:deployment/version_release.md)
                                    prefixed_name = prefix + rel_path
                                    result["files"].append(prefixed_name)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_agent.rules_manager",
                        function="get_all_available_rule_names",
                    )
                    continue

        return result

    def load_all_rules(self, rule_names: Optional[str] = None) -> Tuple[str, Set[str]]:
        """Load all rules and merge

        Backward-compatible method: internally uses the new state-management mechanism

        Args:
            rule_names: a list of rule names (comma-separated)

        Returns:
            (merged_rules, loaded_rule_names): the merged rule string and the list of loaded rule names
        """
        loaded_rule_names: Set[str] = set()

        # If rule_names is specified, load these rules
        if rule_names:
            rule_list = [name.strip() for name in rule_names.split(",") if name.strip()]
            for rule_name in rule_list:
                if self.load_rule(rule_name):
                    loaded_rule_names.add(rule_name)

        # Get the merged rule content
        merged_rules = self.get_loaded_rules_content()

        if merged_rules:
            return merged_rules, loaded_rule_names
        return "", set()

    def load_rule(self, name: str) -> bool:
        """Load a rule with the specified name

        Args:
            name: rule name

        Returns:
            bool: whether it was loaded successfully
        """
        # If the rule is already loaded, return True directly
        if name in self.loaded_rules:
            return True

        # Try to get the rule content
        rule_content = self.get_named_rule(name)
        if rule_content is None:
            return False

        # Load the rule into the cache
        self._loaded_rules[name] = rule_content
        # Mark the rule as loaded
        self.loaded_rules.add(name)
        # Re-merge the loaded rules
        self._merge_loaded_rules()

        # Reversible-effect registration: if the rule comes from a plugin directory, register it with PluginRegistry,
        # so it can be precisely revoked when the plugin is uninstalled.
        plugin_name = self._infer_source_plugin(self.get_rule_file_path(name))
        if plugin_name:
            PluginRegistry.instance().register_rule(plugin_name, name)

        return True

    @staticmethod
    def _infer_source_plugin(file_path: str) -> Optional[str]:
        """Infer the source plugin name from the rule file path (reversible-effect source identification).

        When the path looks like <...>/plugins/<plugin_name>/rules/xxx.md, return the plugin name;
        otherwise return None (meaning a rule not from a plugin).
        """
        try:
            p = Path(file_path)
            parts = p.parts
            for i, part in enumerate(parts):
                if part == "plugins" and i + 1 < len(parts):
                    return parts[i + 1]
        except Exception:
            pass
        return None

    def unregister_rules_by_plugin(self, plugin_name: str) -> int:
        """Revoke all rules registered by the specified plugin (reversible effect).

        Read the rule names registered by this plugin from PluginRegistry and unload them one by one,
        while also clearing this plugin's registration in PluginRegistry.

        Args:
            plugin_name: plugin name

        Returns:
            int: the number of rules revoked
        """
        registry = PluginRegistry.instance()
        rule_names = registry.get_plugin_rules(plugin_name)
        count = 0
        for name in rule_names:
            if self.unload_rule(name):
                count += 1
        # Only clear this plugin's rule registration in PluginRegistry (does not affect tool registration)
        registry.clear_rules(plugin_name)
        return count

    def unload_rule(self, name: str) -> bool:
        """Unload a rule with the specified name

        Args:
            name: rule name

        Returns:
            bool: whether it was unloaded successfully
        """
        # If the rule is not loaded, return False
        if name not in self.loaded_rules:
            return False

        # Unload the rule
        self.loaded_rules.remove(name)
        # Also remove it from the rule content cache
        if name in self._loaded_rules:
            del self._loaded_rules[name]
        # Re-merge the loaded rules
        self._merge_loaded_rules()

        return True

    def get_loaded_rules_content(self) -> str:
        """Get the merged content of all loaded rules

        Returns:
            str: the merged rule content
        """
        return self._merged_rules

    def get_injectable_rules_content(self) -> str:
        """Return the rule content used for injection into the prompt.

        Strategy (rules loaded automatically/force-triggered):
        - With a description: only inject the description + suggestion; the body does not enter the context, and the model fetches the full text with load_rule on demand;
        - Without a description: inject the body (when a single one exceeds _RULE_INJECT_LIMIT, truncate to a summary).

        Rules explicitly specified (@rule:xxx) do not use this method; the caller fetches the full body directly.
        Scenarios such as API display still use the full content from get_loaded_rules_content.
        """
        parts = []
        for rule_name in sorted(self.loaded_rules):
            body = self._loaded_rules.get(rule_name)
            if body is None:
                continue
            rule_path = self.get_rule_file_path(rule_name)
            description = ""
            if rule_path and rule_path != "--":
                description = self._extract_rule_description(rule_path) or ""
            if description:
                parts.append(
                    f"**Rule description**: {description}\n\n"
                    f"[Note: rule {rule_path} is loaded but its body is not injected; "
                    "if it is relevant to this task, first load its full text with the `load_rule` tool]"
                )
            else:
                parts.append(_limit_rule_body(rule_name, body))
        return "\n\n".join(parts)

    def get_rule_status(self, name: str) -> str:
        """Get the status of a rule

        Args:
            name: rule name

        Returns:
            str: the rule status ("loaded", "not_loaded")
        """
        if name in self.loaded_rules or name in self._loaded_rules:
            return "loaded"
        else:
            return "not_loaded"

    def _merge_loaded_rules(self) -> None:
        """Merge the content of all loaded rules"""
        if not self.loaded_rules:
            self._merged_rules = ""
            return

        combined_parts = []
        # Iterate over all loaded rules
        for rule_name in sorted(self.loaded_rules):
            if rule_name in self._loaded_rules:
                # Get the rule file path
                rule_path = self.get_rule_file_path(rule_name)
                # Extract the rule description
                description = ""
                if rule_path and rule_path != "--":
                    description = self._extract_rule_description(rule_path)
                # Format the rule content (the path was already added in _add_path_comment)
                if description:
                    # Add the description before the rule content (the path comment was already added by _add_path_comment)
                    rule_content = f"**Rule description**: {description}\n\n{self._loaded_rules[rule_name]}"
                else:
                    rule_content = self._loaded_rules[rule_name]
                combined_parts.append(rule_content)

        if combined_parts:
            self._merged_rules = "\n\n".join(combined_parts)
        else:
            self._merged_rules = ""

    def get_rule_file_path(self, rule_name: str) -> str:
        """Get the absolute path of a rule file

        Args:
            rule_name: rule name (may contain a prefix, e.g. builtin:, project:, global:, etc.)

        Returns:
            str: the absolute path of the rule file, or "--" if it cannot be obtained
        """
        try:
            # Parse the prefix
            if ":" in rule_name:
                prefix, actual_name = rule_name.split(":", 1)

                # Handle the builtin prefix
                if prefix == "builtin":
                    try:
                        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

                        builtin_dir = _get_builtin_dir()
                        if builtin_dir is not None:
                            builtin_rules_dir = builtin_dir / "rules"
                            return str(builtin_rules_dir / actual_name)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_agent.rules_manager",
                            function="get_rule_file_path",
                        )
                        pass

                # Handle the project prefix
                elif prefix == "project":
                    # Special rule: project:agents corresponds to repository root AGENTS.md/HAIJUN.md
                    if actual_name == "agents":
                        for filename in ("AGENTS.md", "HAIJUN.md"):
                            p = os.path.join(self.root_dir, filename)
                            if os.path.isfile(p):
                                return p
                        return "--"
                    return os.path.join(self.root_dir, ".haijunbot", "rules", actual_name)

                # Handle the global prefix
                elif prefix == "global":
                    return os.path.join(get_data_dir(), "rules", actual_name)

                # Handle the central and config prefixes
                elif prefix == "central" or prefix.startswith("config"):
                    all_rules_dirs = self._get_all_rules_dirs()
                    target_idx = -1
                    if prefix == "central" and len(all_rules_dirs) > 0:
                        target_idx = 0
                    elif prefix.startswith("config"):
                        try:
                            config_num = int(prefix[6:])
                            # configN corresponds to rules_dirs[N] (N>=1, rules_dirs[0] is the global directory)
                            if 1 <= config_num < len(self.rules_dirs):
                                target_idx = (
                                    len(all_rules_dirs) - len(self.rules_dirs)
                                ) + config_num
                        except ValueError:
                            pass

                    if 0 <= target_idx < len(all_rules_dirs):
                        return os.path.join(all_rules_dirs[target_idx], actual_name)

            # For builtin rules, try to get the path
            try:
                from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule_path

                path = get_builtin_rule_path(rule_name)
                if path:
                    return path
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.rules_manager",
                    function="get_rule_file_path",
                )
                pass

            return "--"
        except Exception:
            return "--"

    def get_rule_preview(self, rule_name: str) -> str:
        """Get the first 100 characters of the rule content as a preview

        Args:
            rule_name: rule name

        Returns:
            str: the first 100 characters of the rule content, or "--" if reading fails
        """
        try:
            # Prefer getting it from the cache
            if rule_name in self._loaded_rules:
                content: str | None = self._loaded_rules[rule_name]
            else:
                # Get it from a file or builtin rules
                content = self.get_named_rule(rule_name)

            if content:
                # Remove newlines and extra spaces, keep the first 100 characters
                preview = content.replace("\n", " ").strip()
                return preview[:100] + "..." if len(preview) > 100 else preview
            return "--"
        except Exception:
            return "--"

    def get_all_rules_with_status(self) -> List[Tuple[str, str, bool, str]]:
        """Get all rules and their load status

        Returns:
            List[Tuple[str, str, bool, str]]: (rule name, content preview, is loaded, file path) list
        """
        rules_info = []
        available_rules = self.get_all_available_rule_names()

        # Handle builtin rules
        for rule_name in available_rules.get("builtin", []):
            # Extract the actual rule name from the prefixed name (strip the "builtin:" prefix)
            actual_rule_name = (
                rule_name.split(":", 1)[1] if ":" in rule_name else rule_name
            )
            # For builtin rules, directly use get_builtin_rule() to get the preview
            # because rule names in the new format (e.g. architecture_design:clean_code.md)
            # would be misparsed by get_named_rule() as a prefixed rule
            try:
                from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule

                rule_content = get_builtin_rule(actual_rule_name)
                if rule_content:
                    # Remove newlines and extra spaces, keep the first 100 characters
                    preview = rule_content.replace("\n", " ").strip()
                    preview = preview[:100] + "..." if len(preview) > 100 else preview
                else:
                    preview = "--"
            except Exception:
                preview = "--"
            # Check the status: only explicitly loaded rules show as loaded
            # Also check both prefixed and unprefixed names, for backward compatibility
            is_loaded = (
                rule_name in self.loaded_rules or actual_rule_name in self.loaded_rules
            )
            # Get the actual file path of the builtin rule
            try:
                from haijunbot.haijunbot_agent.builtin_rules import get_builtin_rule_path

                file_path = get_builtin_rule_path(actual_rule_name) or "builtin"
            except Exception:
                file_path = self.get_rule_file_path(rule_name)
            rules_info.append((rule_name, preview, is_loaded, file_path))

        # Handle file rules
        for rule_name in available_rules.get("files", []):
            preview = self.get_rule_preview(rule_name)
            file_path = self.get_rule_file_path(rule_name)
            # Check the status: only explicitly loaded rules show as loaded
            is_loaded = rule_name in self.loaded_rules
            rules_info.append((rule_name, preview, is_loaded, file_path))

        # Handle the builtin rule index file builtin/rules/rule.md
        try:
            from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

            builtin_dir = _get_builtin_dir()
            if builtin_dir is not None:
                builtin_rule_path = builtin_dir / "rules" / "rule.md"
                if builtin_rule_path.exists() and builtin_rule_path.is_file():
                    preview = self.get_rule_preview("builtin_rules")
                    # Check the status: use the new state-management mechanism
                    is_loaded = "builtin_rules" in self.loaded_rules
                    rules_info.append(
                        ("builtin_rules", preview, is_loaded, str(builtin_rule_path))
                    )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.rules_manager",
                function="get_all_rules_with_status",
            )
            pass

        # Handle dynamically loaded rules (rules loaded via the load_rule tool)
        # These rules may not be in available_rules, but need to be shown in the sidebar
        existing_rule_names = {info[0] for info in rules_info}
        for rule_name, rule_content in self._loaded_rules.items():
            if rule_name not in existing_rule_names:
                # Generate the preview
                preview = rule_content.replace("\n", " ").strip()
                preview = preview[:100] + "..." if len(preview) > 100 else preview
                # Check the status: dynamically loaded rules default to loaded
                is_loaded = True
                # Try to extract the file path from the rule content
                file_path = "Dynamically loaded"
                if rule_content.startswith("## Rule file path:"):
                    # Extract the file path from the rule content
                    first_line = rule_content.split("\n")[0]
                    path_part = first_line.replace("## Rule file path:", "").strip()
                    if path_part:
                        file_path = path_part
                rules_info.append((rule_name, preview, is_loaded, file_path))

        # Sort: loaded rules go to the bottom; unloaded rules are sorted by directory
        # Use (is_loaded, rule_name) as the sort key, ensuring False (unloaded) comes first, True (loaded) last
        rules_info.sort(key=lambda x: (x[2], x[0]))

        return rules_info

    def select_rule_by_task(self, task_description: str) -> Optional[List[str]]:
        """Based on the task description, let the model automatically select the most suitable rules (at most 3)

        Args:
            task_description: the task description string

        Returns:
            Optional[List[str]]: the list of recommended rule names (with prefix, e.g. builtin:xxx.md),
                                or None if it cannot select, at most 3 rules
        """
        # Auto-selection limit: better to let the model load more with load_rule midway, than to inject too many rule bodies at once
        MAX_AUTO_RULES = 3
        try:
            # Get all available rules
            all_rules_dict = self.get_all_available_rule_names()
            if not all_rules_dict:
                PrettyOutput.auto_print("⚠️  Failed to get rules index")
                return None

            # Flatten all rules into a list, for numbering
            all_rules_list = []
            for category, rules in all_rules_dict.items():
                all_rules_list.extend(rules)

            if not all_rules_list:
                PrettyOutput.auto_print("⚠️  No rules available")
                return None

            # Prefetch all candidate descriptions, for reuse in the two-stage selection (description prefers YAML Front Matter)
            desc_by_name = {}
            for rule_name in all_rules_list:
                rule_path = self.get_rule_file_path(rule_name)
                description = ""
                if rule_path and rule_path != "--":
                    description = self._extract_rule_description(rule_path) or ""
                if not description:
                    preview = self.get_rule_preview(rule_name)
                    description = (
                        f"(Content preview: {preview})"
                        if preview and preview != "--"
                        else "(No description)"
                    )
                desc_by_name[rule_name] = description

            # Directly do one normal selection over all candidates (no longer narrowing via cheap, to avoid a weak model dropping correct rules)
            # First do a keyword coarse screen, keeping only the most relevant Top-N candidates, reducing the candidate volume fed to the LLM;
            # when the prescreen has no match/no keyword/exception, fall back to the full set, ensuring existing behavior is unchanged.
            prescreened = _preselect_rules(
                task_description, all_rules_list, desc_by_name
            )
            if len(prescreened) < len(all_rules_list):
                PrettyOutput.auto_print(
                    f"🔍 Rule prescreen: {len(all_rules_list)} → {len(prescreened)} candidates"
                )
            top_rules = prescreened

            # Build the numbered list (all candidates)
            numbered_rules = ""
            for i, rule_name in enumerate(top_rules, 1):
                description = desc_by_name.get(rule_name, "(No description)")
                numbered_rules += f"{i}. {rule_name}\n   Description: {description}\n"

            # Build the prompt, requiring the model to return numbers
            prompt = f"""Please select the most suitable rules from the available rules based on the following task description.

<task_description>
{task_description}
</task_description>

<available_rules>
{numbered_rules}
</available_rules>

Requirements:
1. Carefully analyze the task description, and select the rules that match it
2. **Quantity limit**: select at most 1 to {MAX_AUTO_RULES} rules, do not exceed {MAX_AUTO_RULES}
3. If there are multiple relevant rules, select only the 1 to {MAX_AUTO_RULES} most relevant, do not select too many
4. **Important**: if there is no suitable rule, or the rules are irrelevant to the task, you may return "NONE" or "none"
5. **The task does not need rules**: if the task is very simple (e.g. greetings, simple calculation, querying the time, etc.) and can be completed without any rule/track, return "__NO_RULES_NEEDED__"
6. Return the numbers in the following form: <NUM>number1,number2,number3,number4,number5</NUM>
7. Example: <NUM>5</NUM> or <NUM>2,3,5,7,9</NUM> or <NUM>none</NUM> or <NUM>__NO_RULES_NEEDED__</NUM>
8. Separate multiple numbers with commas, no spaces
9. Only return the content within the <NUM> tag, do not output anything else

Selected rule numbers:"""

            def _select_with_normal_model() -> str:
                """Existing flow: use the normal model to select rule numbers."""
                registry = PlatformRegistry.get_global_platform_registry()
                model = registry.create_platform(platform_type="normal")
                if model is None:
                    PrettyOutput.auto_print("⚠️  Failed to create a normal type model")
                    return ""
                # Call the model to select rules (disable output suppression, allowing the model to output its analysis)
                model.set_suppress_output(False)
                try:
                    return model.chat_until_success(prompt).strip()
                finally:
                    model.set_suppress_output(True)

            # Prefer using the structured evaluation model for candidate selection: it only accepts the JSON protocol,
            # so it cannot consume natural-language prompts; thus go through decide_choice for protocol conversion.
            # When the evaluation model is not configured or the call fails, decide_choice internally falls back to the existing flow.
            picked_rules = decide_choice(
                task_description,
                {
                    rule_name: desc_by_name.get(rule_name, "(No description)")
                    for rule_name in top_rules
                },
                lambda: None,
                max_select=MAX_AUTO_RULES,
            )
            if picked_rules:
                PrettyOutput.auto_print(
                    f"✅ The structured evaluation model selected {len(picked_rules)} rules"
                )
                return picked_rules

            # When the structured evaluation model selected no candidate (not configured/failed/no match), go through the existing normal flow.
            # Note: decide() cannot be used again here, because this prompt is a natural-language protocol
            # that the structured evaluation model cannot consume, so it would only fail pointlessly once.
            response = _select_with_normal_model()
            if not response:
                return None
            # Extract the content within the <NUM> tag from the response
            import re

            num_match = re.search(r"<NUM>(.*?)</NUM>", response, re.DOTALL)

            if not num_match:
                # If the <NUM> tag is not found, try parsing the response directly
                selected_index_str = response.strip()
            else:
                selected_index_str = num_match.group(1).strip()
            # Validate the return value
            if selected_index_str and selected_index_str == "__NO_RULES_NEEDED__":
                PrettyOutput.auto_print("✅ The task is simple, can be completed directly without installing tracks")
                return ["__NO_RULES_NEEDED__"]

            if not selected_index_str or selected_index_str.lower() == "none":
                PrettyOutput.auto_print("⚠️  Local rule match: no suitable rule")
                return None

            # Parse the numbers (supports multiple numbers separated by commas)
            try:
                # Try splitting the numbers by commas
                index_strings = selected_index_str.split(",")
                selected_indices = []
                for idx_str in index_strings:
                    idx = int(idx_str.strip())
                    # Validate the number range
                    if 1 <= idx <= len(top_rules):
                        selected_indices.append(idx)
                    else:
                        PrettyOutput.auto_print(f"⚠️  The number returned by the model is out of range: {idx}")

                # If there is no valid number, return None
                if not selected_indices:
                    return None

                # Limit to at most MAX_AUTO_RULES returned rules
                selected_indices = selected_indices[:MAX_AUTO_RULES]
            except ValueError:
                PrettyOutput.auto_print(
                    f"⚠️  Invalid number format returned by the model: {selected_index_str}"
                )
                return None

            # Get the list of rule names (with prefix)
            rule_names = []
            for index in selected_indices:
                rule_name = top_rules[index - 1]
                # Validate whether the rule exists
                if self.get_named_rule(rule_name):
                    rule_names.append(rule_name)
                else:
                    PrettyOutput.auto_print(f"⚠️  The selected rule does not exist: {rule_name}")

            # Before returning the rule name list, do content filtering
            if rule_names:
                PrettyOutput.auto_print(f"🔍 Initially selected rules: {', '.join(rule_names)}")
                # Load the rule content and filter
                filtered_rules = self._filter_rules_by_content(
                    task_description, rule_names
                )
                if filtered_rules:
                    PrettyOutput.auto_print(
                        f"✅ Filtered rules: {', '.join(filtered_rules)}"
                    )
                    return filtered_rules

            return None

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Failed to select rules by task: {e}")
            return None

    def _filter_rules_by_content(
        self, task_description: str, rule_names: List[str]
    ) -> List[str]:
        """Filter out irrelevant rules based on the rule content

        Args:
            task_description: the task description string
            rule_names: the list of rule names to filter

        Returns:
            List[str]: the filtered list of relevant rule names
        """
        try:
            # Load the content of all selected rules
            rules_content = []
            for rule_name in rule_names:
                rule_content = self.get_named_rule(rule_name)
                if rule_content:
                    # Use only the first 2000 characters, to avoid an overly long context
                    content_preview = (
                        rule_content[:2000] + "..."
                        if len(rule_content) > 2000
                        else rule_content
                    )
                    rules_content.append(
                        f"Rule name: {rule_name}\nRule content:\n{content_preview}"
                    )
                else:
                    PrettyOutput.auto_print(f"⚠️  Failed to load rule content: {rule_name}")

            if not rules_content:
                return rule_names  # If the content cannot be loaded, return the original rules

            # Build the filtering prompt
            all_rules_text = "\n\n".join(
                [f"Rule {i + 1}:\n{content}" for i, content in enumerate(rules_content)]
            )

            prompt = f"""Based on the task description, select the truly relevant rules from the rules below.

<task_description>
{task_description}
</task_description>

<candidate_rules>
{all_rules_text}
</candidate_rules>

Requirements:
1. Carefully read the full content of each rule, and judge whether it is really relevant to the task
2. **Conservative strategy**: if you are unsure whether a rule is relevant, lean toward keeping it
3. Only select rules whose content truly matches the task
4. If there is no relevant rule, return "none"
5. **The task does not need rules**: if the task is very simple (e.g. greetings, simple calculation, querying the time, etc.) and can be completed without any rule/track, return "__NO_RULES_NEEDED__"
6. Return the rule names in the following form: <VALID>rule_name1,rule_name2</VALID>
7. Example: <VALID>builtin:xxx.md</VALID> or <VALID>project:yyy.md,global:zzz.md</VALID> or <VALID>__NO_RULES_NEEDED__</VALID>
8. Separate multiple rule names with commas, no spaces
9. Only return the content within the <VALID> tag, do not output anything else

Selected rule names:"""

            # Call the model to filter
            registry = PlatformRegistry.get_global_platform_registry()
            model = registry.create_platform(platform_type="normal")
            if model is None:
                PrettyOutput.auto_print("⚠️  Failed to create a normal type model, skipping filtering")
                return rule_names

            # Call the model to filter rules (disable output suppression, allowing the model to output its analysis)
            model.set_suppress_output(False)
            response = model.chat_until_success(prompt).strip()
            model.set_suppress_output(True)

            # Extract the content within the <VALID> tag from the response
            import re

            valid_match = re.search(r"<VALID>(.*?)</VALID>", response, re.DOTALL)

            if not valid_match:
                # If the <VALID> tag is not found, try parsing the response directly
                valid_rules_str = response.strip()
            else:
                valid_rules_str = valid_match.group(1).strip()
            # Validate the return value
            if valid_rules_str and valid_rules_str == "__NO_RULES_NEEDED__":
                PrettyOutput.auto_print("✅ The task is simple, can be completed directly without installing tracks")
                return ["__NO_RULES_NEEDED__"]

            if not valid_rules_str or valid_rules_str.lower() == "none":
                return []

            # Parse the rule names
            valid_rule_names = []
            for rule_name in valid_rules_str.split(","):
                rule_name = rule_name.strip()
                # Validate whether the rule name is in the original list
                if rule_name in rule_names:
                    valid_rule_names.append(rule_name)
                else:
                    PrettyOutput.auto_print(f"⚠️  Rule '{rule_name}' is not in the candidate list")

            return valid_rule_names if valid_rule_names else rule_names

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Failed to filter rules: {e}")
            return rule_names  # Return the original rule list on exception

    def _build_entry_catalog(self) -> List[list]:
        """Build the (rule name, description) candidate catalog, used for force-trigger cheap judgment."""
        all_rules_dict = self.get_all_available_rule_names()
        names: List[str] = []
        for rules in all_rules_dict.values():
            names.extend(rules)
        rows: List[list] = []
        for name in names:
            rule_path = self.get_rule_file_path(name)
            desc = ""
            if rule_path and rule_path != "--":
                desc = (self._extract_rule_description(rule_path) or "").strip()
            if not desc:
                preview = self.get_rule_preview(name)
                desc = preview if preview and preview != "--" else ""
            rows.append([name, desc[:200]])
        return rows

    def match_task_cheap(self, task_description: str, max_rules: int = 3) -> List[str]:
        """Force trigger: use the cheap model to make a "possibly relevant" loose judgment on a new task.

        As long as it is judged possibly relevant to some rule, return its name (for the Agent to forcibly load), to align with
        the semantics of "load at >=1% hit". Return empty when there is no cheap platform / judgment fails / clearly irrelevant.
        """
        try:
            registry = PlatformRegistry.get_global_platform_registry()
            cheap_model = registry.create_platform(platform_type="cheap")
        except Exception:
            cheap_model = None
        if cheap_model is None:
            return []

        if not hasattr(self, "_catalog_cache") or self._catalog_cache is None:
            self._catalog_cache = self._build_entry_catalog()
        rows = self._catalog_cache
        if not rows:
            return []

        import re

        compact_lines = "\n".join(
            f"{i}. {name}: {desc}" for i, (name, desc) in enumerate(rows, 1)
        )
        prompt = f"""Judge whether the task below needs to load specialized rules/tracks.

<task_description>
{task_description}
</task_description>

<candidate_rules>
{compact_lines}
</candidate_rules>

Requirements:
1. If the task is [possibly] relevant to some rules (even if the likelihood is low), list their numbers, at most {max_rules}; prefer selecting more
2. If clearly irrelevant or merely greetings/chitchat, return none
3. Return in the following form: <NUM>number1,number2</NUM> or <NUM>none</NUM>

Result:"""
        try:
            cheap_model.set_suppress_output(False)
            response = cheap_model.chat_until_success(prompt).strip()
        except Exception:
            # When cheap is unavailable/fails, do not force loading rules, keep a quiet downgrade
            try:
                cheap_model.set_suppress_output(True)
            except Exception:
                pass
            return []
        cheap_model.set_suppress_output(True)

        num_match = re.search(r"<NUM>(.*?)</NUM>", response, re.DOTALL)
        raw = num_match.group(1).strip() if num_match else response.strip()
        if not raw or raw.lower() == "none":
            return []

        picked: List[str] = []
        seen = set()
        for part in raw.split(","):
            try:
                idx = int(part.strip())
            except ValueError:
                continue
            if 1 <= idx <= len(rows):
                name = rows[idx - 1][0]
                if name not in seen:
                    seen.add(name)
                    picked.append(name)
                    if len(picked) >= max_rules:
                        break
        return picked

    def match_rules_to_task(self, task_description: str) -> List[str]:
        """
        Match rules for the task (extends the existing method, supports remote track search)

        Flow:
        1. First match local rules
        2. If the match is low, trigger a remote track search
        3. Automatically download and load high-match tracks
        4. Re-match (including newly installed rules)

        Args:
            task_description: the task description

        Returns:
            the list of matched rule names
        """
        # === Step 1: existing local matching logic ===
        local_matches = self.select_rule_by_task(task_description)
        local_matches = local_matches or []

        # Check whether it is marked as "no rules needed"
        if local_matches == ["__NO_RULES_NEEDED__"]:
            PrettyOutput.auto_print("✅ The task is simple, can be completed directly without installing tracks")
            return []

        # If there are already high-match local rules, return directly
        if local_matches:
            PrettyOutput.auto_print(f"✅ Matched {len(local_matches)} local rules")
            return local_matches

        # === Step 2: trigger remote track search ===
        PrettyOutput.auto_print("🔍 Local rules insufficient, searching remote tracks...")
        remote_tracks = self._search_remote_tracks(task_description)

        if not remote_tracks:
            PrettyOutput.auto_print("⚠️  No matching remote track found")
            return []

        # === Step 3: directly install the searched tracks ===
        tracks_to_install = remote_tracks[:3]
        PrettyOutput.auto_print(f"📦 Installing {len(tracks_to_install)} remote tracks...")

        PrettyOutput.auto_print(f"✅ Found {len(tracks_to_install)} tracks:")
        for i, track in enumerate(tracks_to_install, 1):
            PrettyOutput.auto_print(f"   {i}. {track.name}")

        # === Step 4: install the searched tracks ===
        installed = self._auto_install_tracks(tracks_to_install)
        if installed:
            PrettyOutput.auto_print(
                f"✅ Automatically installed {len(installed)} tracks: {', '.join(installed)}"
            )
            # Re-match (now including the newly installed rules)
            PrettyOutput.auto_print("🔄 Re-matching rules...")
            return self.select_rule_by_task(task_description) or []

        PrettyOutput.auto_print("⚠️  No matching remote track found")
        return []

    def _generate_search_keywords(self, query: str) -> List[str]:
        """Use an LLM to generate precise search keywords based on the task description

        Args:
            query: the task description string

        Returns:
            List[str]: the generated list of 3-5 search keywords, or an empty list if the LLM is unavailable
        """
        try:
            # Build the keyword-generation prompt
            prompt = f"""Based on the task description below, generate three to five precise English search keywords, used to search for related tracks in the track library.

<task_description>
{query}
</task_description>

Requirements:
1. The keywords should be English words or phrases
2. The keywords should accurately reflect the core need of the task
3. Avoid overly broad words (e.g. 'tool', 'helper')
4. Prefer technical terms and specific function descriptions
5. Sort by relevance from high to low
6. Only return the keyword list, one per line, do not output anything else

Example format:
python file processing
automation script
data parsing

Keywords:"""

            # Call the LLM to generate keywords (use the cheap model to reduce cost)
            # Note: this is "generation", not "selection from candidates"; the structured evaluation model is not up to it,
            # so decide/decide_choice is not wired in, keeping the original cheap model flow.
            registry = PlatformRegistry.get_global_platform_registry()
            model = registry.get_cheap_platform()
            if model is None:
                PrettyOutput.auto_print("⚠️ cheap model unavailable, cannot generate search keywords")
                return []

            # Disable output suppression, allowing the model to output its analysis
            model.set_suppress_output(False)
            response = model.chat_until_success(prompt).strip()
            model.set_suppress_output(True)

            # Parse the response, extract the keywords
            keywords = []
            for line in response.split("\n"):
                line = line.strip()
                if line and not line.startswith("Keywords"):
                    # Clean up possible numbers or markers
                    cleaned = re.sub(r"^[\d\.\-\*]+\s*", "", line)
                    if cleaned:
                        keywords.append(cleaned)

            # Limit to at most 5 keywords
            result = keywords[:5]

            if result:
                PrettyOutput.auto_print(f"✅ The LLM generated {len(result)} search keywords")
            else:
                PrettyOutput.auto_print("⚠️ The LLM failed to generate valid keywords")

            return result

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to generate search keywords: {str(e)}")
            return []

    def _search_remote_tracks(self, query: str) -> List[Any]:
        """Search the remote track marketplace"""
        try:
            from haijunbot.haijunbot_agent.track_discovery.search_engine import (
                TrackSearchEngine,
            )

            # Step 1: use the LLM to generate precise search keywords
            search_keywords = self._generate_search_keywords(query)
            if not search_keywords:
                PrettyOutput.auto_print("⚠️ The LLM failed to generate keywords, cannot search")
                return []

            PrettyOutput.auto_print(
                f"🔍 Search keywords generated from the task description: {', '.join(search_keywords)}"
            )

            # Step 2: use the generated keywords to search
            engine = TrackSearchEngine(
                min_relevance=0.5, min_quality=5.0, max_results=10
            )
            PrettyOutput.auto_print(
                f"🔍 Search sources: {len(engine.sources)} (TrackHub, GitHub)"
            )
            # Use the first (most relevant) keyword to search
            results = engine.search(search_keywords[0])
            PrettyOutput.auto_print(f"🔍 Search done, raw results: {len(results)} tracks")

            # Show an overview of the found tracks
            if results:
                for i, r in enumerate(results[:5], 1):
                    PrettyOutput.auto_print(
                        f"   {i}. {r.name} (relevance: {r.relevance_score:.2f}, quality: {r.quality_score:.1f})"
                    )

            # Filter: keep only tracks with relevance (>0.3) and quality (>4.0)
            filtered = [
                r for r in results if r.relevance_score > 0.3 and r.quality_score > 4.0
            ]
            PrettyOutput.auto_print(
                f"🔍 Kept after filtering: {len(filtered)} tracks (threshold: relevance>0.3, quality>4.0)"
            )

            return filtered
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to search remote tracks: {str(e)}")
            return []

    def _auto_install_tracks(self, tracks: List[Any]) -> List[str]:
        """Automatically install tracks"""
        try:
            from haijunbot.haijunbot_agent.track_discovery.installer import TrackInstaller

            installer = TrackInstaller(rules_manager=self)
            installed_names = []

            for track in tracks:
                try:
                    # Download and save TRACK.md (no conversion, save as-is)
                    installer.install(track)
                    installed_names.append(track.name)
                except Exception as e:
                    PrettyOutput.auto_print(f"⚠️ Failed to install track '{track.name}': {e}")

            return installed_names
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️  Failed to initialize the installer: {e}")
            return []
