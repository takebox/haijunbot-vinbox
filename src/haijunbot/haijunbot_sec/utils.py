# -*- coding: utf-8 -*-
"""Utility functions module"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output

from haijunbot.haijunbot_sec.workflow import direct_scan


def git_restore_if_dirty(repo_root: str) -> int:
    """
    If repo_root is a git repository: detect whether the working tree has changes;
    if so, restore it using 'git checkout -- .'
    Returns the estimated number of changed files (based on the number of lines from git status --porcelain).
    """
    try:
        import subprocess as _sub

        root = Path(repo_root)
        if not (root / ".git").exists():
            return 0
        proc = _sub.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=False,
        )
        if proc.returncode != 0:
            return 0
        lines = [
            line for line in decode_output(proc.stdout).splitlines() if line.strip()
        ]
        if lines:
            _sub.run(
                ["git", "checkout", "--", "."],
                cwd=str(root),
                capture_output=True,
                text=False,
            )
            return len(lines)
    except Exception as e:
        save_exception(e, module="haijunbot_sec.utils", function="git_restore_if_dirty")
        pass
    return 0


def get_sec_dir(base_path: str) -> Path:
    """Get the path of the .haijunbot/sec directory, supporting base_path being the project root or already the .haijunbot/sec directory"""
    base = Path(base_path)
    # Check whether base_path is already the .haijunbot/sec directory
    if base.name == "sec" and base.parent.name == ".haijunbot":
        return base
    # Otherwise, assume base_path is the project root directory
    return base / ".haijunbot" / "sec"


def initialize_analysis_context(
    entry_path: str,
    status_mgr: Any,
) -> Tuple[Path, Optional[str], Any]:
    """
    Initialize the analysis context, including status management, progress files, directories, etc.

    Returns: (sec_dir, progress_path, _progress_append)
    """
    # Get the .haijunbot/sec directory
    sec_dir = get_sec_dir(entry_path)
    progress_path = None  # progress.jsonl is no longer used

    # Progress append function (empty function, no longer records)
    def _progress_append(rec: Dict[str, Any]) -> None:
        pass  # No longer records progress logs

    return sec_dir, progress_path, _progress_append


def load_or_run_heuristic_scan(
    entry_path: str,
    langs: List[str],
    exclude_dirs: Optional[List[str]],
    sec_dir: Path,
    status_mgr: Any,
    _progress_append: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load or run the heuristic scan.

    Prefer loading from the new candidates.jsonl file; if it does not exist, fall back to the old heuristic_issues.jsonl.

    Returns: (candidates, summary)
    """
    candidates: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}

    # Prefer the new candidates.jsonl file
    from haijunbot.haijunbot_sec.file_manager import get_candidates_file
    from haijunbot.haijunbot_sec.file_manager import load_candidates

    candidates = load_candidates(sec_dir)

    if candidates:
        try:
            PrettyOutput.auto_print(
                f"✨ [haijunbot-sec] Resuming the heuristic scan from {get_candidates_file(sec_dir)}",
                timestamp=True,
            )
            _progress_append(
                {
                    "event": "pre_scan_resumed",
                    "path": str(get_candidates_file(sec_dir)),
                    "issues_found": len(candidates),
                }
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.utils", function="load_or_run_heuristic_scan"
            )
            pass
    else:
        # Fall back to the old heuristic_issues.jsonl file (backward compatibility)
        _heuristic_path = sec_dir / "heuristic_issues.jsonl"
        if _heuristic_path.exists():
            try:
                PrettyOutput.auto_print(
                    f"✨ [haijunbot-sec] Resuming the heuristic scan from {_heuristic_path} (legacy format)",
                    timestamp=True,
                )
                with _heuristic_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            candidates.append(json.loads(line))
                _progress_append(
                    {
                        "event": "pre_scan_resumed",
                        "path": str(_heuristic_path),
                        "issues_found": len(candidates),
                    }
                )
            except Exception as e:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Failed to resume the heuristic scan, running a full scan: {e}",
                    timestamp=True,
                )
                candidates = []  # Reset so that a full scan can be run

    # Pre-initialize the heuristic scan result file path (for the full scan below to write to)
    _heuristic_path = sec_dir / "heuristic_issues.jsonl"

    if not candidates:
        _progress_append(
            {"event": "pre_scan_start", "entry_path": entry_path, "languages": langs}
        )
        status_mgr.update_pre_scan(message="Starting heuristic scan...")
        pre_scan = direct_scan(entry_path, languages=langs, exclude_dirs=exclude_dirs)
        candidates = pre_scan.get("issues", [])
        summary = pre_scan.get("summary", {})
        scanned_files = summary.get("scanned_files", 0)
        status_mgr.update_pre_scan(
            current_files=scanned_files,
            total_files=scanned_files,
            issues_found=len(candidates),
            message=f"Heuristic scan completed, {len(candidates)} candidate issues found",
        )
        _progress_append(
            {
                "event": "pre_scan_done",
                "entry_path": entry_path,
                "languages": langs,
                "scanned_files": scanned_files,
                "issues_found": len(candidates),
            }
        )
        # Persist
        try:
            _heuristic_path.parent.mkdir(parents=True, exist_ok=True)
            with _heuristic_path.open("w", encoding="utf-8") as f:
                for item in candidates:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            _progress_append(
                {
                    "event": "heuristic_report_written",
                    "path": str(_heuristic_path),
                    "issues_count": len(candidates),
                }
            )
            PrettyOutput.auto_print(
                f"✅ [haijunbot-sec] Wrote {len(candidates)} heuristic scan issues to {_heuristic_path}",
                timestamp=True,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.utils", function="load_or_run_heuristic_scan"
            )
            pass
    else:
        # Resume the heuristic scan results from a checkpoint
        status_mgr.update_pre_scan(
            issues_found=len(candidates),
            message=f"Resumed from checkpoint, {len(candidates)} candidate issues found so far",
        )

    return candidates, summary


