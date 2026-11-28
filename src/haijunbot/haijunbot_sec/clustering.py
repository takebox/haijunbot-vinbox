# -*- coding: utf-8 -*-
# type: ignore
"""Clustering-related modules"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


from haijunbot.haijunbot_sec.agents import create_cluster_agent
from haijunbot.haijunbot_sec.agents import subscribe_summary_event
from haijunbot.haijunbot_sec.file_manager import get_all_clustered_gids
from haijunbot.haijunbot_sec.file_manager import get_clusters_file
from haijunbot.haijunbot_sec.file_manager import load_clusters
from haijunbot.haijunbot_sec.file_manager import save_cluster
from haijunbot.haijunbot_sec.file_manager import validate_clustering_completeness
from haijunbot.haijunbot_sec.parsers import parse_clusters_from_text
from haijunbot.haijunbot_sec.prompts import get_cluster_summary_prompt
from haijunbot.haijunbot_sec.utils import group_candidates_by_file
from haijunbot.haijunbot_utils.output import PrettyOutput


def load_existing_clusters(
    sec_dir: Path,
) -> tuple[Dict[tuple[str, int], List[Dict[str, Any]]], set[str], set[int]]:
    """
    Load existing cluster reports to support checkpoint recovery.

    Prefer the new clusters.jsonl file; fall back to the old cluster_report.jsonl only when it does not exist.

    Returns: (_existing_clusters, _completed_cluster_batches, _reviewed_invalid_gids)
    """
    _existing_clusters: Dict[tuple[str, int], List[Dict[str, Any]]] = {}
    _completed_cluster_batches: set[str] = set()
    _reviewed_invalid_gids: set[int] = set()  # Gids of the already-reviewed invalid clusters

    try:
        # Prefer the new clusters.jsonl file
        clusters = load_clusters(sec_dir)

        if clusters:
            # Load from the new clusters.jsonl
            for cluster in clusters:
                f_name = str(cluster.get("file") or "")
                bidx = int(cluster.get("batch_index", 1) or 1)
                _existing_clusters.setdefault((f_name, bidx), []).append(cluster)

                # Read the reviewed invalid clusters from the analysis result file
                # A cluster is considered reviewed if it is invalid and all its gids are marked as false positives in the analysis results
                if cluster.get("is_invalid", False):
                    gids_list = cluster.get("gids", [])
                    if isinstance(gids_list, list):
                        # Check whether all these gids are marked as false positives in the analysis results
                        from haijunbot.haijunbot_sec.file_manager import (
                            get_false_positive_gids,
                        )

                        false_positive_gids = get_false_positive_gids(sec_dir)
                        all_false_positive = all(
                            int(gid_val) in false_positive_gids
                            for gid_val in gids_list
                            if isinstance(gid_val, (int, str))
                        )
                        if all_false_positive:
                            for gid_val in gids_list:
                                try:
                                    gid_int = int(gid_val)
                                    if gid_int >= 1:
                                        _reviewed_invalid_gids.add(gid_int)
                                except Exception as e:
                                    save_exception(
                                        e,
                                        module="haijunbot_sec.clustering",
                                        function="load_existing_clusters",
                                    )
                                    pass
        # No longer falls back to the old cluster_report.jsonl, because the user requires compatibility not to be considered
    except Exception:
        _existing_clusters = {}
        _completed_cluster_batches = set()
        _reviewed_invalid_gids = set()

    return _existing_clusters, _completed_cluster_batches, _reviewed_invalid_gids


def restore_clusters_from_checkpoint(
    _existing_clusters: Dict[tuple[str, int], List[Dict[str, Any]]],
    _file_groups: Dict[str, List[Dict[str, Any]]],
    _reviewed_invalid_gids: set[int],
) -> tuple[
    List[List[Dict[str, Any]]], List[Dict[str, Any]], List[Dict[str, Any]], set[int]
]:
    """
    Restore the clustering results from a checkpoint.

    Returns: (cluster_batches, cluster_records, invalid_clusters_for_review, clustered_gids)
    """
    # 1. Collect the gids of all candidates
    all_candidate_gids_in_clustering = set[int]()
    gid_to_candidate: Dict[int, Dict[str, Any]] = {}
    for _file, _items in _file_groups.items():
        for it in _items:
            try:
                _gid = int(it.get("gid", 0))
                if _gid >= 1:
                    all_candidate_gids_in_clustering.add(_gid)
                    gid_to_candidate[_gid] = it
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="restore_clusters_from_checkpoint",
                )
                pass

    # 2. Restore all clustering results from cluster_report.jsonl
    clustered_gids = set[
        int
    ]()  # Clustered gids (including valid and invalid ones, because invalid ones also need to enter the review phase)
    invalid_clusters_for_review: List[Dict[str, Any]] = []  # Invalid cluster list (restored from the checkpoint)
    cluster_batches: List[List[Dict[str, Any]]] = []
    cluster_records: List[Dict[str, Any]] = []
    skipped_reviewed_count = 0  # Number of already-reviewed invalid clusters (skipped)
    missing_gids_in_restore = set[int]()  # Records gids that could not be matched during recovery (for diagnostics)

    # First, collect all clustered gids from all cluster records (regardless of whether they are in the current candidate set)
    # This ensures that even if a match fails, as long as a gid is in clusters.jsonl and in the current candidate set, it is counted in clustered_gids
    all_clustered_gids_from_file = set[int]()
    for (_file_key, _batch_idx), cluster_recs in _existing_clusters.items():
        for rec in cluster_recs:
            gids_list = rec.get("gids", [])
            if isinstance(gids_list, list):
                for _gid in gids_list:
                    try:
                        _gid_int = int(_gid)
                        if _gid_int >= 1:
                            all_clustered_gids_from_file.add(_gid_int)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.clustering",
                            function="restore_clusters_from_checkpoint",
                        )
                        pass

    # For all gids recorded in clusters.jsonl, if they are also in the current candidate set, count them in clustered_gids
    # This avoids omissions caused by match failures
    for _gid_int in all_clustered_gids_from_file:
        if _gid_int in all_candidate_gids_in_clustering:
            clustered_gids.add(_gid_int)

    # Then, try to restore the specific cluster information (for restoring cluster_batches and invalid_clusters_for_review)
    for (_file_key, _batch_idx), cluster_recs in _existing_clusters.items():
        for rec in cluster_recs:
            gids_list = rec.get("gids", [])
            if not gids_list:
                continue
            is_invalid = rec.get("is_invalid", False)
            verification = str(rec.get("verification", "")).strip()
            members: List[Dict[str, Any]] = []
            for _gid in gids_list:
                try:
                    _gid_int = int(_gid)
                    if _gid_int >= 1:
                        if _gid_int in gid_to_candidate:
                            # Only restore this cluster when the gid exists in the current run
                            candidate = gid_to_candidate[_gid_int]
                            candidate["verify"] = verification
                            members.append(candidate)
                        else:
                            # The gid is not in gid_to_candidate, meaning it cannot be directly matched
                            # Possible reasons:
                            # 1. The gid is not in the current candidate set (the candidate list changed) - this is normal and should not be counted in clustered_gids
                            # 2. The gid is in the current candidate set but cannot be matched (data inconsistency) - this should theoretically not happen
                            # Because all_candidate_gids_in_clustering is collected from _file_groups, and gid_to_candidate is also built from _file_groups
                            # If a gid is in all_candidate_gids_in_clustering, it should theoretically be in gid_to_candidate
                            # But to be safe, try to look it up from _file_groups
                            if _gid_int in all_candidate_gids_in_clustering:
                                # The gid is in the current candidate set; try to look it up from _file_groups (double insurance)
                                found_candidate = None
                                for _file, _items in _file_groups.items():
                                    for it in _items:
                                        try:
                                            it_gid = int(it.get("gid", 0))
                                            if it_gid == _gid_int:
                                                found_candidate = it
                                                break
                                        except Exception as e:
                                            save_exception(
                                                e,
                                                module="haijunbot_sec.clustering",
                                                function="restore_clusters_from_checkpoint",
                                            )
                                            pass
                                    if found_candidate:
                                        break

                                if found_candidate:
                                    # Found the corresponding candidate; add it to members
                                    found_candidate["verify"] = verification
                                    members.append(found_candidate)
                                else:
                                    # This path should theoretically not be reached, because all_candidate_gids_in_clustering is collected from _file_groups
                                    # If a gid is in all_candidate_gids_in_clustering, it should be found in _file_groups
                                    # But if it really cannot be found, there is a bug; record the diagnostic information
                                    # Note: even if it is not found, the gid has already been counted in clustered_gids in the loop above
                                    missing_gids_in_restore.add(_gid_int)
                            else:
                                # The gid is not in the current candidate set, meaning the candidate list has changed
                                # These gids should not be counted in clustered_gids, because they are not in the current run
                                # This is normal and does not need to be recorded as a miss (because they are indeed not in the current run)
                                pass
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.clustering",
                        function="restore_clusters_from_checkpoint",
                    )
                    pass

            # Only restore this cluster when at least one gid is in the current candidate set
            # If no gid is in the current candidate set, it means the candidates corresponding to these gids do not exist in the current run
            # In this case, this cluster should not be restored, because these gids are not in the current run
            if members:
                if is_invalid:
                    # Check whether all gids of this invalid cluster have already been reviewed
                    cluster_gids = [m.get("gid") for m in members]
                    # Convert cluster_gids to int for comparison
                    cluster_gids_int = set()
                    for gid_val in cluster_gids:
                        try:
                            if gid_val is None:
                                continue
                            gid_int = int(gid_val)
                            if gid_int >= 1:
                                cluster_gids_int.add(gid_int)
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_sec.clustering",
                                function="restore_clusters_from_checkpoint",
                            )
                            pass
                    # Check whether all gids have already been reviewed
                    all_reviewed = cluster_gids_int and cluster_gids_int.issubset(
                        _reviewed_invalid_gids
                    )

                    if not all_reviewed:
                        # If there are still unreviewed gids, collect them into the review list
                        invalid_clusters_for_review.append(
                            {
                                "file": _file_key,
                                "batch_index": _batch_idx,
                                "gids": cluster_gids,
                                "verification": verification,
                                "invalid_reason": str(
                                    rec.get("invalid_reason", "")
                                ).strip(),
                                "members": members,  # Save the candidate information, for possibly re-entering verification after review
                                "count": len(members),
                            }
                        )
                    else:
                        # If all gids have already been reviewed, skip (do not add to the review list)
                        skipped_reviewed_count += 1
                else:
                    # Valid cluster: restore it to cluster_batches
                    cluster_batches.append(members)
                    cluster_records.append(
                        {
                            "file": _file_key,
                            "verification": verification,
                            "gids": [m.get("gid") for m in members],
                            "count": len(members),
                            "batch_index": _batch_idx,
                            "is_invalid": False,
                        }
                    )

    # Output the statistics
    if _reviewed_invalid_gids:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: found {len(_reviewed_invalid_gids)} reviewed invalid cluster gids",
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="restore_clusters_from_checkpoint",
            )
            pass
    if skipped_reviewed_count > 0:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] checkpoint recovery: skipped {skipped_reviewed_count} reviewed invalid clusters",
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="restore_clusters_from_checkpoint",
            )
            pass
    if missing_gids_in_restore:
        # Diagnostic information: record the number of gids that could not be matched during recovery
        # Note: these gids are in the current candidate set but cannot be matched, which may indicate a data inconsistency
        # This should not happen normally
        missing_count = len(missing_gids_in_restore)
        try:
            if missing_count <= 20:
                missing_list = sorted(list(missing_gids_in_restore))
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] checkpoint recovery diagnostic: found {missing_count} gids present in the current candidate set that cannot be matched (possible data inconsistency): {missing_list}",
                )
            else:
                missing_list = sorted(list(missing_gids_in_restore))
                display_list = missing_list[:10] + ["..."] + missing_list[-10:]
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] checkpoint recovery diagnostic: found {missing_count} gids present in the current candidate set that cannot be matched (possible data inconsistency): {display_list}",
                )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="restore_clusters_from_checkpoint",
            )
            pass

    return cluster_batches, cluster_records, invalid_clusters_for_review, clustered_gids


def create_cluster_snapshot_writer(
    sec_dir: Path,
    cluster_records: List[Dict[str, Any]],
    compact_candidates: List[Dict[str, Any]],
    _progress_append: Any,
) -> Any:
    """Create the cluster snapshot writing function"""

    def _write_cluster_batch_snapshot(batch_records: List[Dict[str, Any]]) -> None:
        """Write the clustering results of a single batch, supporting incremental saves"""
        try:
            # Group by (file, batch_index), and generate a unique cluster_index for the records within each group
            from collections import defaultdict

            records_by_key = defaultdict(list)
            for record in batch_records:
                file_name = str(record.get("file", ""))
                batch_index = int(record.get("batch_index", 0))
                key = (file_name, batch_index)
                records_by_key[key].append(record)

            # Generate a cluster_index for the records within each group
            for (file_name, batch_index), records in records_by_key.items():
                for local_idx, record in enumerate(records):
                    # If the record does not contain a cluster_index, use the local index
                    cluster_index = record.get("cluster_index")
                    if cluster_index is None:
                        cluster_index = local_idx
                    else:
                        cluster_index = int(cluster_index)

                    cluster_id = f"{file_name}|{batch_index}|{cluster_index}"

                    # Convert to the new format
                    cluster = {
                        "cluster_id": cluster_id,
                        "file": file_name,
                        "batch_index": batch_index,
                        "cluster_index": cluster_index,
                        "gids": record.get("gids", []),
                        "verification": str(record.get("verification", "")).strip(),
                        "is_invalid": record.get("is_invalid", False),
                        "invalid_reason": str(record.get("invalid_reason", "")).strip(),
                    }

                    # Save using the new file manager
                    save_cluster(sec_dir, cluster)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="_write_cluster_batch_snapshot",
            )
            pass

    def _write_cluster_report_snapshot() -> None:
        """Write the cluster report snapshot"""
        try:
            # Generate a cluster_id for each record and save it
            for idx, record in enumerate(cluster_records):
                file_name = str(record.get("file", ""))
                batch_index = int(record.get("batch_index", 0))
                cluster_index = idx  # Use the index as the cluster_index
                cluster_id = f"{file_name}|{batch_index}|{cluster_index}"

                # Convert to the new format
                cluster = {
                    "cluster_id": cluster_id,
                    "file": file_name,
                    "batch_index": batch_index,
                    "cluster_index": cluster_index,
                    "gids": record.get("gids", []),
                    "verification": str(record.get("verification", "")).strip(),
                    "is_invalid": record.get("is_invalid", False),
                    "invalid_reason": str(record.get("invalid_reason", "")).strip(),
                }

                # Save using the new file manager
                save_cluster(sec_dir, cluster)

            _progress_append(
                {
                    "event": "cluster_report_snapshot",
                    "path": str(get_clusters_file(sec_dir)),
                    "clusters": len(cluster_records),
                    "total_candidates": len(compact_candidates),
                }
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="_write_cluster_report_snapshot",
            )
            pass

    return _write_cluster_batch_snapshot, _write_cluster_report_snapshot


def collect_candidate_gids(file_groups: Dict[str, List[Dict[str, Any]]]) -> set[int]:
    """Collect the gids of all candidates"""
    all_gids = set[int]()
    for _file, _items in file_groups.items():
        for it in _items:
            try:
                _gid = int(it.get("gid", 0))
                if _gid >= 1:
                    all_gids.add(_gid)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.clustering", function="collect_candidate_gids"
                )
                pass
    return all_gids


def collect_clustered_gids(
    cluster_batches: List[List[Dict[str, Any]]],
    invalid_clusters_for_review: List[Dict[str, Any]],
) -> set[int]:
    """Collect all clustered gids"""
    all_clustered_gids = set[int]()
    for batch in cluster_batches:
        for item in batch:
            try:
                _gid = int(item.get("gid", 0))
                if _gid >= 1:
                    all_clustered_gids.add(_gid)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.clustering", function="collect_clustered_gids"
                )
                pass
    # Also collect the gids in the invalid clusters (they have already entered the review flow)
    for invalid_cluster in invalid_clusters_for_review:
        gids_list = invalid_cluster.get("gids", [])
        for _gid in gids_list:
            try:
                _gid_int = int(_gid)
                if _gid_int >= 1:
                    all_clustered_gids.add(_gid_int)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.clustering", function="collect_clustered_gids"
                )
                pass
    return all_clustered_gids


# Note: the supplement_missing_gids_for_clustering function has been removed
# Because gids are now saved in heuristic_issues.jsonl, the recovery logic can correctly match all gids
# Theoretically, missing gids should no longer occur, so no supplementary handling is needed


def filter_single_gid_clusters(
    cluster_batches: List[List[Dict[str, Any]]],
    sec_dir: Path,
    _progress_append: Any,
) -> List[List[Dict[str, Any]]]:
    """
    Filter out the singly clustered batches (batches containing only 1 gid) to avoid a surge in analysis workload.

    These single clusters are usually created automatically for previously missing gids and are no longer needed now.
    """
    filtered_batches: List[List[Dict[str, Any]]] = []
    removed_count = 0
    removed_gids = set[int]()

    # Read the analyzed gids (from analysis.jsonl)
    from haijunbot.haijunbot_sec.file_manager import get_all_analyzed_gids

    processed_gids = set[int](get_all_analyzed_gids(sec_dir))

    # Read all gids in clusters.jsonl
    cluster_report_gids = get_all_clustered_gids(sec_dir)

    for batch in cluster_batches:
        # Check the batch size
        if len(batch) == 1:
            # This is a single cluster; check whether it needs to be retained
            single_item = batch[0]
            try:
                gid = int(single_item.get("gid", 0))
                if gid >= 1:
                    # If the gid has already been analyzed in analysis.jsonl, it is safe to remove it (no omission)
                    if gid in processed_gids:
                        removed_count += 1
                        removed_gids.add(gid)
                        _progress_append(
                            {
                                "event": "single_cluster_removed",
                                "gid": gid,
                                "reason": "already_analyzed",
                            }
                        )
                        continue

                    # Check the verification field; if it is the default "verify candidate X security risk", it is an automatically created single cluster
                    verification = str(single_item.get("verify", "")).strip()
                    is_auto_created = verification.startswith(
                        "verify candidate "
                    ) and verification.endswith(" security risk")

                    if is_auto_created:
                        # This is an automatically created single cluster
                        # If the gid is recorded in clusters.jsonl, it has already been clustered and can be safely removed
                        # If it is neither in clusters.jsonl nor in analysis.jsonl, it needs analysis and should be retained
                        if gid in cluster_report_gids:
                            removed_count += 1
                            removed_gids.add(gid)
                            _progress_append(
                                {
                                    "event": "single_cluster_removed",
                                    "gid": gid,
                                    "reason": "auto_created_and_in_clusters",
                                }
                            )
                            continue
                        else:
                            # An automatically created single cluster, but it is neither in clusters.jsonl nor in analysis.jsonl
                            # This means it needs analysis; retain it (to avoid missing alerts)
                            # But issue a warning, because this should not happen
                            try:
                                PrettyOutput.auto_print(
                                    f"[haijunbot-sec] warning: gid={gid} is an auto-created single cluster but is not in clusters.jsonl; retained to avoid missing alerts",
                                )
                            except Exception as e:
                                save_exception(
                                    e,
                                    module="haijunbot_sec.clustering",
                                    function="filter_single_gid_clusters",
                                )
                                pass
                    else:
                        # Not an automatically created single cluster; it may be a normal single-alert file (created by handle_single_alert_file)
                        # Retain it (to avoid missing alerts)
                        pass
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="filter_single_gid_clusters",
                )
                pass

        # Retain this batch (not a single cluster, or a single cluster that needs to be retained)
        filtered_batches.append(batch)

    if removed_count > 0:
        try:
            if len(removed_gids) <= 20:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] removed {removed_count} single-cluster batches ({len(removed_gids)} gids in total) to avoid a surge in analysis workload",
                )
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] removed gids: {sorted(list(removed_gids))}",
                )
            else:
                removed_gids_list = sorted(list(removed_gids))
                display_list = (
                    removed_gids_list[:10] + ["..."] + removed_gids_list[-10:]
                )
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] removed {removed_count} single-cluster batches ({len(removed_gids)} gids in total) to avoid a surge in analysis workload",
                )
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] removed gids (sample): {display_list}",
                )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="filter_single_gid_clusters"
            )
            pass

    return filtered_batches


def handle_single_alert_file(
    file: str,
    single_item: Dict[str, Any],
    single_gid: int,
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
    _progress_append: Any,
    _write_cluster_batch_snapshot: Any,
) -> None:
    """Handle a single-alert file: skip clustering and write it directly"""
    default_verification = f"verify candidate {single_gid} security risk"
    single_item["verify"] = default_verification
    cluster_batches.append([single_item])
    cluster_records.append(
        {
            "file": file,
            "verification": default_verification,
            "gids": [single_gid],
            "count": 1,
            "batch_index": 1,
            "note": "single alert skips clustering",
        }
    )
    _progress_append(
        {
            "event": "cluster_status",
            "status": "done",
            "file": file,
            "batch_index": 1,
            "skipped": True,
            "reason": "single_alert",
        }
    )
    current_batch_records = [
        rec
        for rec in cluster_records
        if rec.get("file") == file and rec.get("batch_index") == 1
    ]
    if current_batch_records:
        _write_cluster_batch_snapshot(current_batch_records)
    PrettyOutput.auto_print(
        f"[haijunbot-sec] file {file} has only one alert (gid={single_gid}), skipping clustering and writing directly",
    )


def validate_cluster_format(
    cluster_items: List[Dict[str, Any]],
) -> tuple[bool, List[str]]:
    """Validate the format of the clustering result; returns (is valid, list of error details)"""
    if not isinstance(cluster_items, list) or not cluster_items:
        return False, ["result is not an array or the array is empty"]

    errors: List[str] = []
    for idx, it in enumerate(cluster_items):
        # Validate that each element must be a dict
        if not isinstance(it, dict):
            errors.append(f"element {idx} is not a dict")
            continue

        # Get and validate the required fields
        vals = it.get("gids", [])
        verification = it.get("verification", "")

        # Validate the verification field
        if not isinstance(verification, str):
            errors.append(f"element {idx} verification is not a string")
            continue

        # Validate the gids field
        if not isinstance(vals, list):
            errors.append(f"element {idx} gids is not an array")
            continue

        # Validate that each element of gids is a valid integer
        for gid_idx, gid_val in enumerate(vals):
            try:
                gid_int = int(gid_val)
                if gid_int < 1:
                    errors.append(
                        f"element {idx} gids[{gid_idx}] is not a valid positive integer (value: {gid_val})"
                    )
                    break
            except (ValueError, TypeError):
                errors.append(
                    f"element {idx} gids[{gid_idx}] is not a valid integer (value: {gid_val})"
                )
                break
        else:
            # Only continue when all the previous validations passed
            # Validate the is_invalid field
            is_invalid_val = it.get("is_invalid")
            if is_invalid_val is None:
                errors.append(f"element {idx} is missing the required is_invalid field")
                continue
            if not isinstance(is_invalid_val, bool):
                errors.append(f"element {idx} is_invalid is not a boolean")
                continue

            # If is_invalid is true, validate invalid_reason
            if is_invalid_val is True:
                invalid_reason = it.get("invalid_reason", "")
                if not isinstance(invalid_reason, str) or not invalid_reason.strip():
                    errors.append(
                        f"element {idx} has is_invalid true but is missing the invalid_reason field or the reason is empty (required)"
                    )

    if errors:
        return False, errors
    return True, []


def extract_classified_gids(cluster_items: List[Dict[str, Any]]) -> set[int]:
    """Extract all classified gids from the clustering result

    Note: this function assumes that format validation has already passed and all gids are valid integers.
    If a malformed gid is encountered, a warning is recorded but no exception is raised (because format validation should have caught these issues).
    """
    classified_gids = set[int]()
    for cl in cluster_items:
        raw_gids = cl.get("gids", [])
        if isinstance(raw_gids, list):
            for x in raw_gids:
                try:
                    xi = int(x)
                    if xi >= 1:
                        classified_gids.add(xi)
                except (ValueError, TypeError):
                    # This path should theoretically not be reached (format validation should have caught it), but if it is reached, record a warning
                    try:
                        PrettyOutput.auto_print(
                            f"[haijunbot-sec] warning: encountered a format error while extracting gids (value={x}, type={type(x).__name__}); this should not happen (format validation should have caught it)",
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.clustering",
                            function="extract_classified_gids",
                        )
                        pass
                    continue
    return classified_gids


def build_cluster_retry_task(
    file: str,
    missing_gids: set[int],
    error_details: List[str],
) -> str:
    """Build the clustering retry task"""
    retry_task = f"""
