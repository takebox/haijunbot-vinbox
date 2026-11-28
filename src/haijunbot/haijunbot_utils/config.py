# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
from functools import lru_cache
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import cast

from haijunbot.haijunbot_utils.builtin_replace_map import BUILTIN_REPLACE_MAP
from haijunbot.haijunbot_utils.collections import CaseInsensitiveDict
from haijunbot.haijunbot_utils.exception_utils import save_exception


# Global environment variable storage

GLOBAL_CONFIG_DATA: CaseInsensitiveDict = CaseInsensitiveDict()

# System default encoding: Windows uses gbk, other platforms use utf-8
DEFAULT_ENCODING = "gbk" if sys.platform == "win32" else "utf-8"


def get_default_encoding() -> str:
    """Get the system default encoding. gbk for Windows, utf-8 for others"""
    return DEFAULT_ENCODING


# Encoding detection: common encoding trial order (utf-8 first, for modern files; gbk next, for Windows Chinese)
# Note: 'utf-16' is not included, because Python's utf-16 encoder strictly requires a BOM, and BOM detection is handled separately
_DETECT_ENCODINGS = ["utf-8", "gbk", "gb2312", "utf-16-le", "utf-16-be", "latin1"]
_DETECT_SAMPLE_SIZE = 16384  # Read the first 16KB for detection


def _score_chinese_text(text: str) -> int:
    """Evaluate the number of valid Chinese characters in the text (used to distinguish GBK from Big5)"""
    score = 0
    for char in text:
        # Common Chinese character ranges: CJK Unified Ideographs (most common)
        if "\u4e00" <= char <= "\u9fff":
            score += 10
        # Extended A area Chinese characters
        elif "\u3400" <= char <= "\u4dbf":
            score += 5
        # Other CJK symbols and punctuation
        elif "\u3000" <= char <= "\u303f":
            score += 3
        # Full-width characters
        elif "\uff00" <= char <= "\uffef":
            score += 2
        # ASCII alphanumeric
        elif char.isascii() and char.isalnum():
            score += 1
    return score


def detect_file_encoding(
    file_path: str, sample_size: int = _DETECT_SAMPLE_SIZE
) -> Optional[str]:
    """Detect encoding based on file content

    Uses the file --mime-encoding command for encoding detection.

    Args:
        file_path: File path
        sample_size: Unused, retained for interface compatibility

    Returns:
        The detected encoding name, or None if it fails
    """
    try:
        if not os.path.exists(file_path):
            return None

        result = subprocess.run(
            ["file", "--mime-encoding", "-b", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            detected = result.stdout.strip().lower()
            # Normalize encoding name
            encoding_map = {
                "gb2312": "gb18030",
                "gbk": "gb18030",
                "ascii": "utf-8",
                "us-ascii": "utf-8",
                "iso-8859-1": "latin1",
                "binary": None,
            }
            detected = encoding_map.get(detected, detected)

            # Return gb18030 uniformly for Chinese encodings
            if detected in ("gb18030", "gbk", "big5", "gb2312"):
                return "gb18030"

            return detected

    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    return None


def read_text_file(
    file_path: str,
    *,
    encoding: Optional[str] = None,
    errors: str = "replace",
    detect_encoding: bool = True,
) -> str:
    """Read a text file, with automatic encoding detection support

    Args:
        file_path: File path
        encoding: Specified encoding; if None, auto-detect or use the system default
        errors: Decoding error handling; defaults to "replace"
        detect_encoding: Whether to detect encoding first; defaults to True

    Returns:
        The text content of the file
    """
    enc = encoding
    if enc is None and detect_encoding:
        enc = detect_file_encoding(file_path)
    if enc is None:
        enc = get_default_encoding()
    with open(file_path, "r", encoding=enc, errors=errors) as f:
        return f.read()


# Context length limit constants
MAX_CONTEXT_LENGTH = 64 * 1024  # 64k token absolute upper limit


def calculate_token_limit(remaining_tokens: int) -> int:
    """
    Calculate the token limit: the minimum of 2/3 of the remaining tokens and MAX_CONTEXT_LENGTH

    Args:
        remaining_tokens: Number of remaining tokens

    Returns:
        int: The maximum allowed token count (2/3 of remaining tokens or 64k, whichever is smaller)
    """
    if remaining_tokens <= 0:
        return 0
    return min(int(remaining_tokens * 2 / 3), MAX_CONTEXT_LENGTH)


def set_global_config_data(env_data: Dict[str, Any]) -> None:
    """Set global environment variable data"""
    global GLOBAL_CONFIG_DATA
    # Update in place, to avoid other modules that hold old references via `from ... import GLOBAL_CONFIG_DATA`
    # having them become invalid after config reload.
    GLOBAL_CONFIG_DATA.clear()
    GLOBAL_CONFIG_DATA.update(env_data)


def get_global_config_data() -> CaseInsensitiveDict:
    """Get global configuration data

    Returns:
        CaseInsensitiveDict: Global configuration dictionary
    """
    global GLOBAL_CONFIG_DATA
    return GLOBAL_CONFIG_DATA


def set_config(key: str, value: Any) -> None:
    """Set configuration"""
    GLOBAL_CONFIG_DATA[key] = value


def get_llm_group() -> Optional[str]:
    """Get the current model group name

    Returns:
        Optional[str]: Model group name, or None if not set
    """
    value = GLOBAL_CONFIG_DATA.get("llm_group")
    return cast(Optional[str], value)


def set_llm_group(llm_group: Optional[str]) -> None:
    """Set the current model group

    Args:
        llm_group: Model group name; if None, the existing configuration is not modified
    """
    # Only set when llm_group is not None, to avoid overwriting the llm_group in the config file
    if llm_group is not None:
        GLOBAL_CONFIG_DATA["llm_group"] = llm_group


def get_fallback_group() -> Optional[str]:
    """Get the fallback model group name of the current model group

    The fallback group is specified by the fallback_group field of the current group in llm_groups, used in non-interactive mode
    to automatically switch when the current group's model fails repeatedly.

    Returns:
        Optional[str]: Fallback model group name; returns None when the current group is not configured, when fallback_group is not configured,
            when the fallback group is empty or the same as the current group, or when the fallback group is not in llm_groups
    """
    current_group = get_llm_group()
    if not current_group:
        return None

    model_groups = GLOBAL_CONFIG_DATA.get("llm_groups", {})
    if not isinstance(model_groups, dict):
        return None

    group_config = model_groups.get(current_group)
    if not isinstance(group_config, dict):
        return None

    fallback_group = group_config.get("fallback_group")
    if not isinstance(fallback_group, str):
        return None
    fallback_group = fallback_group.strip()
    if not fallback_group or fallback_group == current_group:
        return None
    if fallback_group not in model_groups:
        return None
    return fallback_group


def switch_to_fallback_group() -> bool:
    """Switch to the fallback model group of the current model group

    Only switches the llm_group in the global configuration; the caller must rebuild the model instance after switching for the config to take effect.

    Returns:
        bool: Whether the switch succeeded (returns False when no available fallback group)
    """
    fallback_group = get_fallback_group()
    if not fallback_group:
        return False
    set_llm_group(fallback_group)
    return True


def get_plugin_dirs() -> List[str]:
    """Get the list of plugin directories

    Returns:
        List[str]: List of plugin directory paths, or an empty list if not configured
    """
    value = GLOBAL_CONFIG_DATA.get("plugin_dirs", [])
    return cast(List[str], value)


def get_plugin_config(plugin_name: str) -> Dict[str, Any]:
    """Get the private configuration of the specified plugin (non-extension-point fields).

    In the plugin config.yaml, fields other than the extension-point fields (tool_load_dirs/rules_load_dirs, etc.)
    are isolated into a separate configuration item `plugin_configs.<plugin_name>` for the plugin itself
    to read, avoiding polluting the global configuration and avoiding private fields with the same name in multiple plugins overwriting each other.

    Args:
        plugin_name: Plugin name (directory name or the name field of config.yaml)

    Returns:
        Dict[str, Any]: Plugin private configuration dictionary; returns an empty dictionary if not found
    """
    plugin_configs = GLOBAL_CONFIG_DATA.get("plugin_configs", {})
    if isinstance(plugin_configs, dict):
        config = plugin_configs.get(plugin_name)
        if isinstance(config, dict):
            return config
    return {}


def get_all_plugin_configs() -> Dict[str, Any]:
    """Get the private configuration of all plugins.

    Returns:
        Dict[str, Any]: Mapping of plugin name -> plugin private configuration
    """
    plugin_configs = GLOBAL_CONFIG_DATA.get("plugin_configs", {})
    return plugin_configs if isinstance(plugin_configs, dict) else {}


"""Configuration management module.

This module provides functions to obtain various configuration settings of the HaijunBot system.
All configurations are read from environment variables, with fallback default values.
"""


def get_git_commit_prompt() -> str:
    """
    Get the Git commit prompt template

    Returns:
        str: Git commit message generation prompt template, or an empty string if not configured
    """
    return cast(str, GLOBAL_CONFIG_DATA.get("git_commit_prompt", ""))


def get_after_change_tools_config() -> Dict[str, List[str]]:
    """Get the file post-change processing tool command configuration (read from config.yaml)

    The key of the configuration item after_change_tools is the file extension/filename, and the value is a list of command templates.
    Supported formats: ["template1", "template2"] or [("tool1", "template1"), ("tool2", "template2")].
    Keys are uniformly converted to lowercase.

    Returns:
        Dict[str, List[str]]: File extension/filename -> list of command templates, or an empty dictionary if not configured
    """
    raw = GLOBAL_CONFIG_DATA.get("after_change_tools", {})
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, List[str]] = {}
    for k, v in raw.items():
        if not isinstance(v, list) or not v:
            continue
        k_lower = str(k).lower()
        if isinstance(v[0], str):
            # New format: directly a list of command templates
            result[k_lower] = v
        elif isinstance(v[0], (list, tuple)) and len(v[0]) == 2:
            # Old format: need to extract the template
            result[k_lower] = [template for _, template in v]
    return result


def get_lint_tools_config() -> Dict[str, List[str]]:
    """Get the lint tool command configuration (read from config.yaml)

    The key of the configuration item lint_tools is the file extension/filename, and the value is a list of command templates.
    Supported formats: ["template1", "template2"] or [("tool1", "template1"), ("tool2", "template2")].
    Keys are uniformly converted to lowercase.

    Returns:
        Dict[str, List[str]]: File extension/filename -> list of command templates, or an empty dictionary if not configured
    """
    raw = GLOBAL_CONFIG_DATA.get("lint_tools", {})
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, List[str]] = {}
    for k, v in raw.items():
        if not isinstance(v, list) or not v:
            continue
        k_lower = str(k).lower()
        if isinstance(v[0], str):
            # New format: directly a list of command templates
            result[k_lower] = v
        elif isinstance(v[0], (list, tuple)) and len(v[0]) == 2:
            # Old format: need to extract the template
            result[k_lower] = [template for _, template in v]
    return result


