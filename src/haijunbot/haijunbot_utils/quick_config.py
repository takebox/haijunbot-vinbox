# -*- coding: utf-8 -*-
"""
Quick Config CLI tool
Used to quickly configure LLM platform information (Haijun/OpenAI) into the llms section of the HaijunBot configuration file
"""

import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Any
from typing import Dict
import typer
from rich.console import Console
import requests

from .output import PrettyOutput
from .input import get_single_line_input, user_confirm
from .utils import init_env
from .free_providers import PROVIDERS as FREE_PROVIDERS
from .free_providers import free_provider_ids
from .free_providers import provider_base_url
from .free_providers import providers_table as _provider_rows

app = typer.Typer(help="Quickly configure LLM platform information into the HaijunBot configuration file")
console = Console()


@app.command()
def quick_config(
    platform: str = typer.Option(None, help="Platform type (openai/haijun/vinbox), required in non-interactive mode"),
    base_url: str = typer.Option(None, help="API base URL, required in non-interactive mode"),
    api_key: str = typer.Option(
        None, help="API key (omit for keyless providers such as opencode)"
    ),
    model: str = typer.Option(
        None, help="Model name, required in non-interactive mode (shared by normal/smart/cheap)"
    ),
    group: str = typer.Option(None, help="Model group name, optional in non-interactive mode, defaults to the model name"),
    max_tokens: int = typer.Option(200000, help="Maximum input token count, optional in non-interactive mode"),
    skip_test: bool = typer.Option(
        False, "--skip-test", help="Skip the API connectivity test (recommended for CI scenarios)"
    ),
):
    """Quickly configure LLM platform information into the llms section of the HaijunBot configuration file

    Interactive mode: run hqc directly without arguments and enter as prompted.
    Non-interactive mode (for CI): provide --platform/--base-url/--api-key/--model and the configuration is written automatically.
    """
    try:
        candidate = (platform or "").strip().lower()
        keyless = candidate in free_provider_ids() and not _provider_needs_key(candidate)
        if platform and model and (api_key or keyless):
            run_quick_config_noninteractive(
                platform=platform,
                base_url=base_url,
                api_key=api_key or "",
                model=model,
                group=group,
                max_tokens=max_tokens,
                skip_test=skip_test,
            )
        else:
            run_quick_config()
    except SystemExit:
        raise typer.Exit(code=1)


def _normalize_platform(platform, base_url, api_key):
    """Map a free provider id onto the free platform and fill its defaults."""
    normalized = (platform or "").strip().lower()
    if normalized in free_provider_ids():
        provider = normalized
        return (
            "free",
            provider,
            base_url or provider_base_url(provider),
            api_key or "",
        )
    return normalized, "", base_url or "", api_key or ""


def _print_provider_table() -> None:
    """List every provider with its tier, key variable and key page."""
    PrettyOutput.auto_print("Free tier first (paid is optional):")
    for row in _provider_rows():
        key = ", ".join(row["env_keys"]) or "no key"
        page = row["signup_url"] or "self-hosted, set the base URL"
        PrettyOutput.auto_print(
            "  [{tier}] {name:<14} key: {key:<32} {page}".format(
                tier=row["tier"].upper(),
                name=row["id"],
                key=key,
                page=page,
            )
        )


