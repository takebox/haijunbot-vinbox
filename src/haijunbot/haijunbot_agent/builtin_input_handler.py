# -*- coding: utf-8 -*-
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import yaml

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_platform_manager.main import chat_with_model
from haijunbot.haijunbot_utils.config import (
    get_replace_map,
    get_llm_group,
    set_llm_group,
    get_global_config_data,
    get_builtin_input_handler_dirs,
)
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.input import (
    add_additional_completion_dir,
    get_choice,
    get_single_line_input,
)
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import load_config

from haijunbot.haijunbot_agent.rules_manager import RulesManager
from haijunbot.haijunbot_agent.utils import build_fix_prompt
from haijunbot.haijunbot_code_agent.diff_visualizer import visualize_diff_enhanced
from haijunbot.haijunbot_code_agent.code_agent_git import GitManager
from haijunbot.haijunbot_utils.git_utils import (
    get_latest_commit_hash,
    get_diff_between_commits,
    find_git_root,
    advance_start_commit,
    find_recent_non_checkout_commit,
)


def _report_agent_config_change(updates: Dict[str, Any]) -> None:
    """Report Agent runtime config changes to the owning Gateway.

    Called after config is modified at runtime via commands (e.g. <SetConfig> switching
    model group or proxy node), so the Gateway can update AgentInfo and the Agent list
    config stays consistent with the real running state. Failures degrade silently.

    Args:
        updates: dict of changed fields, e.g. {"llm_group": "xxx"} / {"proxy_node": "xxx"}
    """
    import haijunbot.haijunbot_utils.globals as jglobals

    if not jglobals.agent_id or not jglobals.master_url or not updates:
        return
    try:
        from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool

        if not GatewayManagerTool.check():
            return
        result = GatewayManagerTool()._request_gateway(
            "PATCH",
            f"/api/agents/{jglobals.agent_id}",
            json_data=updates,
            error_prefix="Report agent config change failed",
        )
        if not result.get("success"):
            PrettyOutput.auto_print(
                f"⚠️ Failed to report config to gateway: {result.get('error', 'unknown error')}"
            )
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Exception reporting config to gateway: {e}")


def _print_markdown_table(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    header_styles: Optional[List[str]] = None,
) -> None:
    """Output a markdown table compatible with terminal and frontend."""
    # Build the header row
    header_row = "| " + " | ".join(headers) + " |"
    # Build the separator row
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    # Build the data rows
    data_rows = ["| " + " | ".join(row) + "|" for row in rows]
    # Assemble the markdown content
    md_content = (
        f"## {title}\n\n"
        + header_row
        + "\n"
        + separator_row
        + "\n"
        + "\n".join(data_rows)
    )
    PrettyOutput.print_markdown(md_content)


# Helper function: get global config data (avoids import-time binding issues)
def _get_global_config() -> Any:
    """Helper function to get global config data

    Uses a function call instead of a direct import, to avoid using a stale
    reference after set_global_config_data() reassigns it.
    """
    return get_global_config_data()


def extract_tags_from_text(text: str | list | None) -> List[str]:
    """Extract all '<tag>' format tags from text

    Args:
        text: input text, may be plain text, a multimodal content list, or None

    Returns:
        List[str]: list of extracted tags (without angle brackets or single quotes)
    """
    if not text:
        return []

    # Handle multimodal content (list format)
    if isinstance(text, list):
        text = " ".join(b.get("text", "") for b in text if b.get("type") == "text")

    # Extract '<tag>' format tags
    return re.findall(r"'<([^>]+)>'", text)


def _get_rule_content(rule_name: str) -> str | None:
    """Get rule content

    Args:
        rule_name: rule name

    Returns:
        str | None: rule content, or None if not found
    """
    try:
        import os

        # Use the current working directory as root_dir
        rules_manager = RulesManager(root_dir=os.getcwd())
        return rules_manager.get_named_rule(rule_name)
    except ImportError:
        return None


# Custom input handler registry: tag -> handler
_custom_tag_handlers: Dict[str, Callable] = {}
_handlers_loaded: bool = False


def _load_custom_input_handlers() -> None:
    """
    Scan Python files in builtin_input_handler_dirs and dynamically register custom input handlers.

    Convention/priority (register on first match):
    - Module-level callable: input_handler_cb (must have a tag attribute)
    - Factory method returning one or more callables: get_input_handler_cb(), register_input_handler_cb()

    handler signature: handler(user_input, agent, tag) -> Tuple[str, bool]
    handler must have a tag attribute identifying the marker name it handles.
    """
    global _handlers_loaded
    if _handlers_loaded:
        return
    _handlers_loaded = True

    try:
        dirs = get_builtin_input_handler_dirs()
        if not dirs:
            return
        for d in dirs:
            p_dir = Path(d)
            if not p_dir.exists() or not p_dir.is_dir():
                continue
            for file_path in p_dir.glob("*.py"):
                if file_path.name == "__init__.py":
                    continue
                parent_dir = str(file_path.parent)
                added_path = False
                try:
                    if parent_dir not in sys.path:
                        sys.path.insert(0, parent_dir)
                        added_path = True
                    module_name = file_path.stem

                    # Parse the requirements comment at the file header
                    requirements: List[str] = []
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("# requirements:"):
                                    deps_str = line[len("# requirements:") :].strip()
                                    if deps_str:
                                        requirements = deps_str.split()
                                    break
                    except Exception:
                        pass

                    # Install dependencies
                    if requirements:
                        PrettyOutput.auto_print(
                            f"🔧 Installing input handler dependencies [{file_path.name}]: {', '.join(requirements)}"
                        )
                        try:
                            result = subprocess.run(
                                ["uv", "pip", "install"] + requirements,
                                capture_output=True,
                                text=True,
                                timeout=120,
                            )
                            if result.returncode == 0:
                                PrettyOutput.auto_print(
                                    f"✅ Dependencies installed successfully [{file_path.name}]"
                                )
                            else:
                                PrettyOutput.auto_print(
                                    f"❌ Failed to install dependencies [{file_path.name}]: {result.stderr.strip()}"
                                )
                        except subprocess.TimeoutExpired:
                            PrettyOutput.auto_print(
                                f"❌ Dependency installation timed out [{file_path.name}] (over 120 seconds)"
                            )
                        except Exception as e:
                            PrettyOutput.auto_print(
                                f"❌ Dependency installation error [{file_path.name}]: {e}"
                            )

                    module = __import__(module_name)
                    PrettyOutput.auto_print(f"📦 Loading input handler from config file: {file_path}")

                    candidates: List[Callable] = []

                    # 1) Directly exported callback
                    if hasattr(module, "input_handler_cb"):
                        obj = getattr(module, "input_handler_cb")
                        if callable(obj):
                            candidates.append(obj)

                    # 2) Factory method: get_input_handler_cb()
                    if hasattr(module, "get_input_handler_cb"):
                        factory = getattr(module, "get_input_handler_cb")
                        if callable(factory):
                            try:
                                ret = factory()
                                if callable(ret):
                                    candidates.append(ret)
                                elif isinstance(ret, (list, tuple)):
                                    for c in ret:
                                        if callable(c):
                                            candidates.append(c)
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"⚠ Failed to call get_input_handler_cb(): {e}"
                                )

                    # 3) Factory method: register_input_handler_cb()
                    if hasattr(module, "register_input_handler_cb"):
                        factory2 = getattr(module, "register_input_handler_cb")
                        if callable(factory2):
                            try:
                                ret2 = factory2()
                                if callable(ret2):
                                    candidates.append(ret2)
                                elif isinstance(ret2, (list, tuple)):
                                    for c in ret2:
                                        if callable(c):
                                            candidates.append(c)
                            except Exception as e:
                                PrettyOutput.auto_print(
                                    f"⚠ Failed to call register_input_handler_cb(): {e}"
                                )

                    for handler in candidates:
                        tag = getattr(handler, "tag", None)
                        if not tag:
                            PrettyOutput.auto_print(
                                f"⚠ Input handler {file_path.name} is missing the tag attribute, skipped"
                            )
                            continue
                        _custom_tag_handlers[tag] = handler
                        PrettyOutput.auto_print(f"✅ Registered custom input handler: '<{tag}>'")

                except Exception as e:
                    PrettyOutput.auto_print(
                        f"⚠ Failed to load input handler {file_path.name}: {e}"
                    )
                finally:
                    if added_path:
                        try:
                            sys.path.remove(parent_dir)
                        except ValueError:
                            pass
    except Exception as e:
        PrettyOutput.auto_print(f"⚠ Failed to load custom input handlers: {e}")