def get_haijunbot_github_url() -> str:
    """
    Get the GitHub repository address of HaijunBot

    Returns:
        str: GitHub repository address, or a default value if not configured
    """
    return cast(
        str,
        GLOBAL_CONFIG_DATA.get(
            "haijunbot_github_url", "https://github.com/takebox/HaijunBot.git"
        ),
    )


def get_haijunbot_gitee_url() -> str:
    """
    Get the Gitee repository address of HaijunBot

    Returns:
        str: Gitee repository address, or a default value if not configured
    """
    return cast(
        str,
        GLOBAL_CONFIG_DATA.get(
            "haijunbot_gitee_url", "https://gitee.com/takebox/HaijunBot.git"
        ),
    )


@lru_cache(maxsize=None)
def get_replace_map() -> Dict[str, Any]:
    """
    Get the replacement mapping table.

    Prefer the configuration in GLOBAL_CONFIG_DATA['replace_map'],
    and return the built-in replacement mapping table if not configured.

    Note: it performs Jinja2 rendering on the template content in the built-in replacement mapping table,
    replacing variable placeholders with actual paths.

    Returns:
        dict: The merged replacement mapping table dictionary (built-in + the mapping table in the configuration)
    """
    from haijunbot.haijunbot_utils.template_utils import render_rule_template

    # Render the templates in the built-in replacement mapping table
    rendered_builtin_map = {}
    for key, value in BUILTIN_REPLACE_MAP.items():
        if isinstance(value, dict) and "template" in value:
            # Render the template content
            template_str = value["template"]
            if not isinstance(template_str, str):
                rendered_builtin_map[key] = value
                continue
            rendered_template = render_rule_template(template_str, "")
            rendered_builtin_map[key] = {**value, "template": rendered_template}
        else:
            rendered_builtin_map[key] = value

    if "replace_map" in GLOBAL_CONFIG_DATA:
        return {**rendered_builtin_map, **GLOBAL_CONFIG_DATA["replace_map"]}

    return rendered_builtin_map


def get_max_input_token_count() -> int:
    """
    Get the maximum input token count allowed by the model.

    Preferably use the environment variable HAIJUNBOT_MAX_INPUT_TOKEN_COUNT; if not set, obtain it from the model configuration.

    Returns:
        int: The maximum input token count the model can handle.
    """
    env_value = os.environ.get("HAIJUNBOT_MAX_INPUT_TOKEN_COUNT")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass
    config = _get_resolved_model_config()
    return int(config.get("max_input_token_count", "200000"))


def calculate_content_token_limit(agent: Any = None) -> int:
    """
    Dynamically calculate the content length limit (token count) based on the current model configuration

    Args:
        agent: Agent instance, used to obtain the model and the remaining token count

    Returns:
        int: The maximum allowed token count (calculated based on remaining tokens, retaining a safety margin)
    """
    try:
        # Prefer the remaining token count
        if agent and hasattr(agent, "model"):
            try:
                remaining_tokens = agent.model.get_remaining_token_count()
                # Use 2/3 of the remaining tokens as the limit, retaining 1/3 as a safety margin
                return calculate_token_limit(remaining_tokens)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_utils.config",
                    function="calculate_content_token_limit",
                )
                pass

        # Fallback: use 2/3 of the input window
        max_input_tokens = get_max_input_token_count()
        # Calculate the token count for the 2/3 limit
        return int(max_input_tokens * 2 / 3)
    except Exception:
        # If all methods fail, return the default value of 500 tokens
        return 500


def get_cheap_max_input_token_count() -> int:
    """
    Get the maximum input token count allowed by the cheap model.

    Returns:
        int: The maximum input token count the model can handle; falls back to the normal configuration if not configured
    """
    config = _get_resolved_model_config()
    cheap_max_token = config.get("cheap_max_input_token_count")
    if cheap_max_token:
        return int(cheap_max_token)
    return get_max_input_token_count()


