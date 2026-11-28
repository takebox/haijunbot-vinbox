# -*- coding: utf-8 -*-
"""Review-related module"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from typing import Any, Dict, List, Optional, cast

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_sec.agents import create_review_agent
from haijunbot.haijunbot_sec.agents import subscribe_summary_event
from haijunbot.haijunbot_sec.parsers import try_parse_summary_report
from haijunbot.haijunbot_sec.prompts import build_verification_summary_prompt
from haijunbot.haijunbot_sec.prompts import get_review_summary_prompt
from haijunbot.haijunbot_sec.prompts import get_review_system_prompt
from haijunbot.haijunbot_sec.utils import git_restore_if_dirty


def build_review_task(
    review_batch: List[Dict[str, Any]], entry_path: str, langs: List[str]
) -> str:
    """Build the review task context"""
    import json as _json_review

    return f"""
# Review invalid cluster task
Context parameters:
- entry_path: {entry_path}
- languages: {langs}

Invalid clusters to review (JSON array):
{_json_review.dumps(review_batch, ensure_ascii=False, indent=2)}

Please carefully review whether the invalid_reason of each invalid cluster is sufficient and whether it truly considered all possible paths, callers, and edge cases.
For each gid, judge whether the invalid reasoning is sufficient (is_reason_sufficient: true/false) and give a review explanation.
        """.strip()


def is_valid_review_item(item: Dict[str, Any]) -> bool:
    """Validate the format of a review result item"""
    if not isinstance(item, dict) or "is_reason_sufficient" not in item:
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


def build_gid_to_review_mapping(
    review_results: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """Build the mapping from gid to review result (supports both gid and gids formats)"""
    gid_to_review: Dict[int, Dict[str, Any]] = {}
    for rr in review_results:
        # Support both gid and gids formats
        gids_to_process: List[int] = []
        if "gids" in rr and isinstance(rr.get("gids"), list):
            # Merged format: gids array
            for gid_val in rr.get("gids", []):
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids_to_process.append(gid_int)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.review",
                        function="build_gid_to_review_mapping",
                    )
                    pass
        elif "gid" in rr:
            # Single format: gid
            try:
                gid_int = int(rr.get("gid", 0))
                if gid_int >= 1:
                    gids_to_process.append(gid_int)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.review",
                    function="build_gid_to_review_mapping",
                )
                pass

        # Create a review result mapping for each gid
        is_reason_sufficient = rr.get("is_reason_sufficient")
        review_notes = str(rr.get("review_notes", "")).strip()
        for gid in gids_to_process:
            gid_to_review[gid] = {
                "is_reason_sufficient": is_reason_sufficient,
                "review_notes": review_notes,
            }
    return gid_to_review


def process_review_batch(
    review_batch: List[Dict[str, Any]],
    review_results: Optional[List[Dict[str, Any]]],
    reviewed_clusters: List[Dict[str, Any]],
    reinstated_candidates: List[Dict[str, Any]],
    sec_dir: Optional[Any] = None,
) -> None:
    """Process the results of a single review batch"""
    if review_results:
        # Build the mapping from gid to review result
        gid_to_review = build_gid_to_review_mapping(review_results)

        # Process each invalid cluster
        for invalid_cluster in review_batch:
            cluster_gids = invalid_cluster.get("gids", [])
            cluster_members = invalid_cluster.get("members", [])

            # Check the review results of all gids in this cluster
            all_sufficient = True
            any_reviewed = False
            insufficient_review_result = None
            for gid in cluster_gids:
                review_result = gid_to_review.get(gid)
                if review_result:
                    any_reviewed = True
                    if review_result.get("is_reason_sufficient") is not True:
                        all_sufficient = False
                        if not insufficient_review_result:
                            insufficient_review_result = review_result
                        break

            if any_reviewed and not all_sufficient:
                # Reasoning insufficient; bring back into the verification flow
                PrettyOutput.auto_print(
                    f"🔵 [haijunbot-sec] Review result: invalid cluster (gids={cluster_gids}) reasoning insufficient, bringing back into the verification flow"
                )
                for member in cluster_members:
                    reinstated_candidates.append(member)
                reviewed_clusters.append(
                    {
                        **invalid_cluster,
                        "review_result": "reinstated",
                        "review_notes": insufficient_review_result.get(
                            "review_notes", ""
                        )
                        if insufficient_review_result
                        else "",
                    }
                )
            else:
                # Reasoning sufficient; confirm as invalid
                review_notes = ""
                if cluster_gids and gid_to_review.get(cluster_gids[0]):
                    review_notes = gid_to_review[cluster_gids[0]].get(
                        "review_notes", ""
                    )
                PrettyOutput.auto_print(
                    f"✅ [haijunbot-sec] Review result: invalid cluster (gids={cluster_gids}) reasoning sufficient, confirmed as invalid"
                )
                reviewed_clusters.append(
                    {
                        **invalid_cluster,
                        "review_result": "confirmed_invalid",
                        "review_notes": review_notes,
                    }
                )

                # Save the confirmed-invalid gids to the false_positive_gids in analysis.jsonl, so that reviewed invalid clusters can be correctly identified during checkpoint resume
                if sec_dir:
                    try:
                        from datetime import datetime
                        from pathlib import Path

                        from haijunbot.haijunbot_sec.file_manager import save_analysis_result

                        # Build the cluster_id
                        file_name = invalid_cluster.get("file", "")
                        batch_index = invalid_cluster.get("batch_index", 1)
                        cluster_id = f"{file_name}|{batch_index}|review"

                        # Convert gids to an integer list
                        false_positive_gids = []
                        for gid_val in cluster_gids:
                            try:
                                gid_int = int(gid_val)
                                if gid_int >= 1:
                                    false_positive_gids.append(gid_int)
                            except Exception as e:
                                save_exception(
                                    e,
                                    module="haijunbot_sec.review",
                                    function="process_review_batch",
                                )
                                pass

                        # Save the analysis result
                        if false_positive_gids:
                            analysis_result = {
                                "cluster_id": cluster_id,
                                "file": file_name,
                                "batch_index": batch_index,
                                "gids": false_positive_gids,
                                "verified_gids": [],
                                "false_positive_gids": false_positive_gids,
                                "issues": [],
                                "analyzed_at": datetime.now().isoformat(),
                            }
                            save_analysis_result(Path(sec_dir), analysis_result)
                    except Exception as e:
                        # A save failure does not affect the main flow; only log a warning
                        try:
                            PrettyOutput.auto_print(
                                f"⚠️ [haijunbot-sec] Warning: failed to save the review result to analysis.jsonl: {str(e)}"
                            )
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_sec.review",
                                function="process_review_batch",
                            )
                            pass
    else:
        # Review result parsing failed; conservative strategy: bring back into the verification flow
        PrettyOutput.auto_print(
            "⚠️ [haijunbot-sec] Warning: failed to parse the review result; conservative strategy: bring all candidates in the batch back into the verification flow"
        )
        for invalid_cluster in review_batch:
            cluster_members = invalid_cluster.get("members", [])
            for member in cluster_members:
                reinstated_candidates.append(member)
            reviewed_clusters.append(
                {
                    **invalid_cluster,
                    "review_result": "reinstated",
                    "review_notes": "Review result parsing failed; conservative strategy brought it back into verification",
                }
            )


def process_review_batch_items(
    review_batch: List[Dict[str, Any]],
    review_results: Optional[List[Dict[str, Any]]],
    reviewed_clusters: List[Dict[str, Any]],
    reinstated_candidates: List[Dict[str, Any]],
    sec_dir: Optional[Any] = None,
) -> None:
    """Process the results of a single review batch"""
    process_review_batch(
        review_batch,
        review_results,
        reviewed_clusters,
        reinstated_candidates,
        sec_dir,
    )


def reinstated_candidates_to_cluster_batches(
    reinstated_candidates: List[Dict[str, Any]],
    cluster_batches: List[List[Dict[str, Any]]],
    _progress_append: Any,
) -> None:
    """Add the reinstated candidates to cluster_batches"""
    from collections import defaultdict as _dd2

    if not reinstated_candidates:
        return

    PrettyOutput.auto_print(
        f"🔄 [haijunbot-sec] Review completed: {len(reinstated_candidates)} candidates brought back into the verification flow"
    )
    # Group the reinstated candidates by file
    reinstated_by_file: Dict[str, List[Dict[str, Any]]] = _dd2(list)
    for cand in reinstated_candidates:
        file_key = str(cand.get("file") or "")
        reinstated_by_file[file_key].append(cand)

    # Create a batch for the reinstated candidates of each file
    for file_key, cands in reinstated_by_file.items():
        if cands:
            cluster_batches.append(cands)
            _progress_append(
                {
                    "event": "review_reinstated",
                    "file": file_key,
                    "gids": [c.get("gid") for c in cands],
                    "count": len(cands),
                }
            )


def run_review_agent_with_retry(
    review_agent: Any,
    review_task: str,
    review_summary_prompt: str,
    entry_path: str,
    review_summary_container: Dict[str, str],
) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Run the review Agent and retry forever until the format is correct; returns (review results, parse error)"""
    use_direct_model_review = False
    prev_parse_error_review: Optional[str] = None
    review_attempt = 0

    while True:
        review_attempt += 1
        review_summary_container["text"] = ""

        if use_direct_model_review:
            # After format validation fails, call the model interface directly
            review_summary_prompt_text = build_verification_summary_prompt()
            error_guidance = ""
            if prev_parse_error_review:
                error_guidance = f"\n\n**Format error details (please fix the output format based on the following errors):**\n- JSON parsing failed: {prev_parse_error_review}\n\nPlease ensure the output JSON format is correct, including correct quotes, commas, braces, etc. Output only one <REPORT> block, and the block directly contains the JSON array (no extra tags needed). Jsonnet syntax is supported (such as trailing commas, comments, etc.)."

            full_review_prompt = (
                f"{review_task}{error_guidance}\n\n{review_summary_prompt_text}"
            )
            try:
                review_response = review_agent.model.chat_until_success(
                    full_review_prompt
                )
                review_summary_container["text"] = review_response
            except Exception as e:
                try:
                    PrettyOutput.auto_print(
                        f"✨ [haijunbot-sec] Direct model call failed during review: {e}, falling back to run()",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.review",
                        function="run_review_agent_with_retry",
                    )
                    pass
                review_agent.run(review_task)
        else:
            review_agent.run(review_task)

        # Workspace protection
        try:
            _changed_review = git_restore_if_dirty(entry_path)
            if _changed_review:
                try:
                    PrettyOutput.auto_print(
                        f"✨ [haijunbot-sec] Review Agent workspace restored ({_changed_review} files)",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.review",
                        function="run_review_agent_with_retry",
                    )
                    pass
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.review", function="run_review_agent_with_retry"
            )
            pass

        # Parse the review result
        review_summary_text = review_summary_container.get("text", "")
        parse_error_review = None
        if review_summary_text:
            review_parsed, parse_error_review = try_parse_summary_report(
                review_summary_text
            )
            if parse_error_review:
                prev_parse_error_review = parse_error_review
                try:
                    PrettyOutput.auto_print(
                        f"✨ [haijunbot-sec] Failed to parse the review result JSON: {parse_error_review}",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.review",
                        function="run_review_agent_with_retry",
                    )
                    pass
            else:
                prev_parse_error_review = None
                if isinstance(review_parsed, list):
                    # Validate the review result format
                    if review_parsed and all(
                        is_valid_review_item(cast(Dict[str, Any], item))
                        for item in review_parsed
                    ):
                        return cast(List[Dict[str, Any]], review_parsed), None

        # Format validation failed; subsequent retries use a direct model call
        use_direct_model_review = True
        if parse_error_review:
            try:
                PrettyOutput.auto_print(
                    f"✨ [haijunbot-sec] Failed to parse the review result JSON -> retry #{review_attempt} (using a direct model call, will feed back the parse error)",
                    timestamp=True,
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.review",
                    function="run_review_agent_with_retry",
                )
                pass
        else:
            try:
                PrettyOutput.auto_print(
                    f"✨ [haijunbot-sec] Invalid review result format -> retry #{review_attempt} (using a direct model call)",
                    timestamp=True,
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.review",
                    function="run_review_agent_with_retry",
                )
                pass


