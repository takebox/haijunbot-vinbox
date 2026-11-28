import json
import importlib
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Protocol
from typing import Tuple
from typing import Set

import yaml  # type: ignore[import-untyped]

from haijunbot.haijunbot_mcp import McpClient
from haijunbot.haijunbot_mcp.sse_mcp_client import SSEMcpClient
from haijunbot.haijunbot_mcp.stdio_mcp_client import StdioMcpClient
from haijunbot.haijunbot_mcp.streamable_mcp_client import StreamableMcpClient
from haijunbot.haijunbot_platform.openai import PARSE_ERROR_KEY
from haijunbot.haijunbot_tools.base import Tool
from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry
from haijunbot.haijunbot_utils.config import calculate_token_limit
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import read_text_file
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import get_tool_load_dirs

# -*- coding: utf-8 -*-
from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import daily_check_git_updates
from haijunbot.haijunbot_utils.utils import extract_json_from_text
from haijunbot.haijunbot_utils.utils import is_context_overflow


# Module-level builtin tool cache: builtin tool classes are stateless, can be safely reused across ToolRegistry instances, 
# avoid re-importing heavy modules like sub_code_agent/code_agent on each instantiation (significantly slows down
# scenarios like test_tool_parsing that frequently create ToolRegistry instances).
_BUILTIN_TOOLS_CACHE: Optional[Dict[str, Tool]] = None


tool_call_help = """
## Tool Calling Guide (Markdown)

**Tool Call Format (Json)**
```json
{
  "want": "Information to extract from execution results",
  "name": "Tool name",
  "arguments": {
    "param1": "Value1",
    "param2": "Value2"
  }
}
```

**Scheduled Execution (Optional)**
Add any of the following parameters in arguments to create a scheduled task:
- `after`: Delayed execution (seconds), e.g. `"after": 10` executes after 10 seconds
- `at`: Scheduled execution (ISO time format), e.g. `"at": "2024-12-31T23:59:59"`
- `loop`: Recurring execution (seconds), e.g. `"loop": 60` executes every 60 seconds

```json
// Example: execute script after 10 seconds
{
  "name": "execute_script",
  "arguments": {
    "script_content": "echo hello",
    "after": 10
  }
}
```

**JSON Format Features**
- String quotes: double or single quotes allowed
- Trailing commas: commas allowed after the last element in objects/arrays
- Comments: supports // single-line or /* */ multi-line comments

**Key Rules**
1. You can call one or more tools at once; multiple calls between them must **not depend on each other** (results/side effects of earlier tools cannot be inputs to later tools). If there are dependencies, execute the dependent tools first, wait for results, then proceed
2. If information is insufficient, ask the user, do not proceed without complete information
3. Scheduled params (after/at/loop) automatically create scheduled tasks, tools do not execute immediately

**Multiple Tool Calls**
- Supports calling multiple tools at once, Each tool call is an independent JSON object:
  ```json
  {"name": "tool1", "arguments": {...}}
  ```
  ```json
  {"name": "tool2", "arguments": {...}}
  ```
- **Important Limitations**: multiple tool calls between them must **have no dependencies**
  - Tool A's execution results cannot be inputs to Tool B
  - Tool B cannot depend on side effects produced by Tool A (file creation, state changes, etc.)
  - If tools have dependencies, they must be called separately, execute dependent tools first, wait for results, then call subsequent tools
- Multiple tool calls execute in order; results from each tool are merged and returned

**Common Errors**
- Calling multiple dependent tools simultaneously (violates independence requirement)
- Assuming tool results
- JSON format error
- JSON object missing name or arguments field
"""


# Pre-select Top-N: after coarse filtering by task-context keywords, output only the top-N tools to save prompt tokens
_TOOL_PRESELECT_TOP_N = 50

# Pre-select threshold: only enable keyword pre-selection when the tool count exceeds this value (to avoid affecting small tool sets)
_TOOL_PRESELECT_THRESHOLD = 50

# Pre-select stop words (single characters/English function words removed, kept after jieba segmentation)
_TOOL_PRESELECT_STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "and",
    "or",
    "for",
    "with",
    "in",
    "on",
    "at",
    "by",
    "from",
    "as",
    "if",
    "then",
    "else",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "we",
    "you",
    "i",
    "my",
    "your",
    "our",
    "please",
    "use",
    "using",
    "do",
    "not",
}


def _preselect_tools(
    task_context: str,
    tools: List[Dict[str, Any]],
    top_n: int = _TOOL_PRESELECT_TOP_N,
) -> List[Dict[str, Any]]:
    """Coarsely filter tools by task-context keywords and keep the top-N with the highest match count.

     Use jieba to segment the task-context keywords, count how many appear in the tool name/description string, 
     and keep the top_n with the highest scores. Used to compress the prompt in the "many tools, single call" scenario.
    After coarse filtering, the result still goes through the pre-filter.

    Note: this function does not change the Agent's available tool set and only affects the tools shown in the prompt:
    - Keyword source is the current-round task context / task / goal; if keywords cannot be extracted, all tools are returned;
    - Pre-selection affects only the prompt and not execute_tool (execute_tool can access all _all_tools).

    Returns:
         The tool list after pre-selection. If pre-selection fails (no keyword match / exception), all tools are returned.
    """
    try:
        import jieba

        # Segment the task context into keywords (single characters and stop words removed)
        keywords = [
            w.strip()
            for w in jieba.cut(task_context)
            if len(w.strip()) > 1
            and w.strip().lower() not in _TOOL_PRESELECT_STOP_WORDS
        ]
        if not keywords:
            return tools

        # Score each tool (keyword matches + name/description)
        scored: List[Tuple[int, Dict[str, Any]]] = []
        for tool in tools:
            haystack = (f"{tool.get('name', '')} {tool.get('description', '')}").lower()
            score = sum(1 for kw in keywords if kw.lower() in haystack)
            scored.append((score, tool))

        # Sort by score; if no tool matches any keyword, keep all tools
        scored.sort(key=lambda x: x[0], reverse=True)
        matched = [tool for score, tool in scored if score > 0]
        if not matched:
            return tools  # No keyword matched, keep all tools 

        # Keep Top-N (only among matched tools)
        return matched[:top_n]
    except Exception:
        return tools  # On exception, do not filter; keep the same behavior as without pre-selection


class OutputHandlerProtocol(Protocol):
    def name(self) -> str: ...

    def can_handle(self, response: str) -> bool: ...

    def prompt(self) -> str: ...

    def handle(self, response: str, agent: Any) -> Tuple[bool, Any]: ...


