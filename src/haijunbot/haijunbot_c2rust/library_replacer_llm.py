# -*- coding: utf-8 -*-
"""LLM model creation and evaluation module for library replacer."""

from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.constants import MAX_LLM_RETRIES
from haijunbot.haijunbot_c2rust.library_replacer_prompts import build_subtree_prompt


def check_llm_availability() -> tuple[bool, Any, Any, Any, Any]:
    """Check LLM availability; returns (available, PlatformRegistry, get_smart_platform_name, get_smart_model_name, get_llm_config)
    Uses the smart platform, suitable for complex scenarios such as code generation
    """
    try:
        from haijunbot.haijunbot_platform.registry import PlatformRegistry
        from haijunbot.haijunbot_utils.config import get_llm_config
        from haijunbot.haijunbot_utils.config import get_smart_model_name
        from haijunbot.haijunbot_utils.config import get_smart_platform_name

        return (
            True,
            PlatformRegistry,
            get_smart_platform_name,
            get_smart_model_name,
            get_llm_config,
        )
    except Exception:
        return False, None, None, None, None


def create_llm_model(
    llm_group: Optional[str],
    disabled_display: str,
    model_available: bool,
    PlatformRegistry: Any,
    get_smart_platform_name: Any,
    get_smart_model_name: Any,
    get_llm_config: Any,
) -> Optional[Any]:
    """Create the LLM model; uses the smart platform, suitable for complex scenarios such as code generation"""
    if not model_available:
        return None
    try:
        # Use the global PlatformRegistry instance
        from haijunbot.haijunbot_platform.registry import PlatformRegistry

        # Use the global PlatformRegistry instance to ensure the platform is loaded correctly
        # get_smart_platform internally calls get_llm_config("smart", ...); get_llm_config now handles the fallback logic
        registry = PlatformRegistry.get_global_platform_registry()
        model = registry.get_smart_platform()

        # Ensure the model has no console output (consistent with code_agent.py)
        try:
            model.set_suppress_output(False)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.library_replacer_llm",
                function="create_llm_model",
            )
            pass

        # Set the system prompt
        model.set_system_prompt(
            "You are a senior C→Rust migration expert. Task: given a function and its call subtree (dependency graph summary, function signatures, source snippets), "
            "determine whether one or more mature Rust libraries can replace the functionality of the entire subtree (multiple APIs within a library cooperating and multiple libraries combined are allowed; immature/uncommon libraries are not allowed). "
            "If replaceable, provide a libraries list (library names), and optionally representative APIs/modules and implementation notes (how these libraries cooperate to implement it). "
            "Output format: output only one <SUMMARY> block; the block directly contains a JSON object (no extra tags). Fields: replaceable(bool), libraries(list[str]), confidence(float 0..1), optional library(str, preferred primary library), api(str) or apis(list), notes(str)."
        )
        return model
    except Exception as e:
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-library] Failed to initialize the LLM platform; falling back to a conservative strategy: {e}"
        )
        return None