def compact_candidate(it: Dict[str, Any]) -> Dict[str, Any]:
    """Condense a candidate issue, keeping only the necessary fields"""
    result = {
        "language": it.get("language"),
        "category": it.get("category"),
        "pattern": it.get("pattern"),
        "file": it.get("file"),
        "line": it.get("line"),
        "evidence": it.get("evidence"),
        "confidence": it.get("confidence"),
        "severity": it.get("severity", "medium"),
    }
    # If the candidate already has a gid, keep it (used for checkpoint resume)
    if "gid" in it:
        try:
            gid_val = int(it.get("gid", 0))
            if gid_val >= 1:
                result["gid"] = gid_val
        except Exception as e:
            save_exception(e, module="haijunbot_sec.utils", function="compact_candidate")
            pass
    return result


def prepare_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Condense the candidate issues into a subtask list, controlling the context length, and assign globally unique IDs.

    Returns: compact_candidates (the candidate list with gids assigned)
    """
    compact_candidates = [compact_candidate(it) for it in candidates]

    # Check whether all candidates already have a gid (when resuming from heuristic_issues.jsonl)
    all_have_gid = all(
        "gid" in it and isinstance(it.get("gid"), int) and it.get("gid", 0) >= 1
        for it in compact_candidates
    )

    if not all_have_gid:
        # If some candidates have no gid, they need to be assigned
        # Prefer keeping existing gids; assign new gids to candidates without one
        existing_gids = set()
        for it in compact_candidates:
            try:
                gid_val = int(it.get("gid", 0))
                if gid_val >= 1:
                    existing_gids.add(gid_val)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.utils", function="prepare_candidates"
                )
                pass

        # Assign new gids to candidates without one
        next_gid = 1
        for it in compact_candidates:
            if (
                "gid" not in it
                or not isinstance(it.get("gid"), int)
                or it.get("gid", 0) < 1
            ):
                # Find an unused gid
                while next_gid in existing_gids:
                    next_gid += 1
                try:
                    it["gid"] = next_gid
                    existing_gids.add(next_gid)
                    next_gid += 1
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.utils", function="prepare_candidates"
                    )
                    pass

    return compact_candidates


def group_candidates_by_file(
    candidates: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group candidate issues by file"""
    from collections import defaultdict

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for it in candidates:
        groups[str(it.get("file") or "")].append(it)
    return groups


