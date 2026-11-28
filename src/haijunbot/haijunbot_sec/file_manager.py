# -*- coding: utf-8 -*-
"""
Status file management module

The 3 configuration files after refactoring:
1. candidates.jsonl - Direct scan result file: saves the information of each original warning, including gid
2. clusters.jsonl - Cluster information file: all clusters (including invalid clusters), the gids included in each cluster
3. analysis.jsonl - Analysis result file: includes all clusters, which issues in a cluster are issues and which are false positives
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput

# ==================== File path definitions ====================


def get_candidates_file(sec_dir: Path) -> Path:
    """Get the direct scan result file path"""
    return sec_dir / "candidates.jsonl"


def get_clusters_file(sec_dir: Path) -> Path:
    """Get the cluster information file path"""
    return sec_dir / "clusters.jsonl"


def get_analysis_file(sec_dir: Path) -> Path:
    """Get the analysis result file path"""
    return sec_dir / "analysis.jsonl"


def get_false_positives_file(sec_dir: Path) -> Path:
    """Get the false positives detail file path"""
    return sec_dir / "false_positives.jsonl"


# ==================== Direct scan result file (candidates.jsonl) ====================


def save_candidates(sec_dir: Path, candidates: List[Dict[str, Any]]) -> None:
    """
    Save the direct scan results to candidates.jsonl

    Format: one candidate per line, containing all original information + gid
    {
        "gid": 1,
        "language": "c",
        "category": "buffer_overflow",
        "pattern": "strcpy",
        "file": "src/main.c",
        "line": 42,
        "evidence": "...",
        "confidence": 0.8,
        "severity": "high"
    }
    """
    path = get_candidates_file(sec_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Overwrite mode, ensuring the file content is up to date
    with path.open("w", encoding="utf-8") as f:
        for candidate in candidates:
            f.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    try:
        PrettyOutput.auto_print(
            f"✅ [haijunbot-sec] Saved {len(candidates)} candidates to {path}"
        )
    except Exception as e:
        save_exception(e, module="haijunbot_sec.file_manager", function="save_candidates")
        pass


def load_candidates(sec_dir: Path) -> List[Dict[str, Any]]:
    """
    Load the direct scan results from candidates.jsonl

    Returns: Candidate list, each candidate contains a gid
    """
    path = get_candidates_file(sec_dir)
    candidates = []

    if path.exists():
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        candidate = json.loads(line)
                        candidates.append(candidate)
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.file_manager",
                            function="load_candidates",
                        )
                        pass
        except Exception as e:
            try:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Warning: Failed to load candidates.jsonl: {e}"
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.file_manager", function="load_candidates"
                )
                pass

    return candidates


def get_all_candidate_gids(sec_dir: Path) -> Set[int]:
    """Get the set of gids of all candidates"""
    candidates = load_candidates(sec_dir)
    gids = set()
    for candidate in candidates:
        try:
            gid = int(candidate.get("gid", 0))
            if gid >= 1:
                gids.add(gid)
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.file_manager", function="get_all_candidate_gids"
            )
            pass
    return gids


# ==================== Cluster information file (clusters.jsonl) ====================


def save_cluster(sec_dir: Path, cluster: Dict[str, Any]) -> None:
    """
    Save a single cluster to clusters.jsonl (append mode)

    Format: one cluster record per line
    {
        "cluster_id": "file_path|batch_index|index",  # Unique identifier
        "file": "src/main.c",
        "batch_index": 1,
        "cluster_index": 0,  # Cluster index within the same batch
        "gids": [1, 2, 3],  # List of gids included in this cluster
        "verification": "Verify the security risk of the candidate",  # Cluster verification description
        "is_invalid": false,  # Whether it is an invalid cluster
        "invalid_reason": "",  # Invalid reason (if is_invalid is true)
        "created_at": "2024-01-01T00:00:00"  # Creation time (optional)
    }
    """
    path = get_clusters_file(sec_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Append mode
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(cluster, ensure_ascii=False) + "\n")


def load_clusters(sec_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all clusters from clusters.jsonl

    Returns: Cluster list
    """
    path = get_clusters_file(sec_dir)
    clusters = []

    if path.exists():
        try:
            # Merge using a dict: the key is cluster_id; merge the gids of all records with the same cluster_id
            seen_clusters: Dict[str, Dict[str, Any]] = {}
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cluster = json.loads(line)
                        cluster_id = cluster.get("cluster_id", "")
                        if cluster_id:
                            if cluster_id in seen_clusters:
                                # If it already exists, merge the gid lists (deduplicate)
                                existing_gids = set(
                                    seen_clusters[cluster_id].get("gids", [])
                                )
                                new_gids = set(cluster.get("gids", []))
                                merged_gids = sorted(list(existing_gids | new_gids))
                                seen_clusters[cluster_id]["gids"] = merged_gids
                                # Keep the latest of the other fields (verification, is_invalid, etc.)
                                seen_clusters[cluster_id].update(
                                    {
                                        k: v
                                        for k, v in cluster.items()
                                        if k != "gids" and k != "cluster_id"
                                    }
                                )
                            else:
                                # First time encountering this cluster_id; save it directly
                                seen_clusters[cluster_id] = cluster
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.file_manager",
                            function="load_clusters",
                        )
                        pass

            clusters = list(seen_clusters.values())
        except Exception as e:
            try:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Warning: Failed to load clusters.jsonl: {e}"
                )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.file_manager", function="load_clusters"
                )
                pass

    return clusters


