# -*- coding: utf-8 -*-
"""
Utility functions (haijunbot_agent.utils)

- join_prompts: unified prompt concatenation strategy (supports plain text and multimodal content)
- is_auto_complete: unified auto-complete marker detection
- fix_tool_call_with_llm: fix the tool call format using an LLM
"""

from enum import Enum
from typing import Any, List
from typing import Iterable
from typing import Optional, Union
from typing import cast


from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot


def join_prompts(
    parts: Iterable[Union[str, List[ContentBlock]]],
) -> Union[str, List[ContentBlock]]:
    """
    Concatenate multiple prompt fragments using a unified rule:
    - Supports plain text and multimodal content
    - If all parts are strings, return the concatenated string
    - If any part is multimodal content, return the merged list of content blocks
    """
    try:
        all_parts = list(parts)
    except Exception:
        # Defensive handling: if parts is not iterable or an exception occurs, return an empty string
        return ""

    # Check whether there is multimodal content
    has_multimodal = any(isinstance(p, list) for p in all_parts)

    if not has_multimodal:
        # All parts are strings, use the original logic
        non_empty: list[str] = [p for p in all_parts if isinstance(p, str) and p]
        return "\n\n".join(non_empty)

    # There is multimodal content, needs merging
    result_blocks: List[ContentBlock] = []

    for part in all_parts:
        if isinstance(part, str):
            if part.strip():
                # Convert non-empty strings into text content blocks
                result_blocks.append({"type": "text", "text": part})
        elif isinstance(part, list):
            # Add the content block list directly
            result_blocks.extend(part)

    return result_blocks


def is_auto_complete(response: str) -> bool:
    """
    Detect whether it contains the auto-complete marker.
    Current implementation: containing ot('!!!COMPLETE!!!') is treated as auto-complete.
    """
    try:
        return ot("!!!COMPLETE!!!") in response
    except Exception:
        # Defensive handling: even if ot raises an exception, do not block the main flow
        return "!!!COMPLETE!!!" in response


def normalize_next_action(next_action: Any) -> str:
    """
    Normalize the next action to a string:
    - If it is an Enum, return its value (if it is a string)
    - If it is a str, return it as is
    - Otherwise return an empty string
    """
    try:
        if isinstance(next_action, Enum):
            value = getattr(next_action, "value", None)
            return value if isinstance(value, str) else ""
        if isinstance(next_action, str):
            return next_action
        return ""
    except Exception:
        return ""


def build_fix_prompt(content: str, error_msg: str, tool_usage: str) -> str:
    """Build the prompt for fixing a tool call

    Args:
        content: Content containing the erroneous tool call
        error_msg: Error message
        tool_usage: Tool usage instructions

    Returns:
        str: The constructed prompt string
    """
    return f"""Your last tool call had an invalid format; please fix the following content according to the tool usage instructions.

**Error message:**
{error_msg}

**Tool usage instructions:**
{tool_usage}

**Erroneous tool call content:**
{content}

Please fix the above tool call content, ensuring that:
1. Output a pure JSON object containing the name and arguments fields
2. The JSON format is correct and contains the name, arguments, and want fields
3. If a multiline string is used, just use a line break

Return the corrected complete tool call content directly, without adding any other text."""


def fix_tool_call_with_llm(content: str, agent: Any, error_msg: str) -> Optional[str]:
    """Fix the tool call format using an LLM

    Args:
        content: Content containing the erroneous tool call
        agent: Agent instance, used to call the LLM
        error_msg: Error message

    Returns:
        Optional[str]: The fixed content, or None if the fix failed
    """
    try:
        # Get the tool usage instructions
        tool_usage = agent.get_tool_usage_prompt()

        # Build the fix prompt
        fix_prompt = build_fix_prompt(content, error_msg, tool_usage)

        # Call the LLM to fix
        PrettyOutput.auto_print("🤖 Attempting to fix the tool call format using the LLM...")
        fixed_content: Any = agent.model.chat_until_success(fix_prompt)

        # Type check: ensure the return value is a string
        if fixed_content and isinstance(fixed_content, str):
            PrettyOutput.auto_print("✅ LLM fix completed")
            # Type assertion: ensure the return type matches the function signature
            return cast(Optional[str], fixed_content)
        else:
            PrettyOutput.auto_print("❌ LLM fix failed: returned content is empty")
            return None

    except Exception as e:
        PrettyOutput.auto_print(f"❌ LLM fix failed: {str(e)}")
        return None


def _compare_versions(v1: str, v2: str) -> Optional[int]:
    """Compare two semantic version numbers.

    Args:
        v1: The first version number (e.g. "1.2.0")
        v2: The second version number (e.g. "1.3.0")

    Returns:
        int: 1 means v1 > v2, 0 means equal, -1 means v1 < v2
        None: returned when either version number cannot be parsed
    """
    try:
        from packaging.version import Version

        ver1 = Version(v1)
        ver2 = Version(v2)
        if ver1 > ver2:
            return 1
        if ver1 < ver2:
            return -1
        return 0
    except Exception:
        return None


def _check_version_constraint(version: str, constraint: str) -> bool:
    """Check whether a version satisfies a version constraint.

    Supported constraint formats (multiple conditions can be combined with commas):
        "1.2.0"          exact version
        ">=1.2.0"        greater than or equal to
        ">1.2.0"         greater than
        "<=1.2.0"        less than or equal to
        "<1.2.0"         less than
        "==1.2.0"        exactly equal
        "*"              any version
        ">=1.0.0,<2.0.0" range (multiple conditions separated by commas, all must be satisfied)

    Args:
        version: The version number to check
        constraint: The version constraint expression

    Returns:
        bool: True if the constraint is satisfied, otherwise False
    """
    if not version or not constraint:
        return True
    constraint = constraint.strip()
    if not constraint or constraint == "*":
        return True

    # Split the comma-separated conditions, all must be satisfied
    parts = [p.strip() for p in constraint.split(",") if p.strip()]
    if not parts:
        return True

    from packaging.version import Version

    try:
        ver = Version(version)
    except Exception:
        return False

    for part in parts:
        # Parse the operator
        if part.startswith(">="):
            op, target = ">=", part[2:].strip()
        elif part.startswith("<="):
            op, target = "<=", part[2:].strip()
        elif part.startswith("=="):
            op, target = "==", part[2:].strip()
        elif part.startswith(">"):
            op, target = ">", part[1:].strip()
        elif part.startswith("<"):
            op, target = "<", part[1:].strip()
        else:
            op, target = "==", part

        try:
            target_ver = Version(target)
        except Exception:
            # The constraint target cannot be parsed, treat as not satisfied
            return False

        cmp = (ver > target_ver) - (ver < target_ver)
        if op == ">=" and cmp < 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == "==" and cmp != 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<" and cmp >= 0:
            return False

    return True


