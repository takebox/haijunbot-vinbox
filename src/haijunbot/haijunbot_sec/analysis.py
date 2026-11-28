# -*- coding: utf-8 -*-
"""Analysis-related module"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from typing import Any, Dict, List, Optional, cast

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_sec.parsers import try_parse_summary_report
from haijunbot.haijunbot_sec.prompts import build_summary_prompt
from haijunbot.haijunbot_sec.utils import git_restore_if_dirty


def _build_detailed_error_guidance(
    prev_parsed_items: Optional[List[Dict[str, Any]]],
) -> str:
    """Build detailed format-error guidance information"""
    if prev_parsed_items is None:
        return "\n\n**Format error details (please fix the output format based on the following errors):**\n- Failed to parse a valid JSON array"

    errors = []
    if not isinstance(prev_parsed_items, list):
        errors.append("The result is not an array")  # type: ignore[unreachable]
        error_text = "\n".join(f"- {err}" for err in errors)
        return f"\n\n**Format error details (please fix the output format based on the following errors):**\n{error_text}"

    for idx, item in enumerate(prev_parsed_items):
        if not isinstance(item, dict):
            errors.append(f"Element {idx} is not a dict")  # type: ignore[unreachable]
            break

        # Basic field checks
        has_gid = "gid" in item
        has_gids = "gids" in item
        if not has_gid and not has_gids:
            errors.append(f"Element {idx} is missing the required field gid or gids")
            break
        if has_gid and has_gids:
            errors.append(f"Element {idx} cannot contain both gid and gids")
            break

        # Specific field validation
        if has_gid:
            try:
                gid_val = int(item.get("gid", 0))
                if gid_val < 1:
                    errors.append(f"The gid of element {idx} must be >= 1")
                    break
            except (ValueError, TypeError):
                errors.append(f"The gid of element {idx} has an invalid format (must be an integer)")
                break

        elif has_gids:
            gids_list = item.get("gids", [])
            if not isinstance(gids_list, list) or len(gids_list) == 0:
                errors.append(f"The gids of element {idx} must be a non-empty array")
                break
            for g_idx, gid_val in enumerate(gids_list):
                try:
                    if int(str(gid_val)) < 1:
                        errors.append(f"The gids[{g_idx}] of element {idx} must be >= 1")
                        break
                except (ValueError, TypeError):
                    errors.append(f"The gids of element {idx} have an invalid format (must be an integer array)")
                    break

        # has_risk field validation
        has_risk = item.get("has_risk")
        if has_risk is None or not isinstance(has_risk, bool):
            errors.append(f"Element {idx} is missing the required field has_risk (must be a boolean)")
            break

        if has_risk is True:
            required = ["preconditions", "trigger_path", "consequences", "suggestions"]
            for key in required:
                if key not in item:
                    errors.append(f"The has_risk of element {idx} is true, but the required field {key} is missing")
                    break
                val = item[key]
                if not isinstance(val, str) or not val.strip():
                    errors.append(f"The {key} field of element {idx} cannot be empty")
                    break

    if errors:
        error_text = "\n".join(f"- {err}" for err in errors)
        return f"\n\n**Format error details (please fix the output format based on the following errors):**\n{error_text}"

    return "\n\n**Format error details (please fix the output format based on the following errors):**\n- The data format does not meet requirements; please check the required fields and data types"


def valid_items(items: Optional[List[Dict[str, Any]]]) -> bool:
    """Validate the format of the analysis result items"""
    if not isinstance(items, list):
        return False

    for it in items:
        if not isinstance(it, dict):
            return False  # type: ignore[unreachable]
        has_gid = "gid" in it
        has_gids = "gids" in it
        if not has_gid and not has_gids:
            return False
        if has_gid and has_gids:
            return False
        if has_gid:
            try:
                if int(it["gid"]) < 1:
                    return False
            except Exception:
                return False
        elif has_gids:
            if not isinstance(it["gids"], list) or len(it["gids"]) == 0:
                return False
            for gid_val in it["gids"]:
                try:
                    if int(gid_val) < 1:
                        return False
                except Exception:
                    return False
        if "has_risk" not in it or not isinstance(it["has_risk"], bool):
            return False
        if it.get("has_risk"):
            for key in ["preconditions", "trigger_path", "consequences", "suggestions"]:
                if key not in it:
                    return False
                if not isinstance(it[key], str) or not it[key].strip():
                    return False
    return True


def build_analysis_task_context(
    batch: List[Dict[str, Any]], entry_path: str, langs: List[str]
) -> str:
    """Build the analysis task context"""
    import json as _json2

    batch_ctx: List[Dict[str, Any]] = list(batch)
    cluster_verify = str(batch_ctx[0].get("verify") if batch_ctx else "")
    cluster_gids_ctx = [it.get("gid") for it in batch_ctx]
    return f"""
# Security subtask batch
Context parameters:
- entry_path: {entry_path}
- languages: {langs}
- cluster_verification: {cluster_verify}

- cluster_gids: {cluster_gids_ctx}
- note: Each candidate contains gid/verify fields; the model only needs to output gid to uniformly give the verification/judgment conclusion (global numbering); there is no need to use local ids

Batch candidates (JSON array):
{_json2.dumps(batch_ctx, ensure_ascii=False, indent=2)}
""".strip()


def build_validation_error_guidance(
    parse_error_analysis: Optional[str],
    prev_parsed_items: Optional[List[Dict[str, Any]]],
) -> str:
    """Build validation error guidance information"""
    if parse_error_analysis:
        return f"""

**Format error details (please fix the output format based on the following errors):**
- JSON parsing failed: {parse_error_analysis}