def parse_agent_json_summary(
    text: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse the JSON summary returned by the Agent
    Returns (parse_result, error_message)
    If parsing succeeds, returns (data, None)
    If parsing fails, returns (None, error_message)
    """
    if not isinstance(text, str) or not text.strip():
        return None, "Summary text is empty"
    import re as _re

    from haijunbot.haijunbot_utils.jsonnet_compat import loads as _json_loads

    # Extract the <SUMMARY> block
    m_sum = _re.search(r"<SUMMARY>([\s\S]*?)</SUMMARY>", text, flags=_re.IGNORECASE)
    block = (m_sum.group(1) if m_sum else text).strip()

    if not block:
        return None, "No <SUMMARY> or </SUMMARY> tag found, or the tag content is empty"

    # Parse the content inside the <SUMMARY> block directly as JSON
    # jsonnet_compat.loads automatically handles markdown code block markers (such as ```json5, ```json, ```, etc.)
    try:
        data = _json_loads(block)
        if isinstance(data, dict):
            return data, None
        return None, f"The JSON parse result is not a dictionary, but a {type(data).__name__}"
    except Exception as json_err:
        return None, f"JSON parsing failed: {str(json_err)}"


def llm_evaluate_subtree(
    fid: int,
    desc: set,
    by_id: Dict[int, Dict[str, Any]],
    adj_func: Dict[int, List[int]],
    disabled_norm: List[str],
    disabled_display: str,
    model_available: bool,
    new_model_func: Callable[[], Optional[Any]],
    additional_notes: str = "",
) -> Dict[str, Any]:
    """Use the LLM to evaluate whether the subtree is replaceable; supports up to 3 retries"""
    if not model_available:
        return {"replaceable": False}
    model = new_model_func()
    if not model:
        return {"replaceable": False}

    base_prompt = build_subtree_prompt(
        fid, desc, by_id, adj_func, disabled_display, additional_notes
    )
    last_parse_error = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            # Build the prompt for the current attempt
            if attempt == 1:
                prompt = base_prompt
            else:
                # Include the previous error message on retry
                error_hint = ""
                if last_parse_error:
                    error_hint = (
                        f"\n\n**Format error details (fix the output format based on the following error):**\n- {last_parse_error}\n\n"
                        + "Please ensure the output JSON format is correct, including correct quotes, commas, braces, etc. Output only one <SUMMARY> block; the block directly contains a JSON object (no extra tags)."
                    )
                prompt = base_prompt + error_hint

            # Call the LLM
            result = model.chat_until_success(prompt)
            parsed, parse_error = parse_agent_json_summary(result or "")

            if parse_error:
                # JSON parsing failed; record the error and prepare to retry
                last_parse_error = parse_error
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-library] Attempt {attempt}/{MAX_LLM_RETRIES}: JSON parsing failed: {parse_error}"
                )
                # Print the raw content for debugging
                result_text = str(result or "").strip()
                if result_text:
                    PrettyOutput.auto_print(
                        f"📄 [c2rust-library] Raw LLM response content (first 1000 characters):\n{result_text[:1000]}"
                    )
                    if len(result_text) > 1000:
                        PrettyOutput.auto_print(
                            f"📄 [c2rust-library] ... ({len(result_text) - 1000} more characters not shown)"
                        )
                if attempt < MAX_LLM_RETRIES:
                    continue  # keep retrying
                else:
                    # The last attempt also failed; use the default value
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-library] JSON parsing still failed after {MAX_LLM_RETRIES} retries: {parse_error}; using the default value"
                    )
                    return {"replaceable": False}

            # Parsing succeeded; check whether it is a dictionary
            if not isinstance(parsed, dict):
                last_parse_error = f"The parse result is not a dictionary, but a {type(parsed).__name__}"
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-library] Attempt {attempt}/{MAX_LLM_RETRIES}: {last_parse_error}"
                )
                # Print the parse result and raw content for debugging
                PrettyOutput.auto_print(
                    f"📊 [c2rust-library] Parse result type: {type(parsed).__name__}, value: {repr(parsed)[:500]}"
                )
                result_text = str(result or "").strip()
                if result_text:
                    PrettyOutput.auto_print(
                        f"📄 [c2rust-library] Raw LLM response content (first 1000 characters):\n{result_text[:1000]}"
                    )
                if attempt < MAX_LLM_RETRIES:
                    continue  # keep retrying
                else:
                    PrettyOutput.auto_print(
                        f"🔴 [c2rust-library] Result format still incorrect after {MAX_LLM_RETRIES} retries; treated as not replaceable."
                    )
                    return {"replaceable": False}

            # Successfully parsed as a dictionary; process the result
            rep = bool(parsed.get("replaceable") is True)
            lib = str(parsed.get("library") or "").strip()
            api = str(parsed.get("api") or parsed.get("function") or "").strip()
            apis = parsed.get("apis")
            libs_raw = parsed.get("libraries")
            notes = str(parsed.get("notes") or "").strip()
            # Normalize libraries
            libraries: List[str] = []
            if isinstance(libs_raw, list):
                libraries = [str(x).strip() for x in libs_raw if str(x).strip()]
            elif isinstance(libs_raw, str):
                libraries = [s.strip() for s in libs_raw.split(",") if s.strip()]
            conf = parsed.get("confidence")
            try:
                conf = float(conf) if conf is not None else 0.0
            except Exception:
                conf = 0.0
            # Concrete APIs or specific library names are not required; if absent and a library field exists, include it in libraries
            if not libraries and lib:
                libraries = [lib]

            # When a disabled library is hit, force it to be treated as not replaceable
            if disabled_norm:
                libs_lower = [lib_name.lower() for lib_name in libraries]
                lib_single_lower = lib.lower() if lib else ""
                banned_hit = any(
                    lower_lib in disabled_norm for lower_lib in libs_lower
                ) or (lib_single_lower and lib_single_lower in disabled_norm)
                if banned_hit:
                    rep = False
                    warn_libs = (
                        ", ".join(sorted(set([lib] + libraries)))
                        if (libraries or lib)
                        else "(no library name provided)"
                    )
                    root_rec = by_id.get(fid, {})
                    root_name = (
                        root_rec.get("qualified_name")
                        or root_rec.get("name")
                        or f"sym_{fid}"
                    )
                    PrettyOutput.auto_print(
                        f"🚫 [c2rust-library] Evaluation result contains a disabled library; forced to be judged as not replaceable: {root_name} | hit libraries: {warn_libs}"
                    )
                    if notes:
                        notes = notes + f" | disabled library hit: {warn_libs}"
                    else:
                        notes = f"disabled library hit: {warn_libs}"

            result_obj: Dict[str, Any] = {
                "replaceable": rep,
                "library": lib,
                "libraries": libraries,
                "api": api,
                "confidence": conf,
            }
            if isinstance(apis, list):
                result_obj["apis"] = apis
            if notes:
                result_obj["notes"] = notes

            # Result obtained successfully; return
            if attempt > 1:
                PrettyOutput.auto_print(
                    f"✅ [c2rust-library] Successfully obtained the evaluation result on attempt {attempt}"
                )
            return result_obj

        except Exception as e:
            # LLM call exception; record and prepare to retry
            last_parse_error = f"LLM call exception: {str(e)}"
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-library] Attempt {attempt}/{MAX_LLM_RETRIES}: LLM evaluation failed: {e}"
            )
            if attempt < MAX_LLM_RETRIES:
                continue  # keep retrying
            else:
                # The last attempt also failed; return the default value
                PrettyOutput.auto_print(
                    f"🔴 [c2rust-library] LLM evaluation still failed after {MAX_LLM_RETRIES} retries: {e}; treated as not replaceable"
                )
                return {"replaceable": False}

    # Theoretically unreachable, but as a safety net
    return {"replaceable": False}