def _resolve_plugin_dep_url(url: str, tag: Optional[str], branch: Optional[str]) -> str:
    """Resolve the download URL of a plugin dependency based on tag/branch.

    When url is a GitHub repository address (of the form https://github.com/owner/repo)
    and tag or branch is provided, automatically construct the corresponding archive download address:
        tag:    https://github.com/owner/repo/archive/refs/tags/<tag>.tar.gz
        branch: https://github.com/owner/repo/archive/refs/heads/<branch>.tar.gz
    Otherwise (not a GitHub address, or already a complete download address) return url as is.

    Args:
        url: The url configured for the dependency plugin
        tag: The tag configured for the dependency plugin (optional)
        branch: The branch configured for the dependency plugin (optional)

    Returns:
        str: The resolved download URL
    """
    if not url:
        return url
    if not tag and not branch:
        return url
    # Only construct an archive URL when url is a GitHub repository address (without an already specified suffix)
    url = url.rstrip("/")
    if "github.com/" not in url:
        return url
    # Extract owner/repo (ignoring a possible .git suffix)
    parts = url.split("github.com/", 1)
    if len(parts) != 2:
        return url
    repo_path = parts[1].rstrip("/")
    if repo_path.endswith(".git"):
        repo_path = repo_path[:-4]
    repo_path = "/".join(repo_path.split("/")[:2])
    if not repo_path or "/" not in repo_path:
        return url
    if tag:
        return f"https://github.com/{repo_path}/archive/refs/tags/{tag}.tar.gz"
    if branch:
        return f"https://github.com/{repo_path}/archive/refs/heads/{branch}.tar.gz"
    return url


def _check_plugin_dependencies(dependencies: Any, plugins_dir: Any) -> list:
    """Check whether the plugin dependencies of a plugin are installed and version-compatible.

    Args:
        dependencies: Plugin dependency declaration, either a dict ({plugin name: version constraint})
            or a list ([{"name":..., "version":...}])
        plugins_dir: Directory of installed plugins

    Returns:
        list: List of unsatisfied dependencies, each item is a dict (containing type/name/version_constraint/installed/reason,
            with optional url/tag/branch used for automatic dependency installation)
    """
    if not dependencies:
        return []

    import yaml

    # Normalize to dict {name: {"version":..., "url":..., "tag":..., "branch":...}}
    # Shorthand forms {name: "version"} or [{name, version}] are still supported
    dep_map: dict = {}
    if isinstance(dependencies, dict):
        for k, v in dependencies.items():
            name = str(k)
            if isinstance(v, dict):
                # Full form: {name: {version, url, tag, branch}}
                dep_map[name] = {
                    "version": str(v.get("version")) if v.get("version") else "*",
                    "url": v.get("url"),
                    "tag": v.get("tag"),
                    "branch": v.get("branch"),
                }
            else:
                # Shorthand form: {name: "version"}
                dep_map[name] = {
                    "version": str(v) if v else "*",
                    "url": None,
                    "tag": None,
                    "branch": None,
                }
    elif isinstance(dependencies, list):
        for item in dependencies:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    dep_map[str(name)] = {
                        "version": str(item.get("version") or "*"),
                        "url": item.get("url"),
                        "tag": item.get("tag"),
                        "branch": item.get("branch"),
                    }
    else:
        return []

    missing = []
    for dep_name, dep_info in dep_map.items():
        constraint = dep_info["version"]
        dep_url = dep_info.get("url")
        dep_tag = dep_info.get("tag")
        dep_branch = dep_info.get("branch")
        dep_dir = plugins_dir / dep_name
        installed_version = None
        if dep_dir.exists():
            config_file = dep_dir / "config.yaml"
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f)
                        if isinstance(cfg, dict):
                            installed_version = cfg.get("version")
                except Exception:
                    installed_version = None

        if not dep_dir.exists():
            missing.append(
                {
                    "type": "plugins",
                    "name": dep_name,
                    "version_constraint": constraint,
                    "installed": None,
                    "reason": "Not installed",
                    "url": dep_url,
                    "tag": dep_tag,
                    "branch": dep_branch,
                }
            )
        elif installed_version is None:
            # Installed but has no version number, cannot verify, treat as satisfied (conservative)
            continue
        elif not _check_version_constraint(str(installed_version), constraint):
            missing.append(
                {
                    "type": "plugins",
                    "name": dep_name,
                    "version_constraint": constraint,
                    "installed": str(installed_version),
                    "reason": f"Version incompatible (installed {installed_version}, required {constraint})",
                    "url": dep_url,
                    "tag": dep_tag,
                    "branch": dep_branch,
                }
            )

    return missing


def _check_python_dependencies(dependencies: Any) -> list:
    """Check whether the plugin's Python package dependencies are installed and version-compatible.

    Args:
        dependencies: Python package dependency declaration, either a dict ({package name: version constraint})
            or a list ([{"name":..., "version":...}])

    Returns:
        list: List of unsatisfied dependencies, each item is a dict (containing type/name/version_constraint/installed/reason)
    """
    if not dependencies:
        return []

    import importlib.metadata
    import importlib.util

    # Normalize to dict {name: constraint}
    dep_map: dict = {}
    if isinstance(dependencies, dict):
        dep_map = {str(k): (str(v) if v else "*") for k, v in dependencies.items()}
    elif isinstance(dependencies, list):
        for item in dependencies:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    dep_map[str(name)] = str(item.get("version") or "*")
    else:
        return []

    missing = []
    for pkg_name, constraint in dep_map.items():
        # Check whether the package is importable (handles cases where the package name differs from the module name, e.g. Pillow -> PIL)
        try:
            spec = importlib.util.find_spec(pkg_name)
            installed = spec is not None
        except Exception:
            installed = False

        installed_version = None
        if installed:
            try:
                installed_version = importlib.metadata.version(pkg_name)
            except Exception:
                installed_version = None

        if not installed:
            missing.append(
                {
                    "type": "python",
                    "name": pkg_name,
                    "version_constraint": constraint,
                    "installed": None,
                    "reason": "Not installed",
                }
            )
        elif installed_version is None:
            # Installed but the version number cannot be read, cannot verify, treat as satisfied (conservative)
            continue
        elif not _check_version_constraint(str(installed_version), constraint):
            missing.append(
                {
                    "type": "python",
                    "name": pkg_name,
                    "version_constraint": constraint,
                    "installed": str(installed_version),
                    "reason": f"Version incompatible (installed {installed_version}, required {constraint})",
                }
            )

    return missing


def _check_command_dependencies(dependencies: Any) -> list:
    """Check whether the plugin's system command dependencies exist in PATH.

    Args:
        dependencies: Command dependency declaration, either a list (["git", "jq"])
            or a dict ({"git": any value}) or a list ([{"name": "git"}])

    Returns:
        list: List of unsatisfied dependencies, each item is a dict (containing type/name/version_constraint/installed/reason)
    """
    if not dependencies:
        return []

    import shutil

    # Normalize to a list of command names
    cmd_names = []
    if isinstance(dependencies, list):
        for item in dependencies:
            if isinstance(item, str):
                cmd_names.append(item)
            elif isinstance(item, dict) and item.get("name"):
                cmd_names.append(str(item["name"]))
    elif isinstance(dependencies, dict):
        cmd_names = [str(k) for k in dependencies.keys()]

    missing = []
    for cmd in cmd_names:
        if shutil.which(cmd) is None:
            missing.append(
                {
                    "type": "commands",
                    "name": cmd,
                    "version_constraint": "*",
                    "installed": None,
                    "reason": "Command not found",
                }
            )

    return missing


def _check_dependencies(dependencies: Any, plugins_dir: Any) -> list:
    """Check whether the plugin's dependencies are satisfied.

    Supports three types of dependencies:
        1. plugins: plugin dependencies (other installed HaijunBot plugins)
        2. python:  Python package dependencies (importable via importlib)
        3. commands: system command dependencies (findable in PATH)

    Args:
        dependencies: The dependencies field in config.yaml.
            The new format is a dict containing the plugins/python/commands subkeys;
            the old format is a flat dict ({plugin name: version constraint}) or a list, treated as plugin dependencies.
        plugins_dir: Directory of installed plugins

    Returns:
        list: List of unsatisfied dependencies, each item is a dict (containing type/name/version_constraint/installed/reason)
    """
    if not dependencies:
        return []

    # Normalize the categorization: the new format uses the plugins/python/commands subkeys, the old format is treated as plugin dependencies
    if isinstance(dependencies, dict) and any(
        k in dependencies for k in ("plugins", "python", "commands")
    ):
        plugin_deps = dependencies.get("plugins")
        python_deps = dependencies.get("python")
        command_deps = dependencies.get("commands")
    else:
        plugin_deps = dependencies
        python_deps = None
        command_deps = None

    missing = []
    missing.extend(_check_plugin_dependencies(plugin_deps, plugins_dir))
    missing.extend(_check_python_dependencies(python_deps))
    missing.extend(_check_command_dependencies(command_deps))

    return missing


