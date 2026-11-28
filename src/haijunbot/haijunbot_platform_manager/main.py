"""HaijunBot platform manager main module.

This module provides the main entry point for the HaijunBot platform manager.
"""

import os
import sys
from pathlib import Path
import yaml  # type: ignore[import-untyped]

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import typer

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_platform_manager.service import start_service
from haijunbot.haijunbot_utils.config import (
    set_llm_group,
    save_exception,
)
from haijunbot.haijunbot_utils.config import get_normal_model_name
from haijunbot.haijunbot_utils.config import get_normal_platform_name
from haijunbot.haijunbot_utils.fzf import fzf_select
from haijunbot.haijunbot_utils.input import get_multiline_input
from haijunbot.haijunbot_utils.input import get_single_line_input
from haijunbot.haijunbot_utils.utils import init_env

app = typer.Typer(help="HaijunBot AI platform")
manage_app = typer.Typer(help="Manage LLM configurations and model groups")
llm_app = typer.Typer(help="LLM configuration management")
group_app = typer.Typer(help="Model group management")
app.add_typer(manage_app, name="manage")
manage_app.add_typer(llm_app, name="llm")
manage_app.add_typer(group_app, name="group")


# ============================================================================
# Config file operation helper functions
# ============================================================================


def _get_config_file_path() -> Path:
    """Get the config file path

    Returns:
        Path: Config file path (~/.haijunbot/config.yaml)
    """
    return Path.home() / ".haijunbot" / "config.yaml"


def _load_config() -> Dict[str, Any]:
    """Load the config file

    Returns:
        Dict[str, Any]: Config dict; empty dict if file is missing or read fails
    """
    config_file = _get_config_file_path()
    if not config_file.exists():
        return {}

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        PrettyOutput.auto_print(f"❌ Failed to read config file: {exc}")
        return {}


def _save_config(config: Dict[str, Any]) -> bool:
    """Save config to file

    Args:
        config: Config dict

    Returns:
        bool: True on success, otherwise False
    """
    config_file = _get_config_file_path()

    # Ensure the directory exists
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Back up the original config file
    backup_file = config_file.with_suffix(".yaml.bak")
    if config_file.exists():
        try:
            import shutil

            shutil.copy2(config_file, backup_file)
        except Exception:
            pass  # Backup failure does not affect the main flow

    try:
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as exc:
        PrettyOutput.auto_print(f"❌ Failed to save config file: {exc}")
        # Try to restore the backup
        if backup_file.exists():
            try:
                import shutil

                shutil.copy2(backup_file, config_file)
                PrettyOutput.auto_print("ℹ️ Restored the original config file")
            except Exception as e:
                save_exception(
                    e, module="haijunbot_platform_manager.main", function="_save_config"
                )
                pass
        return False


# ============================================================================
# LLM management subcommands
# ============================================================================


# ============================================================================
# LLM management subcommands
# ============================================================================


@llm_app.command("list")
def llm_list() -> None:
    """List all LLM configurations"""
    config = _load_config()
    llms = config.get("llms", {})

    if not llms:
        PrettyOutput.auto_print("ℹ️ No LLM configuration found")
        return

    # Build markdown table
    md_lines = ["## ✅ LLM configuration list", ""]
    md_lines.append("| Name | Platform | Model | Multimodal | Context length |")
    md_lines.append("|------|------|------|--------|--------------|")

    # Add data rows
    for name in sorted(llms.keys()):
        llm_config = llms[name]
        platform = llm_config.get("platform", "unknown")
        model = llm_config.get("model", "unknown")
        max_tokens = llm_config.get("max_input_token_count", "N/A")
        supports_multimodal = llm_config.get("llm_config", {}).get(
            "supports_multimodal", False
        )
        multimodal_str = "✅" if supports_multimodal else "❌"
        md_lines.append(
            f"| {name} | {platform} | {model} | {multimodal_str} | {max_tokens} |"
        )

    # Print the table
    md_table = "\n".join(md_lines)
    PrettyOutput.print_markdown(md_table)