def test_model_connection(
    platform: str, base_url: str, api_key: str, model: str
) -> tuple[bool, str]:
    """Test model API connectivity

    Args:
        platform: Platform type (haijun/openai)
        base_url: API base URL
        api_key: API key
        model: Model name

    Returns:
        (Whether it succeeded, error message)
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if platform in ("openai", "free"):
            # OpenAI-compatible test (free tier too)
            url = f"{base_url.rstrip('/')}/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return True, ""
            else:
                error_msg = (
                    response.json().get("error", {}).get("message", response.text)
                )
                return (
                    False,
                    f"API returned an error (status code: {response.status_code}): {error_msg}",
                )

        elif platform == "haijun":
            # Haijun API test
            url = f"{base_url.rstrip('/')}/messages"
            payload = {
                "model": model,
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Hi"}],
            }
            headers["juglow-version"] = "2023-06-01"
            # Haijun uses x-api-key instead of Authorization
            headers.pop("Authorization")
            headers["x-api-key"] = api_key

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return True, ""
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                return (
                    False,
                    f"API returned an error (status code: {response.status_code}): {error_msg}",
                )

        elif platform == "vinbox":
            # No key, no URL: ask the model lane that lives inside Vinbox.
            from haijunbot.haijunbot_platform.vinbox import load_model_registry

            registry = load_model_registry()
            reply, error = registry.answer("Hi", timeout=30)
            if error:
                return False, f"Vinbox model gagal: {error}"
            return (True, "") if reply else (False, "Vinbox model tidak menjawab")

    except requests.exceptions.Timeout:
        return False, "Request timed out, please check the network connection or whether the API service is available"
    except requests.exceptions.ConnectionError:
        return False, "Unable to connect to the API service, please check whether base_url is correct"
    except Exception as e:
        return False, f"Test failed, error: {str(e)}"

    return False, "Unknown platform type"


def _extract_hostname(base_url: str) -> str:
    """Extract the hostname from base_url, used to generate a unique model configuration name"""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname or base_url
        return hostname.replace(".", "_")
    except Exception:
        return base_url.replace(".", "_").replace("/", "_").replace(":", "_")


def get_models(platform: str, base_url: str, api_key: str, provider: str = "") -> list:
    """Get the platform's model list"""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if platform == "vinbox":
            from haijunbot.haijunbot_platform.vinbox import load_model_registry

            registry = load_model_registry()
            listing = registry.list_models()
            return [
                str(model.get("id"))
                for group in listing.get("groups", [])
                for model in group.get("models", [])
                if model.get("id")
            ]

        if platform == "free":
            spec = FREE_PROVIDERS.get(provider or "")
            if spec:
                return list(spec["models"])
            return sorted({m for s in FREE_PROVIDERS.values() for m in s["models"]})

        if platform in ("openai", "free"):
            url = f"{base_url}/models" if not base_url.endswith("/models") else base_url
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = [item["id"] for item in data.get("data", [])]
                return models
        elif platform == "haijun":
            try:
                from juglow import Juglow

                client = Juglow(api_key=api_key, base_url=base_url)
                page = client.models.list()
                return [getattr(m, "id", None) for m in getattr(page, "data", []) if getattr(m, "id", None)]
            except Exception:
                return []
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Failed to get the model list: {e}")

    return []