def _scaffold_slug(name: str) -> str:
    """Normalize the plugin name into a safe directory/filename slug (lowercase, hyphen-separated)."""
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-").lower()
    return slug or "my-plugin"


def _scaffold_class_name(name: str) -> str:
    """Convert the plugin name into a tool class name (CamelCase + Tool suffix)."""
    parts = _scaffold_slug(name).split("-")
    return "".join(p.capitalize() for p in parts) + "Tool"


def _scaffold_tool_module_name(name: str) -> str:
    """Convert the plugin name into a tool module filename (the filename stem must equal the tool name)."""
    return _scaffold_slug(name) + "_tool"


def scaffold_plugin(name: str, output_dir: Optional[str] = None) -> Optional[str]:
    """Generate a plugin scaffold directory that conforms to HaijunBot' loading conventions.

    Args:
        name: Plugin name (used to generate the directory name, the name in config.yaml, and the tool/rule/Agent naming)
        output_dir: Output directory (defaults to the current working directory)

    Returns:
        str: Absolute path of the generated plugin directory; returns None on failure

    The generated skeleton contains:
        config.yaml      Plugin configuration (with examples for all extension points)
        README.md        Developer documentation
        rules/           Rules directory (YAML front matter template)
        tools/           Tools directory (class XxxTool template, name==filename stem)
        agents/          Agent definition directory template
        orchestration/   Orchestration pipeline template
        frontend/        Frontend extensions (admin_tab.js / sidebar_view.js, using window.Vue)
        plugin/          Plugin private functions (api.py template, with a PUBLIC_FUNCTIONS whitelist)
    """
    import os
    from pathlib import Path

    slug = _scaffold_slug(name)
    base_dir = Path(output_dir or os.getcwd()).resolve()
    plugin_dir = base_dir / slug

    # Reject if the target directory already exists and is non-empty, to avoid accidental overwrite
    if plugin_dir.exists() and any(plugin_dir.iterdir()):
        PrettyOutput.auto_print(f"❌ Target directory already exists and is not empty: {plugin_dir}")
        return None

    tool_class = _scaffold_class_name(name)
    tool_module = _scaffold_tool_module_name(name)
    # Base name for the plugin private function (a Python identifier, hyphens replaced with underscores)
    func_base = slug.replace("-", "_")

    # Directory structure
    for sub in ("rules", "tools", "agents", "orchestration", "frontend", "plugin"):
        (plugin_dir / sub).mkdir(parents=True, exist_ok=True)

    # ---------- config.yaml ----------
    config = f"""---
name: {slug}
description: {name} - please add a plugin description.
version: 0.1.0
license: MIT
builtin: true
# Extension point descriptions (enable as needed, paths use the {{{{plugin_dir}}}} placeholder, rendered automatically at runtime):
# - rules_load_dirs: rules directory, rule files carry YAML front matter (name/description)
# - tool_load_dirs: tools directory, the tool class name must equal the filename stem
# - agent_definition_dirs: Agent definition directory (YAML format)
# - orchestration: orchestration pipeline (consumed with OrganizeAgents + --task-file)
# - frontend: frontend extension points (admin_tabs/sidebar_views/tool_panels, JS uses window.Vue)
# - plugin/: plugin private functions (run on the gateway, called by the frontend proxy, not exposed to the Agent)
#   api.py must define a PUBLIC_FUNCTIONS whitelist at the end; the gateway only allows calling functions in the whitelist.
# Private config isolation: besides the extension point fields above, the remaining fields (name/version/dependencies/custom business fields)
# are isolated into the global config plugin_configs.<plugin name>, without polluting the global config top level and without multiple plugins' same-named private fields overwriting each other;
# A plugin can read its own private config via get_plugin_config("<plugin name>").
rules_load_dirs:
  - "{{{{plugin_dir}}}}/rules"
tool_load_dirs:
  - "{{{{plugin_dir}}}}/tools"
# agent_definition_dirs:
#   - "{{{{plugin_dir}}}}/agents"
# Orchestration pipeline template declaration (auto-discovered with @OrganizeAgents, users can select by number directly)
orchestration:
  - name: "{slug}-pipeline"
    description: "{name} orchestration pipeline"
    file: "{{{{plugin_dir}}}}/orchestration/{slug}_pipeline.yaml"
# frontend:
#   admin_tabs:
#     - id: {slug}-admin
#       title: "{name} Admin"
#       entry: admin_tab.js
#   sidebar_views:
#     - id: {slug}-view
#       title: "{name}"
#       entry: sidebar_view.js
# Dependency declaration (optional, three types: plugins/python/commands)
# dependencies:
#   commands:
#     - git
"""
    (plugin_dir / "config.yaml").write_text(config, encoding="utf-8")

    # ---------- README.md ----------
    readme = f"""# {name}

> Plugin scaffold generated by `haijunbot --new-plugin {name}`.

## Plugin structure

```
{slug}/
├── config.yaml          # Plugin config (name/version + extension point declarations)
├── README.md
├── rules/               # Rules (YAML front matter: name/description)
├── tools/               # Tools (class XxxTool, name==filename stem)
├── agents/              # Agent definitions (optional)
├── orchestration/       # Orchestration pipeline (optional)
├── frontend/            # Frontend extensions (optional, uses window.Vue)
└── plugin/              # Plugin private functions (optional, runs on the gateway, not exposed to the Agent)
```

## Development guide

### 1. Tools (tools/)

A tool file is a Python module with class name `{tool_class}`, and **`name` must equal the filename stem (`{tool_module}`)**,
otherwise the registry will not load it. Implement `check()` (a static method returning bool indicating availability) and
`execute(args) -> {{"success", "stdout", "stderr"}}`.

### 2. Rules (rules/)

A Markdown file with YAML front matter at the beginning:

```yaml
---
name: <rule name>
description: <when to trigger this rule>
---
```

### 3. Frontend extensions (frontend/, optional)

Frontend JS is a pure browser ES module: **render with `window.Vue`, export a default component, and do not `import 'vue'`**.
Declare `admin_tabs` / `sidebar_views` / `tool_panels` in the `frontend` field of config.yaml.

### 4. Orchestration (orchestration/, optional)

A YAML orchestration pipeline, consumed with `OrganizeAgents` and `hca -n --task-file`.

### 5. Plugin Private Functions (plugin/, optional)

Feature implementations used by the plugin itself (such as API wrappers and pure business functions) go in `plugin/api.py`.
**They are not declared in `tool_load_dirs`**, so they are not loaded by ToolRegistry and are invisible and uncallable by the Agent;
they run on the gateway and are called by the frontend proxy. Conventions:

- Each function is a pure function returning a dict: `{{"success": bool, "data": .../ "message": .../ "error": ...}}`.
- Define a `PUBLIC_FUNCTIONS: list[str]` whitelist at the end of the module; the gateway only allows calling functions in the whitelist.
- The frontend calls via `POST /api/plugins/{{node_id}}/function-call` (request body `{{plugin, function, arguments}}`).

## Install

```bash
haijunbot --install-plugin {slug}
```

## Uninstall

```bash
haijunbot --uninstall-plugin {slug}
```
"""
    (plugin_dir / "README.md").write_text(readme, encoding="utf-8")

    # ---------- rules/<slug>.md ----------
    rule = f"""---
name: {slug}_rule
description: Rule template for {name}. Triggered when the conventions of the {name} plugin need to be followed.
---
# {name} Rule

Write the rule body here. Rules are used to guide the Agent's behavior in relevant scenarios.
"""
    (plugin_dir / "rules" / f"{slug}.md").write_text(rule, encoding="utf-8")

    # ---------- tools/<tool_module>.py ----------
    tool = f'''"""
{name} tool template.

Purpose:
- Describe the tool's purpose and behavior here.

Parameters:
- Describe the parameters here.

Returns:
- success (bool)
- stdout (str)
- stderr (str)
"""
import json
from typing import Any
from typing import Dict


class {tool_class}:
    # The filename must match the tool name so the registry can auto-load it
    name = "{tool_module}"
    description = "{name} tool: please add a tool description."

    parameters = {{
        "type": "object",
        "properties": {{
            "input": {{
                "type": "string",
                "description": "Input content",
            }},
        }},
        "required": ["input"],
    }}

    @staticmethod
    def check() -> bool:
        """Whether the tool is available (always returns True when there are no external dependencies)."""
        return True

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = args.get("input")
            if not data or not isinstance(data, str):
                return {{
                    "success": False,
                    "stdout": "",
                    "stderr": "Parameter error: input must be a non-empty string",
                }}
            output = {{
                "echo": data,
                "note": "Implement the actual logic here",
            }}
            return {{
                "success": True,
                "stdout": json.dumps(output, ensure_ascii=False, indent=2),
                "stderr": "",
            }}
        except Exception as e:
            return {{
                "success": False,
                "stdout": "",
                "stderr": f"{tool_module} execution error: {{e}}",
            }}
'''
    (plugin_dir / "tools" / f"{tool_module}.py").write_text(tool, encoding="utf-8")

    # ---------- agents/<slug>.yaml ----------
    agent = f"""# {name} Agent definition template (optional, requires enabling agent_definition_dirs in config.yaml)
name: {slug}_agent
description: Agent role definition for {name}.
system_prompt: |
  You are the dedicated Agent for the {name} plugin.
"""
    (plugin_dir / "agents" / f"{slug}.yaml").write_text(agent, encoding="utf-8")

    # ---------- orchestration/<slug>_pipeline.yaml ----------
    pipeline = f"""# {name} orchestration pipeline template (optional, consumed with OrganizeAgents + --task-file)
# Refer to the example orchestration file format under builtin/agent_orchestration/.
agents:
  - name: {slug}_worker
    role: executor
    task: Describe the task here
"""
    (plugin_dir / "orchestration" / f"{slug}_pipeline.yaml").write_text(
        pipeline, encoding="utf-8"
    )

    # ---------- frontend/admin_tab.js ----------
    admin_tab_js = """// Admin page Tab component template (optional, requires declaring frontend.admin_tabs in config.yaml)
// Convention: a pure browser ES module, render with window.Vue, export a default component, do not import 'vue'.
export default {
  name: "PluginAdminTab",
  template: `
    <div style="padding: 16px;">
      <h3>Plugin Admin Page</h3>
      <p>Implement the admin functionality here.</p>
    </div>
  `,
};
"""
    (plugin_dir / "frontend" / "admin_tab.js").write_text(
        admin_tab_js, encoding="utf-8"
    )

    # ---------- frontend/sidebar_view.js ----------
    sidebar_view_js = """// Sidebar view component template (optional, requires declaring frontend.sidebar_views in config.yaml)
// Convention: a pure browser ES module, render with window.Vue, export a default component, do not import 'vue'.
export default {
  name: "PluginSidebarView",
  template: `
    <div style="padding: 16px;">
      <h3>Plugin View</h3>
      <p>Implement the sidebar view content here.</p>
    </div>
  `,
};
"""
    (plugin_dir / "frontend" / "sidebar_view.js").write_text(
        sidebar_view_js, encoding="utf-8"
    )

    # ---------- plugin/api.py ----------
    api_py = f'''"""
{name} plugin private function layer (runs on the gateway, called by the frontend proxy; not exposed to the Agent).

This module is not declared in tool_load_dirs, so it is not loaded by ToolRegistry and is invisible and uncallable by the Agent;
the gateway dynamically loads and calls it via the plugin function proxy endpoint (POST /api/plugins/{{node_id}}/function-call).

Conventions:
- Each function is a pure function returning a dict: {{"success": bool, "data": .../ "message": .../ "error": ...}}.
- Define a PUBLIC_FUNCTIONS whitelist at the end of the module; the gateway only allows calling functions in the whitelist.
"""
from typing import Any
from typing import Dict


def {func_base}_echo(text: str = "") -> Dict[str, Any]:
    """Example function: echo the input text. Implement the actual business logic here."""
    if not text:
        return {{"success": False, "error": "Parameter error: text cannot be empty"}}
    return {{"success": True, "data": {{"echo": text}}}}


# The gateway only allows calling functions within the whitelist (prevents arbitrary functions from being called)
PUBLIC_FUNCTIONS: list[str] = ["{func_base}_echo"]
'''
    (plugin_dir / "plugin" / "api.py").write_text(api_py, encoding="utf-8")

    PrettyOutput.auto_print(
        f"✅ Plugin scaffold generated: {plugin_dir}\n   Install: haijunbot --install-plugin {slug}"
    )
    return str(plugin_dir)