class ToolRegistry(OutputHandlerProtocol):
    def name(self) -> str:
        return "TOOL_CALL"

    def can_handle(self, response: str) -> bool:
        # Method 1: scan for a standard-format JSON, i.e. a JSON object containing the name and arguments strings (regardless of position)
        for i, ch in enumerate(response):
            if ch == "{":
                json_str, _ = extract_json_from_text(response, i)
                if json_str:
                    try:
                        parsed = json_loads(json_str)
                        if (
                            isinstance(parsed, dict)
                            and "name" in parsed
                            and "arguments" in parsed
                        ):
                            return True
                    except Exception as e:
                        save_exception(
                            e, module="haijunbot_tools.registry", function="can_handle"
                        )
                        continue

        # Method 2: check for a known "name": "tool_name" style format, which must conform to the Tool Call Format
        #  Case 2: must have the "name": "tool_name" format and contain an arguments string
        if self.tools:
            for tool_name in self.tools.keys():
                #  Must satisfy both: "name": "tool_name" and an "arguments" string
                if (
                    f'"name": "{tool_name}"' in response
                    or f'"name":"{tool_name}"' in response
                ):
                    if '"arguments"' in response or '"arguments":' in response:
                        return True

        #  Case 3: plus a complete JSON object  -  contains the name and arguments strings
        tool_call_markers = ["<TOOL_CALL>", "tool_call", "```json"]
        for marker in tool_call_markers:
            if marker in response:
                #  Must contain the name and arguments keys, satisfying the format
                if '"name"' in response and '"arguments"' in response:
                    return True

        # Method 4: the response contains the "name" key (even without quotes), and the quotes may be omitted
        if self.tools:
            for tool_name, tool_info in self.tools.items():
                # The "name" key and its value appear directly in the response
                if '"name"' in response and f"{tool_name}" in response:
                    # Format may be broken or quotes omitted
                    parameters = (
                        tool_info.parameters
                        if hasattr(tool_info, "parameters")
                        else tool_info.get("parameters", {})
                    )
                    if isinstance(parameters, dict):
                        properties = parameters.get("properties", {})
                        if isinstance(properties, dict):
                            for param_name in properties:
                                if f'"{param_name}"' in response:
                                    return True

        # Method 5: parameter-only format - no name string in the JSON, matched by the parameter keys
        # e.g.: {"files": [...]} corresponds to read_code, {"interpreter": "bash", "script_content": "..."} corresponds to execute_script
        if self.tools:
            for i, ch in enumerate(response):
                if ch == "{":
                    json_str, _ = extract_json_from_text(response, i)
                    if json_str:
                        try:
                            parsed = json_loads(json_str)
                            if isinstance(parsed, dict) and "name" not in parsed:
                                json_keys = set(parsed.keys())
                                matched_tools = []
                                for tool_name, tool_info in self.tools.items():
                                    parameters = (
                                        tool_info.parameters
                                        if hasattr(tool_info, "parameters")
                                        else tool_info.get("parameters", {})
                                    )
                                    if isinstance(parameters, dict):
                                        properties = parameters.get("properties", {})
                                        required = parameters.get("required", [])
                                        if isinstance(properties, dict) and isinstance(
                                            required, list
                                        ):
                                            param_keys = set(properties.keys())
                                            # If required fields exist, they must all be in the JSON keys, and the JSON keys must be a subset of the parameters 
                                            if (
                                                required
                                                and all(
                                                    r in json_keys for r in required
                                                )
                                                and json_keys.issubset(param_keys)
                                            ):
                                                matched_tools.append(tool_name)
                                # If exactly one matches, it is considered a tool call 
                                if len(matched_tools) == 1:
                                    return True
                        except Exception as e:
                            save_exception(
                                e, module="haijunbot_tools.registry", function="can_handle"
                            )
                            continue

        # Method 6: special marker + tool name - contains a marker and a matching tool name
        # Scan the response for a special marker and a matching tool name
        # May be in a non-standard format, e.g. "tool_call: read_code\npath: App.vue"
        tool_call_markers = ["tool_call", "<TOOL_CALL>", "function_call", "action_call"]
        has_tool_call_marker = any(marker in response for marker in tool_call_markers)
        if has_tool_call_marker and self.tools:
            for tool_name in self.tools.keys():
                if tool_name in response:
                    return True

        # Method 7: fallback, e.g. when the above rules cannot determine the result
        #  Use _extract_tool_calls to do a complete extraction as the final fallback 
        try:
            results, _, _ = ToolRegistry._extract_tool_calls(response, None)
            if results and any(r.get("name") in self.tools for r in results):
                return True
        except Exception as e:
            save_exception(e, module="haijunbot_tools.registry", function="can_handle")
            pass

        return False

    def prompt(self, task_context: Optional[str] = None) -> str:
        """Build the tool prompt

        Args:
            task_context: optional current task context, used for keyword pre-selection.
                 Keyword pre-selection is enabled only when the number of tools exceeds _TOOL_PRESELECT_THRESHOLD and task_context is provided;
                it affects only the prompt and, if it fails or cannot match, does not affect the final available tools.
        """
        tools = self.get_all_tools()
        if tools:
            from haijunbot.haijunbot_platform.native_tools import _compact_tool_schema

            # Coarse filtering by task-context keywords; affects only the prompt (when a single call has too few tools, none is filtered)
            if task_context and len(tools) > _TOOL_PRESELECT_THRESHOLD:
                tools = _preselect_tools(task_context, tools)
                # Ensure required tools are never dropped by pre-selection (they may not be included)
                prescreened_names = {t.get("name") for t in tools}
                for tool_name in self._required_tools:
                    if (
                        tool_name not in prescreened_names
                        and tool_name in self._all_tools
                    ):
                        tools.append(self._all_tools[tool_name].to_dict())

            tools_prompt = "## Available Tools\n"
            for tool in tools:
                try:
                    tools_prompt += f"- **Tool name**: {tool['name']}\n"
                    tools_prompt += f"  - Description: {tool['description']}\n"
                    tools_prompt += "  - Parameters:\n"
                    tools_prompt += "```json\n"

                    #  The schema may be a string; parse it before use
                    parameters = tool["parameters"]
                    if isinstance(parameters, str):
                        try:
                            parameters = json.loads(parameters)
                        except Exception:
                            parameters = {}
                    parameters = _compact_tool_schema(parameters)

                    # Format as JSON
                    json_params = json.dumps(
                        parameters,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=False,
                    )

                    # Add line by line to avoid trailing format issues
                    for line in json_params.split("\n"):
                        tools_prompt += f"{line.rstrip()}\n"

                    tools_prompt += "```\n"

                except Exception as e:
                    PrettyOutput.auto_print(
                        f"❌ Failed to load tool {tool['name']}: {str(e)}"
                    )
                    continue

            tools_prompt += tool_call_help.rstrip()  # Remove trailing whitespace
            return tools_prompt
        return ""

    def handle(self, response: str, agent: Any) -> Tuple[bool, Any]:
        try:
            #  Call _extract_tool_calls (for details, see the agent implementation) 
            tool_calls, err_msg, auto_completed = self._extract_tool_calls(
                response, agent
            )
            if err_msg:
                # On error, attach usage instructions (consistent with a single <ToolUsage>)
                try:
                    from haijunbot.haijunbot_agent import Agent

                    agent_obj: Agent = agent
                    tool_usage = agent_obj.get_tool_usage_prompt()
                    return False, f"{err_msg}\n\n{tool_usage}"
                except Exception:
                    # Fall back: when the Agent lacks a ToolUsage prompt, attach tool_call_help
                    return False, f"{err_msg}\n\n{tool_call_help}"

            # Multiple Tool Calls
            # Format the tool_calls
            if isinstance(tool_calls, list):
                if len(tool_calls) == 0:
                    result = ""
                elif len(tool_calls) == 1:
                    result = self.handle_tool_calls(tool_calls[0], agent)
                else:
                    # Multiple Tool Calls
                    tool_calls_dict = {}
                    for i, tool_call in enumerate(tool_calls):
                        name = tool_call.get("name", f"unknown_{i}")
                        # e.g. when multiple results are returned, name them with indices
                        if name in tool_calls_dict:
                            base_name = name
                            index = 1
                            while f"{base_name}_{index}" in tool_calls_dict:
                                index += 1
                            name = f"{base_name}_{index}"
                        tool_calls_dict[name] = tool_call
                    result = self.handle_multiple_tool_calls(tool_calls_dict, agent)
            else:
                # Otherwise: format directly (not a list)
                result = self.handle_tool_calls(tool_calls, agent)

            # auto_completed (currently does not auto-complete)
            return False, result
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to handle tool call: {str(e)}")
            from haijunbot.haijunbot_agent import Agent

            agent_final: Agent = agent
            return (
                False,
                f"Tool call handling failed: {str(e)}\n\n{agent_final.get_tool_usage_prompt()}",
            )

    def __init__(self) -> None:
        """Initialize the tool registry"""
        self.tools: Dict[str, Tool] = {}
        # Built-in tool names, not overwritten by user tools
        self._builtin_tool_names: Set[str] = set()
        # External tool sources (tool name -> plugin name), for reversible effects (may be empty)
        self._external_tool_sources: Dict[str, str] = {}
        # Required tools (may not be removable)
        self._required_tools: List[str] = ["execute_script"]
        # Load tools
        self._load_builtin_tools()
        self._load_external_tools()
        self._load_mcp_tools()
        # Apply the tool config filter
        self._apply_tool_config_filter()
        # Register the tool revoker (may be empty), called by PluginRegistry.revoke_plugin 
        PluginRegistry.instance().set_tool_revoker(self.unregister_tools_by_plugin)

    def use_tools(self, name: List[str]) -> None:
        """Use only the specified tools

        Args:
            name: list of tool names to use
        """
        self.tools = {
            tool_name: self.tools[tool_name]
            for tool_name in name
            if tool_name in self.tools
        }

    def dont_use_tools(self, names: List[str]) -> None:
        """Do not use the specified tools

        Args:
            names: list of tool names
        """
        # Filter out the specified tools, but do not drop required tools
        filtered_names = [name for name in names if name not in self._required_tools]
        if filtered_names != names:
            removed_required = [name for name in names if name in self._required_tools]
            PrettyOutput.auto_print(
                f"⚠️ Required tools cannot be removed: {', '.join(removed_required)}"
            )
        self.tools = {
            name: tool
            for name, tool in self.tools.items()
            if name not in filtered_names
        }

    def _apply_tool_config_filter(self) -> None:
        """Apply the tool use/dont-use array rules"""
        # If the filter is fully applied, execute_tool will follow it (otherwise not)
        self._all_tools = self.tools.copy()

        from haijunbot.haijunbot_utils.config import get_tool_dont_use_list
        from haijunbot.haijunbot_utils.config import get_tool_use_list

        # Back up the previous reference
        required_tools_backup: Dict[str, Tool] = {}
        for tool_name in self._required_tools:
            if tool_name in self.tools:
                required_tools_backup[tool_name] = self.tools[tool_name]

        use_list = get_tool_use_list()
        dont_use_list = get_tool_dont_use_list()

        # If a use list is configured, keep only the tools in it 
        if use_list:
            filtered_tools = {}
            missing = []
            for tool_name in use_list:
                if tool_name in self.tools:
                    filtered_tools[tool_name] = self.tools[tool_name]
                else:
                    missing.append(tool_name)
            if missing:
                PrettyOutput.auto_print(
                    "⚠️ The following tools were not found: "
                    + ", ".join(f"'{name}'" for name in missing)
                )
            self.tools = filtered_tools

        # If a dont_use list is configured, remove those tools (excluding required tools)
        if dont_use_list:
            for tool_name in dont_use_list:
                if tool_name in self.tools and tool_name not in self._required_tools:
                    del self.tools[tool_name]

        # Restore required tools (in case the filter above removed them)
        for tool_name in self._required_tools:
            if tool_name in required_tools_backup:
                self.tools[tool_name] = required_tools_backup[tool_name]
            elif tool_name not in self.tools:
                PrettyOutput.auto_print(
                    f"⚠️ Required tool '{tool_name}' cannot be added; it may not exist"
                )

    def _load_mcp_tools(self) -> None:
        """Load MCP tools; config takes priority, falling back to the data directory"""
        from haijunbot.haijunbot_utils.config import get_mcp_config

        # Priority: MCP config
        mcp_configs = get_mcp_config()
        if mcp_configs:
            for config in mcp_configs:
                self.register_mcp_tool_by_config(config)
            return

        # If no config exists, fall back to the rule directory
        mcp_tools_dir = Path(get_data_dir()) / "mcp"
        if not mcp_tools_dir.exists():
            return

        # Load additional files
        PrettyOutput.auto_print(
            "⚠️ Notice: using the old MCP file format for adding; please migrate to the new mcp config format"
        )

        # Read each .yaml file
        error_lines = []
        for file_path in mcp_tools_dir.glob("*.yaml"):
            try:
                content = read_text_file(str(file_path))
                config = yaml.safe_load(content)
                self.register_mcp_tool_by_config(config)
            except Exception as e:
                error_lines.append(f"Failed to load {file_path}: {str(e)}")
        if error_lines:
            PrettyOutput.auto_print("⚠️ " + "\n⚠️ ".join(error_lines))

    def _load_builtin_tools(self) -> None:
        """Load built-in tools (cacheable, avoids repeated import of heavy modules)"""
        global _BUILTIN_TOOLS_CACHE
        tools_dir = Path(__file__).parent

        # Use the cache if available, to avoid repeated import of heavy modules
        if _BUILTIN_TOOLS_CACHE is not None:
            self.tools.update(_BUILTIN_TOOLS_CACHE)
            self._builtin_tool_names = set(_BUILTIN_TOOLS_CACHE.keys())
            return

        # Read each .py file
        for file_path in tools_dir.glob("*.py"):
            # Skip base.py, __init__.py and registry.py
            if file_path.name in ["base.py", "__init__.py", "registry.py"]:
                continue

            self.register_tool_by_file(str(file_path))

        # Treat all previously added tool names as built-in tools
        self._builtin_tool_names = set(self.tools.keys())
        _BUILTIN_TOOLS_CACHE = dict(self.tools)

    def _load_external_tools(self) -> None:
        """Load external tools from haijunbot_data/tools and the configured directories"""
        from haijunbot.haijunbot_utils.config import get_central_tool_repo

        tool_dirs = [str(Path(get_data_dir()) / "tools")] + get_tool_load_dirs()

        # If a central tools repository is configured, add it to the load path
        central_repo = get_central_tool_repo()
        if central_repo:
            # Support local directory paths or Git repository URLs
            expanded = os.path.expanduser(os.path.expandvars(central_repo))
            if os.path.isdir(expanded):
                # Use the local directory directly (supports subdirectories of Git repositories)
                tool_dirs.append(expanded)
            else:
                # The central tools repository is stored at a specific location under the data directory
                central_repo_path = os.path.join(get_data_dir(), "central_tool_repo")
                tool_dirs.append(central_repo_path)

                # Ensure the central tools repository is cloned/updated
                if not os.path.exists(central_repo_path):
                    try:
                        import subprocess

                        subprocess.run(
                            ["git", "clone", central_repo, central_repo_path],
                            check=True,
                        )
                    except Exception as e:
                        PrettyOutput.auto_print(f"❌ Failed to clone central tools repository: {str(e)}")

        # --- Global daily update check (runs in a background thread to avoid blocking) ---
        def check_tool_updates() -> None:
            try:
                daily_check_git_updates(tool_dirs, "tools")
            except Exception:
                # Fail silently, do not affect normal usage
                pass

        threading.Thread(target=check_tool_updates, daemon=True).start()

        for tool_dir in tool_dirs:
            p_tool_dir = Path(tool_dir)
            if not p_tool_dir.exists() or not p_tool_dir.is_dir():
                continue

            # Iterate over all .py files in the directory
            for file_path in p_tool_dir.glob("*.py"):
                # Skip __init__.py
                if file_path.name == "__init__.py":
                    continue

                self.register_tool_by_file(str(file_path))

    def register_mcp_tool_by_config(self, config: Dict[str, Any]) -> bool:
        """Load and register tools from a config dictionary

        Args:
            config: MCP tool config dictionary

        Returns:
            bool: Whether the tool was loaded successfully
        """
        try:
            if "type" not in config:
                PrettyOutput.auto_print(f"⚠️ Config {config.get('name', '')} is missing the type field")
                return False

            # Check the enable flag
            if not config.get("enable", True):
                return False

            name = config.get("name", "mcp")

            # Register resource tools
            def create_resource_list_func(
                client: McpClient,
            ) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
                def execute(arguments: Dict[str, Any]) -> Dict[str, Any]:
                    args = arguments.copy()
                    args.pop("agent", None)
                    args.pop("want", None)
                    ret = client.get_resource_list()

                    return {
                        "success": True,
                        "stdout": json.dumps(ret, ensure_ascii=False, indent=2),
                        "stderr": "",
                    }

                return execute

            def create_resource_get_func(
                client: McpClient,
            ) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
                def execute(arguments: Dict[str, Any]) -> Dict[str, Any]:
                    args = arguments.copy()
                    args.pop("agent", None)
                    args.pop("want", None)
                    if "uri" not in args:
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": "Missing required uri parameter",
                        }
                    ret = client.get_resource(args["uri"])

                    return ret

                return execute

            def create_mcp_execute_func(
                tool_name: str, client: McpClient
            ) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
                def execute(arguments: Dict[str, Any]) -> Dict[str, Any]:
                    args = arguments.copy()
                    args.pop("agent", None)
                    args.pop("want", None)
                    ret = client.execute(tool_name, args)

                    return ret

                return execute

            if config["type"] == "stdio":
                if "command" not in config:
                    PrettyOutput.auto_print(
                        f"⚠️ Config {config.get('name', '')} is missing the command field"
                    )
                    return False
            elif config["type"] == "sse":
                if "base_url" not in config:
                    PrettyOutput.auto_print(
                        f"⚠️ Config {config.get('name', '')} is missing the base_url field"
                    )
                    return False
            elif config["type"] == "streamable":
                if "base_url" not in config:
                    PrettyOutput.auto_print(
                        f"⚠️ Config {config.get('name', '')} is missing the base_url field"
                    )
                    return False
            else:
                PrettyOutput.auto_print(f"⚠️ Unsupported MCP client type: {config['type']}")
                return False

            # Create the MCP client
            mcp_client: McpClient
            if config["type"] == "stdio":
                mcp_client = StdioMcpClient(config)
            elif config["type"] == "sse":
                mcp_client = SSEMcpClient(config)
            elif config["type"] == "streamable":
                mcp_client = StreamableMcpClient(config)
            else:
                raise ValueError(f"Unsupported MCP client type: {config['type']}")

            # Get tool information
            tools = mcp_client.get_tool_list()
            if not tools:
                PrettyOutput.auto_print(
                    f"⚠️ Failed to get tool list from config {config.get('name', '')}"
                )
                return False

            # Register each tool
            for tool in tools:
                # Register the tool
                self.register_tool(
                    name=f"{name}.tool_call.{tool['name']}",
                    description=tool["description"],
                    parameters=tool["parameters"],
                    func=create_mcp_execute_func(tool["name"], mcp_client),
                )

            # Register the resource list tool
            self.register_tool(
                name=f"{name}.resource.get_resource_list",
                description=f"Get the resource list on the {name} MCP server",
                parameters={"type": "object", "properties": {}, "required": []},
                func=create_resource_list_func(mcp_client),
            )

            # Register the get resource tool
            self.register_tool(
                name=f"{name}.resource.get_resource",
                description=f"Get the specified resource on the {name} MCP server",
                parameters={
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string", "description": "URI identifier of the resource"}
                    },
                    "required": ["uri"],
                },
                func=create_resource_get_func(mcp_client),
            )

            return True

        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ Failed to load MCP config {config.get('name', '')}: {str(e)}"
            )
            return False

    def register_tool_by_file(self, file_path: str) -> bool:
        """Load and register tools from the specified file

        Args:
            file_path: Path to the tool file

        Returns:
            bool: Whether the tool was loaded successfully
        """
        try:
            p_file_path = Path(file_path).resolve()  # Get the absolute path
            if not p_file_path.exists() or not p_file_path.is_file():
                PrettyOutput.auto_print(f"❌ File does not exist: {p_file_path}")
                return False

            # Temporarily add the parent directory to sys.path
            parent_dir = str(p_file_path.parent)
            sys.path.insert(0, parent_dir)

            try:
                # Compute the module name for import: tools inside the haijunbot_tools package use the full package path for import,
                # avoiding importing under a top-level module name that would produce a module object different from haijunbot.haijunbot_tools.<name>
                # (module-level singletons/caches would otherwise split, e.g. timer's get_timer_manager).
                stem = p_file_path.stem
                try:
                    if p_file_path.parent.resolve() == Path(__file__).parent.resolve():
                        import_module_name = f"haijunbot.haijunbot_tools.{stem}"
                    else:
                        import_module_name = stem
                except Exception:
                    import_module_name = stem
                module = importlib.import_module(import_module_name)

                # Find tool classes in the module
                tool_found = False
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    # Check whether it is a class and has the necessary attributes
                    if (
                        isinstance(item, type)
                        and hasattr(item, "name")
                        and hasattr(item, "description")
                        and hasattr(item, "parameters")
                        and hasattr(item, "execute")
                        and item.name == stem
                    ):
                        if hasattr(item, "check"):
                            if not item.check():
                                continue

                        # Instantiate the tool class
                        tool_instance = item()

                        # Register the tool (user tool classes may declare interactive=True to require serial execution)
                        self.register_tool(
                            name=tool_instance.name,
                            description=tool_instance.description,
                            parameters=tool_instance.parameters,
                            func=tool_instance.execute,
                            protocol_version=getattr(
                                tool_instance, "protocol_version", "1.0"
                            ),
                            interactive=getattr(tool_instance, "interactive", False),
                        )
                        # Record the source plugin name (inferred when the path contains plugins/<name>/), for later unregistration.
                        # Also explicitly register into PluginRegistry (the source of truth for reversible effects),
                        # so that unregister_tools_by_plugin can precisely undo it.
                        source_plugin = self._infer_source_plugin(p_file_path)
                        if source_plugin:
                            self._external_tool_sources[tool_instance.name] = (
                                source_plugin
                            )
                            PluginRegistry.instance().register_tool(
                                source_plugin, tool_instance.name
                            )
                        tool_found = True
                        break

                if not tool_found:
                    return False

                return True

            finally:
                # Remove the directory from sys.path
                sys.path.remove(parent_dir)

        except Exception as e:
            PrettyOutput.auto_print(
                f"❌ Failed to load tool from {Path(file_path).name}: {str(e)}"
            )
            return False

    @staticmethod
    def _infer_source_plugin(file_path: Path) -> Optional[str]:
        """Infer the source plugin name from the tool file path (reversible-effect source tracking).

        When the file path looks like <...>/plugins/<plugin_name>/tools/xxx.py, return the plugin name,
        otherwise return None (indicating a tool not from a plugin, such as a built-in tool or a tool in the user tools directory).
        """
        try:
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part == "plugins" and i + 1 < len(parts):
                    return parts[i + 1]
        except Exception:
            pass
        return None

    def unregister_tool(self, name: str) -> bool:
        """Undo the registration of the specified tool (reversible effect).

        Remove the specified tool from self.tools and self._all_tools, and clean up the source record.
        Built-in tools (in _builtin_tool_names) will not be removed.

        Args:
            name: Tool name

        Returns:
            bool: Whether the tool was removed
        """
        if name in self._builtin_tool_names:
            return False
        removed = False
        if name in self.tools:
            del self.tools[name]
            removed = True
        if hasattr(self, "_all_tools") and name in self._all_tools:
            del self._all_tools[name]
            removed = True
        self._external_tool_sources.pop(name, None)
        return removed

    def unregister_tools_by_plugin(self, plugin_name: str) -> int:
        """Undo all tools registered by the specified plugin (reversible effect).

        Read the tool names registered by the plugin from PluginRegistry and undo them one by one, while cleaning up
        the plugin's registrations in PluginRegistry.

        Args:
            plugin_name: Plugin name

        Returns:
            int: Number of tools that were undone
        """
        registry = PluginRegistry.instance()
        tool_names = registry.get_plugin_tools(plugin_name)
        count = 0
        for name in tool_names:
            if self.unregister_tool(name):
                count += 1
        # Only clean up the plugin's tool registrations in PluginRegistry (does not affect rule registrations)
        registry.clear_tools(plugin_name)
        return count

    @staticmethod
    def _has_tool_calls_block(content: str) -> bool:
        """Check whether the content contains a tool call JSON"""
        return '"name"' in content and '"arguments"' in content

    @staticmethod
    def _get_long_response_hint(content: str) -> str:
        """Generate the prompt message for a long response

        Args:
            content: Response content

        Returns:
            str: If the response is long, return the prompt message; otherwise return an empty string
        """
        if len(content) > 2048:
            return (
                "\n\n⚠️ Notice: The response content is long (exceeds 2048 characters); it may be context overflow causing tool-call parsing to fail."
                "If this is a file modification (edit_file/edit_file_by_line/write_file) operation,"
                "it is recommended to do it in multiple passes, processing part of the file each time."
            )
        return ""

    @staticmethod
    def _extract_json_from_text(
        text: str, start_pos: int = 0
    ) -> Tuple[Optional[str], int]:
        """Extract a complete JSON object from text (via bracket matching)

        Args:
            text: The text to extract from
            start_pos: Position to start searching

        Returns:
            Tuple[Optional[str], int]:
                - The first element is the extracted JSON string (if found), otherwise None
                - The second element is the position after the end of the JSON
        """
        # Skip whitespace characters
        pos = start_pos
        while pos < len(text) and text[pos] in (" ", "\t", "\n", "\r"):
            pos += 1

        if pos >= len(text):
            return None, pos

        # Check whether it starts with {
        if text[pos] != "{":
            return None, pos

        # Use bracket matching to find the complete JSON object
        brace_count = 0
        in_string = False
        escape_next = False
        string_char = None

        json_start = pos
        for i in range(pos, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if not in_string:
                if char in ('"', "'"):
                    in_string = True
                    string_char = char
                elif char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        # Found the complete JSON object
                        return text[json_start : i + 1], i + 1
            else:
                if char == string_char:
                    in_string = False
                    string_char = None

        return None, len(text)

    @staticmethod
    @staticmethod
    def _fuzzy_extract_tool_json(
        content: str, valid_tool_names: Optional[set] = None
    ) -> List[str]:
        """Broad extraction: search the whole text for JSON objects and check whether they contain name and arguments fields

        Compatible with models that do not output tags according to the spec (e.g. GLM outputs a <TOOL_CALL> prefix instead of standard JSON)

        Args:
            content: The text content to search
            valid_tool_names: Set of valid tool names, used to validate tool calls

        Returns:
            List[str]: List of extracted valid tool-call JSON strings
        """
        results = []
        for i, ch in enumerate(content):
            if ch == "{":
                json_str, end_pos = extract_json_from_text(content, i)
                if json_str is None:
                    continue
                try:
                    json_str = ToolRegistry._clean_extra_markers(json_str)
                    parsed = json_loads(json_str)
                    if (
                        isinstance(parsed, dict)
                        and "name" in parsed
                        and "arguments" in parsed
                    ):
                        # If a set of tool names is provided, validate whether name is a registered tool
                        tool_name = parsed.get("name", "")
                        if valid_tool_names is None or tool_name in valid_tool_names:
                            results.append(json_str)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.registry",
                        function="_fuzzy_extract_tool_json",
                    )
                    continue
        return results

    @staticmethod
    def _clean_extra_markers(text: str) -> str:
        """Clean up extra markers in the text (such as <|tool_call_end|> etc.)

        Args:
            text: The text to clean

        Returns:
            The cleaned text
        """
        # Common extra marker patterns
        extra_markers = [
            r"<\|tool_call_end\|>",
            r"<\|tool_calls_section_end\|>",
            r"<\|.*?\|>",  # Match all markers in the <|...|> format
        ]

        cleaned = text
        for pattern in extra_markers:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        return cleaned.strip()

    @staticmethod
    def _try_llm_fix(content: str, agent: Any, error_msg: str) -> Optional[str]:
        """Attempt to repair the tool-call format using a large model

        Args:
            content: Content containing the erroneous tool call
            agent: Agent instance, used to call the large model
            error_msg: Error message

        Returns:
            Optional[str]: The repaired content, or None if repair failed
        """
        try:
            from haijunbot.haijunbot_agent.utils import fix_tool_call_with_llm

            # Call the common function to perform the repair
            return fix_tool_call_with_llm(content, agent, error_msg)

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Large model repair failed: {str(e)}")
            return None

    @staticmethod
    def _check_and_handle_multiple_tool_calls(
        content: str, blocks: List[str]
    ) -> Tuple[Optional[str], bool]:
        """Detect and handle the case of multiple tool calls

        Args:
            content: Content containing tool calls
            blocks: List of tool-call blocks

        Returns:
            Tuple[Optional[str], bool]:
                - First element: if multiple tool calls are detected, return an error message; otherwise None
                - Second element: whether multiple tool calls were detected (now always returns False, because multiple tool calls are supported)
        """
        # Multiple tool calls are now supported, no longer return an error
        return None, False

    @staticmethod
    def _parse_tool_call_format(content: str) -> list:
        """Parse the <tool_call>tool_name args JSON format

        Supports two formats:
        1. <tool_call>tool_name {JSON object args}
        2. <tool_call name="tool_name"> [JSON array args] </tool_call>
        """
        ret: list = []

        # Format 1: <tool_call>tool_name {JSON object args}
        tool_call_pattern = r"<tool_call>\s*(\w+)\s+"
        matches = re.finditer(tool_call_pattern, content)

        for match in matches:
            tool_name = match.group(1)
            json_start = match.end()
            while json_start < len(content) and content[json_start].isspace():
                json_start += 1

            if json_start < len(content) and content[json_start] == "{":
                json_str, end_pos = extract_json_from_text(content, json_start)
                if json_str:
                    try:
                        arguments = json_loads(json_str)
                        tool_call = {"name": tool_name, "arguments": arguments}
                        ret.append(tool_call)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_parse_tool_call_format",
                        )
                        continue

        # Format 2: <tool_call name="tool_name"> [JSON array args] </tool_call>
        named_pattern = r'<tool_call\s+name="(\w+)"\s*>\s*'
        for match in re.finditer(named_pattern, content):
            tool_name = match.group(1)
            json_start = match.end()
            while json_start < len(content) and content[json_start].isspace():
                json_start += 1

            if json_start < len(content) and content[json_start] in ("{", "["):
                json_str, end_pos = extract_json_from_text(content, json_start)
                if json_str:
                    try:
                        arguments = json_loads(json_str)
                        tool_call = {"name": tool_name, "arguments": arguments}
                        ret.append(tool_call)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_parse_tool_call_format",
                        )
                        continue

        return ret

    @staticmethod
    def _parse_special_marker_format(content: str) -> list:
        """Parse the special marker format: <|tool_call_begin|>functions.tool_name:index<|tool_call_argument_begin|>JSON<|tool_call_end|>"""
        ret: list = []
        # Match <|tool_call_begin|>functions.{tool_name}:{index}<|tool_call_argument_begin|>
        pattern = r"<\|tool_call_begin\|>functions\.([a-zA-Z_][a-zA-Z0-9_]*):\d+<\|tool_call_argument_begin\|>"
        matches = re.finditer(pattern, content)

        for match in matches:
            tool_name = match.group(1)  # Extract the actual tool name
            json_start = match.end()

            # Find the <|tool_call_end|> marker to determine where the JSON ends
            end_marker = "<|tool_call_end|>"
            end_pos = content.find(end_marker, json_start)
            if end_pos == -1:
                # If there is no end marker, try to extract JSON from the current position
                if json_start < len(content) and content[json_start] == "{":
                    json_str, _ = extract_json_from_text(content, json_start)
                    if json_str:
                        try:
                            arguments = json_loads(json_str)
                            tool_call = {"name": tool_name, "arguments": arguments}
                            ret.append(tool_call)
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_tools.registry",
                                function="_parse_special_marker_format",
                            )
                            continue
            else:
                # There is an end marker, extract the content between the markers
                json_content = content[json_start:end_pos].strip()
                if json_content.startswith("{"):
                    try:
                        arguments = json_loads(json_content)
                        tool_call = {"name": tool_name, "arguments": arguments}
                        ret.append(tool_call)
                    except Exception:
                        # JSON parsing failed, try using extract_json_from_text
                        if json_start < len(content) and content[json_start] == "{":
                            json_str, _ = extract_json_from_text(content, json_start)
                            if json_str:
                                try:
                                    arguments = json_loads(json_str)
                                    tool_call = {
                                        "name": tool_name,
                                        "arguments": arguments,
                                    }
                                    ret.append(tool_call)
                                except Exception as e:
                                    save_exception(
                                        e,
                                        module="haijunbot_tools.registry",
                                        function="_parse_special_marker_format",
                                    )
                                    continue
        return ret

    @staticmethod
    def _parse_function_call_format(content: str) -> list:
        """Parse the function-call format: tool_name(JSON args)

        Format example:
        read_code({"files": [{"path": "src/file.py"}]})
        """
        ret: list = []
        # Match the tool_name(JSON object) format, supporting multi-line JSON
        pattern = r"(\w+)\s*\(\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})\s*\)"
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            tool_name = match.group(1)
            json_str = match.group(2).strip()
            try:
                arguments = json_loads(json_str)
                tool_call = {"name": tool_name, "arguments": arguments}
                ret.append(tool_call)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_tools.registry",
                    function="_parse_function_call_format",
                )
                continue
        return ret

    @staticmethod
    def _parse_tool_name_json_format(content: str) -> list:
        """Parse the tool_name+JSON format: tool_name\n{JSON args} (not wrapped in parentheses)"""
        ret: list = []

        # First extract the position ranges of all code blocks, to avoid misidentifying the language identifier inside a code block
        # Allow whitespace (indentation) before the code block marker, use a capture group to include only the code block itself
        code_block_ranges = []
        for match in re.finditer(r"(?:^|\n)(\s*```[\w]*\n[\s\S]*?\n\s*```)", content):
            # Use the position of capture group 1, excluding the leading newline
            code_block_ranges.append((match.start(1), match.end(1)))

        # Match tool_name + optional whitespace/newline + JSON object (not starting with a left parenthesis, to distinguish from the function-call format)
        pattern = r"(\w+)\s*\n?\s*(\{(?:[^{}]|\{[^{}]*\})*\})"
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            match_start = match.start()
            # Check whether the match position is inside a code block
            in_code_block = any(
                start <= match_start < end for start, end in code_block_ranges
            )
            if in_code_block:
                continue

            tool_name = match.group(1)
            json_str = match.group(2).strip()
            try:
                arguments = json_loads(json_str)
                if isinstance(arguments, dict):
                    ret.append({"name": tool_name, "arguments": arguments})
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_tools.registry",
                    function="_parse_tool_name_json_format",
                )
                continue
        return ret

    @staticmethod
    def _parse_xml_tag_format(content: str, existing: list) -> list:
        """Parse the XML tag format: <name>...</name><arguments>...</arguments>"""
        ret: list = []
        xml_name_pattern = r"<name>\s*(\w+)\s*</name>"
        xml_name_matches = list(re.finditer(xml_name_pattern, content))

        for name_match in xml_name_matches:
            xml_tool_name = name_match.group(1)
            search_start = name_match.end()
            xml_args_pattern = r"<arguments>\s*"
            args_match = re.search(xml_args_pattern, content[search_start:])
            if args_match:
                args_content_start = search_start + args_match.end()
                close_tag_pos = content.find("</arguments>", args_content_start)
                if close_tag_pos != -1:
                    args_content = content[args_content_start:close_tag_pos].strip()
                    try:
                        arguments = json_loads(args_content)
                        tool_call = {"name": xml_tool_name, "arguments": arguments}
                        already_found = False
                        for ex in existing:
                            if isinstance(ex, dict) and ex.get("name") == xml_tool_name:
                                already_found = True
                                break
                        if not already_found:
                            ret.append(tool_call)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_parse_xml_tag_format",
                        )
                        pass
        return ret

    @staticmethod
    def _parse_xml_parameter_format(content: str, existing: list) -> list:
        """Parse the XML parameter tag format: <tool_name><parameter name="key">value</parameter></tool_name>"""
        ret: list = []
        # Match the <tag_name> ... </tag_name> format, where the interior contains a <parameter name="...">...</parameter> child tag
        tag_pattern = r"<(\w+)>\s*(.*?)\s*</\1>"
        param_pattern = r'<parameter\s+name="(\w+)"\s*>\s*(.*?)\s*</parameter>'
        for tag_match in re.finditer(tag_pattern, content, re.DOTALL):
            tool_name = tag_match.group(1)
            inner_content = tag_match.group(2)
            # Check whether it contains a parameter child tag (excluding XML that is not in parameter format)
            if "<parameter" not in inner_content:
                continue
            arguments: dict = {}
            for param_match in re.finditer(param_pattern, inner_content, re.DOTALL):
                param_name = param_match.group(1)
                param_value = param_match.group(2)
                # Try JSON parsing, keep it as a string if it fails
                try:
                    param_value = json_loads(param_value)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.registry",
                        function="_parse_xml_parameter_format",
                    )
                    pass
                arguments[param_name] = param_value
            if arguments:
                # Deduplicate
                already_found = any(
                    isinstance(ex, dict) and ex.get("name") == tool_name
                    for ex in existing
                )
                if not already_found:
                    ret.append({"name": tool_name, "arguments": arguments})
        return ret

    @staticmethod
    def _parse_tool_calls_xml_format(content: str) -> list:
        """Parse the various tool_call formats wrapped by <tool_calls>.

        Supports two sub-formats:
        1. <tool_call name="xxx"><parameter name="xxx" string="false">value</parameter></tool_call>
        2. <tool_call name="xxx">JSON</tool_call> (the tag directly contains JSON args)
        """
        ret: list = []
        # Match the outer <tool_calls> ... </tool_calls> container
        tc_pattern = r"<tool_calls>\s*(.*?)\s*</tool_calls>"
        tc_match = re.search(tc_pattern, content, re.DOTALL)
        if not tc_match:
            return ret
        inner = tc_match.group(1)
        # Match <tool_call name="xxx"> ... </tool_call>
        tool_call_pattern = r'<tool_call\s+name="(\w+)"\s*>\s*(.*?)\s*</tool_call>'
        for tc in re.finditer(tool_call_pattern, inner, re.DOTALL):
            tool_name = tc.group(1)
            params_content = tc.group(2).strip()
            arguments: dict = {}
            # First try parsing the inner content as JSON (new format: direct JSON)
            if params_content.startswith("{"):
                try:
                    arguments = json_loads(params_content)
                    if isinstance(arguments, dict):
                        ret.append({"name": tool_name, "arguments": arguments})
                        continue
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.registry",
                        function="_parse_tool_calls_xml_format",
                    )
                    pass
            # Fall back to the <parameter> child tag format (old format)
            param_pattern = r'<parameter\s+name="(\w+)"(?:\s+string="(true|false)")?\s*>\s*(.*?)\s*</parameter>'
            for pm in re.finditer(param_pattern, params_content, re.DOTALL):
                param_name = pm.group(1)
                is_string = pm.group(2)
                param_value = pm.group(3)
                # Attempt JSON parsing when string="false"
                if is_string == "false":
                    try:
                        param_value = json_loads(param_value)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_parse_tool_calls_xml_format",
                        )
                        pass
                arguments[param_name] = param_value
            if arguments:
                ret.append({"name": tool_name, "arguments": arguments})
        return ret

    @staticmethod
    def _parse_arg_key_value_format(content: str, existing: list) -> list:
        """Parse the [TOOL_CALL] marker + arg_key/arg_value tag format

        Format example:
        [TOOL_CALL]
        read_code
        <arg_key>files</arg_key><arg_value>[{"path": "src/file.py"}]</arg_value>
        """
        ret: list = []

        # Match the [TOOL_CALL] marker
        tool_call_marker_pattern = r"\[TOOL_CALL\]\s*\n(\w+)"
        marker_matches = list(re.finditer(tool_call_marker_pattern, content))

        for match in marker_matches:
            tool_name = match.group(1)
            search_start = match.end()

            # Check whether this tool has already been found
            already_found = False
            for ex in existing:
                if isinstance(ex, dict) and ex.get("name") == tool_name:
                    already_found = True
                    break
            if already_found:
                continue

            # Extract all arg_key and arg_value pairs
            arg_pattern = r"<arg_key>(\w+)</arg_key>\s*<arg_value>(.*?)</arg_value>"
            arg_matches = list(
                re.finditer(arg_pattern, content[search_start:], re.DOTALL)
            )

            if arg_matches:
                arguments = {}
                for arg_match in arg_matches:
                    key = arg_match.group(1)
                    value_str = arg_match.group(2).strip()

                    # Try to parse the value as JSON
                    try:
                        value = json_loads(value_str)
                    except Exception:
                        # If it is not valid JSON, keep it as a string
                        value = value_str

                    arguments[key] = value

                tool_call = {"name": tool_name, "arguments": arguments}
                ret.append(tool_call)

        return ret

    @staticmethod
    def _parse_code_block_format(
        content: str, existing: list
    ) -> Tuple[list, bool, List[Tuple[int, int]]]:
        """Parse the tool name + markdown code block format

        Returns:
            Tuple[list, bool, List[Tuple[int, int]]]:
                - List of recognized tool calls
                - Whether auto-completion occurred
                - List of (start, end) positions of recognized regions, used by subsequent parsers to skip
        """
        ret: list = []
        auto_completed = False
        used_ranges: List[Tuple[int, int]] = []
        # Match: tool name (on its own line) + newline + code block
        # Regex explanation:
        # - (?:^|\n): the tool name must be preceded by the start of the text or a newline
        # - \s*: allows indentation before the tool name
        # - ([a-zA-Z_]\w*): tool name (capture group 1)
        # - \s*\n: whitespace and newline after the tool name
        # - \s*```[a-zA-Z]*\n: code block start marker (indentation allowed)
        # - (.*?): code block content (capture group 2)
        # - \n\s*```: code block end marker (indentation allowed)
        code_block_pattern = r"(?:^|\n)\s*([a-zA-Z_]\w*)\s*\n\s*```[\w]*\n(.*?)\n\s*```"
        code_block_matches = list(re.finditer(code_block_pattern, content, re.DOTALL))

        # Filter out overlapping matches (to prevent language identifiers inside code blocks from being mistaken for tool names)
        filtered_matches = []
        for i, match in enumerate(code_block_matches):
            tool_name = match.group(1)
            start_pos = match.start()

            # Check whether this match is inside the code block of a previous match
            is_inside_previous = False
            for prev_match in code_block_matches[:i]:
                prev_start = prev_match.start()
                prev_end = prev_match.end()
                if prev_start < start_pos < prev_end:
                    is_inside_previous = True
                    break

            if is_inside_previous:
                continue

            # Extra check: if the tool name looks like a language identifier (all lowercase, common language), skip
            if tool_name.lower() in [
                "json",
                "python",
                "javascript",
                "bash",
                "shell",
                "yaml",
                "xml",
                "html",
                "css",
                "sql",
                "java",
                "cpp",
                "c",
                "go",
                "rust",
                "typescript",
                "jsx",
                "tsx",
            ]:
                continue

            filtered_matches.append(match)

        for match in filtered_matches:
            tool_name = match.group(1)
            code_content = match.group(2).strip()
            # Record the region of this match, used by subsequent parsers to skip
            used_ranges.append((match.start(), match.end()))

            already_found = False
            for ex in existing:
                if isinstance(ex, dict) and ex.get("name") == tool_name:
                    already_found = True
                    break
            if already_found:
                continue

            try:
                parsed_content = json_loads(code_content)
                if isinstance(parsed_content, dict):
                    if "name" in parsed_content and "arguments" in parsed_content:
                        ret.append(parsed_content)
                    else:
                        tool_call = {"name": tool_name, "arguments": parsed_content}
                        ret.append(tool_call)
                    auto_completed = True
                    continue
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_tools.registry",
                    function="_parse_code_block_format",
                )
                pass

            tool_call = {"name": tool_name, "arguments": {"content": code_content}}
            ret.append(tool_call)
            auto_completed = True
        return ret, auto_completed, used_ranges

    @staticmethod
    def _parse_embedded_json_format(
        content: str, valid_tool_names: Optional[set] = None
    ) -> list:
        """Scan the full text for JSON objects and extract the standard format containing name+arguments.

        As long as the JSON format is correct and name is a registered tool, it is recognized as a tool call (regardless of whether it is inside a code block).
        This supports standard-format tool calls inside code blocks, while excluding example data through tool name validation.

        Parameters:
            content: the text content to scan
            valid_tool_names: set of valid tool names, used to validate the name field
        """
        ret: list = []
        used_ranges: list = []

        for i, ch in enumerate(content):
            if ch == "{":
                # Check whether it is within an already-used range
                in_used = False
                for start, end in used_ranges:
                    if start <= i <= end:
                        in_used = True
                        break
                if in_used:
                    continue

                json_str, end_pos = extract_json_from_text(content, i)
                if json_str:
                    try:
                        parsed = json_loads(json_str)
                        if (
                            isinstance(parsed, dict)
                            and "name" in parsed
                            and "arguments" in parsed
                        ):
                            # Validate whether name is a registered tool name
                            tool_name = parsed.get("name")
                            if (
                                valid_tool_names is None
                                or tool_name in valid_tool_names
                            ):
                                ret.append(parsed)
                                used_ranges.append((i, end_pos))
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_parse_embedded_json_format",
                        )
                        continue
        return ret

    @staticmethod
    def _save_parse_error(
        content: str, error_msg: str, agent: Optional[Any] = None
    ) -> None:
        """Save content for which tool call parsing failed, for later parser optimization.

        Parameters:
            content: the raw response content that failed to parse
            error_msg: error message
            agent: optional Agent instance, used to obtain context such as the model name
        """
        try:
            # Create the save directory
            error_dir = os.path.join(get_data_dir(), "tool_parse_errors")
            os.makedirs(error_dir, exist_ok=True)

            # Get the model name
            model_name = "unknown"
            if agent is not None:
                try:
                    if hasattr(agent, "model") and agent.model:
                        model_name = (
                            getattr(agent.model, "model_name", None)
                            or getattr(agent.model, "name", None)
                            or "unknown"
                        )
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_tools.registry", function="_save_parse_error"
                    )
                    pass

            # Sanitize: remove potentially sensitive information such as API keys
            safe_content = content
            sensitive_patterns = [
                r"sk-[a-zA-Z0-9]{20,}",
                r'key["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
                r'token["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
                r'password["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
            ]
            for pattern in sensitive_patterns:
                safe_content = re.sub(pattern, "[REDACTED]", safe_content)

            # Build the save data
            error_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": model_name,
                "error_msg": error_msg,
                "content": safe_content,
            }

            # Save file: timestamp_modelname.json
            filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{model_name.replace('/', '_').replace('\\', '_')}.json"
            filepath = os.path.join(error_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(error_data, f, ensure_ascii=False, indent=2)
        except Exception:
            # A save failure does not affect the main flow; silently ignore
            pass

    @staticmethod
    def _extract_tool_calls(
        content: str,
        agent: Optional[Any] = None,
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """Extract tool calls from the content.

        Parameters:
            content: the content containing tool calls
            agent: optional Agent instance, used to call the large model for repair when parsing fails

        Returns:
            Tuple[List[Dict[str, Any]], str, bool]:
                - The first element is the list of extracted tool calls
                - The second element is the error message string ("" on success)
                - The third element is retained as False (the auto-completion tag is no longer needed)

        Raises:
            Exception: if the tool call is missing required fields
        """
        auto_completed = False
        ret: list = []

        # 1. Parse the <tool_call>tool name arguments JSON format
        ret.extend(ToolRegistry._parse_tool_call_format(content))

        # 1.5. Parse special marker format: <|tool_call_begin|>functions.tool_name:index<|tool_call_argument_begin|>
        ret.extend(ToolRegistry._parse_special_marker_format(content))

        # 1.6. Parse function call format: tool_name(JSON arguments)
        ret.extend(ToolRegistry._parse_function_call_format(content))

        # 1.7. Parse tool name+JSON format: tool_name\n{JSON arguments} (without surrounding parentheses)
        ret.extend(ToolRegistry._parse_tool_name_json_format(content))

        # 2.5. Parse [TOOL_CALL] marker + <arg_key>/<arg_value> tag format
        ret.extend(ToolRegistry._parse_arg_key_value_format(content, ret))
        # 2. Parse XML tag format: <name>...</name><arguments>...</arguments>
        ret.extend(ToolRegistry._parse_xml_tag_format(content, ret))

        # 2.2. Parse XML parameter tag format: <tool_name><parameter name="key">value</parameter></tool_name>
        ret.extend(ToolRegistry._parse_xml_parameter_format(content, ret))

        # 2.3. Parse the <tool_calls><tool_call name="xxx"><parameter name="xxx" string="false">value</parameter></tool_call></tool_calls> format
        ret.extend(ToolRegistry._parse_tool_calls_xml_format(content))

        # 3. Parse the "tool name + markdown code block" format
        code_block_results, auto_completed, code_block_ranges = (
            ToolRegistry._parse_code_block_format(content, ret)
        )
        ret.extend(code_block_results)

        # 4. Scan the full text for JSON objects and extract the standard format containing name+arguments
        # Distinguish tool calls from example data by validating whether name is a registered tool
        # Get the set of registered tool names
        if agent and hasattr(agent, "registry"):
            valid_tool_names = set(agent.registry.tools.keys())
        else:
            # When there is no agent, create a temporary registry to get the default tool list
            temp_registry = ToolRegistry()
            valid_tool_names = set(temp_registry.tools.keys())
        ret.extend(
            ToolRegistry._parse_embedded_json_format(
                content, valid_tool_names=valid_tool_names
            )
        )

        # 5. Broad extraction as a fallback
        if not ret:
            fuzzy_results = ToolRegistry._fuzzy_extract_tool_json(
                content, valid_tool_names
            )
            if fuzzy_results:
                for fuzzy_item in fuzzy_results:
                    try:
                        fuzzy_msg = json_loads(fuzzy_item)
                        if (
                            isinstance(fuzzy_msg, dict)
                            and "name" in fuzzy_msg
                            and "arguments" in fuzzy_msg
                        ):
                            ret.append(fuzzy_msg)
                            auto_completed = True
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.registry",
                            function="_extract_tool_calls",
                        )
                        pass

        # If there is still no data, try using the large model to repair
        if not ret:
            long_hint = ToolRegistry._get_long_response_hint(content)
            error_msg = f"Tool call format error: unable to parse tool call content. Please check whether a JSON object containing the name and arguments fields was output.\n{tool_call_help}{long_hint}"

            # If an agent is provided and long_hint is empty, try using the large model to repair
            if agent is not None and not long_hint:
                llm_fixed_content: Optional[str] = ToolRegistry._try_llm_fix(
                    content, agent, error_msg
                )
                if llm_fixed_content is not None:
                    return ToolRegistry._extract_tool_calls(llm_fixed_content, None)

            # Save content that failed to parse, for later parser optimization
            ToolRegistry._save_parse_error(content, error_msg, agent)

            return (
                [],
                error_msg,
                False,
            )

        # Filter out tool calls that do not exist
        if ret and valid_tool_names:
            filtered_ret = []
            for tool_call in ret:
                tool_name = tool_call.get("name", "")
                if tool_name in valid_tool_names:
                    filtered_ret.append(tool_call)
                else:
                    # Record ignored tool calls (optional logging)
                    pass
            ret = filtered_ret

        # Deduplicate: keep only one tool call for those with identical name and arguments
        if ret:
            seen = set()
            deduplicated_ret = []
            for tool_call in ret:
                # Use the JSON string of name and arguments as the unique identifier
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("arguments", {})
                try:
                    args_key = json.dumps(tool_args, sort_keys=True)
                except (TypeError, ValueError):
                    args_key = str(tool_args)
                unique_key = (tool_name, args_key)
                if unique_key not in seen:
                    seen.add(unique_key)
                    deduplicated_ret.append(tool_call)
            ret = deduplicated_ret

        # Uniformly return a list format
        return ret, "", auto_completed

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Any,
        func: Callable[..., Dict[str, Any]],
        protocol_version: str = "1.0",
        interactive: bool = False,
    ) -> None:
        """Register a new tool

        Parameters:
            name: tool name
            description: tool description
            parameters: tool parameter definition
            func: tool execution function
            protocol_version: tool protocol version
            interactive: whether it is interactive/exclusive (when True, native parallel calls degrade to serial)
        """
        if name in self.tools:
            PrettyOutput.auto_print(f"⚠️ Warning: tool '{name}' already exists and will be overwritten")
        tool = Tool(name, description, parameters, func, protocol_version, interactive)
        self.tools[name] = tool
        # Also update _all_tools to ensure newly registered tools can be called
        if hasattr(self, "_all_tools"):
            self._all_tools[name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool

        Parameters:
            name: tool name

        Returns:
            Optional[Tool]: the found tool instance, or None if it does not exist
        """
        return self.tools.get(name)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools (Ollama format definitions)

        Returns:
            List[Dict[str, Any]]: a list containing information about all tools
        """
        return [tool.to_dict() for tool in self.tools.values()]

    def get_custom_tools(self) -> List[Dict[str, Any]]:
        """Get user-defined tools (non-built-in tools)

        Returns:
            List[Dict[str, Any]]: a list containing information about user-defined tools
        """
        return [
            tool.to_dict()
            for tool in self.tools.values()
            if tool.name not in self._builtin_tool_names
        ]

    def execute_tool(
        self, name: str, arguments: Dict[str, Any], agent: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Execute the specified tool

        Parameters:
            name: tool name
            arguments: tool arguments
            agent: agent instance (passed internally by the system, used in v2.0 to separate agent and arguments)

        Returns:
            Dict[str, Any]: a dictionary containing the execution result, with success, stdout and stderr fields
        """
        tool = self._all_tools.get(name)
        if tool is None:
            return {
                "success": False,
                "stderr": f"Tool {name} does not exist, available tools are: {', '.join(self._all_tools.keys())}",
                "stdout": "",
            }

        # Hook: call before_tool_call hooks (interception type)
        # If any hook returns False, the tool execution is intercepted
        if agent is not None and hasattr(agent, "_before_tool_call_hooks"):
            for hook in agent._before_tool_call_hooks:
                try:
                    if hook(agent=agent, tool_name=name, tool_args=arguments) is False:
                        return {
                            "success": False,
                            "stderr": f"Tool {name} was intercepted by a hook",
                            "stdout": "",
                        }
                except Exception:
                    # A hook exception does not intercept; continue execution
                    pass

        # Dispatch the invocation method based on the protocol version declared by the tool implementation
        try:
            result = None
            if getattr(tool, "protocol_version", "1.0") == "2.0":
                # v2.0: pass agent and arguments separately
                # Try using agent as the second argument; fall back to the old way if incompatible
                try:
                    # v2.0 protocol: pass the two arguments arguments and agent
                    # Use type: ignore to suppress the type checker's warnings
                    result = tool.func(arguments, agent)  # type: ignore
                except Exception:
                    # For compatibility with older v2.0 tools, pass only arguments
                    result = tool.func(arguments)
            else:
                # v1.0: for compatibility with the old implementation, inject agent into arguments (if provided)
                args_to_call = arguments.copy() if isinstance(arguments, dict) else {}
                if agent is not None:
                    args_to_call["agent"] = agent
                result = tool.execute(args_to_call)
        except TypeError:
            # Compatibility handling: if the function signature does not match, fall back to the old way
            args_to_call = arguments.copy() if isinstance(arguments, dict) else {}
            if agent is not None:
                args_to_call["agent"] = agent
            result = tool.execute(args_to_call)

        return result

    def execute_native_tool_call(
        self,
        name: str,
        arguments: Dict[str, Any],
        agent: Any,
        record: bool = True,
    ) -> str:
        """Execute a single tool as a native function call and return formatted result text.

        Difference from the text protocol: name/arguments are given by the model in structured form and need no parsing;
        execution and output processing (formatting/compression/over-limit summarization) reuse the same path as the text protocol.
        The confirmation (confirm) gating is the responsibility of the caller (run_loop).
        record=False is used in parallel batch scenarios: skip writes to the shared agent state,
        and the caller uniformly records executed tools after execution ends.
        """
        try:
            from haijunbot.haijunbot_agent import Agent

            agent_instance: Agent = agent

            # Support delayed/scheduled/looped calls (after/at/loop), consistent with the text protocol:
            # If scheduled parameters are matched, create a scheduled task instead of executing immediately
            if isinstance(arguments, dict):
                effective_args = dict(arguments)
                # If the model includes want in the arguments (the intent description of the text protocol), print it and strip it from the execution arguments
                want_text = effective_args.pop("want", None)
                if want_text:
                    PrettyOutput.auto_print(f"💡 {str(want_text)[:500]}")
                timer_params: Dict[str, Any] = {}
                if "after" in effective_args:
                    timer_params["time_type"] = "relative"
                    timer_params["time_value"] = effective_args.pop("after")
                elif "at" in effective_args:
                    timer_params["time_type"] = "absolute"
                    timer_params["time_value"] = effective_args.pop("at")
                elif "loop" in effective_args:
                    timer_params["time_type"] = "interval"
                    timer_params["time_value"] = effective_args.pop("loop")
                    timer_params["interval_seconds"] = timer_params["time_value"]
                if timer_params:
                    from haijunbot.haijunbot_tools.timer import get_timer_manager

                    try:
                        timer_manager = get_timer_manager()
                        task = timer_manager.add_task(
                            task_type="tool_call",
                            time_type=timer_params["time_type"],
                            time_value=timer_params["time_value"],
                            tool_name=name,
                            tool_args=effective_args,
                            interval_seconds=timer_params.get("interval_seconds"),
                        )
                        time_desc = ""
                        if timer_params["time_type"] == "relative":
                            time_desc = f"after {timer_params['time_value']} seconds"
                        elif timer_params["time_type"] == "absolute":
                            time_desc = f"at {timer_params['time_value']}"
                        elif timer_params["time_type"] == "interval":
                            time_desc = f"every {timer_params['time_value']} seconds"
                        msg = f"✅ Created scheduled task #{task.task_id}: {time_desc} execute tool {name}"
                        PrettyOutput.auto_print(msg)
                        return msg
                    except Exception as e:
                        error_msg = f"❌ Failed to create scheduled task: {e}"
                        PrettyOutput.auto_print(error_msg)
                        return error_msg
                arguments = effective_args

            # Print a summary of call arguments (consistent with the text protocol: mask sensitive keys, truncate over-long content)
            param_summary = ""
            if isinstance(arguments, dict) and arguments:
                sensitive = {"password", "token", "key", "secret", "auth", "credential"}
                parts = []
                for k, v in arguments.items():
                    if str(k).lower() in sensitive:
                        parts.append(f"{k}='***'")
                    elif isinstance(v, (dict, list)):
                        parts.append(f"{k}={type(v).__name__}({len(v)})")
                    elif isinstance(v, str) and len(v) > 50:
                        parts.append(f"{k}='{v[:47]}...'")
                    else:
                        parts.append(f"{k}={v!r}")
                if parts:
                    param_summary = " | ".join(
                        str(p).replace("\n", " ").replace("\r", " ") for p in parts
                    )
            if param_summary:
                PrettyOutput.auto_print(f"🛠️ Executing tool call {name} [{param_summary}]")
            else:
                PrettyOutput.auto_print(f"🛠️ Executing tool call {name}")
            start_time = time.time()
            result = self.execute_tool(name, arguments, agent)
            elapsed_time = time.time() - start_time

            # Record the tools actually executed in this round, for use by upper-layer logic (such as memory-saving decisions)
            # Skipped during parallel batch processing (record=False); the caller uniformly records to avoid shared-state races
            if record:
                try:
                    agent_instance.set_user_data("__last_executed_tool__", name)
                    executed_list = agent_instance.get_user_data("__executed_tools__")
                    if not isinstance(executed_list, list):
                        executed_list = []
                    executed_list.append(name)
                    agent_instance.set_user_data("__executed_tools__", executed_list)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.registry",
                        function="execute_native_tool_call",
                    )
                    pass

            platform = (
                getattr(agent_instance, "model", None) if agent_instance else None
            )
            if not result.get("success", False):
                _stderr = result.get("stderr", "") or ""
                _stdout = result.get("stdout", "") or ""
                _reason = _stderr or _stdout or "unknown error"
                PrettyOutput.auto_print(f"❌ Failed to execute tool call {name}: {_reason}")
                err_output = self._format_tool_output(_stdout, _stderr, platform)
                return err_output

            output = self._format_tool_output(
                result.get("stdout", ""), result.get("stderr", ""), platform
            )
            output = self._compress_output(output)

            # Add execution time information for the LLM's reference
            if elapsed_time > 0:
                output = (
                    output
                    + f"\n\n<execution_time>\nTool name: {name}\nExecution time: {elapsed_time:.2f} seconds\n</execution_time>"
                )

            # When the content is too large, use a cheap model to extract key information
            if is_context_overflow(output, platform):
                return self._summarize_with_cheap_model(output, name)
            return output
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to execute tool call {name}: {str(e)}")
            return f"Tool {name} execution exception: {str(e)}"

    def _format_tool_output(
        self, stdout: str, stderr: str, platform: Any = None
    ) -> str:
        """Format tool output as a readable string

        Args:
            stdout: standard output
            stderr: standard error
            platform: platform instance, used to get the remaining token count

        Returns:
            str: the formatted output
        """
        # Truncate the output based on the remaining token count
        if platform is not None:
            try:
                remaining_tokens = platform.get_remaining_token_count()
                if remaining_tokens > 0:
                    # Compute the maximum allowed character count (consistent with c2rust: use calculate_token_limit and multiply by 4)
                    max_allowed_tokens = calculate_token_limit(remaining_tokens)
                    max_allowed_chars = int(max_allowed_tokens * 4)

                    # Compute the character counts of stdout and stderr
                    stdout_len = len(stdout) if stdout else 0
                    stderr_len = len(stderr) if stderr else 0
                    total_len = stdout_len + stderr_len

                    # If the total character count exceeds the limit, truncate
                    if total_len > max_allowed_chars:
                        # Compute the character counts allocated to stdout and stderr (proportionally)
                        if stdout_len > 0 and stderr_len > 0:
                            stdout_ratio = stdout_len / total_len
                            stderr_ratio = stderr_len / total_len
                            max_stdout_chars = int(max_allowed_chars * stdout_ratio)
                            max_stderr_chars = int(max_allowed_chars * stderr_ratio)
                        elif stdout_len > 0:
                            max_stdout_chars = max_allowed_chars
                            max_stderr_chars = 0
                        else:
                            max_stdout_chars = 0
                            max_stderr_chars = max_allowed_chars

                        # Truncate stdout and stderr (keep only the front part, consistent with c2rust)
                        if stdout and max_stdout_chars > 0:
                            stdout = stdout[:max_stdout_chars]
                            if len(stdout) < stdout_len:
                                stdout += "\n... (output too long, truncated)"
                        if stderr and max_stderr_chars > 0:
                            stderr = stderr[:max_stderr_chars]
                            if len(stderr) < stderr_len:
                                stderr += "\n... (output too long, truncated)"

                        PrettyOutput.auto_print(
                            f"⚠️ Tool output too long ({total_len} characters), truncated based on the remaining token count ({remaining_tokens})"
                        )
            except Exception:
                # If getting the remaining token count fails, do not truncate
                pass

        output_parts = []
        if stdout:
            output_parts.append(f"<stdout>\n{stdout}\n</stdout>")
        if stderr:
            output_parts.append(f"<stderr>\n{stderr}\n</stderr>")
        output = "\n\n".join(output_parts)
        return "<no output or errors>" if not output else output

    def _truncate_output(self, output: str) -> str:
        """Truncate overly long output content

        Args:
            output: the output content to truncate

        Returns:
            the truncated content; if the content does not exceed 60 lines, return the original content
        """
        if len(output.splitlines()) > 60:
            lines = output.splitlines()
            PrettyOutput.auto_print("⚠️ Output too long, keeping first and last 30 lines")
            return "\n".join(
                lines[:30] + ["\n...content too long, kept first and last 30 lines...\n"] + lines[-30:]
            )
        return output

    def _compress_output(self, output: str) -> str:
        """Perform multi-level lossless/high-fidelity compression on tool output.

        Compression strategy (4 layers):
        1. Blank line folding: consecutive blank lines (>=3) folded into 2
        2. JSON compression: detect pure JSON content within <stdout>/<stderr> tags, format compactly
        3. Duplicate line compression: merge consecutive duplicate lines into `line content + ...(repeated N times)`
        4. Line count safety boundary: when exceeding threshold (200 lines), keep the first and last 100 lines each, marking the middle with a summary

        Layers 1-3 are completely lossless; layer 4 triggers when exceeding the threshold, preserving key structure.

        Returns:
            str: the compressed output content
        """
        if not output or output == "<no output or errors>":
            return output

        # Layer 1: blank line folding - disabled
        # lines = output.split("\n")
        # collapsed_lines: list[str] = []
        # empty_count = 0
        # for line in lines:
        #     if line.strip() == "":
        #         empty_count += 1
        #         if empty_count <= 2:
        #             collapsed_lines.append(line)
        #     else:
        #         empty_count = 0
        #         collapsed_lines.append(line)
        # output = "\n".join(collapsed_lines)

        # Layer 2: JSON compression - detect JSON within tags and compact it
        # Match <stdout> or <stderr> tags
        def _compact_json(match: re.Match) -> str:
            tag = match.group(1)
            content = match.group(2)
            # Try to parse JSON
            stripped = content.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    compact = json.dumps(
                        parsed, ensure_ascii=False, separators=(",", ":")
                    )
                    # Only replace if the compressed version is much shorter than the original
                    if len(compact) < len(stripped) * 0.7:
                        return f"<{tag}>\n{compact}\n</{tag}>"
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_tools.registry", function="_compact_json"
                    )
                    pass
            return match.group(0)

        output = re.sub(
            r"<(stdout|stderr)>\n(.*?)\n</\1>", _compact_json, output, flags=re.DOTALL
        )

        # Layer 3: duplicate line compression - detect consecutive duplicate lines
        final_lines = output.split("\n")
        compressed_lines: list[str] = []
        i = 0
        while i < len(final_lines):
            line = final_lines[i]
            # Skip blank lines
            if line.strip() == "":
                compressed_lines.append(line)
                i += 1
                continue
            # Count consecutive identical lines
            repeat_count = 1
            while (
                i + repeat_count < len(final_lines)
                and final_lines[i + repeat_count] == line
            ):
                repeat_count += 1
            if repeat_count >= 4:
                compressed_lines.append(line)
                compressed_lines.append(f"  ...(above content repeated {repeat_count - 1} times)")
                i += repeat_count
            else:
                compressed_lines.append(line)
                i += 1
        output = "\n".join(compressed_lines)

        # Layer 4: line count safety boundary - disabled, handled by the subsequent context truncation mechanism
        # # When exceeding 200 lines, keep the first and last 100 lines each and fold the middle
        # output_lines = output.split("\n")
        # total_lines = len(output_lines)
        # MAX_LINES = 200
        # HEAD_TAIL_LINES = 100
        # if total_lines > MAX_LINES:
        #     head = output_lines[:HEAD_TAIL_LINES]
        #     tail = output_lines[-HEAD_TAIL_LINES:]
        #     output = "\n".join(head)
        #     output += f"\n\n...(middle {total_lines - HEAD_TAIL_LINES * 2} lines folded, total lines {total_lines})\n\n"
        #     output += "\n".join(tail)

        return output

    def _dump_tool_output(self, output: str, tool_name: str = "") -> Optional[str]:
        """Persist overly long tool output fully to disk for the model to read on demand.

        Truncation/summarization discards the complete content; after persisting, the model can use read_code to read the original file when needed.
        Directory: <current working directory>/.haijunbot/tool_results/ (isolated with the agent working directory, no cleanup needed).

        Args:
            output: the complete output content to persist to disk
            tool_name: tool name (used for file naming)

        Returns:
            Optional[str]: absolute path of the persisted file; returns None if persistence fails
        """
        try:
            if not output:
                return None
            # Persist under .haijunbot/tool_results/ of the current working directory, naturally isolated with the agent working directory
            disk_dir = os.path.join(os.getcwd(), ".haijunbot", "tool_results")
            os.makedirs(disk_dir, exist_ok=True)

            # File name: timestamp_toolname_sequence.txt (avoid conflicts when the same tool is called multiple times in the same second)
            safe_name = re.sub(r"[^\w\-]", "_", tool_name or "tool")[:40]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            seq = 0
            while True:
                filepath = os.path.join(disk_dir, f"{timestamp}_{safe_name}_{seq}.txt")
                if not os.path.exists(filepath):
                    break
                seq += 1

            # errors="replace": tool output may contain lone surrogate characters (e.g., returned from the frontend),
            # the default strict mode would raise UnicodeEncodeError, causing persistence to fail and output to be silently lost.
            with open(filepath, "w", encoding="utf-8", errors="replace") as f:
                f.write(output)
            return filepath
        except Exception as e:
            save_exception(
                e, module="haijunbot_tools.registry", function="_dump_tool_output"
            )
            return None

    def _truncate_for_summary(self, output: str, max_chars: int = 120000) -> str:
        """Truncate overly long content for cheap model summarization, keeping the head and tail.

        Args:
            output: the original output
            max_chars: the maximum number of characters allowed to be sent to the cheap model

        Returns:
            str: the truncated content (keeping the head and tail); if not over the limit, returns the original text
        """
        if len(output) <= max_chars:
            return output
        head_chars = max_chars // 2
        tail_chars = max_chars - head_chars
        truncated = (
            output[:head_chars]
            + f"\n\n...(middle {len(output) - head_chars - tail_chars} characters omitted, original total length {len(output)} characters)\n\n"
            + output[-tail_chars:]
        )
        return truncated

    def _summarize_with_cheap_model(self, output: str, tool_name: str = "") -> str:
        """Use the cheap model to extract key information from overly long tool output.

        When tool output exceeds the context limit, use the cheap model to summarize key information,
        avoiding overly long content continuously occupying subsequent conversation context.
        When the content is too long, truncate first (keeping the head and tail) before summarizing, to prevent exceeding the cheap model's context.
        On failure, fall back to truncation.

        Truncation/summarization discards the complete content, so persist the complete output first; the returned result includes the file path,
        so the model can use read_code to read the complete content when needed.

        Args:
            output: the output content to summarize
            tool_name: tool name (used for naming the persisted file)

        Returns:
            str: the summarized content
        """
        # Persist the complete output first for the model to read on demand (truncation/summarization discards the complete content)
        disk_path = self._dump_tool_output(output, tool_name)
        disk_hint = ""
        if disk_path:
            disk_hint = (
                f"\n\n<tool_output_disk>\n"
                f"(original output too long at {len(output)} characters, complete content saved to file)\n"
                f"Complete result file: {disk_path}\n"
                f"If you need the complete content, please use read_code to read this file.\n"
                f"</tool_output_disk>"
            )
        try:
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            # Get the cheap platform instance
            platform = (
                PlatformRegistry.get_global_platform_registry().get_cheap_platform()
            )

            # When the content is too long, truncate first keeping the head and tail, to avoid exceeding the cheap model's context
            summary_input = self._truncate_for_summary(output)

            summary_prompt = (
                "Please extract the key information from the following tool output to replace the original output returned to the Agent. Requirements:\n"
                "1. Keep key data useful for subsequent decisions, error information, file paths, function names, return values, etc.\n"
                "2. Compress redundant content (such as repeated logs, irrelevant details)\n"
                "3. Output concise structured text (such as a list)\n"
                "4. If the output contains errors, you must clearly point out the cause of the error\n"
                "5. Keep it short and highlight the most valuable information\n\n"
                f"Original output content ({len(output)} characters):\n\n{summary_input}"
            )

            # Use stateless completion so as not to affect the main conversation history
            result = platform.complete(summary_prompt)

            if result and result != "<output interrupted by user>":
                return (
                    f"<tool_output_summary>\n"
                    f"(original output too long at {len(output)} characters, key information summarized by the cheap model)\n\n"
                    f"{result}\n"
                    f"</tool_output_summary>" + disk_hint
                )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.registry",
                function="_summarize_with_cheap_model",
            )
            PrettyOutput.auto_print(
                f"⚠ Failed to summarize output with cheap model, falling back to truncation: {str(e)}"
            )

        # On failure, fall back to truncation
        return self._truncate_output(output) + disk_hint

    def handle_tool_calls(self, tool_call: Dict[str, Any], agent: Any) -> str:
        try:
            name = tool_call["name"]  # Ensure name is of type str
            args = tool_call["arguments"]  # Original arguments (from external protocol)
            want = tool_call.get("want", "")

            from haijunbot.haijunbot_agent import Agent

            agent_instance: Agent = agent

            # If args is a string, try to parse it as JSON
            if isinstance(args, str):
                try:
                    args = json_loads(args)
                except Exception:
                    # Return the error with complete tool usage instructions to guide the next correct call
                    try:
                        usage_prompt = agent_instance.get_tool_usage_prompt()
                    except Exception:
                        usage_prompt = tool_call_help
                    PrettyOutput.auto_print("❌ Invalid tool argument format")
                    return f"Invalid tool argument format: {name}. arguments should be a parseable Jsonnet or object, please provide it in the tool call format.\n\n{usage_prompt}"

            # When the arguments returned by the model are not valid JSON, the platform layer puts the original text under PARSE_ERROR_KEY.
            # Provide a self-correctable hint here to avoid falsely reporting "missing arguments".
            if isinstance(args, dict) and PARSE_ERROR_KEY in args:
                raw = args.get(PARSE_ERROR_KEY)
                raw_text = raw if isinstance(raw, str) else str(raw)
                preview = raw_text[:200]
                if len(raw_text) > 200:
                    preview += "..."
                PrettyOutput.auto_print("❌ Failed to parse tool argument JSON")
                return (
                    f"Failed to parse tool argument JSON, cannot execute {name}.\n"
                    "Your arguments are not complete and valid JSON (it may have been truncated by output length, or contains non-JSON content).\n"
                    f"Original snippet: {preview}\n"
                    "Please call this tool again, ensuring arguments is a complete, valid JSON object."
                )

            # Check whether scheduling parameters are included (after/at/loop)
            if isinstance(args, dict):
                timer_params = {}
                if "after" in args:
                    timer_params["time_type"] = "relative"
                    timer_params["time_value"] = args.pop("after")
                elif "at" in args:
                    timer_params["time_type"] = "absolute"
                    timer_params["time_value"] = args.pop("at")
                elif "loop" in args:
                    timer_params["time_type"] = "interval"
                    timer_params["time_value"] = args.pop("loop")
                    timer_params["interval_seconds"] = timer_params["time_value"]

                # If scheduling parameters are included, create a scheduled task instead of executing immediately
                if timer_params:
                    from haijunbot.haijunbot_tools.timer import get_timer_manager

                    timer_manager = get_timer_manager()
                    try:
                        task = timer_manager.add_task(
                            task_type="tool_call",
                            time_type=timer_params["time_type"],
                            time_value=timer_params["time_value"],
                            tool_name=name,
                            tool_args=args,
                            interval_seconds=timer_params.get("interval_seconds"),
                        )
                        time_desc = ""
                        if timer_params["time_type"] == "relative":
                            time_desc = f"after {timer_params['time_value']} seconds"
                        elif timer_params["time_type"] == "absolute":
                            time_desc = f"at {timer_params['time_value']}"
                        elif timer_params["time_type"] == "interval":
                            time_desc = f"every {timer_params['time_value']} seconds"

                        msg = f"✅ Created scheduled task #{task.task_id}: execute tool {name} {time_desc}"
                        PrettyOutput.auto_print(msg)
                        return msg
                    except Exception as e:
                        error_msg = f"❌ Failed to create scheduled task: {e}"
                        PrettyOutput.auto_print(error_msg)
                        return error_msg

            # Generate an argument summary, filtering sensitive information
            param_summary = ""
            if isinstance(args, dict) and args:
                # List of sensitive fields
                sensitive_keys = {
                    "password",
                    "token",
                    "key",
                    "secret",
                    "auth",
                    "credential",
                }
                summary_parts = []

                for key, value in args.items():
                    if key.lower() in sensitive_keys:
                        summary_parts.append(f"{key}='***'")
                    elif isinstance(value, (dict, list)):
                        # Simplify complex types to type information
                        summary_parts.append(
                            f"{key}={type(value).__name__}({len(value)} items)"
                        )
                    elif isinstance(value, str) and len(value) > 50:
                        # Truncate long strings
                        summary_parts.append(f"{key}='{value[:47]}...'")
                    else:
                        summary_parts.append(f"{key}={repr(value)}")

                if summary_parts:
                    # Replace newline characters in argument values with spaces to avoid newlines in the summary
                    cleaned_parts = [
                        part.replace("\n", " ").replace("\r", " ")
                        for part in summary_parts
                    ]
                    param_summary = " | ".join(cleaned_parts)

            # If there is a want field, print the Agent's intent first
            if want:
                PrettyOutput.auto_print(f"💡 {want}")

            # Merge into one line of output: executing tool call and argument summary
            if param_summary:
                PrettyOutput.auto_print(f"🛠️ Executing tool call {name} [{param_summary}]")
            else:
                PrettyOutput.auto_print(f"🛠️ Executing tool call {name}")

            # Execute the tool call (based on the protocol version implemented by the tool, the system internally decides how to pass the agent)
            start_time = time.time()
            result = self.execute_tool(name, args, agent)
            elapsed_time = time.time() - start_time

            # Print execution status
            if result.get("success", False):
                PrettyOutput.auto_print(
                    f"✅ Executed tool call {name} successfully (elapsed: {elapsed_time:.2f}s)"
                )
            else:
                # Get the failure reason
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_msg = stderr if stderr else (stdout if stdout else "unknown error")
                PrettyOutput.auto_print(f"❌ Failed to execute tool call {name}")
                PrettyOutput.auto_print(f"   Failure reason: {error_msg}")

            # Record the tools actually executed this round, for use by upper-layer logic (such as memory-save decision making)
            try:
                from haijunbot.haijunbot_agent import Agent  # Delayed import to avoid circular dependency

                agent_instance_for_record: Agent = agent_instance
                # Record the last executed tool
                agent_instance_for_record.set_user_data("__last_executed_tool__", name)
                # Record the cumulative list of tools executed this round
                executed_list = agent_instance_for_record.get_user_data(
                    "__executed_tools__"
                )
                if not isinstance(executed_list, list):
                    executed_list = []
                executed_list.append(name)
                agent_instance_for_record.set_user_data(
                    "__executed_tools__", executed_list
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.registry", function="handle_tool_calls"
                )
                pass

            # If execution fails, return with tool usage instructions attached
            if not result.get("success", False):
                try:
                    usage_prompt = agent_instance.get_tool_usage_prompt()
                except Exception:
                    usage_prompt = tool_call_help
                platform = agent_instance.model if agent_instance.model else None
                err_output = self._format_tool_output(
                    result.get("stdout", ""), result.get("stderr", ""), platform
                )
                return f"{err_output}\n\n{usage_prompt}"

            # Format the output
            platform = agent_instance.model if agent_instance.model else None
            output = self._format_tool_output(
                result["stdout"], result.get("stderr", ""), platform
            )

            # Perform multi-level compression on the output (blank line folding/JSON compression/duplicate line merging/line count safety boundary)
            output = self._compress_output(output)

            # Add execution time information for LLM reference
            if elapsed_time > 0:
                execution_time_info = f"\n\n<execution_time>\nTool name: {name}\nExecution time: {elapsed_time:.2f} seconds\n</execution_time>"
                output = output + execution_time_info

            # Check whether the content is too large
            # Use the current model group (no longer inherited from the agent)
            platform = agent_instance.model if agent_instance.model else None
            is_large_content = is_context_overflow(output, platform)

            if is_large_content:
                # Use the cheap model to extract key information, avoiding overly long context continuously occupying subsequent conversation
                return self._summarize_with_cheap_model(output, name)

            return output

        except Exception as e:
            # Try to get the tool name (if already defined)
            tool_name = (
                tool_call.get("name", "unknown")
                if "tool_call" in locals()
                else "unknown"
            )
            if tool_name:
                PrettyOutput.auto_print(f"❌ Failed to execute tool call {tool_name}: {str(e)}")
            else:
                PrettyOutput.auto_print(f"❌ Tool call failed: {str(e)}")
            try:
                from haijunbot.haijunbot_agent import Agent  # Delayed import to avoid circular dependency

                agent_instance_for_prompt: Agent = agent
                usage_prompt = agent_instance_for_prompt.get_tool_usage_prompt()
            except Exception:
                usage_prompt = tool_call_help
            return f"Tool call failed: {str(e)}\n\n{usage_prompt}"

    def handle_multiple_tool_calls(
        self, tool_calls: Dict[str, Dict[str, Any]], agent: Any
    ) -> str:
        """Handle multiple tool calls

        Args:
            tool_calls: dictionary of tool calls, keys are tool names (possibly with index), values are tool call information
            agent: Agent instance

        Returns:
            str: results of all tool calls, joined with a separator
        """
        results = []
        total_count = len(tool_calls)

        PrettyOutput.auto_print(f"🛠️ Preparing to execute {total_count} tool calls")

        for idx, (tool_key, tool_call) in enumerate(tool_calls.items(), 1):
            name = tool_call.get("name", tool_key)
            PrettyOutput.auto_print(f"[{idx}/{total_count}] Executing tool: {name}")

            try:
                result = self.handle_tool_calls(tool_call, agent)
                results.append(
                    f"=== Tool call {idx}/{total_count}: {name} ===\n{result}"
                )
            except Exception as e:
                error_msg = f"Tool call {name} execution failed: {str(e)}"
                PrettyOutput.auto_print(f"❌ {error_msg}")
                results.append(
                    f"=== Tool call {idx}/{total_count}: {name} ===\n❌ {error_msg}"
                )

        # Merge all results
        separator = "\n\n" + "=" * 80 + "\n\n"
        combined_result = separator.join(results)

        PrettyOutput.auto_print(f"✅ Completed {total_count} tool calls")

        return combined_result