Please ensure the output JSON format is correct, including correct quotes, commas, braces, etc. Output only one <REPORT> block, and the block directly contains the JSON array (no extra tags needed). Jsonnet syntax is supported (such as trailing commas, comments, etc.)."""
    elif prev_parsed_items is None:
        return "\n\n**Format error details (please fix the output format based on the following errors):**\n- Failed to parse a valid JSON array from the summary"

    # If it passes the validation function, return an empty string
    if valid_items(prev_parsed_items):
        return ""

    # Otherwise build detailed error guidance
    return _build_detailed_error_guidance(prev_parsed_items)


def run_analysis_agent_with_retry(
    agent: Agent,
    per_task: str,
    summary_container: Dict[str, str],
    entry_path: str,
    task_id: str,
    bidx: int,
    meta_records: List[Dict[str, Any]],
) -> tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]]]:
    """Run the analysis Agent and retry until it succeeds"""
    summary_items: Optional[List[Dict[str, Any]]] = None
    workspace_restore_info: Optional[Dict[str, Any]] = None
    use_direct_model_analysis = False
    prev_parsed_items: Optional[List[Dict[str, Any]]] = None
    parse_error_analysis: Optional[str] = None
    attempt = 0

    while True:
        attempt += 1
        summary_container["text"] = ""

        if use_direct_model_analysis:
            summary_prompt_text = build_summary_prompt()
            error_guidance = build_validation_error_guidance(
                parse_error_analysis, prev_parsed_items
            )
            full_prompt = f"{per_task}{error_guidance}\n\n{summary_prompt_text}"
            try:
                response = agent.model.chat_until_success(full_prompt)
                summary_container["text"] = response
            except Exception as e:
                try:
                    PrettyOutput.auto_print(
                        f"⚠️ [haijunbot-sec] Direct model call failed: {e}, falling back to run()"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.analysis",
                        function="run_analysis_agent_with_retry",
                    )
                    pass
                agent.run(per_task)
        else:
            agent.run(per_task)

        # Workspace protection
        try:
            _changed = git_restore_if_dirty(entry_path)
            workspace_restore_info = {
                "performed": bool(_changed),
                "changed_files_count": int(_changed or 0),
                "action": "git checkout -- .",
            }
            meta_records.append(
                {
                    "task_id": task_id,
                    "batch_index": bidx,
                    "workspace_restore": workspace_restore_info,
                    "attempt": attempt + 1,
                }
            )
            if _changed:
                try:
                    PrettyOutput.auto_print(
                        f"🔵 [haijunbot-sec] Workspace restored ({_changed} files), action: git checkout -- ."
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.analysis",
                        function="run_analysis_agent_with_retry",
                    )
                    pass
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.analysis",
                function="run_analysis_agent_with_retry",
            )
            pass

        # Parse the <REPORT> (JSON) in the summary
        summary_text = summary_container.get("text", "")
        parsed_items: Optional[List[Dict[str, Any]]] = None
        parse_error_analysis = None
        if summary_text:
            rep, parse_error_analysis = try_parse_summary_report(summary_text)
            if parse_error_analysis:
                try:
                    PrettyOutput.auto_print(
                        f"⚠️ [haijunbot-sec] Failed to parse the analysis result JSON: {parse_error_analysis}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.analysis",
                        function="run_analysis_agent_with_retry",
                    )
                    pass
            elif isinstance(rep, list):
                parsed_items = cast(List[Dict[str, Any]], rep)
            elif isinstance(rep, dict):
                rep_dict = cast(Dict[str, Any], rep)
                items = rep_dict.get("issues")
                if isinstance(items, list):
                    parsed_items = cast(List[Dict[str, Any]], items)

        # Key field validation
        # An empty array [] is valid (meaning no issues were found) and needs to be handled separately
        if parsed_items is not None:
            if len(parsed_items) == 0:
                # An empty array means no issues were found; this is a valid format
                summary_items = parsed_items
                break
            elif valid_items(parsed_items):
                # A non-empty array needs format validation
                summary_items = parsed_items
                break

        # Format validation failed; subsequent retries use a direct model call
        use_direct_model_analysis = True
        prev_parsed_items = parsed_items
        if parse_error_analysis:
            try:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Failed to parse the analysis result JSON -> retry #{attempt} (batch={bidx}, using a direct model call, will feed back the parse error)"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.analysis",
                    function="run_analysis_agent_with_retry",
                )
                pass
        else:
            try:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Invalid analysis result format -> retry #{attempt} (batch={bidx}, using a direct model call)"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.analysis",
                    function="run_analysis_agent_with_retry",
                )
                pass

    return summary_items, workspace_restore_info


def expand_and_filter_analysis_results(
    summary_items: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Expand the gids format into individual gid entries, and filter out items with risk"""
    items_with_risk: List[Dict[str, Any]] = []
    items_without_risk: List[Dict[str, Any]] = []
    merged_items: List[Dict[str, Any]] = []

    for it in summary_items:
        has_risk = it.get("has_risk") is True
        if "gids" in it and isinstance(it.get("gids"), list):
            for gid_val in it.get("gids", []):
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        item = {
                            **{k: v for k, v in it.items() if k != "gids"},
                            "gid": gid_int,
                        }
                        if has_risk:
                            merged_items.append(item)
                            items_with_risk.append(item)
                        else:
                            items_without_risk.append(item)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.analysis",
                        function="expand_and_filter_analysis_results",
                    )
                    pass
        elif "gid" in it:
            if has_risk:
                merged_items.append(it)
                items_with_risk.append(it)
            else:
                items_without_risk.append(it)

    return items_with_risk, items_without_risk