def _remove_plugin_dir(path) -> None:
    """
    Safely delete a plugin directory: for a symlink (including a dangling symlink), use os.unlink to delete only the link itself;
    for a real directory, use shutil.rmtree to delete recursively.

    When uninstalling/overwriting a plugin installed via a symlink, only the link should be deleted; never accidentally delete the local source it points to.
    """
    import os
    import shutil

    if os.path.islink(path):
        os.unlink(path)
    else:
        shutil.rmtree(path)


def install_plugin(
    source_path: str,
    force: bool = False,
    source_url: Optional[str] = None,
    _installing_deps: Optional[set] = None,
) -> bool:
    """Install a plugin into the HaijunBot data directory

    Args:
        source_path: Plugin source path, which can be a directory, archive (tar/tar.gz/zip), or http(s) URL
        force: Whether to force-overwrite an installed plugin (ignoring version comparison), defaults to False
        source_url: Source URL (optional); recorded to the plugin directory on successful install, used for upgrades
        _installing_deps: Internal parameter recording the set of dependency plugin names currently being auto-installed, used to prevent recursive dependency loops

    Returns:
        bool: Returns True on successful install, False on failure

    Features:
        1. Verify whether the plugin contains config.yaml
        2. Copy or extract to ~/.haijunbot/plugins/<plugin name>/
        3. The plugin name is taken from the name field of config.yaml, otherwise the directory/filename is used
        4. Version control: a higher-version plugin can overwrite a lower version, a lower version cannot overwrite a higher version
        5. When force=True, ignore version comparison and force-overwrite
        6. Support downloading and installing from a URL, and record the source URL for upgrades
    """
    import os
    import shutil
    import tarfile
    import zipfile
    import tempfile
    import yaml
    from pathlib import Path

    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.exception_utils import save_exception
    from haijunbot.haijunbot_utils.http import get as http_get
    from haijunbot.haijunbot_utils.output import PrettyOutput

    temp_dir = None  # Pre-initialize to ensure the except branch can access it (ty inference limitation)
    download_path = None  # Temp file path for URL download
    try:
        # Support http(s) URLs: download to a temp file, then handle as an archive
        if source_path.startswith("http://") or source_path.startswith("https://"):
            PrettyOutput.auto_print(f"⬇️  Downloading plugin from URL: {source_path}")
            try:
                response = http_get(source_path, stream=True)
                download_path = tempfile.mkstemp(
                    prefix="haijunbot_plugin_dl_", suffix=".tar.gz"
                )[1]
                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                source_path = download_path
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Failed to download plugin: {str(e)}")
                return False

        source = Path(source_path).resolve()

        if not source.exists():
            PrettyOutput.auto_print(f"❌ Plugin source path does not exist: {source_path}")
            return False

        # Get the plugins directory under the HaijunBot data directory
        data_dir = Path(get_data_dir())
        plugins_dir = data_dir / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        # Temp directory used to process archives
        temp_dir = None
        plugin_source_dir = None

        # Determine the source type: directory or file
        if source.is_dir():
            # It is a directory directly
            plugin_source_dir = source
        elif source.is_file():
            # It is an archive, needs extraction
            # Use suffixes to get the full suffix list and correctly recognize compound suffixes like .tar.gz
            suffixes = [s.lower() for s in source.suffixes]
            is_zip = ".zip" in suffixes
            is_tar = ".tar" in suffixes or ".tgz" in suffixes

            if not is_zip and not is_tar:
                PrettyOutput.auto_print(
                    "❌ Unsupported file format, only .tar/.tar.gz/.tgz/.zip are supported"
                )
                return False

            # Create a temp directory for extraction
            temp_dir = tempfile.mkdtemp(prefix="haijunbot_plugin_")

            if is_zip:
                with zipfile.ZipFile(source, "r") as zf:
                    zf.extractall(temp_dir)
            else:  # tar formats (including .tar.gz, .tgz)
                with tarfile.open(source, "r:*") as tf:
                    # Use filter='data' to prevent path traversal attacks (CVE-2007-4559)
                    tf.extractall(temp_dir, filter="data")

            # After extraction, find the directory containing config.yaml
            extracted_items = list(Path(temp_dir).iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                # Only one directory, use it directly
                plugin_source_dir = extracted_items[0]
            else:
                # Multiple files/directories, use the temp directory itself
                plugin_source_dir = Path(temp_dir)
        else:
            PrettyOutput.auto_print("❌ Invalid source path type")
            return False

        # Verify whether it contains config.yaml
        config_file = plugin_source_dir / "config.yaml"
        if not config_file.exists():
            PrettyOutput.auto_print("❌ Plugin is missing the config.yaml file")
            # Clean up the temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return False

        # Read config.yaml to get the plugin name and version
        plugin_version = None
        plugin_dependencies = None
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_content = yaml.safe_load(f)
                if isinstance(config_content, dict):
                    plugin_name = config_content.get("name", None)
                    plugin_version = config_content.get("version", None)
                    plugin_dependencies = config_content.get("dependencies", None)
                else:
                    plugin_name = None
        except Exception:
            plugin_name = None

        # If there is no name field, use the source directory/filename
        if not plugin_name:
            if source.is_dir():
                plugin_name = source.name
            else:
                # Use the filename (without extension)
                plugin_name = source.stem
                # If it is .tar.gz, two extensions need to be removed
                if plugin_name.endswith(".tar"):
                    plugin_name = plugin_name[:-4]

        # Security handling: keep only the filename part to prevent path traversal attacks
        plugin_name = Path(plugin_name).name

        # Target install directory
        target_dir = plugins_dir / plugin_name

        # Dependency check: dependencies declared by the plugin must be installed and version-compatible.
        # For plugins dependencies with a url, auto-download and install when not installed; those without a url or that fail to install are still rejected.
        if plugin_dependencies:
            # Initialize the set of dependencies being installed (to prevent recursive dependency loops, e.g. A->B->A)
            if _installing_deps is None:
                _installing_deps = set()
            if plugin_name in _installing_deps:
                PrettyOutput.auto_print(
                    f"❌ Circular dependency detected: plugin {plugin_name} is already being installed, aborting to avoid an infinite loop"
                )
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return False
            _installing_deps.add(plugin_name)

            missing_deps = _check_dependencies(plugin_dependencies, plugins_dir)
            auto_install_failed = False
            for dep in missing_deps:
                # Only attempt auto-install for plugin dependencies with a url
                if dep.get("type") == "plugins" and dep.get("url"):
                    PrettyOutput.auto_print(
                        f"⬇️  Unsatisfied plugin dependency [{dep['name']}] detected, auto-installing..."
                    )
                    dep_url = _resolve_plugin_dep_url(
                        dep.get("url"), dep.get("tag"), dep.get("branch")
                    )
                    ok = install_plugin(
                        dep_url,
                        source_url=dep_url,
                        _installing_deps=_installing_deps,
                    )
                    if not ok:
                        PrettyOutput.auto_print(
                            f"❌ Failed to auto-install plugin dependency: {dep['name']}"
                        )
                        auto_install_failed = True
                    continue
                # Plugin dependencies without a url, or python/commands dependencies, cannot be auto-installed; report an error
                type_labels = {
                    "plugins": "plugin",
                    "python": "Python package",
                    "commands": "system command",
                }
                label = type_labels.get(dep.get("type"), "dependency")
                PrettyOutput.auto_print(
                    f"❌ Unsatisfied dependency: [{label}] {dep['name']} "
                    f"(requires {dep['version_constraint']}): {dep['reason']}"
                )
                auto_install_failed = True

            # Re-check dependencies: they may still be unsatisfied after auto-install (e.g. version incompatible, url-less dependency)
            if auto_install_failed or _check_dependencies(
                plugin_dependencies, plugins_dir
            ):
                PrettyOutput.auto_print(
                    f"❌ Dependency check failed: the following dependencies of plugin {plugin_name} are unsatisfied"
                )
                for dep in _check_dependencies(plugin_dependencies, plugins_dir):
                    type_labels = {
                        "plugins": "plugin",
                        "python": "Python package",
                        "commands": "system command",
                    }
                    label = type_labels.get(dep.get("type"), "dependency")
                    PrettyOutput.auto_print(
                        f"  - [{label}] {dep['name']} (requires {dep['version_constraint']}): {dep['reason']}"
                    )
                # Clean up the temp directory
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return False

        # If the target directory already exists, perform version control: a higher version can overwrite a lower version, a lower version cannot overwrite a higher version
        if target_dir.exists():
            installed_version = None
            installed_config_file = target_dir / "config.yaml"
            if installed_config_file.exists():
                try:
                    with open(installed_config_file, "r", encoding="utf-8") as f:
                        installed_config = yaml.safe_load(f)
                        if isinstance(installed_config, dict):
                            installed_version = installed_config.get("version", None)
                except Exception:
                    installed_version = None

            # Force overwrite: ignore version comparison
            if force:
                PrettyOutput.auto_print(
                    f"⚠️  Force-overwriting plugin directory: {target_dir} (ignoring version comparison)"
                )
                _remove_plugin_dir(target_dir)
            # Compare when both sides have a version number
            elif installed_version and plugin_version:
                cmp = _compare_versions(plugin_version, installed_version)
                if cmp is not None and cmp < 0:
                    PrettyOutput.auto_print(
                        f"❌ Install rejected: the new version v{plugin_version} is lower than the installed version "
                        f"v{installed_version} (plugin {plugin_name})"
                    )
                    # Clean up the temp directory
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    return False
                if cmp is not None and cmp >= 0:
                    PrettyOutput.auto_print(
                        f"⚠️  Plugin directory already exists, will overwrite: {target_dir} "
                        f"(v{installed_version} -> v{plugin_version})"
                    )
                else:
                    # Version cannot be parsed, conservatively allow overwrite (maintain backward compatibility)
                    PrettyOutput.auto_print(f"⚠️  Plugin directory already exists, will overwrite: {target_dir}")
                _remove_plugin_dir(target_dir)
            else:
                # The installed plugin has no version number (old format) or the new plugin has no version number, allow overwrite for backward compatibility with old plugins
                PrettyOutput.auto_print(f"⚠️  Plugin directory already exists, will overwrite: {target_dir}")
                _remove_plugin_dir(target_dir)

        # Install method: create a symlink for a local directory source (local code changes take effect immediately),
        # while archive/URL extracted artifacts are still copied (no need for continuous local updates).
        # Criterion source.is_dir(): a local directory source matches directly; for archive/URL scenarios
        # source is a file (a downloaded file or archive), plugin_source_dir is the extraction temp directory,
        # the condition is not met, so copytree is still used.
        if source.is_dir():
            os.symlink(source, target_dir)
        else:
            shutil.copytree(plugin_source_dir, target_dir)

        # Record the source URL (used by the upgrade mechanism). Do not write a marker file for symlink installs:
        # target_dir is a symlink, writing would follow the link and land in the local source directory, polluting the user's source;
        # whether it is a symlink install can be determined with os.path.islink(target_dir).
        if source_url and not source.is_dir():
            try:
                with open(target_dir / ".source", "w", encoding="utf-8") as f:
                    f.write(source_url)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.utils", function="install_plugin"
                )

        # Clean up the temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        # Clean up the downloaded temp file
        if download_path and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except Exception:
                pass

        PrettyOutput.auto_print(f"✅ Plugin installed successfully: {plugin_name} -> {target_dir}")
        return True

    except Exception as e:
        PrettyOutput.auto_print(f"❌ Plugin install failed: {str(e)}")
        # Clean up the temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.utils", function="install_plugin"
                )
                pass
        return False