def get_smart_max_input_token_count() -> int:
    """
    Get the maximum input token count allowed by the smart model.

    Returns:
        int: The maximum input token count the model can handle; falls back to the normal configuration if not configured
    """
    config = _get_resolved_model_config()
    smart_max_token = config.get("smart_max_input_token_count")
    if smart_max_token:
        return int(smart_max_token)
    return get_max_input_token_count()


def get_shell_name() -> str:
    """
    Nama shell yang dipakai Vinbox.

    Vinbox memakai PowerShell Core (pwsh) di Windows, Linux dan macOS; tidak ada
    cmd.exe, powershell.exe atau bash yang dipanggil dari kode.

    Returns:
        str: ``pwsh``
    """
    from haijunbot.haijunbot_utils.vinbox_runtime import shell_path

    return os.path.basename(shell_path()).lower()


def _apply_llm_config_to_env(resolved_config: Dict[str, Any]) -> None:
    """
    Apply the llm_config in resolved_config to environment variables.

    Args:
        resolved_config: The parsed model configuration dictionary
    """
    # Handle the llm_config of normal_llm
    if "llm_config" in resolved_config and isinstance(
        resolved_config["llm_config"], dict
    ):
        for key, value in resolved_config["llm_config"].items():
            if value is not None:
                # Convert configuration keys to environment variable format (uppercase, underscore-separated)
                env_key = str(key).upper()
                os.environ[env_key] = str(value)

    # Handle the llm_config of cheap_llm
    if "cheap_llm_config" in resolved_config and isinstance(
        resolved_config["cheap_llm_config"], dict
    ):
        for key, value in resolved_config["cheap_llm_config"].items():
            if value is not None:
                env_key = str(key).upper()
                os.environ[env_key] = str(value)

    # Handle the llm_config of smart_llm
    if "smart_llm_config" in resolved_config and isinstance(
        resolved_config["smart_llm_config"], dict
    ):
        for key, value in resolved_config["smart_llm_config"].items():
            if value is not None:
                env_key = str(key).upper()
                os.environ[env_key] = str(value)


def _resolve_llm_reference(llm_name: str) -> Dict[str, Any]:
    """
    Parse the referenced LLM configuration from the llms configuration.

    Args:
        llm_name: The name of the LLM configuration defined in llms

    Returns:
        Dict[str, Any]: The parsed LLM configuration dictionary, containing platform, model, max_input_token_count, llm_config
    """
    from haijunbot.haijunbot_utils.output import PrettyOutput

    llms = GLOBAL_CONFIG_DATA.get("llms", {})
    if not isinstance(llms, dict):
        return {}

    llm_config = llms.get(llm_name)
    if not isinstance(llm_config, dict):
        PrettyOutput.auto_print(f"⚠️ Warning: configuration named '{llm_name}' not found in llms")
        return {}

    return llm_config.copy()


