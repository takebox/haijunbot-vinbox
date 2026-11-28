# -*- coding: utf-8 -*-
"""Verification-related modules"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import cast

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_sec.agents import create_analysis_agent
from haijunbot.haijunbot_sec.agents import subscribe_summary_event
from haijunbot.haijunbot_sec.analysis import build_analysis_task_context
from haijunbot.haijunbot_sec.analysis import expand_and_filter_analysis_results
from haijunbot.haijunbot_sec.analysis import run_analysis_agent_with_retry
from haijunbot.haijunbot_sec.parsers import try_parse_summary_report
from haijunbot.haijunbot_sec.prompts import build_verification_summary_prompt
from haijunbot.haijunbot_sec.utils import count_issues_from_file
from haijunbot.haijunbot_sec.utils import git_restore_if_dirty
from haijunbot.haijunbot_sec.utils import sig_of
from haijunbot.haijunbot_tools.registry import ToolRegistry


def build_gid_to_verification_mapping(
    verification_results: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """Build a mapping from gid to verification results"""
    gid_to_verification: Dict[int, Dict[str, Any]] = {}
    for vr in verification_results:
        if not isinstance(vr, dict):
            continue  # type: ignore[unreachable]
        gids_to_process: List[int] = []
        if "gids" in vr and isinstance(vr.get("gids"), list):
            for gid_val in vr.get("gids", []):
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids_to_process.append(gid_int)
                except Exception as e:
                    try:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] warning: malformed gids array element in verification result: {gid_val}, error: {e}"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="build_gid_to_verification_mapping",
                        )
                        pass
        elif "gid" in vr:
            try:
                gid_val = vr.get("gid", 0)
                gid_int = int(gid_val)
                if gid_int >= 1:
                    gids_to_process.append(gid_int)
                else:
                    try:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] warning: invalid gid value in verification result: {gid_val} (must be >= 1)"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="build_gid_to_verification_mapping",
                        )
                        pass
            except Exception as e:
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] warning: malformed gid in verification result: {vr.get('gid')}, error: {e}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="build_gid_to_verification_mapping",
                    )
                    pass
        else:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] warning: verification result item lacks gid or gids field: {vr}"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="build_gid_to_verification_mapping",
                )
                pass

        is_valid = vr.get("is_valid")
        verification_notes = str(vr.get("verification_notes", "")).strip()
        for gid in gids_to_process:
            gid_to_verification[gid] = {
                "is_valid": is_valid,
                "verification_notes": verification_notes,
            }
    return gid_to_verification


def merge_verified_items(
    items_with_risk: List[Dict[str, Any]],
    batch: List[Dict[str, Any]],
    gid_to_verification: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge the alerts that passed verification"""
    gid_to_candidate: Dict[int, Dict[str, Any]] = {}
    for c in batch:
        try:
            c_gid = int(c.get("gid", 0))
            if c_gid >= 1:
                gid_to_candidate[c_gid] = c
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.verification", function="merge_verified_items"
            )
            pass

    verified_items: List[Dict[str, Any]] = []
    for item in items_with_risk:
        item_gid = int(item.get("gid", 0))
        verification = gid_to_verification.get(item_gid)
        if verification and verification.get("is_valid") is True:
            # Merge the original candidate information (file, line, pattern, category, language, evidence, confidence, severity, etc.)
            candidate = gid_to_candidate.get(item_gid, {})
            merged_item = {
                **candidate,  # Original candidate information
                **item,  # Analysis result
                "verification_notes": str(
                    verification.get("verification_notes", "")
                ).strip(),
            }
            verified_items.append(merged_item)
        elif verification and verification.get("is_valid") is False:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] verification Agent judged gid={item_gid} as a false positive: {verification.get('verification_notes', '')}"
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.verification", function="merge_verified_items"
                )
                pass
        else:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] warning: gid={item_gid} not found in the verification results, treated as not verified"
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.verification", function="merge_verified_items"
                )
                pass
    return verified_items