def list_plugins() -> None:
    """
    List all installed plugins

    Features:
        Scan the ~/.haijunbot/plugins/ directory, read each plugin's config.yaml,
        and format and output plugin information (name, description, version, etc.)
    """
    from pathlib import Path
    import yaml
    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.output import PrettyOutput

    plugins_dir = Path(get_data_dir()) / "plugins"

    if not plugins_dir.exists():
        PrettyOutput.auto_print("📦 No plugins installed")
        return

    # Get all plugin directories
    plugin_dirs = [d for d in plugins_dir.iterdir() if d.is_dir()]

    if not plugin_dirs:
        PrettyOutput.auto_print("📦 No plugins installed")
        return

    PrettyOutput.auto_print(f"📦 Installed plugins ({len(plugin_dirs)}):\n")

    for plugin_dir in sorted(plugin_dirs):
        config_file = plugin_dir / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if isinstance(config, dict):
                        name = config.get("name", plugin_dir.name)
                        description = config.get("description", "No description")
                        version = config.get("version", "Unknown version")
                        PrettyOutput.auto_print(f"  • {name} (v{version})")
                        PrettyOutput.auto_print(f"    {description}")
                        PrettyOutput.auto_print("")
                    else:
                        PrettyOutput.auto_print(f"  • {plugin_dir.name}")
                        PrettyOutput.auto_print("    Invalid config file format")
                        PrettyOutput.auto_print("")
            except Exception as e:
                PrettyOutput.auto_print(f"  • {plugin_dir.name}")
                PrettyOutput.auto_print(f"    Failed to read config: {str(e)}")
                PrettyOutput.auto_print("")
        else:
            PrettyOutput.auto_print(f"  • {plugin_dir.name}")
            PrettyOutput.auto_print("    ⚠️ Missing config.yaml")
            PrettyOutput.auto_print("")