def create_report_writer(sec_dir: Path, report_file: Optional[str]) -> Any:
    """Create a report writer function"""
    from haijunbot.haijunbot_sec.file_manager import load_clusters
    from haijunbot.haijunbot_sec.file_manager import save_analysis_result

    def _append_report(
        items: List[Dict[str, Any]], source: str, task_id: str, cand: Dict[str, Any]
    ) -> None:
        """
        Append the detection results of the current subtask to the analysis.jsonl file.

        Parameters:
        - items: List of verified issues (has_risk: true)
        - source: Source ("analysis_only" or "verified")
        - task_id: Task ID (e.g. "HAIJUNBOT-SEC-Batch-1")
        - cand: Candidate information, containing batch and candidates
        """
        if not items:
            return

        try:
            # Extract information from the batch
            batch = cand.get("batch", False)
            candidates = cand.get("candidates", [])

            if not batch or not candidates:
                # If there is no batch information, fall back to the legacy format (backward compatibility)
                path = (
                    Path(report_file) if report_file else sec_dir / "agent_issues.jsonl"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    for item in items:
                        line = json.dumps(item, ensure_ascii=False)
                        f.write(line + "\n")
                try:
                    PrettyOutput.auto_print(
                        f"✅ [haijunbot-sec] Wrote {len(items)} issues to {path} (legacy format)",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.utils", function="_append_report"
                    )
                    pass
                return

            # Extract the file and gids from the batch
            batch_file = candidates[0].get("file") if candidates else ""
            batch_gids = []
            for c in candidates:
                try:
                    gid = int(c.get("gid", 0))
                    if gid >= 1:
                        batch_gids.append(gid)
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.utils", function="_append_report"
                    )
                    pass

            # Look up the corresponding cluster_id from clusters.jsonl
            clusters = load_clusters(sec_dir)
            cluster_id = None
            batch_index = None
            cluster_index = None

            # Try to extract batch_index from task_id (format: HAIJUNBOT-SEC-Batch-1)
            try:
                if "Batch-" in task_id:
                    batch_index = int(task_id.split("Batch-")[1])
            except Exception as e:
                save_exception(e, module="haijunbot_sec.utils", function="_append_report")
                pass

            # Find the matching cluster (by file and gids)
            for cluster in clusters:
                cluster_file = str(cluster.get("file", ""))
                cluster_gids = cluster.get("gids", [])

                if cluster_file == batch_file and set(cluster_gids) == set(batch_gids):
                    cluster_id = cluster.get("cluster_id", "")
                    if not cluster_id:
                        # If there is no cluster_id, generate one
                        cluster_id = f"{cluster_file}|{cluster.get('batch_index', batch_index or 0)}|{cluster.get('cluster_index', 0)}"
                    batch_index = cluster.get("batch_index", batch_index or 0)
                    cluster_index = cluster.get("cluster_index", 0)
                    break

            # If no matching cluster is found, generate a temporary cluster_id
            if not cluster_id:
                cluster_id = f"{batch_file}|{batch_index or 0}|0"
                batch_index = batch_index or 0
                cluster_index = 0

            # Separate the gids verified as issues from the gids verified as false positives
            verified_gids = []
            false_positive_gids = []
            issues = []
            false_positives = []  # Record detailed false positive information

            # Extract the verified issues from items
            for item in items:
                try:
                    gid = int(item.get("gid", 0))
                    if gid >= 1:
                        has_risk = item.get("has_risk", False)
                        if has_risk:
                            verified_gids.append(gid)
                            issues.append(item)
                        else:
                            false_positive_gids.append(gid)
                            false_positives.append(item)  # Record false positive details
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.utils", function="_append_report"
                    )
                    pass

            # Extract from candidates all gids not present in items (these may be false positives)
            for c in candidates:
                try:
                    gid = int(c.get("gid", 0))
                    if (
                        gid >= 1
                        and gid not in verified_gids
                        and gid not in false_positive_gids
                    ):
                        # If this gid is not among the verified issues, it may be a false positive
                        false_positive_gids.append(gid)
                        false_positives.append(c)  # Record the candidate issue as a false positive detail
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_sec.utils", function="_append_report"
                    )
                    pass

            # Build the analysis result record
            analysis_result = {
                "cluster_id": cluster_id,
                "file": batch_file,
                "batch_index": batch_index,
                "cluster_index": cluster_index,
                "gids": batch_gids,
                "verified_gids": verified_gids,
                "false_positive_gids": false_positive_gids,
                "issues": issues,
            }

            # Save the false positive details to a separate file
            if false_positives:
                from haijunbot.haijunbot_sec.file_manager import save_false_positives

                save_false_positives(sec_dir, false_positives)

            # Save to analysis.jsonl
            save_analysis_result(sec_dir, analysis_result)

            try:
                PrettyOutput.auto_print(
                    f"✅ [haijunbot-sec] Wrote analysis results for batch {batch_index} to analysis.jsonl (issues: {len(verified_gids)}, false positives: {len(false_positive_gids)})",
                    timestamp=True,
                )
            except Exception as e:
                save_exception(e, module="haijunbot_sec.utils", function="_append_report")
                pass
        except Exception as e:
            # A report write failure does not affect the main flow
            try:
                PrettyOutput.auto_print(f"⚠️ [haijunbot-sec] Warning: failed to save analysis results: {e}")
            except Exception as e:
                save_exception(e, module="haijunbot_sec.utils", function="_append_report")
                pass

    return _append_report