def merge_verified_items_without_verification(
    items_with_risk: List[Dict[str, Any]],
    batch: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge the issues confirmed by the analysis Agent (without second-pass verification)"""
    gid_to_candidate: Dict[int, Dict[str, Any]] = {}
    for c in batch:
        try:
            c_gid = int(c.get("gid", 0))
            if c_gid >= 1:
                gid_to_candidate[c_gid] = c
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.verification",
                function="merge_verified_items_without_verification",
            )
            pass

    verified_items: List[Dict[str, Any]] = []
    for item in items_with_risk:
        item_gid = int(item.get("gid", 0))
        # Handle the case of a gids array
        if "gids" in item:
            gids = item.get("gids", [])
            for gid in gids:
                candidate = gid_to_candidate.get(gid, {})
                merged_item = {
                    **candidate,  # Original candidate information
                    **item,  # Analysis result
                    "gid": gid,  # Use a single gid
                    "verification_notes": "no second-pass verification performed (--no-verification)",
                }
                # Remove the gids field because it has been expanded into individual gids
                merged_item.pop("gids", None)
                verified_items.append(merged_item)
        else:
            # The case of a single gid
            candidate = gid_to_candidate.get(item_gid, {})
            merged_item = {
                **candidate,  # Original candidate information
                **item,  # Analysis result
                "verification_notes": "no second-pass verification performed (--no-verification)",
            }
            verified_items.append(merged_item)
    return verified_items


def is_valid_verification_item(item: Dict[str, Any]) -> bool:
    """Validate the format of a verification result item"""
    if not isinstance(item, dict) or "is_valid" not in item:
        return False
    has_gid = "gid" in item
    has_gids = "gids" in item
    if not has_gid and not has_gids:
        return False
    if has_gid and has_gids:
        return False  # gid and gids cannot appear at the same time
    if has_gid:
        try:
            return int(item["gid"]) >= 1
        except Exception:
            return False
    elif has_gids:
        if not isinstance(item["gids"], list) or len(item["gids"]) == 0:
            return False
        try:
            return all(int(gid_val) >= 1 for gid_val in item["gids"])
        except Exception:
            return False
    return False


def run_verification_agent_with_retry(
    verification_agent: Any,
    verification_task: str,
    verification_summary_prompt: str,
    entry_path: str,
    verification_summary_container: Dict[str, str],
    bidx: int,
) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Run the verification Agent and retry forever until the format is correct; returns (verification results, parse error)"""
    use_direct_model_verify = False
    prev_parse_error_verify: Optional[str] = None
    verify_attempt = 0

    while True:
        verify_attempt += 1
        verification_summary_container["text"] = ""

        if use_direct_model_verify:
            verification_summary_prompt_text = build_verification_summary_prompt()
            error_guidance = ""
            if prev_parse_error_verify:
                error_guidance = f"\n\n**Format error details (fix the output format according to the following error):**\n- JSON parse failed: {prev_parse_error_verify}\n\nEnsure the JSON format of the output is correct, including proper quotes, commas, braces, etc. Output only one <REPORT> block, and the block directly contains the JSON array (no extra tags needed). jsonnet syntax is supported (such as trailing commas, comments, etc.)."

            full_verify_prompt = f"{verification_task}{error_guidance}\n\n{verification_summary_prompt_text}"
            try:
                verify_response = verification_agent.model.chat_until_success(
                    full_verify_prompt
                )
                verification_summary_container["text"] = verify_response
            except Exception as e:
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] direct model call failed in the verification phase: {e}, falling back to run()"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="run_verification_agent_with_retry",
                    )
                    pass
                verification_agent.run(verification_task)
        else:
            verification_agent.run(verification_task)

        # Workspace protection
        try:
            _changed_verify = git_restore_if_dirty(entry_path)
            if _changed_verify:
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] verification Agent workspace restored ({_changed_verify} files)"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="run_verification_agent_with_retry",
                    )
                    pass
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.verification",
                function="run_verification_agent_with_retry",
            )
            pass

        # Parse the verification result
        verification_summary_text = verification_summary_container.get("text", "")
        parse_error_verify = None
        if verification_summary_text:
            verification_parsed, parse_error_verify = try_parse_summary_report(
                verification_summary_text
            )
            if parse_error_verify:
                prev_parse_error_verify = parse_error_verify
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] verification result JSON parse failed: {parse_error_verify}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="run_verification_agent_with_retry",
                    )
                    pass
            else:
                prev_parse_error_verify = None
                if isinstance(verification_parsed, list):
                    if verification_parsed and all(
                        is_valid_verification_item(cast(Dict[str, Any], item))
                        for item in verification_parsed
                    ):
                        return cast(List[Dict[str, Any]], verification_parsed), None

        # Format validation failed; subsequent retries use the direct model call
        use_direct_model_verify = True
        if parse_error_verify:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] verification result JSON parse failed -> retry attempt {verify_attempt} (batch={bidx}, using direct model call, parse error will be fed back)"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="run_verification_agent_with_retry",
                )
                pass
        else:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] invalid verification result format -> retry attempt {verify_attempt} (batch={bidx}, using direct model call)"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="run_verification_agent_with_retry",
                )
                pass