def _expand_llm_references(group_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expand the llm references in llm_groups (normal_llm, cheap_llm, smart_llm) into the corresponding configuration fields.

    Note: llm_groups no longer supports directly defining parameters such as platform and model; it can only reference the configuration defined in llms.

    Args:
        group_config: Model group configuration dictionary

    Returns:
        Dict[str, Any]: The expanded configuration dictionary

    Raises:
        ValueError is raised if parameters such as platform and model are directly defined in the group configuration
    """
    expanded_config = group_config.copy()

    # Check whether disallowed parameters are directly defined
    forbidden_keys = [
        "platform",
        "model",
        "max_input_token_count",
        "cheap_platform",
        "cheap_model",
        "cheap_max_input_token_count",
        "smart_platform",
        "smart_model",
        "smart_max_input_token_count",
        "eval_platform",
        "eval_model",
        "eval_max_input_token_count",
    ]
    found_forbidden = [key for key in forbidden_keys if key in expanded_config]
    if found_forbidden:
        raise ValueError(
            f"❌ Error: llm_groups no longer supports directly defining the following parameters: {', '.join(found_forbidden)}."
            f"Please use normal_llm, cheap_llm, smart_llm, eval_llm to reference the configurations defined in llms."
        )

    # Validate that at least the normal_llm reference is required
    if "normal_llm" not in expanded_config:
        raise ValueError(
            "❌ Error: llm_groups must define at least the normal_llm reference."
            "Please use normal_llm to reference the configuration defined in llms."
        )

    # Handle the normal_llm reference
    llm_ref = _resolve_llm_reference(expanded_config["normal_llm"])
    if not llm_ref:
        raise ValueError(
            f"❌ Error: the '{expanded_config['normal_llm']}' referenced by normal_llm does not exist in llms."
        )
    # Directly use the referenced value; no longer check whether it already exists
    expanded_config["platform"] = llm_ref.get("platform", "openai")
    expanded_config["model"] = llm_ref.get("model", "gpt-5")
    expanded_config["max_input_token_count"] = llm_ref.get(
        "max_input_token_count", 200000
    )
    # Merge llm_config
    if "llm_config" in llm_ref:
        expanded_config["llm_config"] = llm_ref["llm_config"].copy()
    # Remove the reference key
    expanded_config.pop("normal_llm", None)

    # Handle the cheap_llm reference
    if "cheap_llm" in expanded_config:
        # Skip empty values (empty string or None)
        if not expanded_config.get("cheap_llm"):
            expanded_config.pop("cheap_llm", None)
        else:
            llm_ref = _resolve_llm_reference(expanded_config["cheap_llm"])
            if not llm_ref:
                raise ValueError(
                    f"❌ Error: the '{expanded_config['cheap_llm']}' referenced by cheap_llm does not exist in llms."
                )
            # Directly use the referenced value
            expanded_config["cheap_platform"] = llm_ref.get("platform", "openai")
            expanded_config["cheap_model"] = llm_ref.get("model", "gpt-5")
            expanded_config["cheap_max_input_token_count"] = llm_ref.get(
                "max_input_token_count", 200000
            )
            # Merge llm_config
            if "llm_config" in llm_ref:
                expanded_config["cheap_llm_config"] = llm_ref["llm_config"].copy()
            expanded_config.pop("cheap_llm", None)

    # Handle the smart_llm reference
    if "smart_llm" in expanded_config:
        # Skip empty values (empty string or None)
        if not expanded_config.get("smart_llm"):
            expanded_config.pop("smart_llm", None)
        else:
            llm_ref = _resolve_llm_reference(expanded_config["smart_llm"])
            if not llm_ref:
                raise ValueError(
                    f"❌ Error: the '{expanded_config['smart_llm']}' referenced by smart_llm does not exist in llms."
                )
            # Directly use the referenced value
            expanded_config["smart_platform"] = llm_ref.get("platform", "openai")
            expanded_config["smart_model"] = llm_ref.get("model", "gpt-5")
            expanded_config["smart_max_input_token_count"] = llm_ref.get(
                "max_input_token_count", 200000
            )
            # Merge llm_config
            if "llm_config" in llm_ref:
                expanded_config["smart_llm_config"] = llm_ref["llm_config"].copy()
            expanded_config.pop("smart_llm", None)

    # Handle the eval_llm reference (structured evaluation model, optional)
    # When not configured, no eval_* keys are expanded, and the caller determines "not configured" from this and falls back to the existing flow
    if "eval_llm" in expanded_config:
        # Skip empty values (empty string or None)
        if not expanded_config.get("eval_llm"):
            expanded_config.pop("eval_llm", None)
        else:
            llm_ref = _resolve_llm_reference(expanded_config["eval_llm"])
            if not llm_ref:
                raise ValueError(
                    f"❌ Error: the '{expanded_config['eval_llm']}' referenced by eval_llm does not exist in llms."
                )
            # Directly use the referenced value
            expanded_config["eval_platform"] = llm_ref.get("platform", "openai")
            expanded_config["eval_model"] = llm_ref.get("model", "gpt-5")
            expanded_config["eval_max_input_token_count"] = llm_ref.get(
                "max_input_token_count", 200000
            )
            # Merge llm_config
            if "llm_config" in llm_ref:
                expanded_config["eval_llm_config"] = llm_ref["llm_config"].copy()
            expanded_config.pop("eval_llm", None)

    return expanded_config


def _get_resolved_model_config() -> Dict[str, Any]:
    """
    Parse and merge the model configuration, handling model groups.

    Note:
    - The llm_groups format is an object: {'group_name': {...}, ...}, using the group name as the key
    - llm_groups no longer supports directly defining parameters such as platform and model; it can only reference the configuration defined in llms via normal_llm, cheap_llm, smart_llm

    Priority order:
    - When no group is explicitly specified (using the default group or unset):
        1. Top-level environment variables (platform, model, max_input_token_count)
        2. Configuration expanded via references in llm_group
        3. Default values in code

    Returns:
        Dict[str, Any]: Parsed model configuration dictionary

    Raises:
        If parameters such as platform, model are defined directly in llm_groups, or required references are missing, a ValueError is raised
    """

    group_config = {}
    model_group_name = get_llm_group()
    # The format is an object: {'group_name': {...}, ...}
    model_groups = GLOBAL_CONFIG_DATA.get("llm_groups", {})

    if model_group_name and isinstance(model_groups, dict):
        if model_group_name in model_groups:
            group_config = model_groups[model_group_name]

    # Expand llm references (normal_llm, cheap_llm, smart_llm)
    # Only expand references when group_config is not empty (indicating llm_groups is used)
    if group_config:
        group_config = _expand_llm_references(group_config)

    # Start with group config
    resolved_config = group_config.copy()

    # Override strategy:
    # - Keep top-level configuration keys (platform, model, max_input_token_count) for direct configuration
    # - Models must be configured through llms + llm_groups
    # - Keep fallback handling for llm_config related keys (for internal configuration after llm_groups expansion)
    override_keys = [
        "platform",
        "model",
        "max_input_token_count",
        "llm_config",
        "cheap_llm_config",
        "smart_llm_config",
        "eval_llm_config",
    ]
    for key in override_keys:
        if key in GLOBAL_CONFIG_DATA:
            # No group explicitly specified: top-level overrides group
            resolved_config[key] = GLOBAL_CONFIG_DATA[key]

    # Environment variable overrides (non-interactive quick configuration, convenient for CI):
    # Priority: environment variables > config.yaml > default values. When unset, existing behavior is unaffected.
    # HAIJUNBOT_PLATFORM / HAIJUNBOT_MODEL override platform and model; base_url uses standard environment variables
    # (OPENAI_API_BASE / JUGLOW_BASE_URL), read directly by the platform client.
    env_platform = os.environ.get("HAIJUNBOT_PLATFORM")
    if env_platform:
        resolved_config["platform"] = env_platform
    env_model = os.environ.get("HAIJUNBOT_MODEL")
    if env_model:
        resolved_config["model"] = env_model

    # Inside Vinbox there is exactly one model lane: Vinbox's own registry.
    # The model selected in Settings (data/models.json) always wins, so the
    # agent and the Haijun panel never diverge. Standalone behavior is untouched.
    try:
        from haijunbot.haijunbot_utils import vinbox_runtime

        if vinbox_runtime.is_vinbox():
            resolved_config["platform"] = "vinbox"
            model_id = vinbox_runtime.current_model_id()
            if model_id:
                resolved_config["model"] = model_id
            # Vinbox supplies credentials; HaijunBot's provider blocks do not
            # apply here and must not leak a second provider stack.
            resolved_config.pop("llm_config", None)
            resolved_config.pop("cheap_llm_config", None)
            resolved_config.pop("smart_llm_config", None)
            resolved_config.pop("eval_llm_config", None)
    except Exception:
        pass

    # llm_config is no longer applied to environment variables; all configuration is passed directly to platform via the llm_config parameter
    # _apply_llm_config_to_env(resolved_config)

    # Free tier: when an llm_config block names a provider (provider: groq), fill
    # its base URL and key from the free provider catalog. Missing keys stay
    # missing, so a paid subscription is never fabricated or required.
    try:
        from haijunbot.haijunbot_utils.free_providers import apply_to_resolved_config

        resolved_config = apply_to_resolved_config(resolved_config)
    except Exception:
        pass

    return resolved_config


def get_llm_config(platform_type: str = "normal") -> Dict[str, Any]:
    """
    Get the llm_config configuration for the specified platform type.

    Args:
        platform_type: Platform type, valid values are 'normal', 'cheap', or 'smart'

    Returns:
        Dict[str, Any]: llm_config configuration dictionary
    """
    # Do not apply configuration to environment variables, to avoid different llm type configurations overriding each other
    # Configuration is passed directly to platform via the llm_config parameter, without relying on environment variables
    config = _get_resolved_model_config()

    if platform_type == "cheap":
        llm_config = dict(config.get("cheap_llm_config", {}))
        # If cheap_llm_config is empty, fall back to normal_llm_config
        if not llm_config:
            llm_config = dict(config.get("llm_config", {}))
        return llm_config
    elif platform_type == "smart":
        llm_config = dict(config.get("smart_llm_config", {}))
        # If smart_llm_config is empty, fall back to normal_llm_config (consistent with the fallback logic of get_smart_platform_name)
        if not llm_config:
            llm_config = dict(config.get("llm_config", {}))
        return llm_config
    elif platform_type == "eval":
        llm_config = dict(config.get("eval_llm_config", {}))
        # If eval_llm_config is empty, fall back to normal_llm_config (consistent with the fallback logic of get_eval_platform_name)
        if not llm_config:
            llm_config = dict(config.get("llm_config", {}))
        return llm_config
    else:
        return dict(config.get("llm_config", {}))


def get_normal_platform_name() -> str:
    """
    Get the platform name for normal operations.

    Returns:
        str: Platform name, defaults to 'openai'
    """
    config = _get_resolved_model_config()
    return cast(str, config.get("platform", "openai"))


def get_normal_model_name() -> str:
    """
    Get the model name for normal operations.

    Returns:
        str: Model name, defaults to 'gpt-5'
    """
    config = _get_resolved_model_config()
    return cast(str, config.get("model", "gpt-5"))


def get_cheap_platform_name() -> str:
    """
    Get the platform name for cheap operations.

    Returns:
        str: Platform name, falls back to the normal operation platform if not configured
    """
    config = _get_resolved_model_config()
    cheap_platform = config.get("cheap_platform")
    if cheap_platform:
        return cast(str, cheap_platform)
    return get_normal_platform_name()


def get_cheap_model_name() -> str:
    """
    Get the model name for cheap operations.

    Returns:
        str: Model name, falls back to the normal operation model if not configured
    """
    config = _get_resolved_model_config()
    cheap_model = config.get("cheap_model")
    if cheap_model:
        return cast(str, cheap_model)
    return get_normal_model_name()


def get_smart_platform_name() -> str:
    """
    Get the platform name for smart operations.

    Returns:
        str: Platform name, falls back to the normal operation platform if not configured
    """
    config = _get_resolved_model_config()
    smart_platform = config.get("smart_platform")
    if smart_platform:
        return cast(str, smart_platform)
    return get_normal_platform_name()


def get_smart_model_name() -> str:
    """
    Get the model name for smart operations.

    Returns:
        str: Model name, falls back to the normal operation model if not configured
    """
    config = _get_resolved_model_config()
    smart_model = config.get("smart_model")
    if smart_model:
        return cast(str, smart_model)
    return get_normal_model_name()


def is_eval_model_configured() -> bool:
    """
    Determine whether a structured evaluation model (eval_llm) is configured.

    Returns True only when eval_llm is explicitly configured; when not configured, callers should fall back to the existing flow.

    Returns:
        bool: Whether a structured evaluation model is configured
    """
    config = _get_resolved_model_config()
    return bool(config.get("eval_platform") and config.get("eval_model"))


def get_eval_platform_name() -> str:
    """
    Get the platform name of the structured evaluation model.

    Returns:
        str: Platform name, falls back to the normal operation platform if not configured
    """
    config = _get_resolved_model_config()
    eval_platform = config.get("eval_platform")
    if eval_platform:
        return cast(str, eval_platform)
    return get_normal_platform_name()


def get_eval_model_name() -> str:
    """
    Get the model name of the structured evaluation model.

    Returns:
        str: Model name, falls back to the normal operation model if not configured
    """
    config = _get_resolved_model_config()
    eval_model = config.get("eval_model")
    if eval_model:
        return cast(str, eval_model)
    return get_normal_model_name()


def get_eval_max_input_token_count() -> int:
    """
    Get the maximum number of input tokens allowed by the structured evaluation model.

    Returns:
        int: Maximum number of input tokens the model can handle, falls back to the normal configuration if not configured
    """
    config = _get_resolved_model_config()
    eval_max_token = config.get("eval_max_input_token_count")
    if eval_max_token:
        return int(eval_max_token)
    return get_max_input_token_count()


def get_eval_llm_config() -> Dict[str, Any]:
    """
    Get the llm_config configuration of the structured evaluation model.

    Returns:
        Dict[str, Any]: llm_config configuration dictionary, falls back to the normal configuration if not configured
    """
    config = _get_resolved_model_config()
    llm_config = dict(config.get("eval_llm_config", {}))
    if not llm_config:
        llm_config = dict(config.get("llm_config", {}))
    return llm_config


def is_execute_tool_confirm() -> bool:
    """
    Check whether tool execution requires confirmation.

    Returns:
        bool: Returns True if confirmation is required, defaults to False
    """
    return cast(bool, GLOBAL_CONFIG_DATA.get("execute_tool_confirm", False))


def is_confirm_before_apply_patch() -> bool:
    """
    Check whether confirmation is required before applying a patch.

    Returns:
        bool: Returns True if confirmation is required, defaults to False
    """
    return False


def get_data_dir() -> str:
    """
    Get the HaijunBot data storage directory path.

    Returns:
        str: Data directory path, defaults to ~/.haijunbot, can be overridden via the HAIJUNBOT_DATA_DIR environment variable
    """
    # Prefer the environment variable
    env_data_dir = os.environ.get("HAIJUNBOT_DATA_DIR")
    if env_data_dir:
        return env_data_dir

    # Inside Vinbox, state belongs on the bind-mounted data volume so sessions
    # and memories survive a container rebuild. No Vinbox code is touched.
    try:
        from haijunbot.haijunbot_utils import vinbox_runtime

        if vinbox_runtime.is_vinbox():
            return str(vinbox_runtime.data_dir())
    except Exception:
        pass

    # Default to ~/.haijunbot
    return os.path.expanduser("~/.haijunbot")


def get_continuous_learning_dir() -> str:
    """
    Get the continuous learning data storage directory path.

    Returns:
        str: Continuous learning data directory path, which is ~/.haijunbot/continuous_learning
    """
    cl_dir = os.path.join(os.path.expanduser("~/.haijunbot"), "continuous_learning")
    # Ensure the directory exists
    os.makedirs(cl_dir, exist_ok=True)
    return cl_dir


def get_pretty_output() -> bool:
    """
    Get whether PrettyOutput is enabled.

    Returns:
        bool: Returns True if PrettyOutput is enabled, defaults to True
    """
    return True


def is_use_analysis() -> bool:
    """
    Get whether task analysis is enabled.

    Returns:
        bool: Returns True if task analysis is enabled, defaults to True
    """
    return True


def get_tool_load_dirs() -> List[str]:
    """
    Get the tool loading directories.

    Returns:
        List[str]: List of tool loading directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("tool_load_dirs", [])
        if p
    ]