def list_plugins_info() -> List[dict]:
    """
    List all plugins and return structured information (for use by the HTTP API).

    Enumerates both:
    - Built-in plugins: the source built-in directory builtin/plugins/ (builtin: true, not copied, cannot be uninstalled/upgraded)
    - External plugins: the <data_dir>/plugins/ directory
    If a plugin name exists in both the built-in directory and the data directory, the built-in one takes precedence (the data directory copy is skipped).

    Returns:
        list[dict]: Each element is a plugin info dict with fields:
            - name: Plugin name
            - description: Description
            - version: Version
            - dependencies: Dependency declaration (if present)
            - frontend: Frontend extension declaration (if present)
            - builtin: Whether it is a built-in plugin
            - capabilities: Capability list
            - installed: Whether it is available (the directory exists and the config is readable)
    """
    import yaml
    from pathlib import Path
    from haijunbot.haijunbot_utils.config import get_data_dir

    # Collect the built-in plugin directory (builtin/plugins/)
    builtin_dirs: List[Path] = []
    try:
        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

        builtin_dir = _get_builtin_dir()
        if builtin_dir is not None:
            builtin_plugins_dir = builtin_dir / "plugins"
            if builtin_plugins_dir.exists() and builtin_plugins_dir.is_dir():
                builtin_dirs = [
                    d
                    for d in builtin_plugins_dir.iterdir()
                    if d.is_dir() and (d / "config.yaml").exists()
                ]
    except Exception:
        builtin_dirs = []

    # Collect the external plugin directory (data_dir/plugins/), skipping copies with the same name as built-in ones
    plugins_dir = Path(get_data_dir()) / "plugins"
    external_dirs: List[Path] = []
    if plugins_dir.exists() and plugins_dir.is_dir():
        builtin_names = {d.name for d in builtin_dirs}
        external_dirs = [
            d
            for d in plugins_dir.iterdir()
            if d.is_dir() and d.name not in builtin_names
        ]

    result: List[dict] = []
    for plugin_dir in sorted(builtin_dirs + external_dirs):
        config_file = plugin_dir / "config.yaml"
        is_builtin = plugin_dir in builtin_dirs
        info: dict = {
            "name": plugin_dir.name,
            "description": "",
            "version": None,
            "dependencies": None,
            "frontend": None,
            "builtin": is_builtin,
            "capabilities": [],
            "installed": False,
        }
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if isinstance(config, dict):
                    info["name"] = config.get("name", plugin_dir.name)
                    info["description"] = config.get("description", "")
                    info["version"] = config.get("version", None)
                    info["dependencies"] = config.get("dependencies", None)
                    info["frontend"] = config.get("frontend", None)
                    info["builtin"] = is_builtin or bool(config.get("builtin", False))
                    info["capabilities"] = _build_plugin_capabilities(config, plugin_dir)
                    info["installed"] = True
            except Exception:
                info["installed"] = False
        result.append(info)
    return result


def _resolve_plugin_dir(plugin_dir) -> "Path | None":
    """Normalize the plugin directory argument into a Path; returns None when invalid."""
    from pathlib import Path

    if plugin_dir is None:
        return None
    try:
        return Path(plugin_dir)
    except Exception:
        return None