def process_verification_batch(
    batch: List[Dict[str, Any]],
    bidx: int,
    total_batches: int,
    entry_path: str,
    langs: List[str],
    status_mgr: Any,
    _progress_append: Any,
    _append_report: Any,
    meta_records: List[Dict[str, Any]],
    gid_counts: Dict[int, int],
    sec_dir: Any,
    enable_verification: bool = True,
    force_save_memory: bool = False,
) -> None:
    """
    Process a single verification batch.

    Args:
    - batch: the candidate list of the current batch
    - bidx: batch index
    - total_batches: total number of batches
    - other arguments are used for state management and result collection
    """
    task_id = f"HAIJUNBOT-SEC-Batch-{bidx}"
    batch_file = batch[0].get("file") if batch else None

    # Progress: batch start
    _progress_append(
        {
            "event": "batch_status",
            "status": "running",
            "batch_id": task_id,
            "batch_index": bidx,
            "total_batches": total_batches,
            "batch_size": len(batch),
            "file": batch_file,
        }
    )
    # Update the verification phase progress
    status_mgr.update_verification(
        current_batch=bidx,
        total_batches=total_batches,
        batch_id=task_id,
        file_name=batch_file,
        message=f"verifying batch {bidx}/{total_batches}",
    )

    # Display progress (extract all gids in the batch for subsequent printing)
    batch_gids_all = []
    try:
        for item in batch:
            try:
                gid_val = item.get("gid", 0)
                gid_int = int(gid_val) if gid_val else 0
                if gid_int >= 1:
                    batch_gids_all.append(gid_int)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="process_verification_batch",
                )
                pass
        batch_gids_all_sorted = sorted(batch_gids_all)
    except Exception:
        batch_gids_all_sorted = []

    # Display progress
    try:
        if batch_gids_all_sorted:
            gids_str = str(batch_gids_all_sorted)
            PrettyOutput.auto_print(
                f"[haijunbot-sec] analysis batch {bidx}/{total_batches}: size={len(batch)} file='{batch_file}' gids={gids_str}"
            )
        else:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] analysis batch {bidx}/{total_batches}: size={len(batch)} file='{batch_file}' (no valid gid)"
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.verification", function="process_verification_batch"
        )
        pass

    # Create the analysis Agent
    agent = create_analysis_agent(task_id, force_save_memory=force_save_memory)

    # Build the task context
    per_task = build_analysis_task_context(batch, entry_path, langs)

    # Subscribe to the summary event
    summary_container = subscribe_summary_event(agent)

    # Run the analysis Agent with retry
    summary_items, workspace_restore_info = run_analysis_agent_with_retry(
        agent, per_task, summary_container, entry_path, task_id, bidx, meta_records
    )

    # Process the analysis results
    parse_fail = summary_items is None
    verified_items: List[Dict[str, Any]] = []

    # Handle the empty-array case: the analysis Agent returning [] means all candidates were judged as no risk
    if summary_items is not None and len(summary_items) == 0:
        # An empty array means all candidates were judged as no risk; they need to be saved to analysis.jsonl
        try:
            batch_gids = sorted(
                [
                    int(item.get("gid", 0))
                    for item in batch
                    if int(item.get("gid", 0)) >= 1
                ]
            )
            PrettyOutput.auto_print(
                f"[haijunbot-sec] batch {bidx}/{total_batches} analysis Agent returned an empty array, judging all candidates as no risk: risk_gids=[], no_risk_gids={batch_gids}"
            )

            # Build the no-risk items (mark all candidates in the batch as no risk)
            no_risk_items = []
            for item in batch:
                try:
                    gid = int(item.get("gid", 0))
                    if gid >= 1:
                        no_risk_item = {
                            **item,
                            "has_risk": False,
                            "verification_notes": "analysis Agent returned an empty array, judged as no risk",
                        }
                        no_risk_items.append(no_risk_item)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="process_verification_batch",
                    )
                    pass

            # Save to analysis.jsonl
            if no_risk_items:
                merged_no_risk_items = merge_verified_items_without_verification(
                    no_risk_items, batch
                )
                if merged_no_risk_items:
                    _append_report(
                        merged_no_risk_items,
                        "analysis_only",
                        task_id,
                        {"batch": True, "candidates": batch},
                    )
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] batch {bidx}/{total_batches} all no-risk candidates saved to analysis.jsonl: gids={batch_gids}"
                    )
        except Exception as e:
            try:
                PrettyOutput.auto_print(f"[haijunbot-sec] warning: failed to process the empty-array result: {e}")
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="process_verification_batch",
                )
                pass

    elif summary_items:
        # Expand and filter the analysis results
        items_with_risk, items_without_risk = expand_and_filter_analysis_results(
            summary_items
        )

        # Record the analysis conclusions (display the gids with and without risk separately)
        risk_gids = (
            sorted(
                [
                    int(item.get("gid", 0))
                    for item in items_with_risk
                    if int(item.get("gid", 0)) >= 1
                ]
            )
            if items_with_risk
            else []
        )
        no_risk_gids = (
            sorted(
                [
                    int(item.get("gid", 0))
                    for item in items_without_risk
                    if int(item.get("gid", 0)) >= 1
                ]
            )
            if items_without_risk
            else []
        )

        if items_with_risk or items_without_risk:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] batch {bidx}/{total_batches} analysis Agent judgment result: risk_gids={risk_gids}, no_risk_gids={no_risk_gids}"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="process_verification_batch",
                )
                pass

        # If all gids were judged as no risk, they also need to be saved to analysis.jsonl
        if not items_with_risk and items_without_risk:
            try:
                # Save all no-risk gids to analysis.jsonl, ensuring they are marked as analyzed
                no_risk_items = merge_verified_items_without_verification(
                    items_without_risk, batch
                )
                if no_risk_items:
                    _append_report(
                        no_risk_items,
                        "analysis_only",
                        task_id,
                        {"batch": True, "candidates": batch},
                    )
                    try:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] batch {bidx}/{total_batches} all candidates are no risk, saved to analysis.jsonl"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="process_verification_batch",
                        )
                        pass
            except Exception as e:
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] warning: failed to save the no-risk gids: {e}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="process_verification_batch",
                    )
                    pass

        # Run the verification Agent (only when the analysis Agent found issues with risk, and second-pass verification is enabled)
        if items_with_risk:
            if not enable_verification:
                # If second-pass verification is disabled, directly treat the issues confirmed by the analysis Agent as verified issues
                verified_items = merge_verified_items_without_verification(
                    items_with_risk, batch
                )
                if verified_items:
                    verified_gids = sorted(
                        [
                            int(item.get("gid", 0))
                            for item in verified_items
                            if int(item.get("gid", 0)) >= 1
                        ]
                    )
                    for item in verified_items:
                        gid = int(item.get("gid", 0))
                        if gid >= 1:
                            gid_counts[gid] = gid_counts.get(gid, 0) + 1
                    # Compute the no-risk gids (gids in the batch not in verified_gids)
                    no_risk_gids_in_batch = sorted(
                        [
                            gid
                            for gid in batch_gids_all_sorted
                            if gid not in verified_gids
                        ]
                    )
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] batch {bidx}/{total_batches} skipping verification, writing directly: count={len(verified_items)} risk_gids={verified_gids}, no_risk_gids={no_risk_gids_in_batch}"
                    )
                    _append_report(
                        verified_items,
                        "analysis_only",
                        task_id,
                        {"batch": True, "candidates": batch},
                    )
                    current_count = count_issues_from_file(sec_dir)
                    status_mgr.update_verification(
                        current_batch=bidx,
                        total_batches=total_batches,
                        issues_found=current_count,
                        message=f"processed {bidx}/{total_batches} batches, found {current_count} issues (unverified)",
                    )
            else:
                # Second-pass verification is enabled; run the verification Agent
                # Create the verification Agent to verify the analysis Agent's conclusions
                verification_system_prompt = f"""
# Verification Agent constraints
- Your core task is to verify whether the security conclusions given by the analysis Agent are correct.
- You need to carefully check whether the preconditions, trigger paths, consequences, and suggestions given by the analysis Agent are reasonable and accurate.
- Tools first: use read_code to read the source code near the target file (about 50 lines before and after the line number); use execute_script to assist with retrieval when necessary.
- When necessary, trace upward to the callers to view the complete call path, to confirm whether the analysis Agent's conclusion holds.
- It is forbidden to modify any file or execute write operations; only read-only analysis and reading are allowed.
- Execute only one operation at a time; wait for the tool result before proceeding to the next step.
- **Memory usage**:
  - During verification, fully use the memory tool (action=retrieve) to retrieve existing memories, especially the memories related to the current verification function saved by the analysis Agent.
  - These memories may include the analysis key points of the function, pointer null-check status, input validation status, call path analysis results, etc., which can help you verify the analysis conclusion more accurately.
  - If you find that the analysis Agent's conclusion is inconsistent with the information in the memories, you need to verify it carefully.
- After completing the verification, the main output only prints the end marker {ot("!!!COMPLETE!!!")}; do not output anything else. The task summary will be given in a subsequent interaction.
""".strip()

                verification_task_id = f"HAIJUNBOT-SEC-Verify-Batch-{bidx}"
                verification_agent_kwargs: Dict[str, Any] = dict(
                    system_prompt=verification_system_prompt,
                    name=verification_task_id,
                    auto_complete=True,
                    need_summary=True,
                    summary_prompt=build_verification_summary_prompt(),
                    non_interactive=True,
                    in_multi_agent=False,
                    use_methodology=False,
                    use_analysis=False,
                    output_handler=[ToolRegistry()],
                    use_tools=["read_code", "execute_script", "memory"],
                    quick_mode=True,
                )
                verification_agent = Agent(**verification_agent_kwargs)

                # Build the verification task context
                import json as _json3

                verification_task = f"""
# Verification conclusion task
Context parameters:
- entry_path: {entry_path}
- languages: {langs}

Conclusions given by the analysis Agent (to be verified; only items with has_risk: true):
{_json3.dumps(items_with_risk, ensure_ascii=False, indent=2)}

Please verify whether the above analysis conclusions are correct, including:
1. Are the preconditions reasonable?
2. Does the trigger_path hold?
3. Is the consequences assessment accurate?
4. Are the suggestions appropriate?

For each gid, please determine whether the analysis conclusion is correct (is_valid: true/false) and provide a verification note.
""".strip()

                # Subscribe to the verification Agent's summary
                verification_summary_container = subscribe_summary_event(
                    verification_agent
                )

                (
                    verification_results,
                    verification_parse_error,
                ) = run_verification_agent_with_retry(
                    verification_agent,
                    verification_task,
                    build_verification_summary_prompt(),
                    entry_path,
                    verification_summary_container,
                    bidx,
                )

                # Debug log: display the verification result
                if verification_results is None:
                    try:
                        PrettyOutput.auto_print(
                            "[haijunbot-sec] warning: verification Agent returned None, possibly a parse failure"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="process_verification_batch",
                        )
                        pass
                elif not isinstance(verification_results, list):
                    try:  # type: ignore[unreachable]
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] warning: verification Agent returned an unexpected type, expected list, actual: {type(verification_results)}"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="process_verification_batch",
                        )
                        pass
                elif len(verification_results) == 0:
                    try:
                        PrettyOutput.auto_print(
                            "[haijunbot-sec] warning: verification Agent returned an empty list"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="process_verification_batch",
                        )
                        pass
                else:
                    try:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] verification Agent returned {len(verification_results)} result items"
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.verification",
                            function="process_verification_batch",
                        )
                        pass

                # Filter according to the verification results: keep only the alerts that passed verification (is_valid: true)
                if verification_results:
                    gid_to_verification = build_gid_to_verification_mapping(
                        verification_results
                    )

                    # Debug log: display the extracted verification results (including the gid list)
                    if gid_to_verification:
                        try:
                            # Display the verification results by category: passed and failed gids
                            valid_gids = sorted(
                                [
                                    gid
                                    for gid, v in gid_to_verification.items()
                                    if v.get("is_valid") is True
                                ]
                            )
                            invalid_gids = sorted(
                                [
                                    gid
                                    for gid, v in gid_to_verification.items()
                                    if v.get("is_valid") is False
                                ]
                            )
                            all_verified_gids = sorted(gid_to_verification.keys())

                            # Compute the unverified gids (gids in the batch not in the verification results, treated as no risk)
                            unverified_gids = sorted(
                                [
                                    gid
                                    for gid in batch_gids_all_sorted
                                    if gid not in all_verified_gids
                                ]
                            )
                            # Merge all no-risk gids (failed verification + unverified)
                            all_no_risk_gids = sorted(
                                list(set(invalid_gids + unverified_gids))
                            )
                            PrettyOutput.auto_print(
                                f"[haijunbot-sec] verification Agent returned {len(gid_to_verification)} verification results: risk_gids={valid_gids}, no_risk_gids={all_no_risk_gids}"
                            )
                            if valid_gids:
                                PrettyOutput.auto_print(
                                    f"[haijunbot-sec] verification Agent judged {len(valid_gids)} candidates as verified (is_valid: true): risk_gids={valid_gids}"
                                )
                            if invalid_gids:
                                PrettyOutput.auto_print(
                                    f"[haijunbot-sec] verification Agent judged {len(invalid_gids)} candidates as not verified (is_valid: false): no_risk_gids={invalid_gids}"
                                )
                            if unverified_gids:
                                PrettyOutput.auto_print(
                                    f"[haijunbot-sec] unverified candidates (not in the verification results, treated as no risk): no_risk_gids={unverified_gids}"
                                )
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_sec.verification",
                                function="process_verification_batch",
                            )
                            pass
                    else:
                        try:
                            PrettyOutput.auto_print(
                                f"[haijunbot-sec] warning: verification result parsed successfully, but no valid gids were extracted. Verification result: {verification_results}"
                            )
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_sec.verification",
                                function="process_verification_batch",
                            )
                            pass

                    # Merge the alerts that passed verification
                    verified_items = merge_verified_items(
                        items_with_risk, batch, gid_to_verification
                    )
                else:
                    PrettyOutput.auto_print(
                        "[haijunbot-sec] warning: verification Agent result parsing failed; no alerts are retained (conservative strategy)"
                    )

                # Only the alerts that passed verification are written to the file
                if verified_items:
                    verified_gids = sorted(
                        [
                            int(item.get("gid", 0))
                            for item in verified_items
                            if int(item.get("gid", 0)) >= 1
                        ]
                    )
                    for item in verified_items:
                        gid = int(item.get("gid", 0))
                        if gid >= 1:
                            gid_counts[gid] = gid_counts.get(gid, 0) + 1
                    # Compute the no-risk gids (gids in the batch not in verified_gids)
                    no_risk_gids_in_batch = sorted(
                        [
                            gid
                            for gid in batch_gids_all_sorted
                            if gid not in verified_gids
                        ]
                    )
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] batch {bidx}/{total_batches} verification passed: count={len(verified_items)}/{len(items_with_risk)} -> written to file risk_gids={verified_gids}, no_risk_gids={no_risk_gids_in_batch}"
                    )
                    _append_report(
                        verified_items,
                        "verified",
                        task_id,
                        {"batch": True, "candidates": batch},
                    )
                    # Read the current total count from the file (for the status display)
                    current_count = count_issues_from_file(sec_dir)
                    status_mgr.update_verification(
                        current_batch=bidx,
                        total_batches=total_batches,
                        issues_found=current_count,
                        message=f"verified {bidx}/{total_batches} batches, found {current_count} issues (verified)",
                    )
                else:
                    # When there are no valid alerts after verification, the gid list should also be printed (all are treated as no risk)
                    try:
                        risk_gids = sorted(
                            [
                                int(item.get("gid", 0))
                                for item in items_with_risk
                                if int(item.get("gid", 0)) >= 1
                            ]
                        )
                        # All failed verification, so all gids are no risk PrettyOutput.auto_print(f"[haijunbot-sec] batch {bidx}/{total_batches} no valid alerts after verification: analysis Agent found {len(items_with_risk)} issues with risk, all failed verification risk_gids=[], no_risk_gids={batch_gids_all_sorted}")
                    except Exception:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] batch {bidx}/{total_batches} no valid alerts after verification: analysis Agent found {len(items_with_risk)} issues with risk, all failed verification risk_gids=[], no_risk_gids={batch_gids_all_sorted}"
                        )
                    current_count = count_issues_from_file(sec_dir)
                    status_mgr.update_verification(
                        current_batch=bidx,
                        total_batches=total_batches,
                        issues_found=current_count,
                        message=f"verified {bidx}/{total_batches} batches, no valid alerts after verification",
                    )
        elif parse_fail:
            # When parsing fails, the gid list should also be printed (risk cannot be determined, but all gids are displayed)
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] batch {bidx}/{total_batches} parse failed (no <REPORT> in the summary or invalid fields): risk_gids=?, no_risk_gids=? (cannot be determined, gids={batch_gids_all_sorted})"
                )
            except Exception:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] batch {bidx}/{total_batches} parse failed (no <REPORT> in the summary or invalid fields)"
                )
        else:
            # When no issues are found, the gid list should also be printed (all are treated as no risk)
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] batch {bidx}/{total_batches} no issues found: risk_gids=[], no_risk_gids={batch_gids_all_sorted}"
                )
            except Exception:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] batch {bidx}/{total_batches} no issues found"
                )
            current_count = count_issues_from_file(sec_dir)
            status_mgr.update_verification(
                current_batch=bidx,
                total_batches=total_batches,
                issues_found=current_count,
                message=f"verified {bidx}/{total_batches} batches",
            )

    # Write a done record for all candidates in this batch
    for c in batch:
        sig = sig_of(c)
        try:
            c_gid = int(c.get("gid", 0))
        except Exception:
            c_gid = 0
        cnt = gid_counts.get(c_gid, 0)
        _progress_append(
            {
                "event": "task_status",
                "status": "done",
                "task_id": task_id,
                "candidate_signature": sig,
                "candidate": c,
                "issues_count": int(cnt),
                "parse_fail": parse_fail,
                "workspace_restore": workspace_restore_info,
                "batch_index": bidx,
            }
        )

    # Batch end record
    _progress_append(
        {
            "event": "batch_status",
            "status": "done",
            "batch_id": task_id,
            "batch_index": bidx,
            "total_batches": total_batches,
            "issues_count": len(verified_items),
            "parse_fail": parse_fail,
        }
    )