def run_quick_config_noninteractive(
    platform: str,
    base_url: str,
    api_key: str,
    model: str,
    group: str | None = None,
    max_tokens: int = 200000,
    skip_test: bool = False,
) -> None:
    """Non-interactive quick configuration of the LLM platform (for CI environments without a TTY)

    Writes a single model into the llms section of config.yaml, creates a model group (normal/smart/cheap all sharing that model),
    and sets it as the default model group. The logic is equivalent to the "only one model" branch of the interactive version, but skips interactive input.

    Args:
        platform: Platform type (openai/haijun)
        base_url: API base URL
        api_key: API key
        model: Model name
        group: Model group name, defaults to the model name
        max_tokens: Maximum input token count
        skip_test: Whether to skip the API connectivity test
    """
    init_env("")

    platform, provider, base_url, api_key = _normalize_platform(
        platform, base_url, api_key
    )
    supported = ["haijun", "openai", "vinbox", "free"]
    if platform not in supported:
        PrettyOutput.auto_print(
            f"❌ Unsupported platform type: {platform}. Use one of "
            f"{', '.join(supported)}, or a free provider id: "
            f"{', '.join(free_provider_ids())}"
        )
        raise typer.Exit(code=1)

    if platform != "vinbox" and not base_url:
        PrettyOutput.auto_print(
            "❌ --base-url is required for this platform "
            f"(free providers come with a default URL: {', '.join(free_provider_ids())})"
        )
        raise typer.Exit(code=1)

    group_name = (group or model).strip()
    if not group_name:
        PrettyOutput.auto_print("❌ The model group name cannot be empty")
        raise typer.Exit(code=1)

    # Optional connectivity test. Vinbox needs no external API test: the
    # model registry is already part of the machine.
    if not skip_test and platform != "vinbox":
        PrettyOutput.auto_print(f"🔍 Testing API connectivity for model {model}...")
        success, error_msg = test_model_connection(platform, base_url, api_key, model)
        if not success:
            PrettyOutput.auto_print(f"❌ API connectivity test failed: {error_msg}")
            raise typer.Exit(code=1)
        PrettyOutput.auto_print("✅ API connectivity test passed")

    # Read/create the configuration file
    haijunbot_dir = Path.home() / ".haijunbot"
    output_file = haijunbot_dir / "config.yaml"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    config = {}
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to read the configuration file: {e}")

    if "llms" not in config:
        config["llms"] = {}
    if "llm_groups" not in config:
        config["llm_groups"] = {}

    # Reuse the llms configuration of an existing model with the same name, otherwise create a new one
    existing_config_name = None
    for config_key, llm_config in config.get("llms", {}).items():
        if isinstance(llm_config, dict) and llm_config.get("model") == model:
            existing_config_name = config_key
            break

    llm_config_entry: Dict[str, Any] = {}
    if existing_config_name is not None:
        existing_entry = config["llms"][existing_config_name]
        if isinstance(existing_entry, dict):
            llm_config_entry = existing_entry
        llm_config_entry["platform"] = platform
        llm_config_entry["model"] = model
        llm_config_entry["max_input_token_count"] = max_tokens
        model_config_name = existing_config_name
    else:
        hostname_part = _extract_hostname(base_url)
        model_config_name = (
            f"{platform}_{hostname_part}_{model.replace('.', '_').replace('-', '_')}"
        )
        llm_config_entry = {
            "platform": platform,
            "model": model,
            "max_input_token_count": max_tokens,
        }
        config["llms"][model_config_name] = llm_config_entry

    if platform == "free":
        llm_config_entry["llm_config"] = {
            "provider": provider,
            "openai_api_key": api_key,
            "openai_api_base": base_url,
            "supports_multimodal": False,
        }
    elif platform == "openai":
        llm_config_entry["llm_config"] = {
            "openai_api_key": api_key,
            "openai_api_base": base_url,
            "supports_multimodal": False,
        }
    elif platform == "haijun":
        llm_config_entry["llm_config"] = {
            "juglow_api_key": api_key,
            "juglow_base_url": base_url,
            "supports_multimodal": False,
        }
    elif platform == "vinbox":
        # No API key, no base URL. HaijunBot asks Vinbox's model registry.
        llm_config_entry["llm_config"] = {"supports_multimodal": False}

    # Create/update the model group (normal/smart/cheap all sharing that model)
    config["llm_groups"][group_name] = {
        "normal_llm": model_config_name,
        "smart_llm": model_config_name,
        "cheap_llm": model_config_name,
    }
    config["llm_group"] = group_name

    # Save the configuration
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        PrettyOutput.auto_print(
            f"✅ Configuration saved to {output_file} (model group: {group_name}, model: {model})"
        )
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to save the configuration: {e}")
        raise typer.Exit(code=1)


def _provider_needs_key(provider: str) -> bool:
    """Whether a provider needs an API key at all (opencode does not)."""
    spec = FREE_PROVIDERS.get(provider or "")
    if spec is None:
        return True
    return bool(spec["env_keys"])