def _collect_plugin_files(dirs, plugin_dir, extensions) -> list:
    """Collect the actual files under the extension point directory (used to display specific rules/tools).

    dirs: The directory list in config.yaml (may contain the {{plugin_dir}} placeholder or relative/absolute paths)
    plugin_dir: The plugin directory, used to resolve the {{plugin_dir}} placeholder and relative paths
    extensions: A tuple of file extensions of interest, e.g. (".md",) or (".py",)
    """
    import os
    from pathlib import Path

    base = _resolve_plugin_dir(plugin_dir)
    if base is None:
        return []
    if not isinstance(dirs, list):
        return []
    files: list = []
    seen: set = set()
    for d in dirs:
        if not isinstance(d, str):
            continue
        p = d.replace("{{plugin_dir}}", str(base))
        if not os.path.isabs(p):
            p = str(base / p)
        p_path = Path(p)
        if not p_path.exists() or not p_path.is_dir():
            continue
        for f in sorted(p_path.iterdir()):
            if f.is_file() and f.suffix in extensions and str(f) not in seen:
                seen.add(str(f))
                files.append(f)
    return files


def _read_rule_meta(rule_file):
    """Parse the YAML front matter of a rule Markdown, returning (name, description).

    A rule file starts with `---` and the front matter contains name/description.
    Returns (None, None) when parsing fails or name is missing.
    """
    try:
        text = rule_file.read_text(encoding="utf-8")
    except Exception:
        return None, None
    if not text.startswith("---"):
        return None, None
    end = text.find("---", 3)
    if end == -1:
        return None, None
    try:
        import yaml

        meta = yaml.safe_load(text[3:end])
    except Exception:
        return None, None
    if not isinstance(meta, dict):
        return None, None
    return meta.get("name"), meta.get("description")