# Clustering task retry
File: {file}

**Important**: Please output the clustering results again.
""".strip()
    if missing_gids:
        missing_gids_list = sorted(list(missing_gids))
        missing_count = len(missing_gids)
        retry_task += (
            f"\n\n**Missing gids ({missing_count} in total, must be classified):**\n"
            + ", ".join(str(gid) for gid in missing_gids_list)
        )
    if error_details:
        retry_task += "\n\n**Format errors:**\n" + "\n".join(
            f"- {detail}" for detail in error_details
        )
    return retry_task


def build_cluster_error_guidance(
    error_details: List[str],
    missing_gids: set[int],
) -> str:
    """Build the clustering error guidance information"""
    error_guidance = ""
    if error_details:
        error_guidance = (
            "\n\n**Format error details (fix the output format according to the following errors):**\n"
            + "\n".join(f"- {detail}" for detail in error_details)
        )
    if missing_gids:
        missing_gids_list = sorted(list(missing_gids))
        missing_count = len(missing_gids)
        error_guidance += (
            f"\n\n**Completeness error: {missing_count} gids are missing; these gids must be classified:**\n"
            + ", ".join(str(gid) for gid in missing_gids_list)
        )
    return error_guidance


def run_cluster_agent_direct_model(
    cluster_agent: Any,
    cluster_task: str,
    cluster_summary_prompt: str,
    file: str,
    missing_gids: set[int],
    error_details: List[str],
    _cluster_summary: Dict[str, str],
) -> None:
    """Run the clustering Agent using a direct model call"""
    retry_task = build_cluster_retry_task(file, missing_gids, error_details)
    error_guidance = build_cluster_error_guidance(error_details, missing_gids)
    full_prompt = f"{retry_task}{error_guidance}\n\n{cluster_summary_prompt}"
    try:
        response = cluster_agent.model.chat_until_success(full_prompt)
        _cluster_summary["text"] = response
    except Exception as e:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] direct model call failed: {e}, falling back to run()",
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.clustering",
                function="run_cluster_agent_direct_model",
            )
            pass
        cluster_agent.run(cluster_task)


def validate_cluster_result(
    cluster_items: Optional[List[Dict[str, Any]]],
    parse_error: Optional[str],
    attempt: int,
) -> tuple[bool, List[str]]:
    """Validate the clustering result format"""
    if parse_error:
        error_details = [f"JSON parse failed: {parse_error}"]
        PrettyOutput.auto_print(f"[haijunbot-sec] JSON parse failed: {parse_error}")
        return False, error_details
    else:
        valid, error_details = validate_cluster_format(cluster_items or [])
        if not valid:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] invalid clustering result format ({'; '.join(error_details)}), retry attempt {attempt} (using direct model call)",
            )
        return valid, error_details


def check_cluster_completeness(
    cluster_items: List[Dict[str, Any]],
    input_gids: set[int],
    attempt: int,
) -> tuple[bool, set[int]]:
    """Check the clustering completeness; returns (is complete, missing gids)"""
    classified_gids = extract_classified_gids(cluster_items)
    missing_gids = input_gids - classified_gids
    if not missing_gids:
        PrettyOutput.auto_print(
            f"[haijunbot-sec] clustering completeness check passed, all gids classified (attempted {attempt} times)",
        )
        return True, set()
    else:
        missing_gids_list = sorted(list(missing_gids))
        missing_count = len(missing_gids)
        PrettyOutput.auto_print(
            f"[haijunbot-sec] clustering completeness check failed: missing gids: {missing_gids_list} ({missing_count}), retry attempt {attempt} (using direct model call)",
        )
        return False, missing_gids


def run_cluster_agent_with_retry(
    cluster_agent: Any,
    cluster_task: str,
    cluster_summary_prompt: str,
    input_gids: set[int],
    file: str,
    _cluster_summary: Dict[str, str],
    create_agent_func: Optional[Any] = None,
) -> tuple[Optional[List[Dict[str, Any]]], Optional[str], bool]:
    """
    Run the clustering Agent and retry forever until all gids are classified; returns (clustering result, parse error, whether the agent needs to be recreated)
    If the agent needs to be recreated, the third return value is True
    """
    _attempt = 0
    use_direct_model = False
    error_details: List[str] = []
    missing_gids: set[int] = set()
    consecutive_failures = 0  # Number of consecutive failures

    while True:
        _attempt += 1
        _cluster_summary["text"] = ""

        if use_direct_model:
            run_cluster_agent_direct_model(
                cluster_agent,
                cluster_task,
                cluster_summary_prompt,
                file,
                missing_gids,
                error_details,
                _cluster_summary,
            )
        else:
            # The first time, use run() to let the Agent run completely (it may use tools)
            cluster_agent.run(cluster_task)

        cluster_summary_text = _cluster_summary.get("text", "")
        # Debug: if parsing fails, output the first 500 characters of the summary text for debugging
        cluster_items, parse_error = parse_clusters_from_text(cluster_summary_text)

        # If parsing fails and it is the first attempt, output the debug information
        if parse_error and _attempt == 1:
            preview = cluster_summary_text[:500] if cluster_summary_text else "(empty)"
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] debug: summary text preview (first 500 characters): {preview}",
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="run_cluster_agent_with_retry",
                )
                pass

        # Validate the structure
        valid, error_details = validate_cluster_result(
            cluster_items, parse_error, _attempt
        )

        # Completeness check: verify that all input gids are classified
        missing_gids = set[int]()
        if valid and cluster_items:
            is_complete, missing_gids = check_cluster_completeness(
                cluster_items, input_gids, _attempt
            )
            if is_complete:
                return cluster_items, None, False
            else:
                use_direct_model = True
                valid = False
                consecutive_failures += 1
        else:
            consecutive_failures += 1

        # If there are 5 consecutive failures and a function to create the agent is provided, return the flag that the agent needs to be recreated
        if not valid and consecutive_failures >= 5 and create_agent_func is not None:
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] {consecutive_failures} consecutive failures; the agent needs to be recreated",
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="run_cluster_agent_with_retry",
                )
                pass
            return None, parse_error or "5 consecutive failures", True

        if not valid:
            use_direct_model = True
            cluster_items = None


def process_cluster_results(
    cluster_items: List[Dict[str, Any]],
    pending_in_file_with_ids: List[Dict[str, Any]],
    file: str,
    chunk_idx: int,
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
    invalid_clusters_for_review: List[Dict[str, Any]],
    _progress_append: Any,
) -> tuple[int, int]:
    """Process the clustering result; returns (number of valid clusters, number of invalid clusters)"""
    gid_to_item: Dict[int, Dict[str, Any]] = {}
    try:
        for it in pending_in_file_with_ids:
            try:
                _gid = int(it.get("gid", 0))
                if _gid >= 1:
                    gid_to_item[_gid] = it
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="process_cluster_results",
                )
                pass
    except Exception:
        gid_to_item = {}

    _merged_count = 0
    _invalid_count = 0
    classified_gids_final = set[int]()

    for cl in cluster_items:
        verification = str(cl.get("verification", "")).strip()
        raw_gids = cl.get("gids", [])
        is_invalid = cl["is_invalid"]
        norm_keys: List[int] = []
        if isinstance(raw_gids, list):
            for x in raw_gids:
                try:
                    xi = int(x)
                    if xi >= 1:
                        norm_keys.append(xi)
                        classified_gids_final.add(xi)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.clustering",
                        function="process_cluster_results",
                    )
                    pass

        members: List[Dict[str, Any]] = []
        for k in norm_keys:
            item = gid_to_item.get(k)
            if item is not None:
                item["verify"] = verification
                members.append(item)

        # If marked as invalid, collect it into the review list
        if is_invalid:
            _invalid_count += 1
            invalid_gids = [m.get("gid") for m in members]
            invalid_reason = str(cl.get("invalid_reason", "")).strip()
            try:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] judged invalid during the clustering phase (gids={invalid_gids}); will submit to the review Agent for verification",
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="process_cluster_results",
                )
                pass
            invalid_clusters_for_review.append(
                {
                    "file": file,
                    "batch_index": chunk_idx,
                    "gids": invalid_gids,
                    "verification": verification,
                    "invalid_reason": invalid_reason,
                    "members": members,
                    "count": len(members),
                }
            )
            _progress_append(
                {
                    "event": "cluster_invalid",
                    "file": file,
                    "batch_index": chunk_idx,
                    "gids": invalid_gids,
                    "verification": verification,
                    "count": len(members),
                }
            )
            cluster_records.append(
                {
                    "file": file,
                    "verification": verification,
                    "gids": invalid_gids,
                    "count": len(members),
                    "batch_index": chunk_idx,
                    "is_invalid": True,
                    "invalid_reason": invalid_reason,
                }
            )
        elif members:
            _merged_count += 1
            cluster_batches.append(members)
            cluster_records.append(
                {
                    "file": file,
                    "verification": verification,
                    "gids": [m.get("gid") for m in members],
                    "count": len(members),
                    "batch_index": chunk_idx,
                    "is_invalid": False,
                }
            )

    return _merged_count, _invalid_count


def supplement_missing_gids(
    missing_gids_final: set[int],
    gid_to_item: Dict[int, Dict[str, Any]],
    file: str,
    chunk_idx: int,
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
) -> int:
    """Create single clusters for the missing gids; returns the number of supplemented clusters"""
    supplemented_count = 0
    for missing_gid in sorted(missing_gids_final):
        missing_item = gid_to_item.get(missing_gid)
        if missing_item:
            default_verification = f"verify candidate {missing_gid} security risk"
            missing_item["verify"] = default_verification
            cluster_batches.append([missing_item])
            cluster_records.append(
                {
                    "file": file,
                    "verification": default_verification,
                    "gids": [missing_gid],
                    "count": 1,
                    "batch_index": chunk_idx,
                    "note": "missing gid supplemented by the completeness check",
                }
            )
            supplemented_count += 1
    return supplemented_count


def build_cluster_task(
    pending_in_file_with_ids: List[Dict[str, Any]],
    entry_path: str,
    file: str,
    langs: List[str],
) -> str:
    """Build the clustering task context"""
    return f"""