def process_verification_phase(
    cluster_batches: List[List[Dict[str, Any]]],
    entry_path: str,
    langs: List[str],
    sec_dir: Any,
    status_mgr: Any,
    _progress_append: Any,
    _append_report: Any,
    enable_verification: bool = True,
    force_save_memory: bool = False,
) -> List[Dict[str, Any]]:
    """Process the verification phase; return all saved alerts"""
    from haijunbot.haijunbot_sec.file_manager import get_all_analyzed_gids
    from haijunbot.haijunbot_sec.file_manager import load_analysis_results

    batches: List[List[Dict[str, Any]]] = cluster_batches
    total_batches = len(batches)

    # Read the analyzed results from analysis.jsonl
    analysis_results = load_analysis_results(sec_dir)
    analyzed_gids = get_all_analyzed_gids(sec_dir)

    # Build the set of completed batches (matched by cluster_id)
    completed_cluster_ids = set()
    for result in analysis_results:
        cluster_id = result.get("cluster_id", "")
        if cluster_id:
            completed_cluster_ids.add(cluster_id)

    if completed_cluster_ids:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: read {len(completed_cluster_ids)} completed clusters from analysis.jsonl"
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.verification",
                function="process_verification_phase",
            )
            pass

    if analyzed_gids:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: read {len(analyzed_gids)} analyzed gids from analysis.jsonl"
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.verification",
                function="process_verification_phase",
            )
            pass

    meta_records: List[Dict[str, Any]] = []
    gid_counts: Dict[int, int] = {}

    # Load clusters.jsonl to match batches and clusters
    from haijunbot.haijunbot_sec.file_manager import load_clusters

    clusters = load_clusters(sec_dir)

    # Compute the number of batches that actually need to be processed (excluding completed batches)
    pending_batches = []
    skipped_count = 0

    # Debug: display the analyzed gid information
    if analyzed_gids:
        try:
            analyzed_gids_sorted = sorted(list(analyzed_gids))
            sample_gids = (
                analyzed_gids_sorted[:10]
                if len(analyzed_gids_sorted) > 10
                else analyzed_gids_sorted
            )
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: analyzed gid samples: {sample_gids}{'...' if len(analyzed_gids_sorted) > 10 else ''} ({len(analyzed_gids)} in total)"
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.verification",
                function="process_verification_phase",
            )
            pass

    for bidx, batch in enumerate(batches, start=1):
        batch_file = batch[0].get("file") if batch else None

        # Check whether the batch is completed
        is_batch_completed = False
        completion_reason = ""

        # Extract the gids from the batch (ensuring the types are integers)
        batch_gids = set()
        for item in batch:
            try:
                _gid_val = item.get("gid", 0)
                _gid = int(_gid_val) if _gid_val else 0
                if _gid >= 1:
                    batch_gids.add(_gid)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.verification",
                    function="process_verification_phase",
                )
                pass

        if not batch_gids:
            # The batch has no valid gids; skip it
            skipped_count += 1
            continue

        # Method 1: check completion via cluster_id
        # Find the matching cluster (exact match: same file and exactly the same gid set)
        for cluster in clusters:
            cluster_file = str(cluster.get("file", ""))
            cluster_gids_list = cluster.get("gids", [])
            # Convert to a set of integers for comparison
            cluster_gids = set()
            for gid_val in cluster_gids_list:
                try:
                    cluster_gids.add(int(gid_val))
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.verification",
                        function="process_verification_phase",
                    )
                    pass

            # File path matching: compare using a normalized path (strip trailing slashes, etc.)
            def normalize_path(p: str) -> str:
                if not p:
                    return ""
                # Uniformly use forward slashes and strip trailing slashes
                return p.replace("\\", "/").rstrip("/")

            batch_file_normalized = normalize_path(batch_file or "")
            cluster_file_normalized = normalize_path(cluster_file)

            # Matching condition: identical file path (after normalization) and exactly the same gid set
            if (
                cluster_file_normalized == batch_file_normalized
                and cluster_gids == batch_gids
            ):
                cluster_id = cluster.get("cluster_id", "")
                if cluster_id and cluster_id in completed_cluster_ids:
                    is_batch_completed = True
                    completion_reason = f"matched by cluster_id: {cluster_id}"
                    break

        # Method 2: if all gids have been analyzed, the batch is considered completed
        if not is_batch_completed and batch_gids and analyzed_gids:
            # batch_gids is already a set of integers, and analyzed_gids should also be a set of integers
            # Use issubset directly to check
            missing_gids = batch_gids - analyzed_gids
            if not missing_gids:  # All gids have been analyzed
                is_batch_completed = True
                completion_reason = f"all gids analyzed (batch gids: {sorted(list(batch_gids))[:5]}{'...' if len(batch_gids) > 5 else ''})"
            elif bidx <= 3:  # Debug: display the matching status of the first 3 batches
                try:
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] batch {bidx} has some gids not analyzed: missing={sorted(list(missing_gids))[:5]}{'...' if len(missing_gids) > 5 else ''}, analyzed={sorted(list(batch_gids & analyzed_gids))[:5]}{'...' if len(batch_gids & analyzed_gids) > 5 else ''}"
                    )
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.verification", function="normalize_path"
                    )
                    pass

        if is_batch_completed:
            skipped_count += 1
            # Debug log: display the information of skipped batches
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] skipping batch {bidx}/{total_batches} (file={batch_file}, gids={sorted(list(batch_gids))[:5]}{'...' if len(batch_gids) > 5 else ''}): {completion_reason}"
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.verification", function="normalize_path"
                )
                pass
        else:
            # Debug log: display the information of pending batches
            if bidx <= 3:  # Only display the first 3 pending batches
                try:
                    missing_gids = (
                        batch_gids - analyzed_gids if analyzed_gids else batch_gids
                    )
                    PrettyOutput.auto_print(
                        f"[haijunbot-sec] pending batch {bidx}/{total_batches} (file={batch_file}, gids={sorted(list(batch_gids))[:5]}{'...' if len(batch_gids) > 5 else ''}, not_analyzed={sorted(list(missing_gids))[:5]}{'...' if len(missing_gids) > 5 else ''})"
                    )
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.verification", function="normalize_path"
                    )
                    pass
            pending_batches.append((bidx, batch))

    # The number of batches that actually need to be processed
    actual_total_batches = len(pending_batches)
    processed_count = 0

    # Display the skipped batch information
    if skipped_count > 0:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: skipped {skipped_count} completed batches, {actual_total_batches} batches remain pending"
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.verification", function="normalize_path"
            )
            pass

    # Update the verification phase status (using the actual total number of batches to process)
    if actual_total_batches > 0:
        status_mgr.update_verification(
            current_batch=0,
            total_batches=actual_total_batches,
            message=f"starting security verification... ({actual_total_batches} batches pending)",
        )

    # Process the pending batches
    for bidx, batch in pending_batches:
        processed_count += 1
        batch_file = batch[0].get("file") if batch else None

        # Process the verification batch (using the actual processed batch number)
        process_verification_batch(
            batch,
            processed_count,  # Use the actual processed batch number
            actual_total_batches,  # Use the actual total number of batches to process
            entry_path,
            langs,
            status_mgr,
            _progress_append,
            _append_report,
            meta_records,
            gid_counts,
            sec_dir,
            enable_verification=enable_verification,
            force_save_memory=force_save_memory,
        )

    # Read all verified issues from analysis.jsonl
    from haijunbot.haijunbot_sec.file_manager import get_verified_issue_gids
    from haijunbot.haijunbot_sec.file_manager import load_candidates

    get_verified_issue_gids(sec_dir)
    load_candidates(sec_dir)

    # Reload analysis.jsonl to get the latest written verification results
    analysis_results = load_analysis_results(sec_dir)

    # Build the issue list (from the issues field of analysis.jsonl)
    all_issues = []
    for result in analysis_results:
        issues = result.get("issues", [])
        if isinstance(issues, list):
            all_issues.extend(issues)

    return all_issues