def _read_tool_meta(tool_file):
    """Parse the class name/description attributes of a tool Python module, returning (name, description).

    The tool class defines name/description string attributes within the module; returns (None, None) when parsing fails or name is missing.
    """
    import ast

    try:
        tree = ast.parse(tool_file.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        name = None
        desc = None
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "name" and isinstance(stmt.value, ast.Constant):
                    name = stmt.value.value
                elif target.id == "description" and isinstance(stmt.value, ast.Constant):
                    desc = stmt.value.value
        if name:
            return name, desc
    return None, None


def _read_agent_meta(agent_file):
    """Parse the name/description of an Agent definition YAML, returning (name, description).

    The Agent definition file is YAML with YAML front matter, containing name/description.
    Returns (None, None) when parsing fails or name is missing.
    """
    try:
        import yaml

        data = yaml.safe_load(agent_file.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    if not isinstance(data, dict):
        return None, None
    return data.get("name"), data.get("description")


def _build_plugin_capabilities(config: dict, plugin_dir=None) -> List[dict]:
    """
    Build the capability list from the plugin's config.yaml (for frontend display, so users understand which operations the plugin provides).

    Automatically derives from existing capability fields, and merges custom capabilities declared
    by the plugin author through the top-level capabilities field (such as event hooks, @builtin commands, etc.).

    Rules and tools further read the actual files to display the specific rule names/tool names and their purposes,
    so users know what the plugin actually provides and how to use it.

    Args:
        config: The dict parsed from the plugin's config.yaml
        plugin_dir: The plugin directory (Path or str), used to resolve relative paths and read rule/tool files

    Returns:
        list[dict]: Each element is {type, name, description}, where type takes the values:
            rules / tools / agents / orchestration / frontend / replace_map / custom
    """
    capabilities: List[dict] = []

    def _append(ctype: str, name: str, desc: str) -> None:
        capabilities.append({"type": ctype, "name": name, "description": desc})

    # Rules: read the actual files under the rules directory, display the specific rule names and trigger scenarios
    rules = config.get("rules_load_dirs")
    if rules:
        rule_files = _collect_plugin_files(rules, plugin_dir, (".md",))
        if rule_files:
            for rule_file in rule_files:
                name, desc = _read_rule_meta(rule_file)
                if name:
                    _append(
                        "rules",
                        f"Rule: {name}",
                        desc or f"Rule file {rule_file.name}, automatically discoverable and loadable by the Agent",
                    )
        else:
            _append(
                "rules",
                "Rules",
                f"Provides {len(rules)} rules directories, automatically discoverable and loadable by the Agent",
            )
    # Tools: read the actual files under the tools directory, display the specific tool names and purposes
    tools = config.get("tool_load_dirs")
    if tools:
        tool_files = _collect_plugin_files(tools, plugin_dir, (".py",))
        if tool_files:
            for tool_file in tool_files:
                name, desc = _read_tool_meta(tool_file)
                if name:
                    _append(
                        "tools",
                        f"Tool: {name}",
                        desc or f"Tool module {tool_file.name}, registers callable tools",
                    )
        else:
            _append(
                "tools",
                "Tools",
                f"Provides {len(tools)} tools directories, registering callable tools",
            )
    # Agent definitions: read the actual YAML under the agents directory, display the specific role names and responsibilities
    agents = config.get("agent_definition_dirs")
    if agents:
        agent_files = _collect_plugin_files(agents, plugin_dir, (".yaml", ".yml"))
        if agent_files:
            for agent_file in agent_files:
                name, desc = _read_agent_meta(agent_file)
                if name:
                    _append(
                        "agents",
                        f"Agent: {name}",
                        desc or f"Agent definition file {agent_file.name}, selectable by the built-in config selector",
                    )
        else:
            _append(
                "agents",
                "Agent definitions",
                f"Provides {len(agents)} Agent definition directories, selectable by the built-in config selector",
            )
    # Orchestration files
    orchestration = config.get("orchestration")
    if isinstance(orchestration, list):
        for entry in orchestration:
            if isinstance(entry, dict):
                name = entry.get("name") or entry.get("id")
                if name:
                    _append(
                        "orchestration",
                        f"Orchestration: {name}",
                        str(entry.get("description", "") or "Orchestration pipeline template"),
                    )
    # Frontend extensions
    frontend = config.get("frontend")
    if isinstance(frontend, dict):
        frontend_parts = []
        for key in ("admin_tabs", "sidebar_views", "tool_panels"):
            if frontend.get(key):
                frontend_parts.append(key)
        if frontend_parts:
            _append(
                "frontend",
                "Frontend extensions",
                "Provides frontend UI extensions: " + ", ".join(frontend_parts),
            )
    # Custom capabilities declared by the plugin author (event hooks, @builtin commands, etc.)
    custom = config.get("capabilities")
    if isinstance(custom, list):
        for entry in custom:
            if isinstance(entry, dict):
                name = entry.get("name")
                if name:
                    _append(
                        "custom",
                        str(name),
                        str(entry.get("description", "") or ""),
                    )
    # Command templates (replace_map): when the user types <tag> in the input box, it is replaced with the corresponding command template
    replace_map = config.get("replace_map")
    if isinstance(replace_map, dict):
        for tag, info in replace_map.items():
            if not isinstance(info, dict):
                continue
            desc = str(info.get("description", "") or "")
            append_mode = info.get("append")
            if append_mode:
                desc = (desc + " (appended to the current input)") if desc else "Appended to the current input"
            _append(
                "replace_map",
                f"Command <{tag}>",
                desc or f"Typing <{tag}> triggers the corresponding command template",
            )

    return capabilities


def _is_builtin_plugin(plugin_dir) -> bool:
    """
    Determine whether the plugin directory is a built-in plugin.

    Built-in plugin detection uses a double safeguard:
    1. The plugin's config.yaml declares builtin: true;
    2. The plugin name exists in the source built-in directory builtin/plugins/<name> (compatible with already-installed old copies,
       so even if the copy's config.yaml has no builtin marker, it can still be identified as a built-in plugin).

    Args:
        plugin_dir: The plugin directory (Path or str)

    Returns:
        bool: Returns True for a built-in plugin, otherwise False
    """
    import yaml
    from pathlib import Path

    plugin_dir = Path(plugin_dir)
    plugin_name = plugin_dir.name

    # Method 1: config.yaml declares builtin: true
    config_file = plugin_dir / "config.yaml"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if isinstance(config, dict) and config.get("builtin", False):
                return True
        except Exception:
            pass

    # Method 2: the plugin name exists in the source built-in directory builtin/plugins/<name>
    try:
        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

        builtin_dir = _get_builtin_dir()
        if builtin_dir is not None:
            builtin_plugin_dir = builtin_dir / "plugins" / plugin_name
            if builtin_plugin_dir.exists() and builtin_plugin_dir.is_dir():
                return True
    except Exception:
        pass

    return False


def list_plugin_orchestrations() -> List[dict]:
    """
    List the orchestration pipeline templates declared by all plugins (for the frontend orchestration feature).

    Scans both built-in plugins (builtin/plugins/) and external plugins (<data_dir>/plugins/),
    reads each plugin's config.yaml, renders the {{plugin_dir}} template variable, then extracts
    the orchestration declarations and returns the template list.

    Returns:
        list[dict]: Each element is an orchestration template info dict with fields:
            - plugin: Source plugin name
            - name: Template name
            - description: Template description
            - file: Absolute path of the orchestration file ({{plugin_dir}} already rendered)
    """
    import yaml
    from pathlib import Path
    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.template_utils import render_plugin_config_template

    # Collect the built-in plugin directory (builtin/plugins/)
    builtin_dirs: List[Path] = []
    try:
        from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

        builtin_dir = _get_builtin_dir()
        if builtin_dir is not None:
            builtin_plugins_dir = builtin_dir / "plugins"
            if builtin_plugins_dir.exists() and builtin_plugins_dir.is_dir():
                builtin_dirs = [
                    d
                    for d in builtin_plugins_dir.iterdir()
                    if d.is_dir() and (d / "config.yaml").exists()
                ]
    except Exception:
        builtin_dirs = []

    # Collect the external plugin directory (data_dir/plugins/), skipping copies with the same name as built-in ones
    plugins_dir = Path(get_data_dir()) / "plugins"
    external_dirs: List[Path] = []
    if plugins_dir.exists() and plugins_dir.is_dir():
        builtin_names = {d.name for d in builtin_dirs}
        external_dirs = [
            d
            for d in plugins_dir.iterdir()
            if d.is_dir() and d.name not in builtin_names
        ]

    result: List[dict] = []
    for plugin_dir in sorted(builtin_dirs + external_dirs):
        config_file = plugin_dir / "config.yaml"
        if not config_file.exists():
            continue
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config_content = f.read()
            rendered = render_plugin_config_template(config_content, str(plugin_dir))
            config = yaml.safe_load(rendered)
            if not isinstance(config, dict):
                continue
            entries = config.get("orchestration")
            if not isinstance(entries, list):
                continue
            plugin_name = str(config.get("name") or plugin_dir.name)
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("id")
                file_path = entry.get("file") or entry.get("path")
                if not name or not file_path:
                    continue
                result.append(
                    {
                        "plugin": plugin_name,
                        "name": str(name),
                        "description": str(entry.get("description", "") or ""),
                        "file": str(file_path),
                    }
                )
        except Exception:
            continue
    return result


def uninstall_plugin(plugin_name: str) -> bool:
    """
    Uninstall a plugin

    Args:
        plugin_name: Plugin name

    Returns:
        bool: Returns True on successful uninstall, False on failure
    """
    import os
    from pathlib import Path
    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.output import PrettyOutput

    # Security handling: keep only the filename part to prevent path traversal attacks
    plugin_name = Path(plugin_name).name

    plugins_dir = Path(get_data_dir()) / "plugins"
    plugin_dir = plugins_dir / plugin_name

    # Use lexists to determine existence: if the local source of a symlink-installed plugin is deleted, the link dangles,
    # and exists()/is_dir() return False, making uninstall impossible; lexists does not follow the link.
    if not os.path.lexists(plugin_dir):
        PrettyOutput.auto_print(f"⚠️ Plugin does not exist: {plugin_name}")
        return False

    if not plugin_dir.is_dir():
        PrettyOutput.auto_print(f"⚠️ Plugin path is not a directory: {plugin_dir}")
        return False

    # Defensively refuse to uninstall built-in plugins
    if _is_builtin_plugin(plugin_dir):
        PrettyOutput.auto_print(f"⛔ Built-in plugins cannot be uninstalled: {plugin_name}")
        return False

    # Reversible effect: before uninstalling, revoke the tools/rules registered by this plugin (if the current process has loaded
    # ToolRegistry / RulesManager instances, actually remove them; otherwise just clear the registration, since the directory
    # deletion means they will naturally not be loaded again on the next startup).
    try:
        from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry

        registry = PluginRegistry.instance()
        if registry.has_plugin(plugin_name):
            result = registry.revoke_plugin(plugin_name)
            if result.get("tools") or result.get("rules"):
                PrettyOutput.auto_print(
                    f"↩️  Revoked resources registered by plugin '{plugin_name}'"
                    f" (tools: {result.get('tools', 0)}, rules: {result.get('rules', 0)})"
                )
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Failed to revoke plugin resources (continuing uninstall): {str(e)}")

    try:
        # For a symlink, delete only the link itself, not the local source it points to
        _remove_plugin_dir(plugin_dir)
        PrettyOutput.auto_print(f"✅ Plugin uninstalled: {plugin_name}")
        return True
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to uninstall plugin: {str(e)}")
        return False


def upgrade_plugin(plugin_name: str) -> bool:
    """
    Upgrade a plugin

    Re-download the latest version from the plugin's recorded source URL and overwrite-install.
    Only supports plugins installed via URL (a .source file exists).

    Args:
        plugin_name: Plugin name

    Returns:
        bool: Returns True on successful upgrade, False on failure
    """
    import os
    from pathlib import Path
    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.output import PrettyOutput

    # Security handling: keep only the filename part to prevent path traversal attacks
    plugin_name = Path(plugin_name).name

    plugins_dir = Path(get_data_dir()) / "plugins"
    plugin_dir = plugins_dir / plugin_name

    if not plugin_dir.exists():
        PrettyOutput.auto_print(f"⚠️ Plugin does not exist: {plugin_name}")
        return False

    # Defensively refuse to upgrade built-in plugins
    if _is_builtin_plugin(plugin_dir):
        PrettyOutput.auto_print(f"⛔ Built-in plugins cannot be upgraded: {plugin_name}")
        return False

    # Plugin installed via a local symlink: source updates take effect immediately, no upgrade needed (upgrading would accidentally delete the local source)
    if os.path.islink(plugin_dir):
        PrettyOutput.auto_print(
            f"ℹ️  Plugin {plugin_name} was installed via a local symlink; source updates take effect immediately, no upgrade needed"
        )
        return False

    # Read the source URL
    source_file = plugin_dir / ".source"
    if not source_file.exists():
        PrettyOutput.auto_print(f"⚠️ Plugin {plugin_name} was not installed via URL and cannot be upgraded")
        return False

    try:
        source_url = source_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to read plugin source: {str(e)}")
        return False

    if not source_url:
        PrettyOutput.auto_print(f"⚠️ Plugin {plugin_name} has no recorded source URL and cannot be upgraded")
        return False

    PrettyOutput.auto_print(f"⬆️  Upgrading plugin {plugin_name} (source: {source_url})")
    return install_plugin(source_url, force=True, source_url=source_url)


__all__ = [
    "join_prompts",
    "is_auto_complete",
    "normalize_next_action",
    "fix_tool_call_with_llm",
    "install_plugin",
    "uninstall_plugin",
    "upgrade_plugin",
]