# Clustering task (analysis input)
Context:
- entry_path: {entry_path}
- file: {file}
- languages: {langs}

Candidates (JSON array, containing gid/file/line/pattern/category/evidence):
{json.dumps(pending_in_file_with_ids, ensure_ascii=False, indent=2)}
        """.strip()


def extract_input_gids(pending_in_file_with_ids: List[Dict[str, Any]]) -> set[int]:
    """Extract the gid set from the items to be clustered"""
    input_gids = set()
    for it in pending_in_file_with_ids:
        try:
            _gid = int(it.get("gid", 0))
            if _gid >= 1:
                input_gids.add(_gid)
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="extract_input_gids"
            )
            pass
    return input_gids


def build_gid_to_item_mapping(
    pending_in_file_with_ids: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """Build the mapping from gid to item"""
    gid_to_item: Dict[int, Dict[str, Any]] = {}
    try:
        for it in pending_in_file_with_ids:
            try:
                _gid = int(it.get("gid", 0))
                if _gid >= 1:
                    gid_to_item[_gid] = it
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="build_gid_to_item_mapping",
                )
                pass
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.clustering", function="build_gid_to_item_mapping"
        )
        pass
    return gid_to_item


def process_cluster_chunk(
    chunk: List[Dict[str, Any]],
    chunk_idx: int,
    file: str,
    entry_path: str,
    langs: List[str],
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
    invalid_clusters_for_review: List[Dict[str, Any]],
    _progress_append: Any,
    _write_cluster_batch_snapshot: Any,
    force_save_memory: bool = False,
) -> None:
    """Process a single clustering batch"""
    if not chunk:
        return

    pending_in_file_with_ids = list(chunk)

    # Record the start of the clustering batch
    _progress_append(
        {
            "event": "cluster_status",
            "status": "running",
            "file": file,
            "batch_index": chunk_idx,
            "total_in_batch": len(pending_in_file_with_ids),
        }
    )

    # Create the clustering Agent
    cluster_agent = create_cluster_agent(
        file, chunk_idx, force_save_memory=force_save_memory
    )

    # Build the task context
    cluster_task = build_cluster_task(pending_in_file_with_ids, entry_path, file, langs)

    # Extract the input gids
    input_gids = extract_input_gids(pending_in_file_with_ids)

    # Run the clustering Agent (supports recreating the agent, with no limit on the number of times)
    cluster_summary_prompt = get_cluster_summary_prompt()
    recreate_count = 0

    while True:
        # Subscribe to the summary event (re-subscribe after each agent recreation)
        cluster_summary = subscribe_summary_event(cluster_agent)

        cluster_items, parse_error, need_recreate = run_cluster_agent_with_retry(
            cluster_agent,
            cluster_task,
            cluster_summary_prompt,
            input_gids,
            file,
            cluster_summary,
            create_agent_func=lambda: create_cluster_agent(
                file, chunk_idx, force_save_memory=force_save_memory
            ),
        )

        # If the agent does not need to be recreated, exit the loop
        if not need_recreate:
            break

        # The agent needs to be recreated (with no limit on the number of times)
        recreate_count += 1
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] recreating the clustering Agent (attempt {recreate_count})",
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="process_cluster_chunk"
            )
            pass
        cluster_agent = create_cluster_agent(
            file, chunk_idx, force_save_memory=force_save_memory
        )

    # Process the clustering result
    _merged_count = 0
    _invalid_count = 0

    if isinstance(cluster_items, list) and cluster_items:
        gid_to_item = build_gid_to_item_mapping(pending_in_file_with_ids)

        _merged_count, _invalid_count = process_cluster_results(
            cluster_items,
            pending_in_file_with_ids,
            file,
            chunk_idx,
            cluster_batches,
            cluster_records,
            invalid_clusters_for_review,
            _progress_append,
        )

        classified_gids_final = extract_classified_gids(cluster_items)
        missing_gids_final = input_gids - classified_gids_final
        if missing_gids_final:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] warning: there are still missing gids {sorted(list(missing_gids_final))}; a single cluster will be created for each missing gid",
            )
            supplemented_count = supplement_missing_gids(
                missing_gids_final,
                gid_to_item,
                file,
                chunk_idx,
                cluster_batches,
                cluster_records,
            )
            _merged_count += supplemented_count
    else:
        # The clustering result is empty or None: create single clusters for all input gids (conservative strategy)
        if pending_in_file_with_ids:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] warning: clustering result is empty or None (file={file}, batch={chunk_idx}); creating single clusters for all gids",
            )
            gid_to_item_fallback = build_gid_to_item_mapping(pending_in_file_with_ids)

            _merged_count = supplement_missing_gids(
                input_gids,
                gid_to_item_fallback,
                file,
                chunk_idx,
                cluster_batches,
                cluster_records,
            )
            _invalid_count = 0
        else:
            _merged_count = 0
            _invalid_count = 0

    # Mark the clustering batch as complete
    _progress_append(
        {
            "event": "cluster_status",
            "status": "done",
            "file": file,
            "batch_index": chunk_idx,
            "clusters_count": _merged_count,
            "invalid_clusters_count": _invalid_count,
        }
    )
    if _invalid_count > 0:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] clustering batch completed: valid clusters={_merged_count}, invalid clusters={_invalid_count} (skipped)",
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="process_cluster_chunk"
            )
            pass

    # Write the clustering result of the current batch
    current_batch_records = [
        rec
        for rec in cluster_records
        if rec.get("file") == file and rec.get("batch_index") == chunk_idx
    ]
    if current_batch_records:
        _write_cluster_batch_snapshot(current_batch_records)


def filter_pending_items(
    items: List[Dict[str, Any]], clustered_gids: set[int]
) -> List[Dict[str, Any]]:
    """Filter out the items to be clustered"""
    pending_in_file: List[Dict[str, Any]] = []
    for c in items:
        try:
            _gid = int(c.get("gid", 0))
            if _gid >= 1 and _gid not in clustered_gids:
                pending_in_file.append(c)
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="filter_pending_items"
            )
            pass
    return pending_in_file


def process_file_clustering(
    file: str,
    items: List[Dict[str, Any]],
    clustered_gids: set[int],
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
    invalid_clusters_for_review: List[Dict[str, Any]],
    entry_path: str,
    langs: List[str],
    cluster_limit: int,
    _progress_append: Any,
    _write_cluster_batch_snapshot: Any,
    force_save_memory: bool = False,
) -> None:
    """Process the clustering task of a single file"""
    # Filter out the already-clustered gids
    pending_in_file = filter_pending_items(items, clustered_gids)
    if not pending_in_file:
        return

    # Optimization: if the file has only one alert, skip clustering and write it directly
    if len(pending_in_file) == 1:
        single_item = pending_in_file[0]
        single_gid = single_item.get("gid", 0)
        handle_single_alert_file(
            file,
            single_item,
            single_gid,
            cluster_batches,
            cluster_records,
            _progress_append,
            _write_cluster_batch_snapshot,
        )
        return

    # Split the alerts of the file into batches by cluster_limit
    _limit = (
        cluster_limit if isinstance(cluster_limit, int) and cluster_limit > 0 else 50
    )
    _chunks: List[List[Dict[str, Any]]] = [
        pending_in_file[i : i + _limit] for i in range(0, len(pending_in_file), _limit)
    ]

    # Process each batch
    for _chunk_idx, _chunk in enumerate(_chunks, start=1):
        process_cluster_chunk(
            _chunk,
            _chunk_idx,
            file,
            entry_path,
            langs,
            cluster_batches,
            cluster_records,
            invalid_clusters_for_review,
            _progress_append,
            _write_cluster_batch_snapshot,
            force_save_memory=force_save_memory,
        )


# Note: the check_and_supplement_missing_gids function has been removed
# Because gids are now saved in heuristic_issues.jsonl, the recovery logic can correctly match all gids
# Theoretically, missing gids should no longer occur; the completeness check has been moved to process_clustering_phase


def initialize_clustering_context(
    compact_candidates: List[Dict[str, Any]],
    sec_dir: Path,
    _progress_append: Any,
) -> tuple[
    Dict[str, List[Dict[str, Any]]],
    Dict[tuple[str, int], List[Dict[str, Any]]],
    tuple[Any, Any],
    List[List[Dict[str, Any]]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    set[int],
]:
    """Initialize the clustering context; returns (file groups, existing clusters, snapshot write functions, cluster batches, cluster records, invalid clusters, clustered gids)"""
    # Group the candidates by file to build the set to be clustered
    _file_groups = group_candidates_by_file(compact_candidates)

    cluster_batches: List[List[Dict[str, Any]]] = []
    cluster_records: List[Dict[str, Any]] = []
    invalid_clusters_for_review: List[Dict[str, Any]] = []

    # Read the existing cluster reports to support checkpoints
    (
        _existing_clusters,
        _completed_cluster_batches,
        _reviewed_invalid_gids,
    ) = load_existing_clusters(sec_dir)

    # Create the snapshot write functions
    (
        _write_cluster_batch_snapshot,
        _write_cluster_report_snapshot,
    ) = create_cluster_snapshot_writer(
        sec_dir, cluster_records, compact_candidates, _progress_append
    )

    # Restore the clustering results from the checkpoint
    (
        cluster_batches,
        cluster_records,
        invalid_clusters_for_review,
        clustered_gids,
    ) = restore_clusters_from_checkpoint(
        _existing_clusters, _file_groups, _reviewed_invalid_gids
    )

    return (
        _file_groups,
        _existing_clusters,
        (_write_cluster_batch_snapshot, _write_cluster_report_snapshot),
        cluster_batches,
        cluster_records,
        invalid_clusters_for_review,
        clustered_gids,
    )


def check_unclustered_gids(
    all_candidate_gids: set[int],
    clustered_gids: set[int],
) -> set[int]:
    """Check the unclustered gids"""
    unclustered_gids = all_candidate_gids - clustered_gids
    if unclustered_gids:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] found {len(unclustered_gids)} unclustered gids; clustering will be performed",
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="check_unclustered_gids"
            )
            pass
    else:
        try:
            PrettyOutput.auto_print(
                f"[haijunbot-sec] all {len(all_candidate_gids)} candidates are already clustered; skipping the clustering phase",
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="check_unclustered_gids"
            )
            pass
    return unclustered_gids


def execute_clustering_for_files(
    file_groups: Dict[str, List[Dict[str, Any]]],
    clustered_gids: set[int],
    cluster_batches: List[List[Dict[str, Any]]],
    cluster_records: List[Dict[str, Any]],
    invalid_clusters_for_review: List[Dict[str, Any]],
    entry_path: str,
    langs: List[str],
    cluster_limit: int,
    status_mgr: Any,
    _progress_append: Any,
    _write_cluster_batch_snapshot: Any,
    force_save_memory: bool = False,
) -> None:
    """Execute the file clustering"""
    total_files_to_cluster = len(file_groups)
    # Update the clustering phase status
    if total_files_to_cluster > 0:
        status_mgr.update_clustering(
            current_file=0,
            total_files=total_files_to_cluster,
            message="starting clustering analysis...",
        )
    for _file_idx, (_file, _items) in enumerate(file_groups.items(), start=1):
        PrettyOutput.auto_print(
            f"[haijunbot-sec] clustering file {_file_idx}/{total_files_to_cluster}: {_file}",
        )
        # Update the current file progress
        status_mgr.update_clustering(
            current_file=_file_idx,
            total_files=total_files_to_cluster,
            file_name=_file,
            message=f"clustering file {_file_idx}/{total_files_to_cluster}: {_file}",
        )
        # Use a sub-function to process the file clustering
        process_file_clustering(
            _file,
            _items,
            clustered_gids,
            cluster_batches,
            cluster_records,
            invalid_clusters_for_review,
            entry_path,
            langs,
            cluster_limit,
            _progress_append,
            _write_cluster_batch_snapshot,
            force_save_memory=force_save_memory,
        )


def record_clustering_completion(
    sec_dir: Path,
    cluster_records: List[Dict[str, Any]],
    compact_candidates: List[Dict[str, Any]],
    _progress_append: Any,
) -> None:
    """Record the completion of the clustering phase"""
    try:
        _cluster_path = sec_dir / "cluster_report.jsonl"
        _progress_append(
            {
                "event": "cluster_report_written",
                "path": str(_cluster_path),
                "clusters": len(cluster_records),
                "total_candidates": len(compact_candidates),
                "note": "each batch was saved incrementally; no need to rewrite the entire file",
            }
        )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.clustering", function="record_clustering_completion"
        )
        pass


def fallback_to_file_based_batches(
    file_groups: Dict[str, List[Dict[str, Any]]],
    existing_clusters: Dict[tuple[str, int], List[Dict[str, Any]]],
) -> List[List[Dict[str, Any]]]:
    """If clustering fails or is empty, fall back to processing file by file"""
    fallback_batches: List[List[Dict[str, Any]]] = []

    # Collect all unclustered gids (excluding the clustered ones from all candidate gids)
    all_gids_in_file_groups = collect_candidate_gids(file_groups)
    gid_to_item_fallback: Dict[int, Dict[str, Any]] = {}
    for _file, _items in file_groups.items():
        for c in _items:
            try:
                _gid = int(c.get("gid", 0))
                if _gid >= 1:
                    gid_to_item_fallback[_gid] = c
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.clustering",
                    function="fallback_to_file_based_batches",
                )
                pass

    # If there are still unclustered gids, create batches grouped by file
    if all_gids_in_file_groups:
        # Collect the clustered gids (from cluster_report.jsonl)
        clustered_gids_fallback = set()
        for (_file_key, _batch_idx), cluster_recs in existing_clusters.items():
            for rec in cluster_recs:
                if rec.get("is_invalid", False):
                    continue
                gids_list = rec.get("gids", [])
                for _gid in gids_list:
                    try:
                        _gid_int = int(_gid)
                        if _gid_int >= 1:
                            clustered_gids_fallback.add(_gid_int)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.clustering",
                            function="fallback_to_file_based_batches",
                        )
                        pass

        unclustered_gids_fallback = all_gids_in_file_groups - clustered_gids_fallback
        if unclustered_gids_fallback:
            # Group the unclustered gids by file
            from collections import defaultdict

            unclustered_by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for _gid in unclustered_gids_fallback:
                item = gid_to_item_fallback.get(_gid)
                if item:
                    file_key = str(item.get("file") or "")
                    unclustered_by_file[file_key].append(item)

            # Create a batch for each file
            for _file, _items in unclustered_by_file.items():
                if _items:
                    fallback_batches.append(_items)

    return fallback_batches


def process_clustering_phase(
    compact_candidates: List[Dict[str, Any]],
    entry_path: str,
    langs: List[str],
    cluster_limit: int,
    sec_dir: Path,
    status_mgr: Any,
    _progress_append: Any,
    force_save_memory: bool = False,
) -> tuple[List[List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Process the clustering phase; returns (cluster_batches, invalid_clusters_for_review)"""
    # Initialize the clustering context
    (
        _file_groups,
        _existing_clusters,
        (_write_cluster_batch_snapshot, _write_cluster_report_snapshot),
        cluster_batches,
        cluster_records,
        invalid_clusters_for_review,
        clustered_gids,
    ) = initialize_clustering_context(compact_candidates, sec_dir, _progress_append)

    # Collect the gids of all candidates (to check for unclustered gids)
    all_candidate_gids_in_clustering = collect_candidate_gids(_file_groups)

    # Check whether there are unclustered gids
    unclustered_gids = check_unclustered_gids(
        all_candidate_gids_in_clustering, clustered_gids
    )

    # If there are unclustered gids, continue the clustering
    if unclustered_gids:
        execute_clustering_for_files(
            _file_groups,
            clustered_gids,
            cluster_batches,
            cluster_records,
            invalid_clusters_for_review,
            entry_path,
            langs,
            cluster_limit,
            status_mgr,
            _progress_append,
            _write_cluster_batch_snapshot,
            force_save_memory=force_save_memory,
        )

    # Record the completion of the clustering phase
    record_clustering_completion(
        sec_dir, cluster_records, compact_candidates, _progress_append
    )

    # Review Agent: verify all clusters marked as invalid (imported from the review module)
    from haijunbot.haijunbot_sec.review import process_review_phase

    cluster_batches = process_review_phase(
        invalid_clusters_for_review,
        entry_path,
        langs,
        status_mgr,
        _progress_append,
        cluster_batches,
        sec_dir,
    )

    # If clustering fails or is empty, fall back to "processing file by file"
    if not cluster_batches:
        fallback_batches = fallback_to_file_based_batches(
            _file_groups, _existing_clusters
        )
        cluster_batches.extend(fallback_batches)

    # Completeness check: ensure that all candidate gids have been clustered
    # Use the new file manager for validation
    is_complete, missing_gids_final = validate_clustering_completeness(sec_dir)

    if missing_gids_final:
        # If there are still missing gids, the recovery logic is faulty and re-clustering is needed
        try:
            missing_count = len(missing_gids_final)
            if missing_count <= 20:
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] warning: found {missing_count} missing gids (the recovery logic may be faulty): {sorted(list(missing_gids_final))}",
                )
            else:
                missing_list = sorted(list(missing_gids_final))
                display_list = missing_list[:10] + ["..."] + missing_list[-10:]
                PrettyOutput.auto_print(
                    f"[haijunbot-sec] warning: found {missing_count} missing gids (the recovery logic may be faulty): {display_list}",
                )

        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.clustering", function="process_clustering_phase"
            )
            pass

    # Clean up the previously created single clusters (to avoid a surge in analysis workload)
    cluster_batches = filter_single_gid_clusters(
        cluster_batches,
        sec_dir,
        _progress_append,
    )

    return cluster_batches, invalid_clusters_for_review