def get_agent_definition_dirs() -> List[str]:
    """
    Get the loading directories for agent definitions.

    Returns:
        List[str]: List of agent definition loading directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("agent_definition_dirs", [])
        if p
    ]


def get_plugin_orchestrations() -> List[Dict[str, Any]]:
    """Get all orchestration pipeline templates declared by plugins.

    A plugin config.yaml declares available orchestration templates via the `orchestration` field:
        orchestration:
          - name: "demo-pipeline"
            description: "Demo plugin orchestration pipeline"
            file: "{{plugin_dir}}/orchestration/demo-plugin_pipeline.yaml"

    Returns:
        List[Dict]: Each item is {plugin, name, description, file},
                    file is an absolute path ({{plugin_dir}} already rendered),
                    plugin is the source plugin name (inferred from the file path).
    """
    result: List[Dict[str, Any]] = []
    for entry in GLOBAL_CONFIG_DATA.get("orchestration", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("id")
        file_path = entry.get("file") or entry.get("path")
        if not name or not file_path:
            continue
        abs_path = os.path.expanduser(os.path.expandvars(str(file_path)))
        # Infer the source plugin name from the path (path contains plugins/<name>/)
        plugin = ""
        try:
            normalized = abs_path.replace("\\", "/")
            marker = "/plugins/"
            if marker in normalized:
                plugin = normalized.split(marker, 1)[1].split("/", 1)[0]
        except Exception:
            plugin = ""
        result.append(
            {
                "plugin": plugin,
                "name": str(name),
                "description": str(entry.get("description", "") or ""),
                "file": abs_path,
            }
        )
    return result


def get_roles_dirs() -> List[str]:
    """
    Get the loading directories for roles.

    Returns:
        List[str]: List of roles loading directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("roles_dirs", [])
        if p
    ]


def get_after_tool_call_cb_dirs() -> List[str]:
    """
    Get the implementation directories for post-tool-call callback functions.

    Returns:
        List[str]: List of post-tool-call callback function implementation directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("after_tool_call_cb_dirs", [])
        if p
    ]


def get_builtin_input_handler_dirs() -> List[str]:
    """
    Get the built-in input processor extension script directories.

    Returns:
        List[str]: List of built-in input processor extension script directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("builtin_input_handler_dirs", [])
        if p
    ]


def get_before_tool_call_cb_dirs() -> List[str]:
    """
    Get the implementation directories for pre-tool-call callback functions.

    Returns:
        List[str]: List of pre-tool-call callback function implementation directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("before_tool_call_cb_dirs", [])
        if p
    ]


def get_before_model_call_cb_dirs() -> List[str]:
    """
    Get the implementation directories for pre-model-call callback functions.

    Returns:
        List[str]: List of pre-model-call callback function implementation directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("before_model_call_cb_dirs", [])
        if p
    ]