def get_all_clustered_gids(sec_dir: Path) -> Set[int]:
    """Get the set of all clustered gids"""
    clusters = load_clusters(sec_dir)
    gids = set()
    for cluster in clusters:
        gids_list = cluster.get("gids", [])
        if isinstance(gids_list, list):
            for gid_val in gids_list:
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids.add(gid_int)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.file_manager",
                        function="get_all_clustered_gids",
                    )
                    pass
    return gids


def validate_clustering_completeness(sec_dir: Path) -> Tuple[bool, Set[int]]:
    """
    Validate clustering completeness, ensuring the gid of every candidate is clustered

    Returns: (is_complete, missing_gids)
    """
    all_candidate_gids = get_all_candidate_gids(sec_dir)
    all_clustered_gids = get_all_clustered_gids(sec_dir)
    missing_gids = all_candidate_gids - all_clustered_gids

    return len(missing_gids) == 0, missing_gids


# ==================== Analysis result file (analysis.jsonl) ====================


def save_analysis_result(sec_dir: Path, analysis: Dict[str, Any]) -> None:
    """
    Save a single analysis result to analysis.jsonl (append mode)

    Format: one analysis result record per line
    {
        "cluster_id": "file_path|batch_index|index",  # Corresponding cluster ID
        "file": "src/main.c",
        "batch_index": 1,
        "cluster_index": 0,
        "gids": [1, 2, 3],  # All gids included in this cluster
        "verified_gids": [1, 2],  # Gids verified as issues (has_risk: true)
        "false_positive_gids": [3],  # Gids verified as false positives (has_risk: false)
        "issues": [  # Detailed issue list (only those corresponding to verified_gids)
            {
                "gid": 1,
                "has_risk": true,
                "verification_notes": "...",
                "severity": "high",
                ...
            },
            ...
        ],
        "analyzed_at": "2024-01-01T00:00:00"  # Analysis time (optional)
    }
    """
    path = get_analysis_file(sec_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Append mode
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(analysis, ensure_ascii=False) + "\n")