@llm_app.command("show")
def llm_show(
    name: Optional[str] = typer.Argument(None, help="LLM config name; select interactively if omitted"),
) -> None:
    """Show details of the specified LLM configuration"""
    config = _load_config()
    llms = config.get("llms", {})

    if not llms:
        PrettyOutput.auto_print("ℹ️ No LLM configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{llm_name} ({llm_config.get('platform', 'unknown')}/{llm_config.get('model', 'unknown')})"
            for llm_name, llm_config in sorted(llms.items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select LLM config > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Config |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: name (platform/model))
        name = selected_str.split(" (")[0].strip()

    if name not in llms:
        PrettyOutput.auto_print(f"❌ LLM configuration not found: {name}")
        raise typer.Exit(code=1)

    llm_config = llms[name]
    PrettyOutput.auto_print(f"✅ LLM configuration: {name}")
    PrettyOutput.auto_print(f"  Platform: {llm_config.get('platform', 'N/A')}")
    PrettyOutput.auto_print(f"  Model: {llm_config.get('model', 'N/A')}")
    PrettyOutput.auto_print(
        f"  Max token count: {llm_config.get('max_input_token_count', 'N/A')}"
    )

    # Show multimodal support status
    supports_multimodal = llm_config.get("llm_config", {}).get(
        "supports_multimodal", False
    )
    PrettyOutput.auto_print(
        f"  Multimodal support: {'✅ Yes' if supports_multimodal else '❌ No'}"
    )

    llm_config_dict = llm_config.get("llm_config", {})
    if llm_config_dict:
        PrettyOutput.auto_print("  Other configuration:")
        for key, value in llm_config_dict.items():
            # Skip fields already shown above
            if key == "supports_multimodal":
                continue
            PrettyOutput.auto_print(f"    {key}: {value}")


@llm_app.command("delete")
def llm_delete(
    name: Optional[str] = typer.Argument(None, help="LLM config name; select interactively if omitted"),
) -> None:
    """Delete the specified LLM configuration"""
    config = _load_config()
    llms = config.get("llms", {})

    if not llms:
        PrettyOutput.auto_print("ℹ️ No LLM configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{llm_name} ({llm_config.get('platform', 'unknown')}/{llm_config.get('model', 'unknown')})"
            for llm_name, llm_config in sorted(llms.items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select LLM config to delete > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Config |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: name (platform/model))
        name = selected_str.split(" (")[0].strip()

    if name not in llms:
        PrettyOutput.auto_print(f"❌ LLM configuration not found: {name}")
        raise typer.Exit(code=1)

    # Check whether it is referenced by any model group
    llm_groups = config.get("llm_groups", {})
    for group_name, group_config in llm_groups.items():
        for key in ["normal_llm", "cheap_llm", "smart_llm", "eval_llm"]:
            if group_config.get(key) == name:
                PrettyOutput.auto_print(f"⚠️ This config is referenced by model group '{group_name}'")

    # Confirm deletion
    from haijunbot.haijunbot_utils.input import user_confirm

    if not user_confirm(f"Delete LLM config '{name}'?", default=False):
        PrettyOutput.auto_print("ℹ️ Deletion cancelled")
        return

    # Delete the config
    if "llms" not in config:
        config["llms"] = {}
    config["llms"].pop(name, None)

    # Save config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Deleted LLM configuration: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


def _llm_add_batch(config: Dict[str, Any], base_config_name: str) -> None:
    """Batch-add LLM models based on an existing config

    Args:
        config: Config dict
        base_config_name: Base config name
    """
    from haijunbot.haijunbot_utils.input import get_single_line_input, user_confirm

    # 1. Verify the base config exists
    if base_config_name not in config.get("llms", {}):
        PrettyOutput.auto_print(f"❌ Base config '{base_config_name}' does not exist")
        available_llms = sorted(config.get("llms", {}).keys())
        if available_llms:
            md_lines = ["## Available configurations", ""]
            for llm_name in available_llms:
                md_lines.append(f"- {llm_name}")
            PrettyOutput.print_markdown("\n".join(md_lines))
        raise typer.Exit(code=1)

    base_llm_config = config["llms"][base_config_name]
    if not isinstance(base_llm_config, dict):
        PrettyOutput.auto_print(f"❌ Base config '{base_config_name}' has an invalid format")
        raise typer.Exit(code=1)

    # 2. Extract base config information
    platform = base_llm_config.get("platform", "").strip().lower()
    if not platform:
        PrettyOutput.auto_print(f"❌ Base config '{base_config_name}' is missing platform info")
        raise typer.Exit(code=1)

    llm_config_dict = base_llm_config.get("llm_config", {})
    if not llm_config_dict:
        PrettyOutput.auto_print(f"❌ Base config '{base_config_name}' is missing llm_config info")
        raise typer.Exit(code=1)

    # Extract base_url and api_key
    base_url = None
    api_key = None
    if platform == "openai":
        base_url = llm_config_dict.get("openai_api_base")
        api_key = llm_config_dict.get("openai_api_key")
    elif platform == "haijun":
        base_url = llm_config_dict.get("juglow_base_url")
        api_key = llm_config_dict.get("juglow_api_key")
    else:
        base_url = llm_config_dict.get(f"{platform}_base_url")
        api_key = llm_config_dict.get(f"{platform}_api_key")

    if not base_url or not api_key:
        PrettyOutput.auto_print(f"❌ Base config '{base_config_name}' is missing URL or API Key")
        raise typer.Exit(code=1)

    PrettyOutput.auto_print(f"📋 Base config: platform={platform}, URL={base_url}")

    # 3. Get the list of available models
    from haijunbot.haijunbot_utils.quick_config import get_models

    models = get_models(platform, base_url, api_key)
    if not models:
        PrettyOutput.auto_print("⚠️ Failed to fetch model list from API")
        use_manual_input = user_confirm("Enter model names manually?", default=True)
        if use_manual_input:
            model_input = get_single_line_input(
                "Enter model names (separate multiple models with commas, e.g. gpt-4o,gpt-3.5-turbo):"
            )
            models = [m.strip() for m in model_input.split(",") if m.strip()]
            if not models:
                PrettyOutput.auto_print("❌ No valid model names entered")
                raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print("❌ No model names provided")
            raise typer.Exit(code=0)

    PrettyOutput.auto_print(f"📋 Number of available models: {len(models)}")

    # 4. Select the models to add
    if len(models) > 1:
        md_lines = ["## Available model list", "", "| No. | Model name |", "|------|----------|"]
        for i, model in enumerate(models, 1):
            md_lines.append(f"| {i} | {model} |")
        manual_input_option = len(models) + 1
        md_lines.append(f"| {manual_input_option} | Enter model name manually |")
        PrettyOutput.print_markdown("\n".join(md_lines))

        configure_all = user_confirm("Configure all models?", default=False)

        if configure_all:
            selected_models = models
        else:
            model_choices = get_single_line_input(
                f"Enter the model numbers to configure (separate with commas; enter {manual_input_option} to input names manually):"
            )
            try:
                indices = [int(x.strip()) - 1 for x in model_choices.split(",")]
                selected_models = []
                use_manual_input = False
                for idx in indices:
                    if 0 <= idx < len(models):
                        selected_models.append(models[idx])
                    elif idx == len(models):
                        use_manual_input = True
                    else:
                        PrettyOutput.auto_print(f"❌ Invalid model number: {idx + 1}")
                        raise typer.Exit(code=1)

                if use_manual_input:
                    model_input = get_single_line_input(
                        "Enter model names (separate multiple models with commas, e.g. gpt-4o,gpt-3.5-turbo):"
                    )
                    manual_models = [
                        m.strip() for m in model_input.split(",") if m.strip()
                    ]
                    if not manual_models:
                        PrettyOutput.auto_print("❌ No valid model names entered")
                        raise typer.Exit(code=1)
                    selected_models.extend(manual_models)

                selected_models = list(dict.fromkeys(selected_models))
                if not selected_models:
                    PrettyOutput.auto_print("❌ No valid model selected")
                    raise typer.Exit(code=1)
            except ValueError:
                PrettyOutput.auto_print("❌ Please enter valid numeric indices separated by commas")
                raise typer.Exit(code=1)
    else:
        selected_models = [models[0]]

    PrettyOutput.auto_print(f"✅ Selected {len(selected_models)} models")
    md_lines = ["## Selected models", ""]
    for model in selected_models:
        md_lines.append(f"- {model}")
    PrettyOutput.print_markdown("\n".join(md_lines))

    # 5. Test API connectivity of the normal model
    from haijunbot.haijunbot_utils.quick_config import test_model_connection

    test_model = selected_models[0]
    PrettyOutput.auto_print(f"🔍 Testing API connectivity for model {test_model}...")
    success, error_msg = test_model_connection(platform, base_url, api_key, test_model)

    if success:
        PrettyOutput.auto_print("✅ API connectivity test passed")
    else:
        PrettyOutput.auto_print(f"❌ API connectivity test failed: {error_msg}")
        force_save = user_confirm("Test failed; save the config to file anyway?", default=False)
        if not force_save:
            PrettyOutput.auto_print("👋 Config save cancelled")
            raise typer.Exit(code=0)
        else:
            PrettyOutput.auto_print("⚠️ Will continue saving the config, but the API may not work properly")

    # 6. Set the max token count for each model
    default_max_tokens = base_llm_config.get("max_input_token_count", 200000)
    model_max_tokens = {}

    for model in selected_models:
        while True:
            max_tokens_input = get_single_line_input(
                f"Enter max token count for model {model} (default: {default_max_tokens}):"
            )
            if not max_tokens_input.strip():
                model_max_tokens[model] = default_max_tokens
                PrettyOutput.auto_print(
                    f"✅ Model {model} uses default max token count: {default_max_tokens}"
                )
                break
            try:
                max_tokens = int(max_tokens_input.strip())
                if max_tokens <= 0:
                    PrettyOutput.auto_print("❌ Max token count must be a positive integer")
                    continue
                model_max_tokens[model] = max_tokens
                PrettyOutput.auto_print(
                    f"✅ Model {model} max token count set to: {max_tokens}"
                )
                break
            except ValueError:
                PrettyOutput.auto_print("❌ Please enter a valid positive integer")

    # 6.5. Ask the user whether to enable multimodal support (batch mode asks only once)
    supports_multimodal = user_confirm(
        "Enable multimodal support (image input)?",
        default=False,
    )

    # 7. Create a config for each selected model
    # Extract hostname to generate a unique config name
    from haijunbot.haijunbot_utils.quick_config import _extract_hostname

    hostname_part = _extract_hostname(base_url)
    added_count = 0
    for model in selected_models:
        # Generate config name: {platform}_{hostname}_{model_normalized}
        model_config_name = (
            f"{platform}_{hostname_part}_{model.replace('.', '_').replace('-', '_')}"
        )

        # Check whether it already exists
        if model_config_name in config["llms"]:
            if not user_confirm(
                f"Config '{model_config_name}' already exists; overwrite?", default=True
            ):
                PrettyOutput.auto_print(f"⏭  Skipping config: {model_config_name}")
                continue

        # Generate the config dict based on the platform type
        if platform == "openai":
            llm_config_dict_new = {
                "openai_api_key": api_key,
                "openai_api_base": base_url,
                "supports_multimodal": supports_multimodal,
            }
        elif platform == "haijun":
            llm_config_dict_new = {
                "juglow_api_key": api_key,
                "juglow_base_url": base_url,
                "supports_multimodal": supports_multimodal,
            }
        else:
            llm_config_dict_new = {
                f"{platform}_api_key": api_key,
                f"{platform}_base_url": base_url,
                "supports_multimodal": supports_multimodal,
            }

        # Create the LLM config
        llm_config_new: Dict[str, Any] = {
            "platform": platform,
            "model": model,
            "max_input_token_count": model_max_tokens.get(model, default_max_tokens),
            "llm_config": llm_config_dict_new,
        }

        config["llms"][model_config_name] = llm_config_new
        added_count += 1
        PrettyOutput.auto_print(f"✅ Added config: {model_config_name} -> {model}")

    # 7. Save config
    if added_count > 0:
        if _save_config(config):
            PrettyOutput.auto_print(f"✅ Successfully added {added_count} model configs")
        else:
            PrettyOutput.auto_print("❌ Failed to save config")
            raise typer.Exit(code=1)
    else:
        PrettyOutput.auto_print("ℹ ️  No config was added")


@llm_app.command("add")
def llm_add() -> None:
    """Add a new LLM configuration (interactive)"""
    from haijunbot.haijunbot_utils.input import get_single_line_input, user_confirm

    config = _load_config()
    if "llms" not in config:
        config["llms"] = {}

    # Ask for the add mode
    existing_llms = list(config.get("llms", {}).keys())
    use_batch_mode = False
    base_config_name = None

    if existing_llms:
        use_batch_mode = user_confirm(
            "Batch-add models based on an existing config? (reuse platform, URL, Key info)",
            default=False,
        )

    if use_batch_mode:
        # Let the user choose a base config
        md_lines = [
            "## Available LLM configurations",
            "",
            "| No. | Config name | Platform | Model |",
            "|------|----------|------|------|",
        ]
        for i, llm_name in enumerate(existing_llms, 1):
            llm_info = config["llms"].get(llm_name, {})
            platform = llm_info.get("platform", "unknown")
            model = llm_info.get("model", "unknown")
            md_lines.append(f"| {i} | {llm_name} | {platform} | {model} |")
        PrettyOutput.print_markdown("\n".join(md_lines))

        choice = get_single_line_input("Enter the base config number: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(existing_llms):
                base_config_name = existing_llms[idx]
            else:
                PrettyOutput.auto_print(f"❌ Invalid number: {choice}")
                raise typer.Exit(code=1)
        except ValueError:
            PrettyOutput.auto_print("❌ Please enter a valid numeric index")
            raise typer.Exit(code=1)

        _llm_add_batch(config, base_config_name)
        return

    # Interactively add a single model
    name = get_single_line_input("Enter LLM config name: ").strip()
    if not name:
        PrettyOutput.auto_print("❌ Please provide an LLM config name")
        raise typer.Exit(code=1)

    if name in config["llms"]:
        from haijunbot.haijunbot_utils.input import user_confirm

        if not user_confirm(f"LLM config '{name}' already exists; overwrite?", default=True):
            PrettyOutput.auto_print("ℹ️ Operation cancelled")
            raise typer.Exit(code=0)
        PrettyOutput.auto_print(f"📝 Overwriting LLM config: {name}")
    else:
        PrettyOutput.auto_print(f"📝 Adding LLM config: {name}")

    platform = get_single_line_input("Platform name (openai/haijun/other): ").strip().lower()
    if not platform:
        PrettyOutput.auto_print("❌ Platform name cannot be empty")
        raise typer.Exit(code=1)

    model = get_single_line_input("Model name (e.g. gpt-4o): ").strip()
    if not model:
        PrettyOutput.auto_print("❌ Model name cannot be empty")
        raise typer.Exit(code=1)

    max_tokens_input = get_single_line_input("Max token count (default: 200000): ").strip()
    try:
        max_tokens = int(max_tokens_input) if max_tokens_input else 200000
    except ValueError:
        PrettyOutput.auto_print("❌ Invalid token count; using default 200000")
        max_tokens = 200000

    base_url = get_single_line_input("API base URL: ").strip()
    if not base_url:
        PrettyOutput.auto_print("❌ API base URL cannot be empty")
        raise typer.Exit(code=1)

    api_key = get_single_line_input("API key: ", is_password=True).strip()
    if not api_key:
        PrettyOutput.auto_print("❌ API key cannot be empty")
        raise typer.Exit(code=1)

    # Ask the user whether to enable multimodal support
    supports_multimodal = user_confirm(
        "Enable multimodal support (image input)?",
        default=False,
    )

    if platform == "openai":
        llm_config_dict = {
            "openai_api_key": api_key,
            "openai_api_base": base_url,
            "supports_multimodal": supports_multimodal,
        }
    elif platform == "haijun":
        llm_config_dict = {
            "juglow_api_key": api_key,
            "juglow_base_url": base_url,
            "supports_multimodal": supports_multimodal,
        }
    else:
        llm_config_dict = {
            f"{platform}_api_key": api_key,
            f"{platform}_base_url": base_url,
            "supports_multimodal": supports_multimodal,
        }

    llm_config: Dict[str, Any] = {
        "platform": platform,
        "model": model,
        "max_input_token_count": max_tokens,
        "llm_config": llm_config_dict,
    }

    config["llms"][name] = llm_config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Added LLM config: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


@llm_app.command("update")
def llm_update(
    name: Optional[str] = typer.Argument(None, help="LLM config name; select interactively if omitted"),
) -> None:
    """Update the specified LLM configuration (interactive)"""
    from haijunbot.haijunbot_utils.input import get_single_line_input

    config = _load_config()
    if "llms" not in config:
        config["llms"] = {}

    if not config["llms"]:
        PrettyOutput.auto_print("ℹ️ No LLM configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{llm_name} ({llm_config.get('platform', 'unknown')}/{llm_config.get('model', 'unknown')})"
            for llm_name, llm_config in sorted(config["llms"].items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select LLM config to update > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Config |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: name (platform/model))
        name = selected_str.split(" (")[0].strip()

    if name not in config["llms"]:
        PrettyOutput.auto_print(f"❌ LLM configuration not found: {name}")
        raise typer.Exit(code=1)

    llm_config = config["llms"][name]
    PrettyOutput.auto_print(f"📝 Updating LLM config: {name}")
    PrettyOutput.auto_print(
        f"  Current values - Platform: {llm_config.get('platform', 'N/A')}, Model: {llm_config.get('model', 'N/A')}"
    )

    # Update each field
    platform = get_single_line_input(
        f"Platform name (current: {llm_config.get('platform', '')}, leave blank to keep): "
    ).strip()
    if platform:
        llm_config["platform"] = platform

    model = get_single_line_input(
        f"Model name (current: {llm_config.get('model', '')}, leave blank to keep): "
    ).strip()
    if model:
        llm_config["model"] = model

    max_tokens_input = get_single_line_input(
        f"Max token count (current: {llm_config.get('max_input_token_count', 200000)}, leave blank to keep): "
    ).strip()
    if max_tokens_input:
        try:
            max_tokens = int(max_tokens_input)
            llm_config["max_input_token_count"] = max_tokens
        except ValueError:
            PrettyOutput.auto_print("❌ Invalid token count; keeping the original value")

    # Update API Base URL and API Key
    current_platform = llm_config.get("platform", "").strip().lower()
    llm_config_dict = llm_config.get("llm_config", {})

    # Get the current URL and Key
    current_base_url = None
    current_api_key = None
    if current_platform == "openai":
        current_base_url = llm_config_dict.get("openai_api_base", "")
        current_api_key = llm_config_dict.get("openai_api_key", "")
    elif current_platform == "haijun":
        current_base_url = llm_config_dict.get("juglow_base_url", "")
        current_api_key = llm_config_dict.get("juglow_api_key", "")
    else:
        current_base_url = llm_config_dict.get(f"{current_platform}_base_url", "")
        current_api_key = llm_config_dict.get(f"{current_platform}_api_key", "")

    base_url = get_single_line_input(
        f"API base URL (current: {current_base_url or 'not set'}, leave blank to keep): "
    ).strip()

    api_key = get_single_line_input(
        f"API key (current: {'set' if current_api_key else 'not set'}, leave blank to keep): ",
        is_password=True,
    ).strip()

    # Apply updates to the config if any
    if base_url or api_key:
        if "llm_config" not in llm_config:
            llm_config["llm_config"] = {}

        # Use the updated platform (if the user changed it)
        updated_platform = llm_config.get("platform", "").strip().lower()

        if updated_platform == "openai":
            if base_url:
                llm_config["llm_config"]["openai_api_base"] = base_url
            if api_key:
                llm_config["llm_config"]["openai_api_key"] = api_key
        elif updated_platform == "haijun":
            if base_url:
                llm_config["llm_config"]["juglow_base_url"] = base_url
            if api_key:
                llm_config["llm_config"]["juglow_api_key"] = api_key
        else:
            if base_url:
                llm_config["llm_config"][f"{updated_platform}_base_url"] = base_url
            if api_key:
                llm_config["llm_config"][f"{updated_platform}_api_key"] = api_key

    # Update the multimodal support setting
    current_multimodal = llm_config.get("llm_config", {}).get(
        "supports_multimodal", False
    )
    multimodal_input = (
        get_single_line_input(
            f"Enable multimodal support (current: {'yes' if current_multimodal else 'no'}, enter y/n to change, leave blank to keep): "
        )
        .strip()
        .lower()
    )
    if multimodal_input in ("y", "yes"):
        llm_config.setdefault("llm_config", {})["supports_multimodal"] = True
    elif multimodal_input in ("n", "no"):
        llm_config.setdefault("llm_config", {})["supports_multimodal"] = False

    # Save config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Updated LLM config: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


# ============================================================================
# Model group management subcommands
# ============================================================================


@group_app.command("list")
def group_list() -> None:
    """List all model groups"""
    config = _load_config()
    llm_groups = config.get("llm_groups", {})

    if not llm_groups:
        PrettyOutput.auto_print("ℹ️ No model group found")
        return

    # Build markdown table
    md_lines = ["## ✅ Model group list", ""]
    md_lines.append("| Group name | normal | smart | cheap | eval |")
    md_lines.append("|------|--------|-------|-------|------|")

    # Add data rows
    for name in sorted(llm_groups.keys()):
        group_config = llm_groups[name]
        normal_llm = group_config.get("normal_llm", "N/A")
        smart_llm = group_config.get("smart_llm", "N/A")
        cheap_llm = group_config.get("cheap_llm", "N/A")
        eval_llm = group_config.get("eval_llm", "N/A")
        md_lines.append(
            f"| {name} | {normal_llm} | {smart_llm} | {cheap_llm} | {eval_llm} |"
        )

    # Print the table
    md_table = "\n".join(md_lines)
    PrettyOutput.print_markdown(md_table)


@group_app.command("show")
def group_show(
    name: Optional[str] = typer.Argument(None, help="Model group name; select interactively if omitted"),
) -> None:
    """Show details of the specified model group"""
    config = _load_config()
    llm_groups = config.get("llm_groups", {})

    if not llm_groups:
        PrettyOutput.auto_print("ℹ No model group configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{group_name} (normal: {group_config.get('normal_llm', 'N/A')})"
            for group_name, group_config in sorted(llm_groups.items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select model group > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Model group |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: group_name (normal: xxx))
        name = selected_str.split(" (")[0].strip()

    if name not in llm_groups:
        PrettyOutput.auto_print(f"❌ Model group not found: {name}")
        raise typer.Exit(code=1)

    group_config = llm_groups[name]
    PrettyOutput.auto_print(f"✅ Model group: {name}")
    PrettyOutput.auto_print(f"  normal_llm: {group_config.get('normal_llm', 'N/A')}")
    PrettyOutput.auto_print(f"  cheap_llm: {group_config.get('cheap_llm', 'N/A')}")
    PrettyOutput.auto_print(f"  smart_llm: {group_config.get('smart_llm', 'N/A')}")
    PrettyOutput.auto_print(f"  eval_llm: {group_config.get('eval_llm', 'N/A')}")


@group_app.command("delete")
def group_delete(
    name: Optional[str] = typer.Argument(None, help="Model group name; select interactively if omitted"),
) -> None:
    """Delete the specified model group"""
    config = _load_config()
    llm_groups = config.get("llm_groups", {})

    if not llm_groups:
        PrettyOutput.auto_print("ℹ️ No model group configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{group_name} (normal: {group_config.get('normal_llm', 'N/A')})"
            for group_name, group_config in sorted(llm_groups.items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select model group to delete > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Model group |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: group_name (normal: xxx))
        name = selected_str.split(" (")[0].strip()

    if name not in llm_groups:
        PrettyOutput.auto_print(f"❌ Model group not found: {name}")
        raise typer.Exit(code=1)

    # Confirm deletion
    from haijunbot.haijunbot_utils.input import user_confirm

    if not user_confirm(f"Delete model group '{name}'?", default=False):
        PrettyOutput.auto_print("ℹ️ Deletion cancelled")
        return

    # Delete the config
    if "llm_groups" not in config:
        config["llm_groups"] = {}
    config["llm_groups"].pop(name, None)

    # Save config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Deleted model group: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


@group_app.command("add")
def group_add(name: Optional[str] = typer.Argument(None, help="Model group name")) -> None:
    """Add a new model group (interactive)"""
    from haijunbot.haijunbot_utils.input import get_single_line_input

    config = _load_config()
    if "llm_groups" not in config:
        config["llm_groups"] = {}

    # Get the list of available LLM configurations
    llms = config.get("llms", {})
    if not llms:
        PrettyOutput.auto_print("❌ No available LLM configuration; add an LLM config first")
        raise typer.Exit(code=1)

    llm_list: List[str] = sorted(llms.keys())
    md_lines = ["## Available LLM configurations", "", "| No. | Config name |", "|------|----------|"]
    for i, llm_name in enumerate(llm_list, 1):
        md_lines.append(f"| {i} | {llm_name} |")
    PrettyOutput.print_markdown("\n".join(md_lines))

    def resolve_llm_choice(prompt: str, allow_empty: bool = False) -> str:
        """Resolve the user's choice; supports number or name"""
        choice = get_single_line_input(prompt).strip()
        if not choice:
            return ""
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(llm_list):
                return llm_list[idx]
            else:
                PrettyOutput.auto_print(f"❌ Invalid number: {choice}")
                raise typer.Exit(code=1)
        except ValueError:
            # The user entered a name
            if choice in llms:
                return choice
            else:
                PrettyOutput.auto_print(f"❌ LLM configuration not found: {choice}")
                raise typer.Exit(code=1)

    # Interactive input
    normal_llm = resolve_llm_choice("Normal LLM config (number or name, required): ")
    if not normal_llm:
        PrettyOutput.auto_print("❌ Normal LLM config cannot be empty")
        raise typer.Exit(code=1)

    # Optional cheap and smart
    cheap_llm = resolve_llm_choice(
        "Cheap LLM config (number or name, blank means same as normal): ", allow_empty=True
    )

    smart_llm = resolve_llm_choice(
        "Smart LLM config (number or name, blank means same as normal): ", allow_empty=True
    )

    # Optional structured evaluation model
    eval_llm = resolve_llm_choice(
        "Structured evaluation model LLM config (number or name, blank means disabled): ", allow_empty=True
    )

    # If no model group name was provided, prompt the user for input
    if name is None:
        # Suggest a default name based on the selected configs
        if cheap_llm and smart_llm:
            if cheap_llm == smart_llm == normal_llm:
                default_name = normal_llm
            else:
                default_name = f"{normal_llm}+{cheap_llm}+{smart_llm}"
        elif cheap_llm and cheap_llm != normal_llm:
            default_name = f"{normal_llm}+{cheap_llm}"
        elif smart_llm and smart_llm != normal_llm:
            default_name = f"{normal_llm}+{smart_llm}"
        else:
            default_name = normal_llm

        # Prompt the user for a model group name, with a default value
        name_input = get_single_line_input(
            f"Enter model group name (default: {default_name}): "
        ).strip()
        name = name_input if name_input else default_name

    if name in config["llm_groups"]:
        from haijunbot.haijunbot_utils.input import user_confirm

        if not user_confirm(f"Model group '{name}' already exists; overwrite?", default=True):
            PrettyOutput.auto_print("ℹ️ Operation cancelled")
            raise typer.Exit(code=0)

    PrettyOutput.auto_print(f"📝 Adding model group: {name}")

    # Create the config
    group_config = {
        "normal_llm": normal_llm,
    }
    if cheap_llm:
        group_config["cheap_llm"] = cheap_llm
    if smart_llm:
        group_config["smart_llm"] = smart_llm
    if eval_llm:
        group_config["eval_llm"] = eval_llm

    # Save config
    config["llm_groups"][name] = group_config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Added model group: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


@group_app.command("update")
def group_update(
    name: Optional[str] = typer.Argument(None, help="Model group name; select interactively if omitted"),
) -> None:
    """Update the specified model group (interactive)"""
    from haijunbot.haijunbot_utils.input import get_single_line_input

    config = _load_config()
    if "llm_groups" not in config:
        config["llm_groups"] = {}

    if not config["llm_groups"]:
        PrettyOutput.auto_print("ℹ️ No model group configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{group_name} (normal: {group_config.get('normal_llm', 'N/A')})"
            for group_name, group_config in sorted(config["llm_groups"].items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select model group to update > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Model group |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: group_name (normal: xxx))
        name = selected_str.split(" (")[0].strip()

    if name not in config["llm_groups"]:
        PrettyOutput.auto_print(f"❌ Model group not found: {name}")
        raise typer.Exit(code=1)

    # Get the list of available LLM configurations
    llms = config.get("llms", {})
    if not llms:
        PrettyOutput.auto_print("❌ No available LLM configuration; add an LLM config first")
        raise typer.Exit(code=1)

    llm_list: List[str] = sorted(llms.keys())

    group_config = config["llm_groups"][name]
    PrettyOutput.auto_print(f"📝 Updating model group: {name}")
    PrettyOutput.auto_print(
        f"  Current values - normal: {group_config.get('normal_llm', 'N/A')}, cheap: {group_config.get('cheap_llm', 'N/A')}, smart: {group_config.get('smart_llm', 'N/A')}, eval: {group_config.get('eval_llm', 'N/A')}"
    )
    md_lines = ["## Available LLM configurations", "", "| No. | Config name |", "|------|----------|"]
    for i, llm_name in enumerate(llm_list, 1):
        md_lines.append(f"| {i} | {llm_name} |")
    PrettyOutput.print_markdown("\n".join(md_lines))

    def resolve_llm_choice(prompt: str) -> str:
        """Resolve the user's choice; supports number or name"""
        choice = get_single_line_input(prompt).strip()
        if not choice:
            return ""
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(llm_list):
                return llm_list[idx]
            else:
                PrettyOutput.auto_print(f"❌ Invalid number: {choice}")
                raise typer.Exit(code=1)
        except ValueError:
            # The user entered a name
            if choice in llms:
                return choice
            else:
                PrettyOutput.auto_print(f"❌ LLM configuration not found: {choice}")
                raise typer.Exit(code=1)

    # Update each field
    normal_llm = resolve_llm_choice(
        f"Normal LLM (current: {group_config.get('normal_llm', '')}, number or name, leave blank to keep): "
    )
    if normal_llm:
        group_config["normal_llm"] = normal_llm

    cheap_llm = resolve_llm_choice(
        f"Cheap LLM (current: {group_config.get('cheap_llm', '')}, number or name, leave blank to keep): "
    )
    if cheap_llm:
        group_config["cheap_llm"] = cheap_llm

    smart_llm = resolve_llm_choice(
        f"Smart LLM (current: {group_config.get('smart_llm', '')}, number or name, leave blank to keep): "
    )
    if smart_llm:
        group_config["smart_llm"] = smart_llm

    eval_llm = resolve_llm_choice(
        f"Structured evaluation model LLM (current: {group_config.get('eval_llm', '')}, number or name, leave blank to keep): "
    )
    if eval_llm:
        group_config["eval_llm"] = eval_llm

    # Save config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Updated model group: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


@group_app.command("set")
def group_set(
    name: Optional[str] = typer.Argument(None, help="Model group name; select interactively if omitted"),
) -> None:
    """Set the currently active model group"""
    config = _load_config()
    llm_groups = config.get("llm_groups", {})

    if not llm_groups:
        PrettyOutput.auto_print("ℹ️ No model group configured")
        raise typer.Exit(code=1)

    # If no name is given, use interactive selection
    # If no name is given, use interactive selection
    if name is None:
        fzf_options = [
            f"{group_name} (smart: {group_config.get('smart_llm', 'N/A')}, normal: {group_config.get('normal_llm', 'N/A')}, cheap: {group_config.get('cheap_llm', 'N/A')}, eval: {group_config.get('eval_llm', 'N/A')})"
            for group_name, group_config in sorted(llm_groups.items())
        ]
        selected_str = fzf_select(fzf_options, prompt="Select model group to set > ")
        if not selected_str:
            # fzf unavailable (e.g. gateway mode), fall back to numeric input
            md_lines = ["| No. | Model group |", "|------|------|"]
            for i, opt in enumerate(fzf_options, 1):
                md_lines.append(f"| {i} | {opt} |")
            PrettyOutput.print_markdown("\n".join(md_lines))
            choice = get_single_line_input("Enter number (0 to cancel): ").strip()
            if choice == "0" or not choice:
                PrettyOutput.auto_print("ℹ Cancelled")
                raise typer.Exit(code=0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(fzf_options):
                    selected_str = fzf_options[idx]
                else:
                    PrettyOutput.auto_print("❌ Invalid number")
                    raise typer.Exit(code=0)
            except ValueError:
                PrettyOutput.auto_print("❌ Invalid input")
                raise typer.Exit(code=0)
        # Extract the name from the selected string (format: group_name (normal: xxx))
        name = selected_str.split(" (")[0].strip()

    if name not in llm_groups:
        PrettyOutput.auto_print(f"❌ Model group not found: {name}")
        raise typer.Exit(code=1)

    # Set the current model group
    if "llm_group" not in config:
        config["llm_group"] = ""
    config["llm_group"] = name

    # Save config
    if _save_config(config):
        PrettyOutput.auto_print(f"✅ Current model group set to: {name}")
    else:
        PrettyOutput.auto_print("❌ Failed to save config")
        raise typer.Exit(code=1)


@app.command("info")
def list_platforms(
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="Model group to use, overrides the setting in the config file"
    ),
) -> None:
    """List all supported platforms and models, with interactive selection to view platform details."""
    registry = PlatformRegistry.get_global_platform_registry()
    platform_names = registry.get_available_platforms()

    if not platform_names:
        PrettyOutput.auto_print("⚠️ No platform available")
        return

    # Get the default model group config, or use the specified model group
    set_llm_group(llm_group)
    if llm_group:
        platform_name = get_normal_platform_name()
        model_name = get_normal_model_name()
        PrettyOutput.auto_print(f"✅ Configuration obtained from model group '{llm_group}':")
        PrettyOutput.auto_print(f"  Platform: {platform_name}")
        PrettyOutput.auto_print(f"  Model: {model_name}")

        # Only show the platform info specified in the config
        platform_names = [platform_name]

        # Create a platform instance from the config and show detailed info
        try:
            platform_instance = registry.create_platform("normal")
            if platform_instance:
                models = platform_instance.get_model_list()
                PrettyOutput.auto_print(f"✅ {platform_name}")
                if models:
                    md_lines = [
                        f"## {platform_name} platform model list",
                        "",
                        "| Model name | Description |",
                        "|----------|------|",
                    ]
                    for model_name, description in models:
                        desc = description if description else "-"
                        md_lines.append(f"| {model_name} | {desc} |")
                    PrettyOutput.print_markdown("\n".join(md_lines))
                else:
                    PrettyOutput.auto_print("⚠️   • No model information available")
            else:
                PrettyOutput.auto_print(f"⚠️ Failed to create {platform_name} platform")
        except Exception:
            PrettyOutput.auto_print(f"⚠️ Failed to create {platform_name} platform")
        return
    else:
        # Get the default model group config
        platform_name = get_normal_platform_name()
        default_model = get_normal_model_name()

        # Show default config info
        PrettyOutput.auto_print("✅ Default configuration info:")
        PrettyOutput.auto_print(f"  Platform: {platform_name}")
        PrettyOutput.auto_print(f"  Model: {default_model}")

        # Show details of the default platform
        try:
            platform_instance = registry.create_platform("normal")
            if platform_instance:
                models = platform_instance.get_model_list()
                PrettyOutput.auto_print(f"✅ {platform_name} platform details")
                if models:
                    md_lines = [
                        f"## {platform_name} platform model list",
                        "",
                        "| Model name | Description |",
                        "|----------|------|",
                    ]
                    for model_name, description in models:
                        desc = description if description else "-"
                        md_lines.append(f"| {model_name} | {desc} |")
                    PrettyOutput.print_markdown("\n".join(md_lines))
                else:
                    PrettyOutput.auto_print("⚠️   • No model information available")
            else:
                PrettyOutput.auto_print(f"⚠️ Failed to create {platform_name} platform")
        except Exception:
            PrettyOutput.auto_print(f"⚠️ Failed to create {platform_name} platform")
        return


def chat_with_model(
    system_prompt: str,
) -> None:
    """Chat with the specified platform and model.

    Args:
        platform_name: Platform name
        model_name: Model name
        system_prompt: System prompt
        llm_group: Model group to use, overrides the setting in the config file

    """
    registry = PlatformRegistry.get_global_platform_registry()
    conversation_history: List[Dict[str, str]] = []  # Stores the conversation history

    platform_name = get_normal_platform_name()
    model_name = get_normal_model_name()

    # Create platform instance
    platform = registry.create_platform("normal")
    if platform:
        platform.set_model_name(model_name)

    if not platform:
        PrettyOutput.auto_print(f"⚠️ Failed to create platform {platform_name}")
        return

    try:
        # Set model
        platform.set_model_name(model_name)
        if system_prompt:
            platform.set_system_prompt(system_prompt)
        platform.set_suppress_output(False)
        PrettyOutput.auto_print(f"✅ Connected to {platform_name} platform, {model_name} model")
        PrettyOutput.auto_print("ℹ️ Type /bye to exit the chat")

        # Start conversation loop
        while True:
            # Get user input
            user_input = get_multiline_input("")

            # Check if input is cancelled
            if user_input.strip() == "/bye":
                PrettyOutput.auto_print("✅ Goodbye!")
                break

            # Check if input is empty
            if not user_input.strip():
                PrettyOutput.auto_print("ℹ️ Empty input detected, exiting the chat")
                break

            try:
                conversation_history.append(
                    {"role": "user", "content": user_input}
                )  # Record the user input
                # Send to model and get reply
                response = platform.chat_until_success(user_input)
                if not response:
                    PrettyOutput.auto_print("⚠️ No valid reply")
                else:
                    # Use PrettyOutput.print_markdown to print the LLM response (with markdown highlighting)
                    title = f"[bold cyan]{platform_name} · {model_name}[/bold cyan]"
                    PrettyOutput.print_markdown(
                        response, title=title, border_style="cyan"
                    )
                    conversation_history.append(
                        {"role": "assistant", "content": response}
                    )  # Record the model reply

            except Exception as exc:
                PrettyOutput.auto_print(f"❌ Chat failed: {str(exc)}")

    except typer.Exit:
        raise
    except Exception as exc:
        PrettyOutput.auto_print(f"❌ Failed to initialize session: {str(exc)}")
        sys.exit(1)
    finally:
        # Clean up resources
        try:
            platform.reset()
        except Exception as e:
            save_exception(
                e, module="haijunbot_platform_manager.main", function="chat_with_model"
            )
            pass


def validate_platform_model(platform: Optional[str], model: Optional[str]) -> bool:
    """Validate the platform and model parameters.

    Args:
        platform: Platform name.
        model: Model name.

    Returns:
        bool: True if platform and model are valid, otherwise False.
    """
    if not platform or not model:
        PrettyOutput.auto_print(
            "⚠️ Please specify the platform and model. Use 'haijunbot info' to view available platforms and models."
        )
        return False
    return True


@app.command("chat")
def chat_command(
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="Model group to use, overrides the setting in the config file"
    ),
) -> None:
    """Chat with the specified platform and model."""
    # Get default values from config
    set_llm_group(llm_group)
    platform = get_normal_platform_name()
    model = get_normal_model_name()

    if not validate_platform_model(platform, model):
        return
    chat_with_model("")


@app.command("service")
def service_command(
    host: str = typer.Option("127.0.0.1", help="Service host address (default: 127.0.0.1)"),
    port: int = typer.Option(8000, help="Service port (default: 8000)"),
) -> None:
    """Start an OpenAI-compatible API service."""
    # Get default values from config
    platform = get_normal_platform_name()
    model = get_normal_model_name()
    start_service(host=host, port=port, default_platform=platform, default_model=model)


def load_role_config(config_path: str) -> Dict[str, Any]:
    """Load role config from a YAML file

    Args:
        config_path: Path to the YAML config file

    Returns:
        dict: Role config dict
    """
    import yaml

    if not os.path.exists(config_path):
        PrettyOutput.auto_print(f"❌ Role config file {config_path} does not exist")
        return {}

    with open(config_path, "r", encoding="utf-8", errors="ignore") as file_obj:
        try:
            config = yaml.safe_load(file_obj)
            return config if config else {}
        except yaml.YAMLError as exc:
            PrettyOutput.auto_print(f"❌ Failed to parse role config file: {str(exc)}")
            return {}


@app.command("role")
def role_command(
    config_file: str = typer.Option(
        "~/.haijunbot/roles.yaml",
        "--config",
        "-c",
        help="Path to the role config file (YAML format, default: ~/.haijunbot/roles.yaml)",
    ),
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="Model group to use, overrides the setting in the config file"
    ),
) -> None:
    """Load the role config file and start a conversation."""
    set_llm_group(llm_group)

    config_path = os.path.expanduser(config_file)
    config = load_role_config(config_path)
    if not config or "roles" not in config:
        PrettyOutput.auto_print("❌ Invalid role config file")
        return

    # Show the list of available roles
    PrettyOutput.auto_print("✅ Available roles")
    md_lines = [
        "## Available roles",
        "",
        "| No. | Role name | Description |",
        "|------|----------|------|",
    ]
    for i, role in enumerate(config["roles"], 1):
        desc = role.get("description", "-")
        md_lines.append(f"| {i} | {role['name']} | {desc} |")
    PrettyOutput.print_markdown("\n".join(md_lines))

    # Let the user choose a role (prefer fzf, fall back to numeric input)
    selected_role = None
    fzf_options = [
        f"{i:>3} | {role['name']} - {role.get('description', '')}"
        for i, role in enumerate(config["roles"], 1)
    ]
    selected_str = fzf_select(fzf_options, prompt="Select role number (Enter to exit) > ")
    if selected_str:
        try:
            num_part = selected_str.split("|", 1)[0].strip()
            idx = int(num_part)
            if 1 <= idx <= len(config["roles"]):
                selected_role = config["roles"][idx - 1]
        except Exception:
            selected_role = None

    if selected_role is None:
        raw_choice = get_single_line_input("Select a role (enter number, press Enter to exit): ")
        if not raw_choice.strip():
            PrettyOutput.auto_print("ℹ️ Cancelled, exiting the program")
            raise typer.Exit(code=0)
        try:
            choice = int(raw_choice)
            selected_role = config["roles"][choice - 1]
        except (ValueError, IndexError):
            PrettyOutput.auto_print("❌ Invalid choice")
            return

    system_prompt = selected_role.get("system_prompt", "")

    # Start the conversation
    PrettyOutput.auto_print(f"✅ Selected role: {selected_role['name']}")
    chat_with_model(system_prompt)


def main() -> None:
    """Main entry point of the HaijunBot platform manager."""
    init_env()
    app()


if __name__ == "__main__":
    main()