def process_review_phase(
    invalid_clusters_for_review: List[Dict[str, Any]],
    entry_path: str,
    langs: List[str],
    status_mgr: Any,
    _progress_append: Any,
    cluster_batches: List[List[Dict[str, Any]]],
    sec_dir: Optional[Any] = None,
) -> List[List[Dict[str, Any]]]:
    """
    Process the review phase: verify all clusters marked as invalid.

    Returns: The updated cluster_batches (including the candidates brought back into verification)
    """
    if not invalid_clusters_for_review:
        PrettyOutput.auto_print("🔵 [haijunbot-sec] No invalid clusters to review")
        return cluster_batches

    PrettyOutput.auto_print(
        f"✨ \n[haijunbot-sec] Starting to review {len(invalid_clusters_for_review)} invalid clusters...",
        timestamp=True,
    )
    status_mgr.update_review(
        current_review=0,
        total_reviews=len(invalid_clusters_for_review),
        message="Starting to review invalid clusters...",
    )

    # Review in batches (at most 10 invalid clusters per batch, to avoid overly long contexts)
    review_batch_size = 10
    reviewed_clusters: List[Dict[str, Any]] = []
    reinstated_candidates: List[Dict[str, Any]] = []  # Candidates brought back into verification

    get_review_system_prompt()
    review_summary_prompt = get_review_summary_prompt()

    for review_idx in range(0, len(invalid_clusters_for_review), review_batch_size):
        review_batch = invalid_clusters_for_review[
            review_idx : review_idx + review_batch_size
        ]
        current_review_num = review_idx // review_batch_size + 1
        total_review_batches = (
            len(invalid_clusters_for_review) + review_batch_size - 1
        ) // review_batch_size

        PrettyOutput.auto_print(
            f"✨ [haijunbot-sec] Review batch {current_review_num}/{total_review_batches}: {len(review_batch)} invalid clusters",
            timestamp=True,
        )
        status_mgr.update_review(
            current_review=current_review_num,
            total_reviews=total_review_batches,
            message=f"Reviewing batch {current_review_num}/{total_review_batches}",
        )

        # Build the review task
        review_task = build_review_task(review_batch, entry_path, langs)

        # Create the review Agent
        review_agent = create_review_agent(current_review_num)

        # Subscribe to the review Agent's summary
        review_summary_container = subscribe_summary_event(review_agent)

        # Run the review Agent (retry forever until the format is correct)
        review_results, parse_error = run_review_agent_with_retry(
            review_agent,
            review_task,
            review_summary_prompt,
            entry_path,
            review_summary_container,
        )

        # Process the review results
        process_review_batch_items(
            review_batch,
            review_results,
            reviewed_clusters,
            reinstated_candidates,
            sec_dir,
        )

        # Record the gids of every reviewed invalid cluster (including both confirmed-invalid and reinstated ones)
        for invalid_cluster in review_batch:
            cluster_gids = invalid_cluster.get("gids", [])
            if cluster_gids:
                _progress_append(
                    {
                        "event": "review_invalid_cluster",
                        "gids": cluster_gids,
                        "file": invalid_cluster.get("file"),
                        "batch_index": invalid_cluster.get("batch_index"),
                    }
                )

    # Add the reinstated candidates to cluster_batches
    reinstated_candidates_to_cluster_batches(
        reinstated_candidates,
        cluster_batches,
        _progress_append,
    )

    if not reinstated_candidates:
        PrettyOutput.auto_print(
            "✨ [haijunbot-sec] Review completed: all invalid clusters have sufficient reasoning and are confirmed invalid", timestamp=True
        )

    # Record the review results (summary)
    _progress_append(
        {
            "event": "review_completed",
            "total_reviewed": len(invalid_clusters_for_review),
            "reinstated": len(reinstated_candidates),
            "confirmed_invalid": len(invalid_clusters_for_review)
            - len(reinstated_candidates),
        }
    )

    # Record the gids of all reviewed invalid clusters (to skip reviewed clusters during checkpoint resume)
    all_reviewed_gids = set()
    for invalid_cluster in invalid_clusters_for_review:
        cluster_gids = invalid_cluster.get("gids", [])
        for gid_val in cluster_gids:
            try:
                gid_int = int(gid_val)
                if gid_int >= 1:
                    all_reviewed_gids.add(gid_int)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.review", function="process_review_phase"
                )
                pass

    if all_reviewed_gids:
        _progress_append(
            {
                "event": "review_all_gids",
                "gids": sorted(list(all_reviewed_gids)),
                "total": len(all_reviewed_gids),
            }
        )
    status_mgr.update_review(
        current_review=len(invalid_clusters_for_review),
        total_reviews=len(invalid_clusters_for_review),
        message=f"Review completed: {len(reinstated_candidates)} candidates brought back into verification",
    )

    return cluster_batches