def save_false_positives(sec_dir: Path, false_positives: List[Dict[str, Any]]) -> None:
    """
    Save the false positives details to false_positives.jsonl (append mode)

    Used to record the details of issues the Agent judged as false positives, to facilitate
    subsequent analysis and optimization of detection rules.

    Format: one false positive record per line
    {
        "gid": 3,
        "has_risk": false,
        "file": "src/main.c",
        "line": 100,
        "evidence": "...",
        "description": "...",
        "verification_notes": "...",  # The Agent's reasoning
        "analyzed_at": "2024-01-01T00:00:00"  # Analysis time
    }
    """
    if not false_positives:
        return

    from datetime import datetime

    path = get_false_positives_file(sec_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Append mode; each false positive on its own line
    with path.open("a", encoding="utf-8") as f:
        for fp in false_positives:
            # Add the analysis time
            record = {**fp, "analyzed_at": datetime.now().isoformat()}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_analysis_results(sec_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all analysis results from analysis.jsonl

    Returns: Analysis result list
    """
    path = get_analysis_file(sec_dir)
    results = []

    if path.exists():
        try:
            # Merge using a dict: the key is cluster_id; merge all records with the same cluster_id
            seen_results: Dict[str, Dict[str, Any]] = {}
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        cluster_id = result.get("cluster_id", "")
                        if cluster_id:
                            if cluster_id in seen_results:
                                # If it already exists, merge gid, verified_gids, false_positive_gids, and issues
                                existing = seen_results[cluster_id]

                                # Merge gids (deduplicate)
                                existing_gids = set(existing.get("gids", []))
                                new_gids = set(result.get("gids", []))
                                existing["gids"] = sorted(
                                    list(existing_gids | new_gids)
                                )

                                # Merge verified_gids (deduplicate)
                                existing_verified = set(
                                    existing.get("verified_gids", [])
                                )
                                new_verified = set(result.get("verified_gids", []))
                                existing["verified_gids"] = sorted(
                                    list(existing_verified | new_verified)
                                )

                                # Merge false_positive_gids (deduplicate)
                                existing_false = set(
                                    existing.get("false_positive_gids", [])
                                )
                                new_false = set(result.get("false_positive_gids", []))
                                existing["false_positive_gids"] = sorted(
                                    list(existing_false | new_false)
                                )

                                # Merge issues (deduplicate by gid)
                                existing_issues = {
                                    issue.get("gid"): issue
                                    for issue in existing.get("issues", [])
                                }
                                for issue in result.get("issues", []):
                                    gid = issue.get("gid")
                                    if gid:
                                        existing_issues[gid] = issue  # Keep the latest issue
                                existing["issues"] = list(existing_issues.values())

                                # Keep the latest of the other fields
                                existing.update(
                                    {
                                        k: v
                                        for k, v in result.items()
                                        if k
                                        not in [
                                            "gids",
                                            "verified_gids",
                                            "false_positive_gids",
                                            "issues",
                                            "cluster_id",
                                        ]
                                    }
                                )
                            else:
                                # First time encountering this cluster_id; save it directly
                                seen_results[cluster_id] = result
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_sec.file_manager",
                            function="load_analysis_results",
                        )
                        pass

            results = list(seen_results.values())
        except Exception as e:
            try:
                PrettyOutput.auto_print(
                    f"⚠️ [haijunbot-sec] Warning: Failed to load analysis.jsonl: {e}"
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.file_manager",
                    function="load_analysis_results",
                )
                pass

    return results


def get_all_analyzed_gids(sec_dir: Path) -> Set[int]:
    """Get the set of all analyzed gids (including issues and false positives)"""
    results = load_analysis_results(sec_dir)
    gids = set()
    for result in results:
        gids_list = result.get("gids", [])
        if isinstance(gids_list, list):
            for gid_val in gids_list:
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids.add(gid_int)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.file_manager",
                        function="get_all_analyzed_gids",
                    )
                    pass
    return gids


def get_verified_issue_gids(sec_dir: Path) -> Set[int]:
    """Get the set of all gids verified as issues"""
    results = load_analysis_results(sec_dir)
    gids = set()
    for result in results:
        verified_gids = result.get("verified_gids", [])
        if isinstance(verified_gids, list):
            for gid_val in verified_gids:
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids.add(gid_int)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.file_manager",
                        function="get_verified_issue_gids",
                    )
                    pass
    return gids


def get_false_positive_gids(sec_dir: Path) -> Set[int]:
    """Get the set of all gids verified as false positives"""
    results = load_analysis_results(sec_dir)
    gids = set()
    for result in results:
        false_positive_gids = result.get("false_positive_gids", [])
        if isinstance(false_positive_gids, list):
            for gid_val in false_positive_gids:
                try:
                    gid_int = int(gid_val)
                    if gid_int >= 1:
                        gids.add(gid_int)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.file_manager",
                        function="get_false_positive_gids",
                    )
                    pass
    return gids


# ==================== Resume state check ====================


def get_resume_status(sec_dir: Path) -> Dict[str, Any]:
    """
    Infer the resume state based on the existence and state of the 3 configuration files

    Returns: {
        "has_candidates": bool,  # Whether there are direct scan results
        "has_clusters": bool,  # Whether there are cluster results
        "has_analysis": bool,  # Whether there are analysis results
        "candidates_count": int,  # Number of candidates
        "clusters_count": int,  # Number of clusters
        "analysis_count": int,  # Number of analysis results
        "clustering_complete": bool,  # Whether clustering is complete
        "missing_gids": Set[int],  # Missing gids (if clustering is incomplete)
    }
    """
    status = {
        "has_candidates": False,
        "has_clusters": False,
        "has_analysis": False,
        "candidates_count": 0,
        "clusters_count": 0,
        "analysis_count": 0,
        "clustering_complete": False,
        "missing_gids": set(),
    }

    # Check the direct scan results
    candidates = load_candidates(sec_dir)
    if candidates:
        status["has_candidates"] = True
        status["candidates_count"] = len(candidates)

    # Check the cluster results
    clusters = load_clusters(sec_dir)
    if clusters:
        status["has_clusters"] = True
        status["clusters_count"] = len(clusters)

    # Check the analysis results
    results = load_analysis_results(sec_dir)
    if results:
        status["has_analysis"] = True
        status["analysis_count"] = len(results)

    # Validate clustering completeness
    if status["has_candidates"]:
        is_complete, missing_gids = validate_clustering_completeness(sec_dir)
        status["clustering_complete"] = is_complete
        status["missing_gids"] = missing_gids

    return status