def get_summary_cb_dirs() -> List[str]:
    """
    Get the implementation directories for summarization callback functions.

    Returns:
        List[str]: List of summarization callback function implementation directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("summary_cb_dirs", [])
        if p
    ]


def get_central_tool_repo() -> str:
    """
    Get the central tools Git repository URL.

    Returns:
        str: Central tools Git repository URL, returns an empty string if not configured
    """
    return cast(str, GLOBAL_CONFIG_DATA.get("central_tool_repo", ""))


def get_rules_load_dirs() -> List[str]:
    """
    Get the rule loading directories.

    Returns:
        List[str]: List of rule loading directories
    """
    return [
        os.path.expanduser(os.path.expandvars(str(p)))
        for p in GLOBAL_CONFIG_DATA.get("rules_load_dirs", [])
        if p
    ]


def get_central_rules_repo() -> str:
    """
    Get the central rules Git repository URL.

    Returns:
        str: Central rules Git repository URL, returns an empty string if not configured
    """
    return cast(str, GLOBAL_CONFIG_DATA.get("central_rules_repo", ""))


def get_default_rule_names() -> List[str]:
    """
    Get the list of default rule names.

    Returns:
        List[str]: List of default rule names, returns an empty list if not configured
    """
    value = GLOBAL_CONFIG_DATA.get("default_rule_names", [])
    # If the configuration is a list, return it directly
    if isinstance(value, list):
        return cast(List[str], value)
    # If the configuration is a string (for backward compatibility), split by comma
    if isinstance(value, str) and value.strip():
        return [name.strip() for name in value.split(",") if name.strip()]
    return []


def set_default_rule_names(rule_names: Optional[List[str]]) -> None:
    """
    Set the list of default rule names.

    Args:
        rule_names: List of rule names; if None, the existing configuration is not modified
    """
    if rule_names is not None:
        GLOBAL_CONFIG_DATA["default_rule_names"] = rule_names


def is_print_prompt() -> bool:
    """
    Get whether to print prompts.

    Returns:
        bool: Returns True if prompts are printed, defaults to True
    """
    return cast(bool, GLOBAL_CONFIG_DATA.get("print_prompt", False))


def is_print_error_traceback() -> bool:
    """
    Get whether to print the traceback call chain on error output.

    Returns:
        bool: Returns True if traceback is printed, defaults to False (not printed)
    """
    return False


def is_force_save_memory() -> bool:
    """
    Get whether to force saving memory.

    Returns:
        bool: Returns True if memory saving is forced, defaults to False
    """
    return False


def is_enable_static_analysis() -> bool:
    """
    Get whether static code analysis is enabled.

    Returns:
        bool: Returns True if static code analysis is enabled, defaults to True
    """
    return True


def is_enable_build_validation() -> bool:
    """
    Get whether build verification is enabled.

    Returns:
        bool: Returns True if build verification is enabled, defaults to True
    """
    return True


def is_enable_impact_analysis() -> bool:
    """
    Get whether edit impact scope analysis is enabled.

    Returns:
        bool: Returns True if impact scope analysis is enabled, defaults to True
    """
    return True


def is_enable_request_classification() -> bool:
    """
    Get whether the requirement classification feature is enabled.

    When enabled, CodeAgent classifies user requirements on its first run and loads the corresponding system prompt based on the classification result.
    Enabled by default; can be disabled by setting enable_request_classification: false in the configuration file.

    Returns:
        bool: Returns True if requirement classification is enabled, defaults to True
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_request_classification", True))


def is_enable_quick_mode() -> bool:
    """
    Get whether quick mode is enabled.

    When enabled, CodeAgent skips steps such as task classification, automatic rule loading, context recommendation, and methodology loading, and directly handles user requests.
    Disabled by default; can be enabled by setting enable_quick_mode: true in the configuration file.
    The command-line argument -q/--quick also enables this mode.

    Returns:
        bool: Returns True if quick mode is enabled, defaults to False
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_quick_mode", False))


def is_enable_native_tool_calls() -> bool:
    """
    Get whether native function calling is enabled (sending structured tool definitions to models that support tools).

    Enabled by default; for endpoints that do not support tools, the platform automatically degrades to a plain-text protocol without affecting usage.
    Can be disabled by setting enable_native_tool_calls: false in the configuration file.

    Returns:
        bool: Returns True if native tool calls are enabled, defaults to True
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_native_tool_calls", True))