def _ask_provider_and_key():
    """Ask for provider, base URL and key.

    A provider without a key (opencode) only needs its base URL: the key prompt
    is skipped rather than cancelling the whole configuration.
    Returns (platform, provider, base_url, api_key), or None when cancelled.
    """
    _print_provider_table()
    answer = get_single_line_input(
        "Please enter the platform or provider id "
        "(haijun/openai/vinbox, or: " + "/".join(free_provider_ids()) + "):"
    )
    platform, provider, base_url, api_key = _normalize_platform(answer, "", "")
    spec = FREE_PROVIDERS.get(provider or "")
    if spec is None:
        base_url = get_single_line_input("Please enter the API base URL:")
        api_key = get_single_line_input("Please enter the API key:", is_password=True)
        return platform, provider, base_url, api_key

    PrettyOutput.auto_print(
        f"🔑 {spec['name']} ({spec['tier']}) — key page: "
        f"{spec['signup_url'] or 'self-hosted, no public key page'}"
        f" | env: {', '.join(spec['env_keys']) or 'none'}"
    )
    if spec["base_url"]:
        base_url = spec["base_url"]
    else:
        base_url = get_single_line_input("Please enter the API base URL:")
    if not base_url:
        PrettyOutput.auto_print("❌ Empty base URL, configuration cancelled")
        return None
    if not _provider_needs_key(provider):
        PrettyOutput.auto_print(
            f"ℹ️ {spec['name']} needs no API key; continuing with the base URL only."
        )
        return platform, provider, base_url, ""
    api_key = get_single_line_input(
        f"Please paste a valid {spec['name']} API key:", is_password=True
    ).strip()
    if not api_key:
        PrettyOutput.auto_print("❌ Empty API key, configuration cancelled")
        return None
    return platform, provider, base_url, api_key