def sig_of(c: Dict[str, Any]) -> str:
    """Generate the signature of a candidate issue"""
    return f"{c.get('language', '')}|{c.get('file', '')}|{c.get('line', '')}|{c.get('pattern', '')}"


def load_processed_gids_from_issues(sec_dir: Path) -> Set[int]:
    """Read the processed gids from agent_issues.jsonl"""
    processed_gids = set()
    try:
        _agent_issues_path = sec_dir / "agent_issues.jsonl"
        if _agent_issues_path.exists():
            with _agent_issues_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        issue_obj = json.loads(line)
                        _gid = int(issue_obj.get("gid", 0))
                        if _gid >= 1:
                            processed_gids.add(_gid)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.utils",
                            function="load_processed_gids_from_issues",
                        )
                        pass
            if processed_gids:
                try:
                    PrettyOutput.auto_print(
                        f"✨ [haijunbot-sec] Checkpoint resume: read {len(processed_gids)} processed gids from agent_issues.jsonl",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.utils",
                        function="load_processed_gids_from_issues",
                    )
                    pass
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.utils", function="load_processed_gids_from_issues"
        )
        pass
    return processed_gids


def count_issues_from_file(sec_dir: Path) -> int:
    """Read the issue count from analysis.jsonl"""
    from haijunbot.haijunbot_sec.file_manager import get_verified_issue_gids

    verified_gids = get_verified_issue_gids(sec_dir)
    return len(verified_gids)


def count_issues_from_file_old(sec_dir: Path) -> int:
    """Read the current total issue count from agent_issues.jsonl (for status display)"""
    count = 0
    try:
        _agent_issues_path = sec_dir / "agent_issues.jsonl"
        if _agent_issues_path.exists():
            saved_gids = set()
            with _agent_issues_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        gid = item.get("gid", 0)
                        if gid >= 1 and gid not in saved_gids:
                            # Only count verified warnings (has_risk: true and with verification_notes)
                            if (
                                item.get("has_risk") is True
                                and "verification_notes" in item
                            ):
                                count += 1
                                saved_gids.add(gid)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.utils",
                            function="count_issues_from_file_old",
                        )
                        pass
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.utils", function="count_issues_from_file_old"
        )
        pass
    return count


def load_all_issues_from_file(sec_dir: Path) -> List[Dict[str, Any]]:
    """Read all saved warnings from agent_issues.jsonl"""
    all_issues: List[Dict[str, Any]] = []
    try:
        _agent_issues_path = sec_dir / "agent_issues.jsonl"
        if _agent_issues_path.exists():
            saved_gids_from_file = set()
            with _agent_issues_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        gid = item.get("gid", 0)
                        if gid >= 1 and gid not in saved_gids_from_file:
                            # Keep only verified warnings (has_risk: true and with verification_notes)
                            if (
                                item.get("has_risk") is True
                                and "verification_notes" in item
                            ):
                                all_issues.append(item)
                                saved_gids_from_file.add(gid)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.utils",
                            function="load_all_issues_from_file",
                        )
                        pass

            if all_issues:
                try:
                    PrettyOutput.auto_print(
                        f"✨ [haijunbot-sec] Loaded {len(all_issues)} saved warnings from agent_issues.jsonl",
                        timestamp=True,
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.utils",
                        function="load_all_issues_from_file",
                    )
                    pass
        else:
            try:
                PrettyOutput.auto_print(
                    "✨ [haijunbot-sec] agent_issues.jsonl does not exist; no issues were found in the current run",
                    timestamp=True,
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.utils", function="load_all_issues_from_file"
                )
                pass
    except Exception as e:
        # A load failure does not affect the main flow
        try:
            PrettyOutput.auto_print(
                f"⚠️ [haijunbot-sec] Warning: failed to load warnings from agent_issues.jsonl: {e}",
                timestamp=True,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.utils", function="load_all_issues_from_file"
            )
            pass
    return all_issues


def load_processed_gids_from_agent_issues(sec_dir: Path) -> Set[int]:
    """Read the processed gids from agent_issues.jsonl"""
    processed_gids = set()
    try:
        _agent_issues_path = sec_dir / "agent_issues.jsonl"
        if _agent_issues_path.exists():
            with _agent_issues_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        issue_obj = json.loads(line)
                        _gid = int(issue_obj.get("gid", 0))
                        if _gid >= 1:
                            processed_gids.add(_gid)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.utils",
                            function="load_processed_gids_from_agent_issues",
                        )
                        pass
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.utils",
            function="load_processed_gids_from_agent_issues",
        )
        pass
    return processed_gids