def is_enable_audit() -> bool:
    """
    Get whether the audit system is enabled.

    When enabled, key behavioral events of the Agent (user input, tool calls, task completion, etc.) are recorded to
    JSONL audit logs under the ~/.haijunbot/audit/ directory for security review and behavior tracking.
    Disabled by default; can be enabled by setting enable_audit: true in the configuration file.

    Returns:
        bool: Returns True if the audit system is enabled, defaults to False
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_audit", False))


def _get_native_support_file() -> str:
    """Path to the native tool call support record file."""
    return os.path.join(get_data_dir(), "native_tool_support.json")


def is_model_native_supported(model_name: str) -> bool:
    """
    Query whether a model has ever been confirmed to support native function calling.

    Once a model successfully completes a native tool call, it is persistently recorded as supported;
    afterward, even if a temporary error occurs, it no longer degrades to the plain-text protocol.

    Returns:
        bool: Whether this model has been recorded as supporting native tool calling
    """
    if not model_name:
        return False
    try:
        with open(_get_native_support_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(isinstance(data, dict) and data.get(model_name))
    except Exception:
        return False


def mark_model_native_supported(model_name: str) -> None:
    """
    Persistently record that a model supports native function calling.

    Called after the model successfully returns a native response (content or tool_calls).
    A write failure does not affect the main flow.
    """
    if not model_name:
        return
    try:
        path = _get_native_support_file()
        data: dict = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        if data.get(model_name):
            return
        data[model_name] = True
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_request_timeout() -> Optional[float]:
    """
    Get the SDK request timeout (seconds).

    Returns the default value 300 (5 minutes) when request_timeout config is missing or 0/empty,
    to avoid requests being permanently blocked due to server reasons; if the user explicitly configures a valid value, the configured value is used preferentially.

    Returns:
        Optional[float]: request timeout in seconds; returns the default 300 seconds when not configured
    """
    DEFAULT_REQUEST_TIMEOUT = 300.0
    value = GLOBAL_CONFIG_DATA.get("request_timeout")
    if value is None or value == "":
        return DEFAULT_REQUEST_TIMEOUT
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return DEFAULT_REQUEST_TIMEOUT
    return timeout if timeout > 0 else DEFAULT_REQUEST_TIMEOUT


def get_build_validation_timeout() -> int:
    """
    Get the timeout for build validation (seconds).

    Returns:
        int: timeout, defaults to 30 seconds
    """
    return int(GLOBAL_CONFIG_DATA.get("build_validation_timeout", 30))


def get_build_validation_config() -> Dict[str, Any]:
    """
    Get the static user configuration for build validation.

    Static config (disable_build_validation / disable_reason / custom_build_command)
    merged into the build_validation config item of config.yaml, read through GLOBAL_CONFIG_DATA
    (global + project-level automatically merged, project-level overrides global).

    Returns:
        Dict[str, Any]: build validation static config dictionary, returns an empty dictionary when not configured
    """
    config = GLOBAL_CONFIG_DATA.get("build_validation", {})
    if not isinstance(config, dict):
        return {}
    return config


def update_build_validation_config(project_root: str, updates: Dict[str, Any]) -> bool:
    """Write the build validation static config back to the project-level config.yaml and sync to GLOBAL_CONFIG_DATA.

    Static config write operations (disable_build_validation / enable_build_validation /
    set_custom_build_command) need to be persisted to the project-level config.yaml. When writing, preserve
    the schema comment header (# yaml-language-server: ...), with a .yaml.bak backup.

    Args:
        project_root: project root directory
        updates: build_validation config items to update (key-value pairs)

    Returns:
        bool: whether the write succeeded
    """
    import shutil
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    from haijunbot.haijunbot_utils.output import PrettyOutput

    config_dir = os.path.join(project_root, ".haijunbot")
    config_path = os.path.join(config_dir, "config.yaml")

    try:
        os.makedirs(config_dir, exist_ok=True)

        # Read the existing config.yaml, preserve the leading comment lines (including the schema comment header)
        header_comments = ""
        existing: Dict[str, Any] = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                raw = f.read()
            lines = raw.split("\n")
            comment_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#") or stripped == "":
                    comment_lines.append(line)
                else:
                    break
            if comment_lines:
                header_comments = "\n".join(comment_lines) + "\n"
            try:
                parsed = yaml.safe_load(raw)
                if isinstance(parsed, dict):
                    existing = parsed
            except Exception:
                existing = {}

        # Merge build_validation config
        build_validation = existing.get("build_validation")
        if not isinstance(build_validation, dict):
            build_validation = {}
        build_validation.update(updates)
        existing["build_validation"] = build_validation

        # Backup
        if os.path.exists(config_path):
            backup_path = Path(config_path).with_suffix(".yaml.bak")
            shutil.copy(config_path, str(backup_path))

        # Write back (preserve the leading comment lines)
        content = ""
        if header_comments:
            content += header_comments
        content += yaml.safe_dump(
            existing, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Sync to GLOBAL_CONFIG_DATA so subsequent reads take effect immediately
        set_config("build_validation", build_validation)
        return True
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to save build validation config to config.yaml: {e}")
        return False


def get_mcp_config() -> List[Dict[str, Any]]:
    """
    Get the MCP config list.

    Returns:
        List[Dict[str, Any]]: MCP config item list, returns an empty list if not configured
    """
    return cast(List[Dict[str, Any]], GLOBAL_CONFIG_DATA.get("mcp", []))


def get_gateway_auth_config() -> Dict[str, Any]:
    """
    Get the Gateway auth config.

    Returns:
        Dict[str, Any]: Gateway auth config dictionary
    """
    config = GLOBAL_CONFIG_DATA.get("gateway_auth", {})
    if not isinstance(config, dict):
        config = {}

    return dict(config)


# ==============================================================================
# Web Search Configuration
# ==============================================================================


def get_web_search_platform_name() -> Optional[str]:
    """
    Get the platform name used for Web search.

    Uses the platform config of normal_llm.

    Returns:
        Optional[str]: platform name, returns None if not configured
    """
    return get_normal_platform_name()


def get_web_search_model_name() -> Optional[str]:
    """
    Get the model name used for Web search.

    Uses the model config of normal_llm.

    Returns:
        Optional[str]: model name, returns None if not configured
    """
    return get_normal_model_name()


# ==============================================================================
# Tool Configuration
# ==============================================================================


def _get_resolved_tool_config(
    tool_group_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse and merge tool config, handle tool groups.

    Priority order:
    1. Group config defined in tool_group
    2. Default config (all tools enabled)

    Returns:
        Dict[str, Any]: parsed tool config dictionary, containing 'use' and 'dont_use' lists
    """
    group_config = {}
    tool_group_name = tool_group_override or GLOBAL_CONFIG_DATA.get("tool_group")
    tool_groups = GLOBAL_CONFIG_DATA.get("tool_groups", [])

    if tool_group_name and isinstance(tool_groups, list):
        for group_item in tool_groups:
            if isinstance(group_item, dict) and tool_group_name in group_item:
                group_config = group_item[tool_group_name]
                break

    # If no config group is found, return the default config (empty list means use all tools)
    return group_config.copy() if group_config else {"use": [], "dont_use": []}


def get_tool_use_list() -> List[str]:
    """
    Get the list of tools to use.

    Returns:
        List[str]: list of tool names to use, an empty list means use all tools
    """
    config = _get_resolved_tool_config()
    return cast(List[str], config.get("use", []))


def get_tool_dont_use_list() -> List[str]:
    """
    Get the list of tools not to use.

    Returns:
        List[str]: list of tool names not to use
    """
    config = _get_resolved_tool_config()
    return cast(List[str], config.get("dont_use", []))


def get_tool_filter_threshold() -> int:
    """
    Get the threshold for AI tool filtering.

    Returns:
        int: when the number of tools exceeds this threshold, AI filtering is triggered. Defaults to 30
    """
    return 30


def get_script_execution_timeout() -> int:
    """
    Get the timeout for script execution (seconds).

    Returns:
        int: timeout (180 seconds / 3 minutes)
    """
    return 180


def is_save_session_history() -> bool:
    """
    Whether to save session records.

    Returns:
        bool: returns True if session records are to be saved, defaults to False
    """
    return GLOBAL_CONFIG_DATA.get("save_session_history", False) is True


def is_auto_resume_session() -> bool:
    """
    Whether to enable CodeAgent automatic session recovery.

    Returns:
        bool: returns True if automatic session recovery is enabled, defaults to False
    """
    return GLOBAL_CONFIG_DATA.get("auto_resume_session", False) is True


def is_immediate_abort() -> bool:
    """
    Whether to enable immediate interruption: when a user interrupt signal is detected during a conversation, stop output and return immediately.
    Disabled by default
    """
    return True


def is_non_interactive() -> bool:
    """
    Get whether non-interactive mode is enabled.

    Returns:
        bool: returns True if non-interactive mode is enabled, defaults to False
    """
    try:
        # Prioritize judgment based on the currently active Agent state, to avoid cross-Agent contamination
        from haijunbot.haijunbot_utils import globals as _g

        current_agent_name = _g.get_current_agent_name()
        if current_agent_name:
            agent = _g.get_agent(current_agent_name)
            if agent is not None and hasattr(agent, "non_interactive"):
                try:
                    return bool(getattr(agent, "non_interactive"))
                except Exception:
                    return False
    except Exception:
        # Defensive fallback, keep returning False without affecting the main flow
        return False
    # Default to returning False when there is no current Agent, to avoid depending on global config or environment variables
    return False


def is_quiet() -> bool:
    """
    Get whether quiet mode is enabled.

    When enabled, suppresses hca's rich-text console output (gateway/event output is still retained),
    used for scenarios such as evaluation that need to reduce log noise. Disabled by default.

    Returns:
        bool: returns True if quiet mode is enabled, defaults to False
    """
    return GLOBAL_CONFIG_DATA.get("quiet", False) is True


def is_skip_predefined_tasks() -> bool:
    """
    Whether to skip predefined task loading.

    Returns:
        bool: returns True if predefined task loading is skipped, defaults to False
    """
    return GLOBAL_CONFIG_DATA.get("skip_predefined_tasks", False) is True


def get_addon_prompt_threshold() -> int:
    """
    Get the trigger threshold (number of characters) for the additional prompt.

    When the message length exceeds this threshold, the default additional prompt is added automatically.

    Returns:
        int: trigger threshold, defaults to 4096
    """
    return 4096


def is_enable_intent_recognition() -> bool:
    """
    Get whether the intent recognition feature is enabled.

    Returns:
        bool: whether intent recognition is enabled, defaults to True (configurable via GLOBAL_CONFIG_DATA['enable_intent_recognition'])
    """
    return True


def is_enable_memory_organizer() -> bool:
    """
    Get whether the automatic memory organization feature is enabled.

    Returns:
        bool: whether automatic memory organization is enabled, defaults to False (configurable via GLOBAL_CONFIG_DATA['enable_memory_organizer'])
    """
    return False


def is_enable_memory_value_filter() -> bool:
    """
    Get whether write-time memory value filtering is enabled.

    When enabled, at save time a heuristic value judgment is made on memories not explicitly marked with importance:
    pure pleasantries / too short / no-information content will be discarded, to avoid polluting the memory store.
    Enabled by default, can be disabled via GLOBAL_CONFIG_DATA['enable_memory_value_filter'].

    Returns:
        bool: whether write-time memory value filtering is enabled, defaults to True
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_memory_value_filter", True))


def is_enable_memory_compress() -> bool:
    """
    Get whether pre-storage compression is enabled.

    When enabled, when saving an overly long memory (exceeding the threshold), the content is rule-based summarized and compressed before storage,
    the original complete content is kept in the original_content field, controlling memory store size and retrieval token cost.
    Enabled by default, can be disabled via GLOBAL_CONFIG_DATA['enable_memory_compress'].

    Returns:
        bool: whether pre-storage compression is enabled, defaults to True
    """
    return bool(GLOBAL_CONFIG_DATA.get("enable_memory_compress", True))


def get_memory_compress_threshold() -> int:
    """
    Get the token threshold for pre-storage compression.

    Compression is triggered when the memory content token count exceeds this threshold. Default 2000.
    Configurable via GLOBAL_CONFIG_DATA['memory_compress_threshold'].

    Returns:
        int: compression token threshold
    """
    return int(GLOBAL_CONFIG_DATA.get("memory_compress_threshold", 2000))


def get_context_budget_usage_ratio() -> float:
    """
    Get the context total budget usage ratio.

    Context total budget = model max_input_tokens × usage ratio (leave margin, avoid filling the window completely).
    Default 0.9, configurable via GLOBAL_CONFIG_DATA['context_budget_usage_ratio'].

    Returns:
        float: context total budget usage ratio
    """
    return float(GLOBAL_CONFIG_DATA.get("context_budget_usage_ratio", 0.9))


def get_context_layer_ratios() -> Dict[str, float]:
    """
    Get the budget proportions for layered context injection.

    The proportion of each layer in the "context total budget", used to allocate the limited context window by priority to
    components such as system prompt, memory retrieval, tool descriptions, rules, conversation history, current task, etc.
    Default values reference the design document, can be overridden via GLOBAL_CONFIG_DATA['context_layer_ratios'].

    Returns:
        Dict[str, float]: proportion of each layer (key is layer name, value is a ratio from 0 to 1)
    """
    defaults = {
        "system_prompt": 0.20,  # system prompt (fixed)
        "memory_retrieval": 0.20,  # memory retrieval (dynamic, truncated by relevance)
        "tool_description": 0.15,  # tool descriptions (varies with enabled tools)
        "rules": 0.10,  # rules/specifications
        "conversation_history": 0.25,  # conversation history (compressible)
        "current_task": 0.10,  # current task/user input (fixed reserved)
    }
    configured = GLOBAL_CONFIG_DATA.get("context_layer_ratios")
    if isinstance(configured, dict):
        merged = dict(defaults)
        for key, value in configured.items():
            try:
                merged[key] = float(value)
            except (TypeError, ValueError):
                pass
        return merged
    return defaults


def get_context_memory_retrieval_budget() -> int:
    """
    Get the token cap for a single memory retrieval injection.

    After retrieval results are sorted by relevance, they are truncated once the accumulated tokens exceed this cap.
    Default 3000, configurable via GLOBAL_CONFIG_DATA['context_memory_retrieval_budget'].

    Returns:
        int: token cap for a single memory retrieval injection
    """
    return int(GLOBAL_CONFIG_DATA.get("context_memory_retrieval_budget", 3000))


def calculate_layer_token_budget(total_tokens: int) -> Dict[str, int]:
    """
    Calculate the token budget of each context component according to the layer proportions.

    Based on the proportions from get_context_layer_ratios(), allocate total_tokens to
    layers such as system prompt, memory retrieval, tool descriptions, rules, conversation history, current task, etc.
    Proportions are ratios (0 to 1), each layer's budget = total_tokens × proportion (rounded down).

    Args:
        total_tokens: context total budget (number of tokens)

    Returns:
        Dict[str, int]: token budget of each layer (key is layer name)
    """
    ratios = get_context_layer_ratios()
    budgets: Dict[str, int] = {}
    for layer, ratio in ratios.items():
        budgets[layer] = int(total_tokens * float(ratio))
    return budgets


def is_pipeline_cleanup_on_failure() -> bool:
    """
    Get whether to automatically clean up created resident Agents when the pipeline fails/aborts.

    Enabled by default: when the pipeline ends due to failure or abort, automatically delete the resident Agents created for each stage,
    to avoid leftover processes occupying resources. Can be configured via GLOBAL_CONFIG_DATA['pipeline_cleanup_on_failure']
    to disable (e.g. when debugging requires preserving the Agent scene).

    Returns:
        bool: whether to clean up created Agents on failure/abort
    """
    return bool(GLOBAL_CONFIG_DATA.get("pipeline_cleanup_on_failure", True))


def is_enable_autonomous() -> bool:
    """
    Get whether the intelligent enhancement features (emotion recognition, ambiguity detection, dialogue management, proactive interaction) are enabled.

    Returns:
        bool: whether intelligent enhancement features are enabled, defaults to False
    """
    return GLOBAL_CONFIG_DATA.get("enable_autonomous", False) is True


def get_conversation_turn_threshold() -> int:
    """
    Get the conversation turn threshold used to trigger summarization.

    Returns:
        int: conversation turn threshold (200 turns)
    """
    return 200


def get_sliding_window_size() -> int:
    """
    Get the sliding window size, used for the sliding window compression strategy.

    Returns:
        int: sliding window size (keep the most recent 4 user/tool messages and 5 assistant messages, 9 in total, an odd number to avoid consecutive messages of the same role)
    """
    return 5


def get_importance_score_threshold() -> float:
    """
    Get the importance score threshold, used for the importance score compression strategy.

    Returns:
        float: importance score threshold (messages below this threshold will be compressed, defaults to 3.0)
    """
    return 3.0


def get_incremental_summary_chunk_size() -> int:
    """
    Get the chunk size of incremental summarization, used for the incremental summarization compression strategy.

    Returns:
        int: chunk size (number of conversation turns contained in each chunk, defaults to 20 turns)
    """
    return 20


def get_diff_visualization_mode() -> str:
    """
    Get the diff visualization mode

    Returns:
        str: diff visualization mode, options: "unified", "syntax", "compact", "side_by_side", "default"
        Defaults to "unified"
    """
    return "side_by_side"


def get_diff_show_line_numbers() -> bool:
    """
    Get whether to show line numbers in the diff

    Returns:
        bool: whether to show line numbers, defaults to True
    """
    return True


def get_diff_large_file_threshold() -> int:
    """
    Get the large file threshold (only show statistics if this number of lines is exceeded)

    Returns:
        int: large file threshold, defaults to 300
    """
    return 300


def get_submit_keys() -> List[str]:
    """
    Get the submit shortcut key list for multi-line input.

    Returns:
        List[str]: submit shortcut key list, defaults to ["c-j", "c-]", "c-d"] (Ctrl+J, Ctrl+] and Ctrl+D)
    """
    value = GLOBAL_CONFIG_DATA.get("submit_keys")
    # If the config is a list, return directly
    if isinstance(value, list):
        return [str(k) for k in value if k]
    # If the config is a string (comma-separated supported), split by comma
    if isinstance(value, str) and value.strip():
        return [key.strip() for key in value.split(",") if key.strip()]
    # Default value
    return ["c-j", "c-]", "c-d"]