def run_quick_config():
    """Quickly configure LLM platform information (does not depend on typer, callable by built-in commands)"""
    init_env("")

    selection = _ask_provider_and_key()
    if selection is None:
        return
    platform, provider, base_url, api_key = selection

    # Validate the platform type (a free provider id is accepted too)
    platform, provider, base_url, api_key = _normalize_platform(
        platform, base_url, api_key
    )
    if platform not in ["haijun", "openai", "vinbox", "free"]:
        PrettyOutput.auto_print(
            f"❌ Unsupported platform type: {platform}. Use haijun, openai, vinbox, "
            f"free, or a free provider id: {', '.join(free_provider_ids())}"
        )
        return

    config_name = provider or platform
    PrettyOutput.auto_print(
        f"🚀 Starting configuration for the {platform.upper()} platform, configuration name: {config_name}"
    )

    # Test the API connection and get the model list
    models = get_models(platform, base_url, api_key, provider)
    if not models:
        PrettyOutput.auto_print("⚠️ Failed to automatically get the model list")
        use_manual_input = user_confirm("Do you want to manually enter the model names?", default=True)
        if use_manual_input:
            model_input = get_single_line_input(
                "Please enter the model names (separate multiple models with commas, e.g. gpt-4o,gpt-3.5-turbo):"
            )
            models = [m.strip() for m in model_input.split(",") if m.strip()]
            if not models:
                PrettyOutput.auto_print("❌ No valid model names entered, configuration cancelled")
                return
        else:
            PrettyOutput.auto_print("❌ No model names provided, configuration cancelled")
            return

    PrettyOutput.auto_print(
        f"📋 Available models: {', '.join(models[:10])}{'...' if len(models) > 10 else ''}"
    )

    # Model selection logic
    if len(models) > 1:
        manual_input_option = len(models) + 1
        table_lines = ["| No. | Model Name |", "|------|----------|"]
        for i, model in enumerate(models, 1):
            table_lines.append(f"| {i} | {model} |")
        table_lines.append(f"| {manual_input_option} | Manually enter model names |")
        PrettyOutput.print_markdown("\n".join(table_lines), title="Available model list")

        configure_all = user_confirm("Do you want to configure all models?", default=False)
        if configure_all:
            selected_models = models
        else:
            model_choices = get_single_line_input(
                f"Please enter the numbers of the models to configure (separated by commas, enter {manual_input_option} to manually enter model names):"
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
                        return
                if use_manual_input:
                    model_input = get_single_line_input(
                        "Please enter the model names (separate multiple models with commas):"
                    )
                    manual_models = [
                        m.strip() for m in model_input.split(",") if m.strip()
                    ]
                    if not manual_models:
                        PrettyOutput.auto_print("❌ No valid model names entered")
                        return
                    selected_models.extend(manual_models)
                selected_models = list(dict.fromkeys(selected_models))
                if not selected_models:
                    PrettyOutput.auto_print("❌ No valid model selected")
                    return
            except ValueError:
                PrettyOutput.auto_print("❌ Please enter valid numeric numbers, separated by commas")
                return
    else:
        selected_models = [models[0]]

    PrettyOutput.auto_print(
        f"✅ Selected {len(selected_models)} model(s): {', '.join(selected_models)}"
    )

    # Read/create the configuration file
    haijunbot_dir = Path.home() / ".haijunbot"
    output_file = haijunbot_dir / "config.yaml"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    config = {}
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to read the configuration file: {e}")
            if not user_confirm("Do you want to continue creating a new configuration?", default=True):
                return

    if "llms" not in config:
        config["llms"] = {}
    if "llm_groups" not in config:
        config["llm_groups"] = {}

    # Collect existing models
    existing_config_models = []
    for llm_config in config.get("llms", {}).values():
        if isinstance(llm_config, dict):
            model_name = llm_config.get("model")
            if isinstance(model_name, str) and model_name.strip():
                existing_config_models.append(model_name.strip())

    role_candidate_models = list(selected_models)
    existing_candidate_models = [
        m for m in existing_config_models if m not in role_candidate_models
    ]

    if existing_candidate_models and user_confirm(
        "When configuring the model group, do you also want to allow choosing from models already in the configuration file?", default=False
    ):
        role_candidate_models.extend(existing_candidate_models)
        PrettyOutput.auto_print(
            f"📚 Added existing models from the configuration file to the candidate list: {', '.join(existing_candidate_models)}"
        )

    role_candidate_models = list(dict.fromkeys(role_candidate_models))

    # Pre-initialize to ensure accessibility outside the subsequent branches (ty's cross-branch inference limitation)
    normal_model = ""
    smart_model = ""
    cheap_model = ""
    eval_model = ""

    # Select the normal/smart/cheap models
    if len(role_candidate_models) == 1:
        normal_model = smart_model = cheap_model = role_candidate_models[0]
        PrettyOutput.auto_print(f"🎯 Normal model: {normal_model}")
        PrettyOutput.auto_print(f"🧠 Smart model: {smart_model}")
        PrettyOutput.auto_print(f"💰 Cheap model: {cheap_model}")
    else:
        # Normal
        table_lines = ["| No. | Model Name |", "|------|----------|"]
        for i, model in enumerate(role_candidate_models, 1):
            table_lines.append(f"| {i} | {model} |")
        PrettyOutput.print_markdown(
            "\n".join(table_lines), title="Please select the Normal model (most scenarios)"
        )
        normal_choice = get_single_line_input("Please enter the Normal model number:")
        try:
            normal_idx = int(normal_choice.strip()) - 1
            if 0 <= normal_idx < len(role_candidate_models):
                normal_model = role_candidate_models[normal_idx]
                PrettyOutput.auto_print(f"🎯 Normal model: {normal_model}")
            else:
                PrettyOutput.auto_print(f"❌ Invalid model number: {normal_choice}")
                return
        except ValueError:
            PrettyOutput.auto_print("❌ Please enter a valid numeric number")
            return
        # Smart
        table_lines = ["| No. | Model Name |", "|------|----------|"]
        for i, model in enumerate(role_candidate_models, 1):
            table_lines.append(f"| {i} | {model} |")
        PrettyOutput.print_markdown(
            "\n".join(table_lines), title="Please select the Smart model (code generation)"
        )
        smart_choice = get_single_line_input("Please enter the Smart model number:")
        try:
            smart_idx = int(smart_choice.strip()) - 1
            if 0 <= smart_idx < len(role_candidate_models):
                smart_model = role_candidate_models[smart_idx]
                PrettyOutput.auto_print(f"🧠 Smart model: {smart_model}")
            else:
                PrettyOutput.auto_print(f"❌ Invalid model number: {smart_choice}")
        except ValueError:
            PrettyOutput.auto_print("❌ Please enter a valid numeric number")
            return
        # Cheap
        table_lines = ["| No. | Model Name |", "|------|----------|"]
        for i, model in enumerate(role_candidate_models, 1):
            table_lines.append(f"| {i} | {model} |")
        PrettyOutput.print_markdown(
            "\n".join(table_lines), title="Please select the Cheap model (low-requirement, high-data-volume scenarios)"
        )
        cheap_choice = get_single_line_input("Please enter the Cheap model number:")
        try:
            cheap_idx = int(cheap_choice.strip()) - 1
            if 0 <= cheap_idx < len(role_candidate_models):
                cheap_model = role_candidate_models[cheap_idx]
                PrettyOutput.auto_print(f"💰 Cheap model: {cheap_model}")
            else:
                PrettyOutput.auto_print(f"❌ Invalid model number: {cheap_choice}")
                return
        except ValueError:
            PrettyOutput.auto_print("❌ Please enter a valid numeric number")
            return

    # Eval (optional; leave blank to not enable the structured evaluation model)
    table_lines = ["| No. | Model Name |", "|------|----------|"]
    for i, model in enumerate(role_candidate_models, 1):
        table_lines.append(f"| {i} | {model} |")
    PrettyOutput.print_markdown(
        "\n".join(table_lines),
        title="Please select the Eval model (structured evaluation; leave blank to skip)",
    )
    eval_choice = get_single_line_input(
        "Please enter the Eval model number (leave blank to not enable the structured evaluation model):"
    )
    if eval_choice.strip():
        try:
            eval_idx = int(eval_choice.strip()) - 1
            if 0 <= eval_idx < len(role_candidate_models):
                eval_model = role_candidate_models[eval_idx]
                PrettyOutput.auto_print(f"🧪 Eval model: {eval_model}")
            else:
                PrettyOutput.auto_print(f"❌ Invalid model number: {eval_choice}")
                return
        except ValueError:
            PrettyOutput.auto_print("❌ Please enter a valid numeric number")
            return

    # Test API connectivity
    PrettyOutput.auto_print(f"🔍 Testing API connectivity for model {normal_model}...")
    success, error_msg = test_model_connection(
        platform, base_url, api_key, normal_model
    )
    if success:
        PrettyOutput.auto_print("✅ API connectivity test passed")
    else:
        PrettyOutput.auto_print(f"❌ API connectivity test failed: {error_msg}")
        force_save = user_confirm("The test failed. Do you still want to save the configuration to the file?", default=False)
        if not force_save:
            PrettyOutput.auto_print("👋 Configuration saving cancelled")
            return
        PrettyOutput.auto_print("⚠️ The configuration will be saved despite the test failure")

    # Enter the model group name
    default_group_name = normal_model.replace(".", "_").replace("-", "_")
    group_name_input = get_single_line_input(
        f"Please enter the model group name (default: {default_group_name}):"
    )
    group_name = (
        group_name_input.strip() if group_name_input.strip() else default_group_name
    )
    if not group_name:
        PrettyOutput.auto_print("❌ The model group name cannot be empty")
        return
    PrettyOutput.auto_print(f"✅ Model group name: {group_name}")

    # Set the maximum token count
    default_max_tokens = 200000
    unique_role_models = list(
        dict.fromkeys([normal_model, smart_model, cheap_model, eval_model])
    )
    existing_model_configs = {
        llm_config.get("model"): llm_config
        for llm_config in config.get("llms", {}).values()
        if isinstance(llm_config, dict) and isinstance(llm_config.get("model"), str)
    }
    model_max_tokens = {}
    for model in unique_role_models:
        prev_model_config = existing_model_configs.get(model, {})
        existing_max_tokens = prev_model_config.get("max_input_token_count")
        default_token_count = (
            existing_max_tokens
            if isinstance(existing_max_tokens, int) and existing_max_tokens > 0
            else default_max_tokens
        )
        while True:
            max_tokens_input = get_single_line_input(
                f"Please enter the maximum token count for model {model} (default: {default_token_count}):"
            )
            if not max_tokens_input.strip():
                model_max_tokens[model] = default_token_count
                PrettyOutput.auto_print(
                    f"✅ Model {model} uses the default maximum token count: {default_token_count}"
                )
                break
            try:
                max_tokens = int(max_tokens_input.strip())
                if max_tokens <= 0:
                    PrettyOutput.auto_print("❌ The maximum token count must be a positive integer")
                    continue
                model_max_tokens[model] = max_tokens
                PrettyOutput.auto_print(
                    f"✅ Model {model} maximum token count set to: {max_tokens}"
                )
                break
            except ValueError:
                PrettyOutput.auto_print("❌ Please enter a valid positive integer")

    # Multimodal support
    supports_multimodal = user_confirm(
        "Do you want to enable multimodal support (support image input)?", default=False
    )

    # Create the model configuration
    model_config_names = {}
    for model in unique_role_models:
        existing_config_name = None
        existing_model_config = None
        for config_key, llm_config in config.get("llms", {}).items():
            if isinstance(llm_config, dict) and llm_config.get("model") == model:
                existing_config_name = config_key
                existing_model_config = llm_config
                break
        if existing_config_name is not None and existing_model_config is not None:
            model_config_names[model] = existing_config_name
            existing_model_config["platform"] = platform
            existing_model_config["model"] = model
            existing_model_config["max_input_token_count"] = model_max_tokens[model]
            if platform == "free":
                existing_model_config["llm_config"] = {
                    "provider": provider,
                    "openai_api_key": api_key,
                    "openai_api_base": base_url,
                    "supports_multimodal": supports_multimodal,
                }
            elif platform == "openai":
                existing_model_config["llm_config"] = {
                    "openai_api_key": api_key,
                    "openai_api_base": base_url,
                    "supports_multimodal": supports_multimodal,
                }
            elif platform == "haijun":
                existing_model_config["llm_config"] = {
                    "juglow_api_key": api_key,
                    "juglow_base_url": base_url,
                    "supports_multimodal": supports_multimodal,
                }
            else:
                existing_model_config["llm_config"] = {
                    f"{platform}_api_key": api_key,
                    f"{platform}_base_url": base_url,
                    "supports_multimodal": supports_multimodal,
                }
            PrettyOutput.auto_print(
                f"✅ Updated model configuration: {existing_config_name} -> {model}"
            )
            continue
        hostname_part = _extract_hostname(base_url)
        model_config_name = (
            f"{config_name}_{hostname_part}_{model.replace('.', '_').replace('-', '_')}"
        )
        if platform == "free":
            llm_config_dict = {
                "provider": provider,
                "openai_api_key": api_key,
                "openai_api_base": base_url,
                "supports_multimodal": supports_multimodal,
            }
        elif platform == "openai":
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
        config["llms"][model_config_name] = {
            "platform": platform,
            "model": model,
            "max_input_token_count": model_max_tokens[model],
            "llm_config": llm_config_dict,
        }
        model_config_names[model] = model_config_name

    PrettyOutput.auto_print(f"✅ Created configurations for {len(unique_role_models)} model(s)")

    # Create the model group
    group_config = {
        "normal_llm": model_config_names[normal_model],
        "smart_llm": model_config_names[smart_model],
        "cheap_llm": model_config_names[cheap_model],
    }
    # Only write it when an Eval model is selected; if not selected, no eval_llm key is produced
    if eval_model:
        group_config["eval_llm"] = model_config_names[eval_model]
    config["llm_groups"][group_name] = group_config
    PrettyOutput.auto_print(
        f"✅ Created model group '{group_name}', normal={normal_model}, smart={smart_model}, cheap={cheap_model}"
        + (f", eval={eval_model}" if eval_model else "")
    )

    # Set the default model group
    config["llm_group"] = group_name
    PrettyOutput.auto_print(f"✅ Set the default model group to '{group_name}'")

    # Save the configuration
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
        PrettyOutput.auto_print(f"✅ Configuration saved to {output_file}")
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to save the configuration: {e}")


if __name__ == "__main__":
    app()