def builtin_input_handler(user_input: str, agent_: Any) -> Tuple[str, bool]:
    import os

    """
    Handle built-in special input markers and append the corresponding prompts

    Args:
        user_input: user input
        agent: agent object

    Returns:
        Tuple[str, bool]: the processed input and whether further processing is needed
    """
    from haijunbot.haijunbot_agent import Agent

    agent: Agent = agent_

    # Load custom input handlers
    _load_custom_input_handlers()

    # [New] Strip the sender prefix (format: xxx：or xxx:), to avoid interfering with special-tag matching and orchestration logic
    # The prefix only appears on the first line of a multi-line message, in the format "sender：" or "sender:"
    _sender_prefix = None
    _sender_match = re.match(r"^(.+?)[：:]\s*", user_input)
    if _sender_match and "\n" in user_input:
        _sender_prefix = _sender_match.group(0)
        user_input = user_input[len(_sender_prefix) :]

    # Find special tags
    special_tags = re.findall(r"'<([^>]+)>'", user_input)

    if not special_tags:
        # Restore the sender prefix even when there are no special tags
        if _sender_prefix:
            user_input = _sender_prefix + user_input
        return user_input, False

    # Get the replacement map
    replace_map = get_replace_map()
    processed_tag = set()
    add_on_prompt = ""
    modified_input = user_input

    # Handle the Pin marker first
    if "Pin" in special_tags:
        pin_marker = "'<Pin>'"
        pin_index = modified_input.find(pin_marker)

        if pin_index != -1:
            # Split into content before the Pin marker and after it
            before_pin = modified_input[:pin_index]
            after_pin = modified_input[pin_index + len(pin_marker) :]

            # Append the content after the Pin marker to pin_content
            after_pin_stripped = after_pin.strip()
            if after_pin_stripped:
                if agent.pin_content:
                    agent.pin_content += "\n" + after_pin_stripped
                else:
                    agent.pin_content = after_pin_stripped
                PrettyOutput.auto_print(f"📌 Pinned content: {after_pin_stripped[:50]}...")

            # Remove the Pin marker, keep the surrounding content
            modified_input = before_pin + after_pin

    # Handle other markers
    for tag in special_tags:
        # Handle special markers that return immediately first (excluding Pin)
        if tag == "Summary":
            # Use the full summary directly
            summary = agent._summarize_and_clear_history(trigger_reason="User command triggered")
            memory_tags_prompt = agent.memory_manager.prepare_memory_tags_prompt()
            prompt = ""
            if summary:
                # Set the summary and memory tags as the initial prompt of the new session
                prompt = summary + "\n" + memory_tags_prompt
            else:
                # Even without a summary, ensure memory tags are set as the new session's initial prompt
                prompt = memory_tags_prompt
            return prompt, True
        elif tag == "Clear":
            agent.clear_history()
            return "", True
        elif tag == "ClearPin":
            agent.pin_content = ""
            PrettyOutput.auto_print("🧹 Pinned content cleared")
            return "", True
        elif tag == "ToolUsage":
            agent.set_addon_prompt(agent.get_tool_usage_prompt())
            continue
        elif tag == "ReloadConfig":
            load_config()
            return "", True
        elif tag == "PrintConfig":
            config = get_global_config_data()
            PrettyOutput.auto_print("=== Global Config (YAML format) ===")
            try:
                # Convert to a plain dict for YAML serialization
                config_dict = dict(config)
                yaml_output = yaml.safe_dump(
                    config_dict,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
                PrettyOutput.auto_print(yaml_output)
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️  YAML serialization failed: {e}")
                PrettyOutput.auto_print(f"Fallback output (string format):\n{config}")
            return "", True

        elif tag == "SetConfig":
            tag_marker = "'<SetConfig>'"
            tag_index = modified_input.find(tag_marker)
            if tag_index == -1:
                PrettyOutput.auto_print("❌ Invalid SetConfig command format")
                return "", True

            # Extract the argument part after the tag
            arg_str = modified_input[tag_index + len(tag_marker) :].strip()

            if not arg_str:
                PrettyOutput.auto_print(
                    "❌ Usage: '<SetConfig>' key.path = value\n"
                    "Examples:\n"
                    "  '<SetConfig>' llm_group = \"nebulacoder_v8_0\"\n"
                    "  '<SetConfig>' ENV.http_proxy = \"http://proxy:8080\"\n"
                    "  '<SetConfig>' build_validation_timeout = 60\n"
                    "  '<SetConfig>' TEMP_KEY delete"
                )
                return "", True

            config = get_global_config_data()

            try:
                # Check whether it is a delete operation
                if arg_str.rstrip().endswith(" delete"):
                    key_path = arg_str.rsplit(" delete", 1)[0].strip()
                    if not key_path:
                        PrettyOutput.auto_print("❌ Error: the delete operation requires a key path")
                        return "", True

                    # Delete the nested key
                    success, message = _delete_nested_config(config, key_path)
                    if success:
                        PrettyOutput.auto_print(f"✅ Config deleted: {key_path}")
                    else:
                        PrettyOutput.auto_print(f"❌ {message}")
                    return "", True

                # Parse the key = value format (split only on the first '=')
                if "=" not in arg_str:
                    PrettyOutput.auto_print(
                        "❌ Error: missing '=' separator, correct format: key.path = value"
                    )
                    return "", True

                key_part, value_part = arg_str.split("=", 1)
                key_path = key_part.strip()
                value_str = value_part.strip()

                if not key_path:
                    PrettyOutput.auto_print("❌ Error: key cannot be empty")
                    return "", True

                # Safely parse the value
                value = _safe_parse_value(value_str)

                # Set the nested key
                success, message = _set_nested_config(config, key_path, value)
                if success:
                    PrettyOutput.auto_print(
                        f"✅ Config set: {key_path} = {repr(value)}"
                    )
                    # After changing the model group/proxy node at runtime, report to the gateway so the Agent list config stays consistent
                    if key_path == "llm_group" and isinstance(value, str):
                        _report_agent_config_change({"llm_group": value})
                    elif key_path == "proxy_node" and isinstance(value, str):
                        _report_agent_config_change({"proxy_node": value})
                else:
                    PrettyOutput.auto_print(f"❌ {message}")

            except Exception as e:
                PrettyOutput.auto_print(f"❌ Parse error: {e}")

            return "", True
        elif tag == "QuickConfig":
            from haijunbot.haijunbot_utils.quick_config import run_quick_config

            try:
                run_quick_config()
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Quick config failed: {e}")
            return "", True
        elif tag == "LLMAdd":
            from haijunbot.haijunbot_platform_manager.main import llm_add

            try:
                llm_add()
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to add LLM config: {e}")
            return "", True
        elif tag == "LLMDelete":
            from haijunbot.haijunbot_platform_manager.main import llm_delete

            try:
                llm_delete(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to delete LLM config: {e}")
            return "", True
        elif tag == "LLMUpdate":
            from haijunbot.haijunbot_platform_manager.main import llm_update

            try:
                llm_update(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to update LLM config: {e}")
            return "", True
        elif tag == "LLMGroupAdd":
            from haijunbot.haijunbot_platform_manager.main import group_add

            try:
                group_add(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to add model group: {e}")
            return "", True
        elif tag == "LLMGroupDelete":
            from haijunbot.haijunbot_platform_manager.main import group_delete

            try:
                group_delete(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to delete model group: {e}")
            return "", True
        elif tag == "LLMGroupUpdate":
            from haijunbot.haijunbot_platform_manager.main import group_update

            try:
                group_update(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to update model group: {e}")
            return "", True
        elif tag == "LLMGroupSet":
            from haijunbot.haijunbot_platform_manager.main import group_set

            try:
                group_set(name=None)
            except Exception as e:
                if "Exit" not in str(type(e).__name__):
                    PrettyOutput.auto_print(f"❌ Failed to set model group: {e}")
            return "", True
        elif tag == "Shell":
            # Open an interactive Shell terminal directly (same as Alt+T)
            from haijunbot.haijunbot_utils.input import execute_shell_in_terminal

            execute_shell_in_terminal(agent)
            return "", True
        elif tag == "AddDir":
            tag_marker = "'<AddDir>'"
            tag_index = modified_input.find(tag_marker)
            inline_arg = ""
            if tag_index != -1:
                inline_arg = modified_input[tag_index + len(tag_marker) :].strip()
            if not inline_arg:
                PrettyOutput.auto_print(
                    "❌ AddDir only supports the inline argument form, e.g. '<AddDir>' /path/to/dir"
                )
                return "", True
            target_dir = inline_arg.strip().strip('"').strip("'")
            if add_additional_completion_dir(target_dir):
                PrettyOutput.auto_print(f"✅ Added additional completion directory: {target_dir}")
            else:
                PrettyOutput.auto_print(f"❌ Directory does not exist or is unavailable: {target_dir}")
            return "", True
        elif tag == "OrganizeAgents":
            # Interactively obtain the orchestration file path (supports multi-line input, one path per line)
            import os
            from haijunbot.haijunbot_utils.input import get_multiline_input

            # Auto-discover plugin-declared orchestration pipeline templates, so users don't have to find file paths manually
            plugin_orchestrations = []
            try:
                from haijunbot.haijunbot_utils.config import get_plugin_orchestrations

                plugin_orchestrations = get_plugin_orchestrations()
            except Exception:
                plugin_orchestrations = []

            if plugin_orchestrations:
                PrettyOutput.auto_print(
                    "📋 Detected the following plugin orchestration templates (enter an index to select, or enter a custom path):"
                )
                for idx, orch in enumerate(plugin_orchestrations, start=1):
                    plugin_tag = f"[{orch['plugin']}] " if orch.get("plugin") else ""
                    desc = orch.get("description") or ""
                    PrettyOutput.auto_print(
                        f"  {idx}. {plugin_tag}{orch['name']}"
                        + (f" — {desc}" if desc else "")
                    )
                    PrettyOutput.auto_print(f"     Path: {orch['file']}")
                PrettyOutput.auto_print(
                    "Enter orchestration file path or index (one per line, blank line to finish):"
                )
            else:
                PrettyOutput.auto_print(
                    "Enter orchestration file path (one per line, blank line to finish):"
                )
            file_paths_input = get_multiline_input("orchestration file path")
            if not file_paths_input:
                PrettyOutput.auto_print("❌ No orchestration file path entered")
                return "", True

            # Parse multi-line input and auto-extract file paths from the content
            # Supported formats:
            #   - Plain path: /path/to/file.yaml
            #   - With prefix: Administrator：/path/to/file.yaml
            #   - Quoted: "/path/to/file.yaml" or '/path/to/file.yaml'
            #   - With description: please use the file /path/to/file.yaml
            file_paths = []
            for line in file_paths_input.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 0. Support entering a plugin orchestration template index directly (e.g. "1", "2")
                if plugin_orchestrations and line.isdigit():
                    num = int(line)
                    if 1 <= num <= len(plugin_orchestrations):
                        file_paths.append(plugin_orchestrations[num - 1]["file"])
                        continue
                # Try to extract a file path from the line
                # 1. First try matching a quoted path
                quoted_match = re.search(r'["\']([^"\']+\.ya?ml)["\']', line)
                if quoted_match:
                    file_paths.append(quoted_match.group(1))
                    continue
                # 2. Try matching an absolute path or home path (/path/to/file.yaml or ~/path/to/file.yaml)
                abs_match = re.search(
                    r'(?:^|[\s：:])((/[^\s：:"\']+\.ya?ml)|(~/[^\s：:"\']+\.ya?ml))',
                    line,
                )
                if abs_match:
                    file_paths.append(abs_match.group(1))
                    continue
                # 3. Try matching a relative path (e.g. ./path/file.yaml or ../path/file.yaml)
                rel_match = re.search(
                    r'(?:^|[\s：:])((\.{1,2}/[^\s：:"\']+\.ya?ml))', line
                )
                if rel_match:
                    file_paths.append(rel_match.group(1))
                    continue
                # 4. Try matching a Windows path (e.g. C:\\path\\file.yaml)
                win_match = re.search(
                    r'(?:^|[\s：:])(([A-Za-z]:[\\/][^\s：:"\']+\.ya?ml))', line
                )
                if win_match:
                    file_paths.append(win_match.group(1))
                    continue
                # 5. Last attempt: the whole line is the path (after stripping quotes and whitespace)
                cleaned = line.strip().strip('"').strip("'").strip()
                if cleaned and (cleaned.endswith(".yaml") or cleaned.endswith(".yml")):
                    file_paths.append(cleaned)

            if not file_paths:
                PrettyOutput.auto_print("❌ No valid orchestration file path entered")
                return "", True

            # Read and merge all orchestration files
            all_agents_config = []
            for file_path in file_paths:
                if not os.path.isfile(file_path):
                    PrettyOutput.auto_print(f"❌ Orchestration file does not exist: {file_path}")
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    orchestration = yaml.safe_load(content)
                except Exception as e:
                    PrettyOutput.auto_print(f"❌ Failed to read orchestration file: {file_path} - {e}")
                    continue

                if (
                    not orchestration
                    or not isinstance(orchestration, dict)
                    or "agents" not in orchestration
                ):
                    PrettyOutput.auto_print(
                        f"❌ Invalid orchestration file format: {file_path} is missing the 'agents' list"
                    )
                    continue

                agents_config = orchestration["agents"]
                if not isinstance(agents_config, list) or not agents_config:
                    PrettyOutput.auto_print(
                        f"❌ Invalid orchestration file format: {file_path} 'agents' must be a non-empty list"
                    )
                    continue

                all_agents_config.extend(agents_config)

            if not all_agents_config:
                PrettyOutput.auto_print("❌ No valid orchestration config")
                return "", True

            agents_config = all_agents_config

            # Create Agents in batch
            from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool

            if not GatewayManagerTool.check():
                PrettyOutput.auto_print("❌ Web Gateway not connected, cannot create Agent")
                return "", True

            gateway = GatewayManagerTool()
            success_count = 0
            fail_count = 0
            results = []

            for i, agent_cfg in enumerate(agents_config):
                if not isinstance(agent_cfg, dict):
                    PrettyOutput.auto_print(f"⚠️ Agent config #{i + 1} has an invalid format, skipped")
                    fail_count += 1
                    continue

                agent_name = agent_cfg.get("name", f"agent_{i + 1}")
                # The orchestration system always creates agents as type:agent (hjb); it no longer reads the type field from the orchestration file;
                # legacy orchestration files with a type field are ignored (backward compatible).
                agent_type = "agent"
                working_dir = os.path.abspath(
                    os.path.expanduser(agent_cfg.get("working_dir", os.getcwd()))
                )

                # Required field validation
                if not working_dir:
                    PrettyOutput.auto_print(
                        f"⚠️ Agent '{agent_name}' is missing required field working_dir, skipped"
                    )
                    fail_count += 1
                    continue

                try:
                    result = gateway._create_agent(
                        agent_type=agent_type,
                        working_dir=working_dir,
                        name=agent_name,
                        llm_group=agent_cfg.get("llm_group"),
                        tool_group=agent_cfg.get("tool_group"),
                        config_file=agent_cfg.get("config_file"),
                        task=agent_cfg.get("task"),
                        additional_args=agent_cfg.get("additional_args"),
                        worktree=bool(agent_cfg.get("worktree", False)),
                        quick_mode=bool(agent_cfg.get("quick_mode", False)),
                        no_interaction_mode=bool(
                            agent_cfg.get("no_interaction_mode", False)
                        ),
                        # Cross-node/proxy/access-control passthrough; owner is inferred by gateway_manager
                        # as the current Agent's owner, independent of the orchestration file author
                        node_id=agent_cfg.get("node_id"),
                        proxy_node=agent_cfg.get("proxy_node"),
                        access_acl=agent_cfg.get("access_acl"),
                    )
                    if result.get("success"):
                        success_count += 1
                        results.append([agent_name, agent_type, working_dir, "✅ success"])
                        PrettyOutput.auto_print(f"✅ Agent '{agent_name}' created successfully")
                    else:
                        fail_count += 1
                        error_msg = result.get("stderr", "unknown error")
                        results.append(
                            [agent_name, agent_type, working_dir, f"❌ {error_msg}"]
                        )
                        PrettyOutput.auto_print(
                            f"❌ Failed to create Agent '{agent_name}': {error_msg}"
                        )
                except Exception as e:
                    fail_count += 1
                    results.append(
                        [agent_name, agent_type, working_dir, f"❌ Exception: {e}"]
                    )
                    PrettyOutput.auto_print(f"❌ Exception creating Agent '{agent_name}': {e}")

            # Output summary
            _print_markdown_table(
                f"📋 Agent orchestration result (success: {success_count}, failed: {fail_count})",
                ["Name", "Type", "Working Dir", "Status"],
                results,
            )
            return "", True
        elif tag == "ListRule":
            # List all rules and their status
            # Use the agent's rules_manager instance instead of creating a new one
            # This correctly reflects the loaded state of the rules
            rules_manager = agent.rules_manager
            rules_info = rules_manager.get_all_rules_with_status()

            if not rules_info:
                PrettyOutput.auto_print("📋 No rules found")
            else:
                # Build a markdown table
                headers = ["Rule Name", "Content Preview", "File Path", "Status"]
                rows = []
                for rule_name, preview, is_loaded, file_path in rules_info:
                    if len(file_path) > 37:
                        file_path = file_path[:37] + "..."
                    status = "✅ Active" if is_loaded else "🔴 Inactive"
                    rows.append([rule_name, preview, file_path, status])

                _print_markdown_table("📋 All Available Rules", headers, rows)
                PrettyOutput.auto_print(
                    f"Total: {len(rules_info)} rules", timestamp=None
                )

            return "", True
        elif tag == "UnloadRule":
            # Unload loaded rules
            loaded_rules = list(agent.rules_manager.loaded_rules)
            if not loaded_rules:
                _print_markdown_table(
                    "📋 Loaded Rules", ["No.", "Rule Name"], [["-", "None"]]
                )
                PrettyOutput.auto_print("⚠️  No loaded rules")
                return "", True

            # Build table data
            rows = []
            for i, rule in enumerate(loaded_rules, 1):
                rows.append([str(i), rule])

            _print_markdown_table("📋 Loaded Rules", ["No.", "Rule Name"], rows)

            # Get the indices chosen by the user
            idx_str = get_single_line_input(
                "Enter the index of the rule(s) to unload (multiple separated by commas, e.g. 1,3,5):"
            )
            if not idx_str.strip():
                PrettyOutput.auto_print("❌ No index entered, operation cancelled")
                return "", True

            # Parse and unload
            try:
                indices = [int(x.strip()) for x in idx_str.split(",")]
                unloaded = []
                for idx in indices:
                    if 1 <= idx <= len(loaded_rules):
                        rule_to_unload = loaded_rules[idx - 1]
                        agent.rules_manager.unload_rule(rule_to_unload)
                        unloaded.append(rule_to_unload)
                    else:
                        PrettyOutput.auto_print(f"⚠️  Invalid index: {idx}")

                if unloaded:
                    PrettyOutput.auto_print(
                        f"✅ Unloaded {len(unloaded)} rules: {', '.join(unloaded)}"
                    )
                else:
                    PrettyOutput.auto_print("❌ Failed to unload any rule")
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input format, please enter numeric indices")

            return "", True
        elif tag == "ClearRules":
            # Clear all loaded rules (keep default rules)
            loaded_rules = list(agent.rules_manager.loaded_rules)
            if not loaded_rules:
                PrettyOutput.auto_print("📋 No loaded rules")
                return "", True

            # Unload all rules
            count = 0
            for rule in loaded_rules:
                agent.rules_manager.unload_rule(rule)
                count += 1

            PrettyOutput.auto_print(f"✅ Cleared {count} rules")
            return "", True
        elif tag == "SaveSession":
            # Check whether the SaveSession command is allowed
            if not getattr(agent, "allow_savesession", False):
                PrettyOutput.auto_print("⚠️ SaveSession is only available in the hjb/hca main program.")
                return "", True
            if agent.save_session():
                PrettyOutput.auto_print("✅ Session saved successfully.")
            else:
                PrettyOutput.auto_print("❌ Failed to save session.")
            return "", True
        elif tag == "RestoreSession":
            # Check whether the RestoreSession command is allowed
            if not getattr(agent, "allow_savesession", False):
                PrettyOutput.auto_print(
                    "⚠️ RestoreSession is only available in the hjb/hca main program."
                )
                return "", True
            if agent.restore_session():
                PrettyOutput.auto_print("✅ Session restored successfully.")
            else:
                PrettyOutput.auto_print("❌ Failed to restore session.")
            return "", True
        elif tag == "ListSessions":
            # List all saved session files

            sessions = agent.session._parse_session_files()

            if not sessions:
                PrettyOutput.auto_print("📋 No saved session files found.")
            else:
                PrettyOutput.auto_print(f"📋 Found {len(sessions)} session files:")
                for idx, (file_path, timestamp, session_name, _) in enumerate(
                    sessions, 1
                ):
                    # Get the file size
                    try:
                        file_size = os.path.getsize(file_path)
                        size_str = f"({file_size / 1024:.1f} KB)"
                    except OSError:
                        size_str = "(unknown size)"

                    # Format the timestamp display
                    if timestamp:
                        # Timestamp format: YYYYMMDD_HHMMSS
                        try:
                            dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            time_str = timestamp
                    else:
                        time_str = "(no timestamp)"

                    PrettyOutput.auto_print(f"  {idx}. {os.path.basename(file_path)}")
                    PrettyOutput.auto_print(f"     Time: {time_str}  Size: {size_str}")
            return "", True
        elif tag == "Quiet":
            agent.set_non_interactive(True)
            PrettyOutput.auto_print("🔇 Switched to unattended mode (non-interactive)")
            modified_input = modified_input.replace("'<Quiet>'", "")
            continue
        elif tag == "AutoComplete":
            agent.set_non_interactive(True)
            agent.return_control_on_auto_complete = True
            PrettyOutput.auto_print(
                "🤖 Switched to auto-complete mode: after the Agent finishes it will restore interaction and return control to the user"
            )
            modified_input = modified_input.replace("'<AutoComplete>'", "")
            continue
        elif tag == "FixToolCall":
            # Handle the command to fix a tool call
            if not agent._last_response_content:
                PrettyOutput.auto_print("⚠️ No tool call content found to fix")
                return "", True

            PrettyOutput.auto_print("🔧 Constructing fix prompt...")
            error_msg = "User requested manual tool call fix"

            # Import the prompt construction function

            # Get the tool usage instructions
            tool_usage = agent.get_tool_usage_prompt()

            # Construct the fix prompt
            fix_prompt = build_fix_prompt(
                agent._last_response_content, error_msg, tool_usage
            )

            return fix_prompt, False
        elif tag == "SwitchModelGroup":
            # Handle the switch model group command (only available in the main agent)
            if not getattr(agent, "allow_savesession", False):
                PrettyOutput.auto_print("⚠️ SwitchModel is only available in the hjb/hca main program.")
                return "", True

            if switch_model_group(agent):
                PrettyOutput.auto_print("✅ Model group switched successfully.")
            else:
                PrettyOutput.auto_print("❌ Model group switch failed or was cancelled.")
            return "", True
        elif tag == "SwitchModel":
            # Handle the switch model command (switch among the three models of the current model group)
            if not getattr(agent, "allow_savesession", False):
                PrettyOutput.auto_print("⚠️ SwitchModel is only available in the hjb/hca main program.")
                return "", True

            if switch_model(agent):
                PrettyOutput.auto_print("✅ Model switched successfully.")
            else:
                PrettyOutput.auto_print("❌ Model switch failed or was cancelled.")
            return "", True
        elif tag == "SwitchProxyNode":
            # Handle the switch node proxy command (only available in the main agent)
            if not getattr(agent, "allow_savesession", False):
                PrettyOutput.auto_print(
                    "⚠️ SwitchProxyNode is only available in the hjb/hca main program."
                )
                return "", True

            if switch_proxy_node(agent):
                PrettyOutput.auto_print("✅ Proxy node switched successfully.")
            else:
                PrettyOutput.auto_print("❌ Proxy node switch failed or was cancelled.")
            return "", True
        elif tag == "SubAgent":
            # Start a sub-Agent to run a task; when done, ask the user whether to feed the result back to the current Agent
            try:
                from haijunbot.haijunbot_tools.sub_agent import SubAgentTool
                from haijunbot.haijunbot_utils.input import get_multiline_input

                tag_marker = "'<SubAgent>'"
                tag_index = modified_input.find(tag_marker)
                if tag_index == -1:
                    PrettyOutput.auto_print("❌ Invalid Agent command format")
                    return "", True

                # Call multi-line input to get the task description
                PrettyOutput.auto_print(
                    "🤖 Starting sub-Agent, please enter the task description (Ctrl+C to cancel):"
                )
                try:
                    task_desc = get_multiline_input("Enter the sub-Agent task description")
                    if not task_desc:
                        PrettyOutput.auto_print("⚠️  No task description entered, cancelled")
                        return "", True
                except KeyboardInterrupt:
                    PrettyOutput.auto_print("⚠️  User cancelled input")
                    return "", True

                PrettyOutput.auto_print(f"🤖 Starting sub-Agent to run task: {task_desc[:50]}...")

                # Create a sub-Agent using SubAgentTool
                sub_agent_tool = SubAgentTool()
                result = sub_agent_tool.execute(
                    {
                        "task": task_desc,
                        "name": "UserSubAgent",
                        "background": f"User started a subtask via the @Agent command. Current working directory: {os.getcwd()}",
                        "agent": agent,
                    }
                )

                if result.get("success"):
                    stdout = result.get("stdout", "Task completed")
                    PrettyOutput.auto_print("✅ Sub-Agent task completed")
                    PrettyOutput.auto_print(
                        f"📋 Result:\n{stdout[:500]}"
                        + ("..." if len(stdout) > 500 else "")
                    )

                    # Ask the user whether to feed the result back to the current Agent
                    from haijunbot.haijunbot_utils.input import user_confirm

                    if user_confirm(
                        "Feed the sub-Agent result back to the current Agent?",
                        default=True,
                    ):
                        # Return the result as a prompt to the current Agent for processing
                        return (
                            f"\n\nUser ran a task using a sub-Agent: {task_desc}\n\nThe sub-Agent returned:\n{stdout}",
                            False,
                        )
                    else:
                        PrettyOutput.auto_print("ℹ️ Sub-Agent result not fed back to the current Agent")
                        return "", True
                else:
                    stderr = result.get("stderr", "unknown error")
                    PrettyOutput.auto_print(f"❌ Sub-Agent execution failed: {stderr}")
                    return "", True

            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Failed to start sub-Agent: {str(exc)}")
                return "", True
        elif tag == "Init":
            # Start a sub-Agent to analyze the project and generate the .haijunbot/rule.md project overview file
            try:
                from haijunbot.haijunbot_tools.sub_agent import SubAgentTool

                PrettyOutput.auto_print("🚀 Starting sub-Agent to analyze the project and generate a project overview...")

                # Create a sub-Agent using SubAgentTool
                sub_agent_tool = SubAgentTool()
                result = sub_agent_tool.execute(
                    {
                        "task": "You are a project analysis expert. Strictly follow the principles and steps in the following global analysis:\n'<rule:builtin:development_workflow/init_project.md>'\n\nYour task is to deeply analyze the current project, generate a structured project overview file, and write it to the .haijunbot/rules/rule.md file using the write_file tool.\n\nSpecific requirements: analyze the current project's directory structure, tech stack, architecture design, core modules, build method, test method, etc., generate a project overview, and write it to the .haijunbot/rules/rule.md file. The overview should include: project overview, tech stack, directory structure description, core module description, build and run method, test method, key configuration, etc. Please use the write_file tool to write the content into the .haijunbot/rules/rule.md file.",
                        "name": "InitProjectAgent",
                        "background": f"User started project overview generation via the @Init command. Current working directory: {os.getcwd()}",
                        "agent": agent,
                    }
                )

                if result.get("success"):
                    stdout = result.get("stdout", "Project overview generated")
                    PrettyOutput.auto_print("✅ Project overview generated")
                    PrettyOutput.auto_print(
                        f"📋 Result:\n{stdout[:500]}"
                        + ("..." if len(stdout) > 500 else "")
                    )
                else:
                    stderr = result.get("stderr", "unknown error")
                    PrettyOutput.auto_print(f"❌ Failed to generate project overview: {stderr}")

            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Failed to start project overview Agent: {str(exc)}")

            return "", True
        elif tag == "TestCase":
            # Start a sub-Agent to analyze project requirements and generate text-based test cases
            try:
                from haijunbot.haijunbot_tools.sub_agent import SubAgentTool

                PrettyOutput.auto_print("🚀 Starting sub-Agent to analyze project requirements and generate test cases...")

                # Create a sub-Agent using SubAgentTool
                sub_agent_tool = SubAgentTool()
                result = sub_agent_tool.execute(
                    {
                        "task": "You are a test case design expert. Strictly follow the principles and steps in the following built-in rule:\n'<rule:builtin:development_workflow/generate_testcase.md>'\n\nYour task is to deeply analyze the current project's requirement documents and code interfaces, and generate structured text-based test cases to guide subsequent integration test development.\n\nSpecific requirements: analyze the current project's requirement documents, Spec files (under the .haijunbot/rules/spec/ directory), and code interface definitions, and generate a text-based test case file to guide subsequent integration test development. The test cases should cover: functional testing, boundary condition testing, exception handling testing, interface compatibility testing. Each test case should include: case ID, case name, preconditions, test steps, expected result, priority. Please use the write_file tool to write the test cases into the .haijunbot/rules/spec/test_cases.md file.",
                        "name": "TestCaseAgent",
                        "background": f"User started test case generation via the @TestCase command. Current working directory: {os.getcwd()}",
                        "agent": agent,
                    }
                )

                if result.get("success"):
                    stdout = result.get("stdout", "Test cases generated")
                    PrettyOutput.auto_print("✅ Test cases generated")
                    PrettyOutput.auto_print(
                        f"📋 Result:\n{stdout[:500]}"
                        + ("..." if len(stdout) > 500 else "")
                    )
                else:
                    stderr = result.get("stderr", "unknown error")
                    PrettyOutput.auto_print(f"❌ Failed to generate test cases：{stderr}")

            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Failed to start test case Agent：{str(exc)}")

            return "", True
        elif tag == "SubCodeAgent":
            # Start a sub-CodeAgent to run code tasks; when done, ask the user whether to feed the result back to the current Agent
            try:
                from haijunbot.haijunbot_tools.sub_code_agent import SubCodeAgentTool
                from haijunbot.haijunbot_utils.input import get_multiline_input

                tag_marker = "'<SubCodeAgent>'"
                tag_index = modified_input.find(tag_marker)
                if tag_index == -1:
                    PrettyOutput.auto_print("❌ Invalid SubCodeAgent command format")
                    return "", True

                # Call multi-line input to get the task description
                PrettyOutput.auto_print(
                    "💻 Starting sub-CodeAgent, please enter the task description (Ctrl+C to cancel):"
                )
                try:
                    task_desc = get_multiline_input("Enter the sub-CodeAgent task description")
                    if not task_desc:
                        PrettyOutput.auto_print("⚠️  No task description entered, cancelled")
                        return "", True
                except KeyboardInterrupt:
                    PrettyOutput.auto_print("⚠️  User cancelled input")
                    return "", True

                # Create a sub-CodeAgent using SubCodeAgentTool
                sub_code_agent_tool = SubCodeAgentTool()
                result = sub_code_agent_tool.execute(
                    {
                        "task": task_desc,
                        "name": "UserSubCodeAgent",
                        "background": f"User started a sub code task via the @SubCodeAgent command. Current working directory: {os.getcwd()}",
                        "agent": agent,
                    }
                )

                if result.get("success"):
                    stdout = result.get("stdout", "Task completed")
                    PrettyOutput.auto_print("✅ Sub-CodeAgent task completed")
                    PrettyOutput.auto_print(
                        f"📋 Result:\n{stdout[:500]}"
                        + ("..." if len(stdout) > 500 else "")
                    )

                    # Ask the user whether to feed the result back to the current Agent
                    from haijunbot.haijunbot_utils.input import user_confirm

                    if user_confirm(
                        "Feed the sub-CodeAgent result back to the current Agent?",
                        default=True,
                    ):
                        # Return the result as a prompt to the current Agent for processing
                        return (
                            f"\n\nUser ran a task using a sub-CodeAgent: {task_desc}\n\nThe sub-CodeAgent returned:\n{stdout}",
                            False,
                        )
                    else:
                        PrettyOutput.auto_print("ℹ️ Sub-CodeAgent result not fed back to the current Agent")
                        return "", True
                else:
                    stderr = result.get("stderr", "unknown error")
                    PrettyOutput.auto_print(f"❌ Sub-CodeAgent execution failed: {stderr}")
                    return "", True

            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Failed to start sub-CodeAgent: {str(exc)}")
                return "", True
        elif tag == "Btw":
            # Handle the temporary chat command, without disturbing the main agent context
            try:
                PrettyOutput.auto_print("💬 Entering temporary chat mode (type /bye or an empty line to exit)")
                chat_with_model("")
                PrettyOutput.auto_print("✅ Returned to the main Agent")
            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Chat failed: {str(exc)}")
            return "", True
        elif tag == "Commit":
            # Handle the code commit command (must run inside a git repository)
            try:
                find_git_root()
            except Exception:
                PrettyOutput.auto_print("⚠️ The Commit command must run inside a git repository.")
                return "", True

            PrettyOutput.auto_print("📝 Committing code...")

            # Get the current end commit
            end_commit = get_latest_commit_hash()

            # Get or create the GitManager
            git_manager = getattr(agent, "git_manager", None)
            if git_manager is None:
                git_manager = GitManager(os.getcwd())

            # Get the commit history
            start_commit = getattr(agent, "start_commit", None)
            if start_commit is None:
                # Not a code agent (or the start commit cannot be obtained): find the first
                # non-CheckPoint commit going back from HEAD as the initial start point, and squash
                # the temporary commits left by CodeAgent into a formal commit, avoiding leftover history.
                start_commit = find_recent_non_checkout_commit()
                if start_commit:
                    PrettyOutput.auto_print(
                        f"ℹ️ Detected a temporary CheckPoint commit, squashing from {start_commit[:7]} into a formal commit"
                    )
                    commits = git_manager.show_commit_between(start_commit, end_commit)
                    post_process_func = getattr(
                        getattr(agent, "post_process_manager", None),
                        "post_process_modified_files",
                        None,
                    )
                    if post_process_func is None:
                        post_process_func = lambda *args, **kwargs: None  # noqa: E731

                    git_manager.handle_commit_confirmation(
                        commits,
                        start_commit,
                        prefix=getattr(agent, "prefix", ""),
                        suffix=getattr(agent, "suffix", ""),
                        agent=agent,
                        post_process_func=post_process_func,
                        skip_confirm=True,
                    )
                else:
                    # Brand new repository (no non-CheckPoint commits): commit the current working tree changes directly
                    from haijunbot.haijunbot_git_utils.git_commiter import GitCommitTool

                    git_commiter = GitCommitTool()
                    git_commiter.execute(
                        {
                            "prefix": getattr(agent, "prefix", ""),
                            "suffix": getattr(agent, "suffix", ""),
                            "agent": agent,
                            "llm_group": get_llm_group(),
                        }
                    )
            else:
                # There may already be formal commits during the task (user manual commits or from a prior <Commit>).
                # First advance the task start point to the last non-temporary commit, to avoid the subsequent
                # handle_commit_confirmation's reset --mixed clobbering these formal commits.
                new_start = advance_start_commit(start_commit)
                if new_start and new_start != start_commit:
                    start_commit = new_start
                    agent.start_commit = new_start
                    PrettyOutput.auto_print(
                        f"ℹ️ Detected a formal commit, task start point updated to {new_start[:7]}"
                    )

                commits = git_manager.show_commit_between(start_commit, end_commit)

                # Call handle_commit_confirmation to handle commit confirmation
                # Use the prefix/suffix stored in the agent; no extra post-processing function needed
                post_process_func = getattr(
                    getattr(agent, "post_process_manager", None),
                    "post_process_modified_files",
                    None,
                )
                if post_process_func is None:
                    post_process_func = lambda *args, **kwargs: None  # noqa: E731

                git_manager.handle_commit_confirmation(
                    commits,
                    start_commit,
                    prefix=getattr(agent, "prefix", ""),
                    suffix=getattr(agent, "suffix", ""),
                    agent=agent,
                    post_process_func=post_process_func,
                    skip_confirm=True,
                )

            # Automatically save the session after the commit completes
            if getattr(agent, "allow_savesession", False):
                if agent.save_session():
                    PrettyOutput.auto_print("✅ Session saved successfully.")
                else:
                    PrettyOutput.auto_print("❌ Failed to save session.")

            # Return a hint message, appended to addon_prompt
            return (
                "\n\n**🔖 Code committed**: The previous task goal is complete and the code has been committed successfully.\n\n**⚠️ Important**:\n- The previous goal is done, no need to focus on it anymore\n- When reviewing code, don't review the previous changes\n- Please start a new task goal based on the user's new requirements\n",
                True,
            )

        elif tag == "GitPush":
            # Handle the GitPush command, push code to remotes
            try:
                find_git_root()
            except Exception:
                PrettyOutput.auto_print("⚠ Current directory is not in a Git repository, cannot push code")
                return "", True

            PrettyOutput.auto_print("🚀 Pushing code to all remotes...")
            try:
                from haijunbot.haijunbot_tools.execute_script import ScriptTool

                if sys.platform == "win32":
                    interpreter = "powershell"
                    script_content = (
                        "$remotes = git remote; "
                        "if (-not $remotes) { Write-Output 'NO_REMOTE'; exit 0 }; "
                        "$branch = git branch --show-current; "
                        "$failed = @(); "
                        "foreach ($r in $remotes) { "
                        'Write-Output "=== PUSH $r ==="; '
                        "git push $r; "
                        "if ($LASTEXITCODE -ne 0) { "
                        "if ($branch) { git push $r $branch }; "
                        "if ($LASTEXITCODE -ne 0) { $failed += $r } "
                        "} "
                        "}; "
                        "if ($failed.Count -gt 0) { "
                        "Write-Output (\"FAILED_REMOTES: \" + ($failed -join ', ')); exit 1 } "
                        "else { Write-Output 'ALL_PUSH_OK' }"
                    )
                else:
                    interpreter = "bash"
                    script_content = (
                        "remotes=$(git remote); "
                        "if [ -z \"$remotes\" ]; then echo 'NO_REMOTE'; exit 0; fi; "
                        "branch=$(git branch --show-current); "
                        "failed=''; "
                        "for r in $remotes; do "
                        'echo "=== PUSH $r ==="; '
                        'git push "$r" || { '
                        'if [ -n "$branch" ]; then git push "$r" "$branch"; fi; '
                        "}; "
                        'if [ $? -ne 0 ]; then failed="$failed $r"; fi; '
                        "done; "
                        'if [ -n "$failed" ]; then '
                        'echo "FAILED_REMOTES:$failed"; exit 1; '
                        "else echo 'ALL_PUSH_OK'; fi"
                    )

                script_tool = ScriptTool()
                result = script_tool.execute(
                    {
                        "interpreter": interpreter,
                        "script_content": script_content,
                        "execution_mode": "interactive",
                    }
                )
                stdout = result.get("stdout", "") or ""
                stderr = result.get("stderr", "") or ""
                if result.get("success"):
                    if "NO_REMOTE" in stdout:
                        PrettyOutput.auto_print("⚠ No remote repository configured, nothing to push")
                    else:
                        PrettyOutput.auto_print("✅ Code pushed to all remotes")
                        if stdout.strip():
                            PrettyOutput.auto_print(stdout.strip())
                else:
                    PrettyOutput.auto_print("❌ Some or all remote pushes failed")
                    if stdout.strip():
                        PrettyOutput.auto_print(stdout.strip())
                    if stderr.strip():
                        PrettyOutput.auto_print(stderr.strip())
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Code push exception: {e}")
            return "", True

        elif tag == "Pin":
            # The Pin marker was already handled earlier, skip
            continue
        elif tag == "Diff":
            # Handle the Diff command, show changes from start_commit to now

            # Check whether the agent has a start_commit attribute
            if not hasattr(agent, "start_commit"):
                PrettyOutput.auto_print("⚠️ The current Agent has no start_commit attribute, cannot show changes")
                return "", True

            start_commit = agent.start_commit
            if not start_commit:
                PrettyOutput.auto_print("⚠️ start_commit is empty, cannot show changes")
                return "", True

            # Get the current commit
            end_commit = get_latest_commit_hash()
            if not end_commit:
                PrettyOutput.auto_print("⚠️ Cannot get the current commit")
                return "", True

            # Get the diff
            PrettyOutput.auto_print(
                f"📊 Getting changes from {start_commit[:8]} to {end_commit[:8]}..."
            )
            diff_text = get_diff_between_commits(start_commit, end_commit)

            if not diff_text:
                PrettyOutput.auto_print("✅ No changes")
                return "", True

            # Show the diff
            PrettyOutput.auto_print("📝 Changes:")
            visualize_diff_enhanced(diff_text, mode="side_by_side")
            return "", True

        elif tag == "InstallTrack":
            import subprocess

            tag_marker = "'<InstallTrack>'"
            tag_index = modified_input.find(tag_marker)
            inline_arg = ""
            if tag_index != -1:
                inline_arg = modified_input[tag_index + len(tag_marker) :].strip()
            if not inline_arg:
                PrettyOutput.auto_print(
                    "❌ InstallTrack requires arguments. Usage:\n"
                    "  '<InstallTrack>' https://github.com/user/repo  # install from a remote repository\n"
                    "  '<InstallTrack>' /path/to/local/track        # install from a local path (symlink)"
                )
                return "", True

            track_path = inline_arg.strip().strip('"').strip("'")
            tracks_dir = os.path.join(
                os.path.expanduser("~"), ".haijunbot", "rules", "tracks"
            )
            os.makedirs(tracks_dir, exist_ok=True)

            # Determine whether it is a remote link or a local path
            if track_path.startswith(("http://", "https://", "git@", "ssh://")):
                # Remote repository: git clone
                # Extract the repository name from the URL as the directory name
                repo_name = track_path.rstrip("/").split("/")[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
                target_dir = os.path.join(tracks_dir, repo_name)

                if os.path.exists(target_dir):
                    PrettyOutput.auto_print(f"❌ Track directory already exists: {target_dir}")
                    return "", True

                try:
                    PrettyOutput.auto_print(
                        f"📦 Installing Track from remote repository: {track_path}"
                    )
                    result = subprocess.run(
                        ["git", "clone", track_path, target_dir],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        PrettyOutput.auto_print(f"✅ Track installed successfully: {target_dir}")
                    else:
                        # Clean up the directory when clone fails
                        if os.path.exists(target_dir):
                            import shutil

                            shutil.rmtree(target_dir, ignore_errors=True)
                        PrettyOutput.auto_print(
                            f"❌ git clone failed: {result.stderr.strip()}"
                        )
                except subprocess.TimeoutExpired:
                    if os.path.exists(target_dir):
                        import shutil

                        shutil.rmtree(target_dir, ignore_errors=True)
                    PrettyOutput.auto_print("❌ git clone timed out (120 seconds)")
                except Exception as e:
                    if os.path.exists(target_dir):
                        import shutil

                        shutil.rmtree(target_dir, ignore_errors=True)
                    PrettyOutput.auto_print(f"❌ Installation failed: {e}")
            elif (
                os.path.isabs(track_path)
                or track_path.startswith("./")
                or track_path.startswith("../")
            ):
                # Local path: create a symlink
                if not os.path.exists(track_path):
                    PrettyOutput.auto_print(f"❌ Local path does not exist: {track_path}")
                    return "", True

                # Get the link name (use the last directory segment of the path)
                link_name = os.path.basename(os.path.normpath(track_path))
                link_path = os.path.join(tracks_dir, link_name)

                if os.path.exists(link_path) or os.path.islink(link_path):
                    PrettyOutput.auto_print(f"❌ Track link already exists: {link_path}")
                    return "", True

                try:
                    abs_track_path = os.path.abspath(track_path)
                    if os.name == "nt":
                        # Windows: use copy instead of symlink
                        import shutil

                        if os.path.isdir(abs_track_path):
                            shutil.copytree(abs_track_path, link_path)
                        else:
                            shutil.copy2(abs_track_path, link_path)
                        PrettyOutput.auto_print(
                            f"✅ Track file copied successfully: {link_path} <- {abs_track_path}"
                        )
                    else:
                        os.symlink(abs_track_path, link_path)
                        PrettyOutput.auto_print(
                            f"✅ Track symlink created successfully: {link_path} -> {abs_track_path}"
                        )
                except Exception as e:
                    PrettyOutput.auto_print(f"❌ Failed to create link/copy: {e}")
            else:
                PrettyOutput.auto_print(
                    "❌ Invalid argument, provide a remote repository link (http/https/ssh) or a local absolute path"
                )

            return "", True
        elif tag == "Review":
            # Handle the Review command, run a single code review
            # Check whether it is a CodeAgent
            agent_type = getattr(agent, "_agent_type", "agent")
            if agent_type != "code_agent":
                PrettyOutput.auto_print(
                    "⚠ The Review command only supports CodeAgent; the current Agent does not support code review"
                )
                return "", True

            # Call the review tool to run a single review (reuse tool logic instead of calling CodeReviewer directly)
            from haijunbot.haijunbot_tools.review import ReviewTool

            result = ReviewTool().run_review(agent)

            # Review passed, return directly
            if result.get("ok", True):
                return "", True

            # Review found issues, ask the user whether to feed them back into the next round for fixing
            issues = result.get("issues", [])
            if not issues:
                return "", True

            from haijunbot.haijunbot_utils.input import user_confirm

            if user_confirm(
                "Feed the review issues back into the next conversation round for fixing?",
                default=True,
            ):
                # Build a fix prompt using CodeReviewer
                from haijunbot.haijunbot_code_agent.code_reviewer import CodeReviewer

                review_prompt = CodeReviewer.build_review_fix_prompt(result)
                return review_prompt, False
            else:
                PrettyOutput.auto_print("ℹ️ User chose not to feed back the review issues")
                return "", True

        elif tag == "SetMaxToken":
            # Handle the SetMaxToken command, set the max input token count
            value_str = get_single_line_input(
                "Enter the max input token count (<200000 sets it to 200000, 0 removes the limit):"
            )
            if value_str is None:
                return "", True
            try:
                value = int(value_str.strip())
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input, please enter an integer")
                return "", True
            if value == 0:
                os.environ.pop("HAIJUNBOT_MAX_INPUT_TOKEN_COUNT", None)
                PrettyOutput.auto_print("✅ Max input token limit removed")
            else:
                if value < 200000:
                    value = 200000
                    PrettyOutput.auto_print("⚠ Input value is less than 200000, automatically set to 200000")
                os.environ["HAIJUNBOT_MAX_INPUT_TOKEN_COUNT"] = str(value)
                PrettyOutput.auto_print(f"✅ Max input token count set to {value}")
            return "", True
        elif tag == "C2RustConfig":
            # Handle the C2RustConfig command, manage transpilation config
            from haijunbot.haijunbot_c2rust.eli import config as c2rust_config
            from pathlib import Path
            from haijunbot.haijunbot_utils.input import user_confirm, get_multiline_input

            PrettyOutput.auto_print("📋 C2Rust Config Management")

            # Ask for the operation type
            action = (
                get_single_line_input("Operation type [config/show/clear]: ").strip().lower()
            )

            if action == "show":
                # Show the current config
                c2rust_config(show=True)
                return "", True
            elif action == "clear":
                # Clear the config
                if user_confirm("Confirm clearing the config?", default=False):
                    c2rust_config(clear=True)
                return "", True
            elif action == "config" or action == "":
                # Config mode
                # Ask for the header file path (optional)
                files_input = get_single_line_input(
                    "Header file paths (multiple separated by commas, leave blank to skip): "
                ).strip()
                files = None
                if files_input:
                    files = [Path(f.strip()) for f in files_input.split(",")]

                # Ask for the root symbol list (optional)
                root_syms = get_single_line_input(
                    "Root symbol list (comma separated, leave blank to skip): "
                ).strip()
                root_list_syms = root_syms if root_syms else None

                # Ask for the disabled library list (optional)
                disabled_libs_input = get_single_line_input(
                    "Disabled library list (comma separated, leave blank to skip): "
                ).strip()
                disabled_libs = disabled_libs_input if disabled_libs_input else None

                # Ask for additional notes (optional, multi-line)
                additional_notes = get_multiline_input("Additional notes (blank line to finish)")

                # Ask whether to enable FFI validation (optional, confirm)
                enable_ffi = user_confirm("Enable FFI export validation?", default=True)

                try:
                    c2rust_config(
                        files=files,
                        root_list_syms=root_list_syms,
                        disabled_libs=disabled_libs,
                        additional_notes=additional_notes,
                        enable_ffi_export_validation=enable_ffi,
                    )
                except Exception as e:
                    PrettyOutput.auto_print(f"❌ C2Rust config failed: {e}")
                return "", True
            else:
                PrettyOutput.auto_print(f"❌ Unknown operation type: {action}")
                return "", True
        elif tag == "C2RustRun":
            # Handle the C2RustRun command, run the transpilation pipeline
            from haijunbot.haijunbot_c2rust.eli import run as c2rust_run
            from haijunbot.haijunbot_utils.input import user_confirm

            PrettyOutput.auto_print("🚀 C2Rust Transpilation Pipeline")

            # Ask for the model group (optional)
            llm_group = get_single_line_input("Model group name (leave blank for default): ").strip()
            llm_group = llm_group if llm_group else None

            # Ask for the max retry count (default 0)
            max_retries_input = get_single_line_input(
                "Max retries [0=unlimited]: "
            ).strip()
            max_retries = int(max_retries_input) if max_retries_input else 0

            # Ask whether to use interactive mode (default false)
            interactive = user_confirm("Enable interactive mode?", default=False)

            # Ask whether to reset state (default false)
            reset = user_confirm("Reset state and start over?", default=False)

            # Ask whether to use quick mode (default true)
            quick_mode = user_confirm("Enable quick mode?", default=True)

            try:
                c2rust_run(
                    llm_group=llm_group,
                    max_retries=max_retries,
                    interactive=interactive,
                    reset=reset,
                    quick_mode=quick_mode,
                )
            except Exception as e:
                PrettyOutput.auto_print(f"❌ C2Rust transpilation failed: {e}")
            return "", True
        elif tag == "C2RustVerify":
            # Handle the C2RustVerify command, verify feature parity
            from haijunbot.haijunbot_c2rust.eli import verify as c2rust_verify
            from haijunbot.haijunbot_utils.input import user_confirm

            PrettyOutput.auto_print("🔍 C2Rust Feature Verification")

            # Ask for the model group (optional)
            llm_group = get_single_line_input("Model group name (leave blank for default): ").strip()
            llm_group = llm_group if llm_group else None

            # Ask for the max iteration count (default 10)
            max_iterations_input = get_single_line_input("Max iterations [10]: ").strip()
            max_iterations = int(max_iterations_input) if max_iterations_input else 10

            # Ask whether to use interactive mode (default false)
            interactive = user_confirm("Enable interactive mode?", default=False)

            # Ask whether to use quick mode (default true)
            quick_mode = user_confirm("Enable quick mode?", default=True)

            try:
                c2rust_verify(
                    llm_group=llm_group,
                    max_iterations=max_iterations,
                    interactive=interactive,
                    quick_mode=quick_mode,
                )
            except Exception as e:
                PrettyOutput.auto_print(f"❌ C2Rust verification failed: {e}")
            return "", True
        elif tag == "SecConfig":
            # Handle the SecConfig command, manage security scan config
            from haijunbot.haijunbot_sec.eli import config as sec_config
            from haijunbot.haijunbot_utils.input import user_confirm

            PrettyOutput.auto_print("🔒 Security Scan Config Management")

            # Ask for the operation type
            action = (
                get_single_line_input("Operation type [config/show/clear]: ").strip().lower()
            )

            if action == "show":
                sec_config(show=True)
                return "", True
            elif action == "clear":
                if user_confirm("Confirm clearing the config?", default=False):
                    sec_config(clear=True)
                return "", True
            elif action == "config" or action == "":
                # Config mode
                # Ask for the scan target
                target = get_single_line_input(
                    "Scan target (file or directory path, leave blank to skip): "
                ).strip()
                target = target if target else None

                # Ask for the language filter
                languages = get_single_line_input(
                    "Language filter (comma separated e.g. c,cpp,rust, leave blank to skip): "
                ).strip()
                languages = languages if languages else None

                # Ask for excluded directories
                exclude_dirs = get_single_line_input(
                    "Exclude directories (comma separated, leave blank to skip): "
                ).strip()
                exclude_dirs = exclude_dirs if exclude_dirs else None

                # Ask for the output format
                output_format = get_single_line_input(
                    "Output format [csv/markdown]: "
                ).strip()
                output_format = output_format if output_format else None

                # Ask for the output file
                output_file = get_single_line_input(
                    "Output file path (leave blank to skip): "
                ).strip()
                output_file = output_file if output_file else None

                # Ask for the cluster limit
                cluster_limit_input = get_single_line_input("Cluster limit [50]: ").strip()
                cluster_limit = (
                    int(cluster_limit_input) if cluster_limit_input else None
                )

                # Ask whether to enable secondary verification
                enable_verification = user_confirm("Enable secondary verification?", default=True)

                # Ask whether to force using memory
                force_save_memory = user_confirm("Force using memory?", default=False)

                # Ask for the model group
                llm_group = get_single_line_input(
                    "Model group name (leave blank for default): "
                ).strip()
                llm_group = llm_group if llm_group else None

                try:
                    sec_config(
                        target=target,
                        languages=languages,
                        exclude_dirs=exclude_dirs,
                        output_format=output_format,
                        output_file=output_file,
                        cluster_limit=cluster_limit,
                        enable_verification=enable_verification,
                        force_save_memory=force_save_memory,
                        llm_group=llm_group,
                    )
                except Exception as e:
                    PrettyOutput.auto_print(f"❌ Sec config failed: {e}")
                return "", True
            else:
                PrettyOutput.auto_print(f"❌ Unknown operation type: {action}")
                return "", True
        elif tag == "SecAnalyze":
            # Handle the SecAnalyze command, analyze security issues from JSON
            from haijunbot.haijunbot_sec.eli import analyze as sec_analyze
            from haijunbot.haijunbot_utils.input import user_confirm

            PrettyOutput.auto_print("📊 Analyzing security issues from JSON")

            # Ask for the input file (required)
            input_file = get_single_line_input("JSON file path: ").strip()
            if not input_file:
                PrettyOutput.auto_print("❌ Must provide a JSON file path")
                return "", True

            # Ask for the output format
            output_format = get_single_line_input("Output format [csv/markdown]: ").strip()
            output_format = output_format if output_format else None

            # Ask for the output file
            output_file = get_single_line_input("Output file path (leave blank to skip): ").strip()
            output_file = output_file if output_file else None

            # Ask for the cluster limit
            cluster_limit_input = get_single_line_input("Cluster limit [50]: ").strip()
            cluster_limit = int(cluster_limit_input) if cluster_limit_input else None

            # Ask whether to enable secondary verification
            enable_verification = user_confirm("Enable secondary verification?", default=True)

            # Ask whether to force using memory
            force_save_memory = user_confirm("Force using memory?", default=False)

            try:
                sec_analyze(
                    input=input_file,
                    output_format=output_format,
                    output_file=output_file,
                    cluster_limit=cluster_limit,
                    enable_verification=enable_verification,
                    force_save_memory=force_save_memory,
                )
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Sec analysis failed: {e}")
            return "", True
        elif tag == "SecHeuristic":
            # Handle the SecHeuristic command, heuristic security scan
            from haijunbot.haijunbot_sec.eli import heuristic as sec_heuristic

            PrettyOutput.auto_print("🔍 Heuristic Security Scan")

            # Ask for the scan target (required)
            target = get_single_line_input("Scan target (file or directory path): ").strip()
            if not target:
                PrettyOutput.auto_print("❌ Must provide a scan target")
                return "", True

            # Ask for the output format
            output_format = get_single_line_input("Output format [json/markdown]: ").strip()
            output_format = output_format if output_format else "json"

            # Ask for the output file
            output_file = get_single_line_input(
                "Output file path (leave blank to print to terminal): "
            ).strip()
            output_file = output_file if output_file else None

            # Ask for the rule filter
            rules = get_single_line_input(
                "Rule filter (comma separated e.g. unsafe_api,buffer_overflow, leave blank to skip): "
            ).strip()
            rules = rules if rules else None

            try:
                sec_heuristic(
                    target=target,
                    output_format=output_format,
                    output_file=output_file,
                    rules=rules,
                )
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Sec heuristic scan failed: {e}")
            return "", True
        elif tag == "SecScan":
            # Handle the SecScan command, run a security scan
            from haijunbot.haijunbot_sec.eli import scan as sec_scan

            PrettyOutput.auto_print("🔒 Running Security Scan")
            PrettyOutput.auto_print("Reading config from the config file; to modify, use the SecConfig command")

            try:
                sec_scan()
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Sec scan failed: {e}")
            return "", True
        elif tag == "Cat":
            # Handle the Cat command, view file contents
            import os
            from haijunbot.haijunbot_utils.input import get_multiline_input

            PrettyOutput.auto_print("🐱 View File Contents")
            PrettyOutput.auto_print("Please enter a file path (relative or absolute):")

            # Use multi-line input to get the file path
            file_path = get_multiline_input("Enter the file path, press Enter to confirm").strip()

            if not file_path:
                PrettyOutput.auto_print("⚠️ No file path entered, operation cancelled")
                return "", True

            # Handle the path
            if not os.path.isabs(file_path):
                # Relative path, based on the current working directory
                file_path = os.path.join(os.getcwd(), file_path)

            # Check whether the file exists
            if not os.path.exists(file_path):
                PrettyOutput.auto_print(f"❌ File does not exist: {file_path}")
                return "", True

            if not os.path.isfile(file_path):
                PrettyOutput.auto_print(f"❌ Not a file: {file_path}")
                return "", True

            # Read the file contents
            try:
                # Check the file size; prompt the user if over 1MB
                file_size = os.path.getsize(file_path)
                if file_size > 1024 * 1024:  # 1MB
                    PrettyOutput.auto_print(
                        f"⚠️ File is large ({file_size / 1024 / 1024:.2f} MB), reading may take a while..."
                    )

                # Try reading the file with multiple encodings
                encodings = ["utf-8", "gbk", "gb2312", "latin1"]
                content = None
                used_encoding = None

                for encoding in encodings:
                    try:
                        with open(file_path, "r", encoding=encoding) as f:
                            content = f.read()
                        used_encoding = encoding
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue

                if content is None:
                    # If all encodings fail, try reading in binary mode
                    with open(file_path, "rb") as f:
                        content = f.read().decode("utf-8", errors="replace")
                    used_encoding = "binary (with replacement)"

                # Show file info
                PrettyOutput.auto_print(f"📄 File: {file_path}")
                PrettyOutput.auto_print(f"📊 Size: {file_size} bytes")
                PrettyOutput.auto_print(f"🔤 Encoding: {used_encoding}")

                # Show the file contents
                PrettyOutput.auto_print(content)
                PrettyOutput.auto_print("✅ File read complete")

            except Exception as e:
                PrettyOutput.auto_print(f"❌ Failed to read file: {e}")

            return "", True
        # Check custom input handlers
        if tag in _custom_tag_handlers:
            try:
                handler = _custom_tag_handlers[tag]
                result = handler(user_input, agent, tag)
                if isinstance(result, tuple) and len(result) == 2:
                    return result
                PrettyOutput.auto_print(
                    f"⚠ Custom input handler '<{tag}>' returned a wrong format; expected (str, bool)"
                )
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Custom input handler '<{tag}>' execution failed: {e}")
            return "", True

        # Handle plain replacement markers
        if tag in replace_map:
            processed_tag.add(tag)
            if (
                "append" in replace_map[tag]
                and replace_map[tag]["append"]
                and tag not in processed_tag
            ):
                modified_input = modified_input.replace(f"'<{tag}>'", "")
                add_on_prompt += replace_map[tag]["template"] + "\n"
            else:
                modified_input = modified_input.replace(
                    f"'<{tag}>'", replace_map[tag]["template"]
                )
        elif tag.startswith("rule:"):
            # Handle rule:xxx format rule markers
            if tag not in processed_tag:
                rule_name = tag[5:]  # strip the "rule:" prefix
                processed_tag.add(tag)

                # Load the rule: call RulesManager.load_rule()
                # Use the Agent's existing rules_manager instance instead of creating a new one
                # The Agent always has a rules_manager attribute, use it directly
                rules_manager = agent.rules_manager
                loaded = rules_manager.load_rule(rule_name)

                if loaded:
                    # Add the loaded rule to agent.loaded_rule_names
                    if not hasattr(agent, "loaded_rule_names"):
                        agent.loaded_rule_names = set()
                    agent.loaded_rule_names.add(rule_name)
                    PrettyOutput.auto_print(f"🟢 Rule loaded: {rule_name}")

                    # Get the content from the loaded-rule cache
                    rule_content = rules_manager._loaded_rules.get(rule_name)
                    if rule_content:
                        separator = "\n" + "=" * 50 + "\n"
                        modified_input = modified_input.replace(
                            f"'<{tag}>'", f"<rule>\n{rule_content}\n</rule>{separator}"
                        )

    # Set the addon prompt and return the processed content
    agent.set_addon_prompt(add_on_prompt)

    # [New] Restore the sender prefix to preserve sender info in the agent conversation
    if _sender_prefix and not modified_input.startswith(_sender_prefix):
        modified_input = _sender_prefix + modified_input

    return modified_input, False


def get_platform_type_from_agent(agent: Any) -> str:
    """Return the platform type based on the Agent's _model_type attribute

    Args:
        agent: Agent instance

    Returns:
        str: platform type, 'smart', 'normal', or 'cheap'
    """
    return getattr(agent, "_model_type", "normal")


def list_model_groups() -> Optional[List[Tuple[str, str, str, str, str]]]:
    """List all available model groups

    Returns:
        Optional[List[Tuple[str, str, str, str, str]]]: list of model groups, each element is (group_name, smart_model, normal_model, cheap_model, eval_model)
    """

    model_groups = _get_global_config().get("llm_groups", {})
    if not isinstance(model_groups, dict) or not model_groups:
        PrettyOutput.auto_print("📋 No model group config found")
        return None

    groups = []
    for group_name, group_config in model_groups.items():
        if isinstance(group_config, dict):
            # Get the model name for each platform
            smart_model = group_config.get("smart_llm", "-")
            normal_model = group_config.get("normal_llm", "-")
            cheap_model = group_config.get("cheap_llm", "-")
            # Show "-" when the structured eval model is not configured
            eval_model = group_config.get("eval_llm", "-")
            groups.append(
                (group_name, smart_model, normal_model, cheap_model, eval_model)
            )

    return groups


def check_context_limit(
    agent: Any, new_model_group: str, platform_type: str = "normal"
) -> Tuple[bool, str]:
    """Check whether the current conversation exceeds the new model's context limit

    Args:
        agent: Agent instance
        new_model_group: new model group name
        platform_type: platform type ('normal' or 'smart')

    Returns:
        Tuple[bool, str]: (whether switching is allowed, reason)
    """
    model_groups = _get_global_config().get("llm_groups", {})
    if not isinstance(model_groups, dict):
        return False, "model group config does not exist"

    group_config = model_groups.get(new_model_group)
    if not isinstance(group_config, dict):
        return False, f"model group '{new_model_group}' does not exist"

    # Get the token count of the current conversation
    current_tokens = 0
    if hasattr(agent, "model"):
        # Get all messages from model and compute tokens
        try:
            messages_text = str(agent.model.get_messages())
            current_tokens = get_context_token_count(messages_text)
        except Exception:
            # If it cannot be computed, use a rough estimate
            current_tokens = 0

    # Get the corresponding token limit by platform type
    if platform_type == "smart":
        token_limit_key = "smart_max_input_token_count"
    else:
        token_limit_key = "max_input_token_count"

    # Get the token limit from the model group config
    token_limit = group_config.get(token_limit_key)
    if token_limit is None:
        # Try to get it from the llms reference
        normal_llm = group_config.get("normal_llm")
        if normal_llm:
            llms = _get_global_config().get("llms", {})
            llm_config = llms.get(normal_llm, {})
            token_limit = llm_config.get("max_input_token_count")

    if token_limit is None:
        # Use the default limit
        token_limit = 200000

    # Check whether the limit is exceeded (leaving 10% headroom)
    if current_tokens > token_limit * 0.9:
        return (
            False,
            f"Current conversation ({current_tokens} tokens) exceeds 90% of the new model limit ({token_limit} tokens)",
        )

    return (
        True,
        f"Current conversation ({current_tokens} tokens) is within the new model limit ({token_limit} tokens)",
    )


def switch_platform_type(
    agent: Any, platform_type: str, preserve_model_group: bool = True
) -> bool:
    """Switch platform type (smart/normal/cheap), keeping or updating the model group

    Args:
        agent: Agent instance
        platform_type: platform type ('smart', 'normal', or 'cheap')
        preserve_model_group: whether to keep the current model group unchanged (default True)

    Returns:
        bool: whether the switch succeeded
    """
    try:
        # Save the old model's messages
        old_messages = agent.model.get_messages()

        # Recreate the model
        platform_registry = PlatformRegistry()
        if platform_type == "smart":
            agent.model = platform_registry.get_smart_platform()
        elif platform_type == "cheap":
            agent.model = platform_registry.get_cheap_platform()
        else:
            agent.model = platform_registry.get_normal_platform()

        agent.model.set_suppress_output(False)
        agent.model.agent = agent

        # Set the old messages on the new model
        if old_messages:
            agent.model.set_messages(old_messages)

        # Set the new model on the existing session
        agent.session.model = agent.model

        return True
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to switch platform type: {e}")
        return False


def perform_switch(
    agent: Any, new_model_group: str, platform_type: str = "normal"
) -> bool:
    """Perform the model group switch

    Args:
        agent: Agent instance
        new_model_group: new model group name
        platform_type: platform type ('normal' or 'smart')

    Returns:
        bool: whether the switch succeeded
    """
    try:
        # Update the global config
        set_llm_group(new_model_group)

        # Use the generic platform type switch function
        result = switch_platform_type(agent, platform_type, preserve_model_group=False)
        if result:
            agent._model_type = platform_type
            # Report to the gateway so the Agent list model group stays consistent with the real running state
            _report_agent_config_change({"llm_group": new_model_group})
        return result
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to switch model group: {e}")
        return False


def switch_model_group(agent: Any) -> bool:
    """Main function to switch the model group

    Args:
        agent: Agent instance

    Returns:
        bool: whether the switch succeeded
    """
    # Get the current model group
    current_group = get_llm_group() or "(not set)"
    PrettyOutput.auto_print(f"📌 Current model group: {current_group}")

    # List all model groups
    groups = list_model_groups()
    if not groups:
        return False

    # Check whether fzf is available
    import shutil

    fzf_available = shutil.which("fzf") is not None

    # Show the model group list (print a markdown table only when fzf is unavailable)
    if not fzf_available:
        headers = ["No.", "Model Group Name", "Smart", "Normal", "Cheap", "Eval"]
        rows = []
        for idx, (
            group_name,
            smart_model,
            normal_model,
            cheap_model,
            eval_model,
        ) in enumerate(groups, 1):
            rows.append(
                [
                    str(idx),
                    group_name,
                    smart_model,
                    normal_model,
                    cheap_model,
                    eval_model,
                ]
            )
        _print_markdown_table("📋 Available Model Groups", headers, rows)
        PrettyOutput.auto_print("")
    # User selection (using an interactive selector)
    # Show detailed info in fzf mode, and simple names in single-line input mode
    if fzf_available:
        # Show detailed info in fzf mode
        choice_names = [
            f"{group_name} (Smart: {smart_model}, Normal: {normal_model}, Cheap: {cheap_model}, Eval: {eval_model})"
            for group_name, smart_model, normal_model, cheap_model, eval_model in groups
        ]
    else:
        # Show simple names in single-line input mode
        choice_names = [group_name for group_name, *_ in groups]

    selected = get_choice("Select a model group:", choice_names)

    # Handle cancellation (Esc in fzf or an empty string input)
    if not selected:
        PrettyOutput.auto_print("🚫 Switch cancelled")
        return False

    # Extract the selected model group name (remove the detailed info in fzf mode)
    if fzf_available:
        # Extract the model group name from the detailed string
        selected_group_name = selected.split(" (")[0]
    else:
        selected_group_name = selected

    # Find the index of the selected model group
    choice_idx = -1
    for idx, (group_name, *_) in enumerate(groups):
        if group_name == selected_group_name:
            choice_idx = idx
            break

    if choice_idx == -1:
        PrettyOutput.auto_print("❌ Invalid selection")
        return False

    new_group = groups[choice_idx][0]

    # Perform the switch logic
    try:
        # Check whether it is the same as the current model group
        if new_group == current_group:
            PrettyOutput.auto_print("⚠️ Already using this model group")
            return False

        # Get the platform type
        platform_type = get_platform_type_from_agent(agent)

        # Check the context limit
        can_switch, reason = check_context_limit(agent, new_group, platform_type)
        if not can_switch:
            PrettyOutput.auto_print(f"⚠️ {reason}")
            PrettyOutput.auto_print("🚫 Switch cancelled")
            return False
        else:
            PrettyOutput.auto_print(f"✅ {reason}")

        # Perform the switch
        PrettyOutput.auto_print(f"🔄 Switching to model group '{new_group}'...")
        if perform_switch(agent, new_group, platform_type):
            PrettyOutput.auto_print(f"✅ Successfully switched to model group '{new_group}'")
            # Set the manual switch flag to disable subsequent automatic switching
            agent._manual_model_switch = True
            return True
        else:
            return False
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Switch failed: {e}")
        return False


def _check_context_and_compress_if_needed(
    agent: Any, target_platform_type: str
) -> bool:
    """Check whether switching to the target model will exceed the context limit, and trigger compression if so

    Args:
        agent: Agent instance
        target_platform_type: target model type (smart/normal/cheap)

    Returns:
        bool: True if the context check passes (or compression succeeds), otherwise False
    """
    try:
        from haijunbot.haijunbot_utils.config import (
            get_max_input_token_count,
            get_smart_max_input_token_count,
            get_cheap_max_input_token_count,
        )

        # Get the target model's context limit
        if target_platform_type == "smart":
            target_max_tokens = get_smart_max_input_token_count()
        elif target_platform_type == "cheap":
            target_max_tokens = get_cheap_max_input_token_count()
        else:  # normal
            target_max_tokens = get_max_input_token_count()

        # Get the currently used token count
        current_used_tokens = agent.model.get_used_token_count()

        # If the currently used token count exceeds the target model's limit, trigger compression
        if current_used_tokens > target_max_tokens:
            PrettyOutput.auto_print(
                f"⚠️ Current context ({current_used_tokens} tokens) exceeds the target model limit ({target_max_tokens} tokens)"
            )
            PrettyOutput.auto_print("🔄 Triggering context compression...")

            # Trigger compression
            compression_success = agent._adaptive_compression()
            if not compression_success:
                PrettyOutput.auto_print("❌ Context compression failed, cannot switch to the target model")
                return False

            # Re-check after compression
            new_used_tokens = agent.model.get_used_token_count()
            if new_used_tokens > target_max_tokens:
                PrettyOutput.auto_print(
                    f"❌ After compression the context ({new_used_tokens} tokens) still exceeds the target model limit ({target_max_tokens} tokens)"
                )
                return False

            PrettyOutput.auto_print(
                f"✅ Compression succeeded, current context: {new_used_tokens} tokens"
            )

        return True
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Context check failed: {e}")
        # Allow switching to continue when the check fails (keep the previous behavior)
        return True


def switch_model(agent: Any) -> bool:
    """Switch between the three models (smart/normal/cheap) of the current model group

    Args:
        agent: Agent instance

    Returns:
        bool: whether the switch succeeded
    """
    # Get the current model group
    current_group = get_llm_group()
    if not current_group:
        PrettyOutput.auto_print("❌ No model group set")
        return False

    PrettyOutput.auto_print(f"📌 Current model group: {current_group}")

    # Get the current model group's config
    model_groups = _get_global_config().get("llm_groups", {})
    if not isinstance(model_groups, dict):
        PrettyOutput.auto_print("❌ Model group config does not exist")
        return False

    group_config = model_groups.get(current_group)
    if not isinstance(group_config, dict):
        PrettyOutput.auto_print(f"❌ Model group '{current_group}' config does not exist")
        return False

    # Get the three models
    smart_model = group_config.get("smart_llm", "")
    normal_model = group_config.get("normal_llm", "")
    cheap_model = group_config.get("cheap_llm", "")

    # Build the list of available models
    available_models = []
    if smart_model:
        available_models.append(("smart", "Smart", smart_model))
    if normal_model:
        available_models.append(("normal", "Normal", normal_model))
    if cheap_model:
        available_models.append(("cheap", "Cheap", cheap_model))

    if not available_models:
        PrettyOutput.auto_print("❌ The current model group has no available models")
        return False

    # Get the currently used model type
    current_platform_type = get_platform_type_from_agent(agent)
    PrettyOutput.auto_print(f"📌 Current model type: {current_platform_type}")

    # Check whether fzf is available
    import shutil

    fzf_available = shutil.which("fzf") is not None

    # Get the global config to get LLM details
    global_config = _get_global_config()
    llms_config = global_config.get("llms", {})

    # Show the model list (print a markdown table only when fzf is unavailable)
    if not fzf_available:
        headers = ["No.", "Type", "Model Name", "Multimodal", "Context Length", "Status"]
        rows = []
        for idx, (model_type, type_name, model_name) in enumerate(available_models, 1):
            # Get LLM config details
            llm_detail = llms_config.get(model_name, {})
            max_tokens = llm_detail.get("max_input_token_count", "N/A")
            supports_multimodal = llm_detail.get("llm_config", {}).get(
                "supports_multimodal", False
            )
            multimodal_str = "✅" if supports_multimodal else "❌"
            status = "✓ current" if model_type == current_platform_type else ""
            rows.append(
                [
                    str(idx),
                    type_name,
                    model_name,
                    multimodal_str,
                    str(max_tokens),
                    status,
                ]
            )
        _print_markdown_table(f"📋 Available models in model group '{current_group}'", headers, rows)
        PrettyOutput.auto_print("")
    # User selection (using an interactive selector)
    # Show detailed info in fzf mode, and simple names in single-line input mode
    if fzf_available:
        # Show detailed info in fzf mode
        choice_names = []
        for model_type, type_name, model_name in available_models:
            # Get LLM config details
            llm_detail = llms_config.get(model_name, {})
            max_tokens = llm_detail.get("max_input_token_count", "N/A")
            supports_multimodal = llm_detail.get("llm_config", {}).get(
                "supports_multimodal", False
            )
            choice_names.append(
                f"{type_name}: {model_name} (multimodal: {'✅' if supports_multimodal else '❌'}, context: {max_tokens})"
            )
    else:
        # Show simple names in single-line input mode
        choice_names = [
            f"{type_name}: {model_name}"
            for _, type_name, model_name in available_models
        ]

    selected = get_choice("Select a model:", choice_names)

    # Handle cancellation (Esc in fzf or an empty string input)
    if not selected:
        PrettyOutput.auto_print("🚫 Switch cancelled")
        return False

    # Extract the selected model type name (remove the detailed info in fzf mode)
    if fzf_available:
        # Extract the model type name from the detailed string
        selected_type_name = selected.split(": ")[0]
    else:
        selected_type_name = selected.split(": ")[0]

    # Find the index of the selected model
    choice_idx = -1
    for idx, (model_type, type_name, model_name) in enumerate(available_models):
        if type_name == selected_type_name:
            choice_idx = idx
            break

    if choice_idx == -1:
        PrettyOutput.auto_print("❌ Invalid selection")
        return False

    selected_type, type_name, model_name = available_models[choice_idx]

    # Check whether it is the same as the current model
    if selected_type == current_platform_type:
        PrettyOutput.auto_print("⚠️ Already using this model")
        return False

    # Check the context limit and trigger compression if necessary
    if not _check_context_and_compress_if_needed(agent, selected_type):
        PrettyOutput.auto_print("❌ Context check failed, cannot switch model")
        return False

    PrettyOutput.auto_print(f"🔄 Switching to {type_name} model '{model_name}'...")

    # Use the generic platform type switch function
    if switch_platform_type(agent, selected_type):
        agent._model_type = selected_type
        PrettyOutput.auto_print(f"✅ Successfully switched to {type_name} model '{model_name}'")
        # Set the manual switch flag to disable subsequent automatic switching
        agent._manual_model_switch = True
        return True
    else:
        PrettyOutput.auto_print("❌ Failed to switch model")
        return False


def switch_proxy_node(agent: Any) -> bool:
    """Main function to switch the node proxy.

    Model platforms support accessing models through other node proxies: when
    jglobals.proxy_node and jglobals.master_url are set, each platform's base_url
    is rewritten to a Gateway-forwarded proxy address; the original node may become invalid, so this command allows switching to another node at runtime.

    Interaction: first list the nodes known to the gateway and let the user choose
    by number; leaving it blank means no proxy (i.e. direct connection).

    Args:
        agent: Agent instance

    Returns:
        bool: whether the switch succeeded
    """
    import json

    import haijunbot.haijunbot_utils.globals as jglobals

    # Proxy relies on master_url to build the forwarding address; unusable when not set
    if not jglobals.master_url:
        PrettyOutput.auto_print(
            "❌ master_url is not set, cannot use node proxy.\n"
            "   Please start with --master-url or set the HAIJUNBOT_MASTER_URL environment variable."
        )
        return False

    current_node = jglobals.proxy_node or "(no proxy)"
    PrettyOutput.auto_print(f"📌 Current node proxy: {current_node}")

    # Get the gateway node list (degrade to manual node ID input on failure)
    node_ids: List[str] = []
    try:
        from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool

        if GatewayManagerTool.check():
            result = GatewayManagerTool()._list_nodes()
            if result.get("success"):
                nodes = json.loads(result.get("stdout", "{}")).get("nodes", [])
                for node in nodes:
                    if isinstance(node, dict) and node.get("node_id"):
                        node_ids.append(str(node["node_id"]))
            else:
                PrettyOutput.auto_print(
                    f"⚠️ Failed to get node list: {result.get('stderr', 'unknown error')}"
                )
        else:
            PrettyOutput.auto_print("⚠️ Web Gateway not connected, falling back to manual node ID input")
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Exception getting node list: {e}")

    if node_ids:
        # Show the node list (markdown table compatible with terminal and frontend)
        rows = [[str(idx), node_id] for idx, node_id in enumerate(node_ids, 1)]
        _print_markdown_table("📋 Available Nodes", ["No.", "Node ID"], rows)
        prompt = (
            "Enter the index of the node proxy to use (blank means no proxy; enter a node ID to specify directly): "
        )
    else:
        prompt = "Enter the node proxy node ID to use (blank means no proxy): "

    user_input = get_single_line_input(prompt)
    if user_input is None:
        PrettyOutput.auto_print("🚫 Switch cancelled")
        return False

    user_input = user_input.strip()

    # Blank: no proxy
    if not user_input:
        if jglobals.proxy_node is None:
            PrettyOutput.auto_print("⚠️ No proxy is currently in use")
            return False
        jglobals.proxy_node = None
        PrettyOutput.auto_print("🔄 Node proxy disabled, rebuilding model...")
        if switch_platform_type(agent, get_platform_type_from_agent(agent)):
            PrettyOutput.auto_print("✅ Switched to direct connection (no proxy)")
            # Report to the gateway to clear the proxy, so the Agent list proxy node stays consistent
            _report_agent_config_change({"proxy_node": ""})
            return True
        PrettyOutput.auto_print("❌ Failed to rebuild model; proxy settings updated but may not take effect")
        return False

    # Parse input: numeric index takes priority, otherwise treat as node ID
    new_node = ""
    if user_input.isdigit() and node_ids:
        idx = int(user_input)
        if 1 <= idx <= len(node_ids):
            new_node = node_ids[idx - 1]
        else:
            PrettyOutput.auto_print(f"❌ Index out of range (1-{len(node_ids)})")
            return False
    else:
        new_node = user_input

    if new_node == jglobals.proxy_node:
        PrettyOutput.auto_print("⚠️ Already using this node proxy")
        return False

    # Update the proxy node and rebuild the model so the new proxy takes effect immediately
    jglobals.proxy_node = new_node
    PrettyOutput.auto_print(f"🔄 Switching to node proxy '{new_node}'...")
    if switch_platform_type(agent, get_platform_type_from_agent(agent)):
        PrettyOutput.auto_print(f"✅ Successfully switched to node proxy '{new_node}'")
        # Report to the gateway so the Agent list proxy node stays consistent
        _report_agent_config_change({"proxy_node": new_node})
        return True
    PrettyOutput.auto_print("❌ Failed to rebuild model; proxy settings updated but may not take effect")
    return False


def _safe_parse_value(value_str: str):
    """
    Safely parse a config value, supporting YAML-compatible syntax.

    Parse strategy:
    1. Try yaml.safe_load() (supports strings, numbers, booleans, lists, dicts)
    2. If parsing fails, return the original string as-is
    3. Never use eval(), to ensure safety

    Args:
        value_str: string representation of the value

    Returns:
        The parsed value (may be any YAML-compatible type)
    """

    value_str = value_str.strip()

    # Empty string
    if not value_str:
        return ""

    # Try YAML parsing
    try:
        parsed = yaml.safe_load(value_str)
        # yaml.safe_load parses unquoted strings into their corresponding types
        # If it is None (e.g. input "null"), return the original string
        if parsed is None and value_str.lower() != "null":
            return value_str
        return parsed
    except yaml.YAMLError:
        # Parsing failed, return the original string as-is
        return value_str


def _set_nested_config(config, key_path: str, value) -> tuple[bool, str]:
    """
    Set a nested config key-value.

    Args:
        config: config dict object (CaseInsensitiveDict or a plain dict)
        key_path: dot-separated key path (e.g. "ENV.http_proxy")
        value: the value to set

    Returns:
        (success: bool, message: str): success flag and message
    """
    keys = key_path.split(".")

    if not keys or not keys[0]:
        return False, "key path cannot be empty"

    # Walk to the second-to-last key, creating intermediate nodes if needed
    current = config
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            # Auto-create intermediate dict nodes
            current[key] = {}
        elif not isinstance(current[key], (dict, type(config))):
            return False, f"Path conflict: '{key}' already exists but is not a dict (cannot nest further)"
        current = current[key]

    # Set the value of the last key
    final_key = keys[-1]
    try:
        current[final_key] = value
        return True, ""
    except Exception as e:
        return False, f"Set failed: {e}"


def _delete_nested_config(config, key_path: str) -> tuple[bool, str]:
    """
    Delete a nested config key.

    Args:
        config: config dict object
        key_path: dot-separated key path

    Returns:
        (success: bool, message: str): success flag and message
    """
    keys = key_path.split(".")

    if not keys or not keys[0]:
        return False, "key path cannot be empty"

    # Walk to the second-to-last key
    current = config
    for i, key in enumerate(keys[:-1]):
        if key not in current:
            return False, f"Path does not exist: '{key}' at level {i + 1}"
        elif not isinstance(current[key], (dict, type(config))):
            return False, f"Invalid path: '{key}' is not a dict, cannot access nested keys"
        current = current[key]

    # Delete the last key
    final_key = keys[-1]
    if final_key not in current:
        return False, f"Config item does not exist: {key_path}"

    try:
        del current[final_key]
        return True, ""
    except Exception as e:
        return False, f"Delete failed: {e}"
