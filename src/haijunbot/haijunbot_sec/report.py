# -*- coding: utf-8 -*-
"""
Security Analysis Suite -- Report aggregation and scoring module

Goal:
- Aggregate and score the structured issue lists output by the heuristic checkers, generating unified JSON and Markdown reports.
- Keep the output structure consistent with workflow.direct_scan / multi-Agent Aggregator, to facilitate evaluation parsing and expert review.

Output structure (JSON example):
{
  "summary": {
    "total": 0,
    "by_language": {"c/cpp": 0, "rust": 0},
    "by_category": {
      "buffer_overflow": 0, "unsafe_api": 0, "memory_mgmt": 0, "error_handling": 0,
      "unsafe_usage": 0, "concurrency": 0, "ffi": 0
    },
    "top_risk_files": ["path1", "path2"]
  },
  "issues": [
    {
      "id": "C001",
      "language": "c/cpp",
      "category": "unsafe_api",
      "pattern": "strcpy",
      "file": "src/foo.c",
      "line": 123,
      "evidence": "strcpy(dst, src);",
      "preconditions": "N/A",
      "trigger_path": "When function foobar calls strcpy, its input src comes from an unvalidated network packet",
      "consequences": "May cause a buffer overflow",
      "suggestions": "Use strncpy_s or another safe function instead",
      "confidence": 0.85,
      "severity": "high | medium | low",
      "score": 2.55
    }
  ]
}

Functions provided:
- aggregate_issues(issues: List[Union[Issue, Dict]], scanned_root: Optional[str] = None, scanned_files: Optional[int] = None) -> Dict
- format_markdown_report(report_json: Dict) -> str
- format_csv_report(report_json: Dict) -> str
- build_json_and_markdown(issues: List[Union[Issue, Dict]], scanned_root: Optional[str] = None, scanned_files: Optional[int] = None, output_file: Optional[str] = None) -> str
  - If output_file has the .csv suffix, output CSV format; otherwise output Markdown format
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import csv
import hashlib
import io
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import cast

# Depends on the Issue structure, but this module does not import dataclass directly;
# it accepts both dict and Issue forms
try:
    from haijunbot.haijunbot_sec.types import Issue  # For type hints, to avoid circular dependencies
except Exception:
    Issue = Dict[str, Any]  # type: ignore


# ---------------------------
# Internal utilities
# ---------------------------

_CATEGORY_ORDER = [
    "unsafe_api",
    "buffer_overflow",
    "memory_mgmt",
    "error_handling",
    "unsafe_usage",
    "concurrency",
    "ffi",
]

_SEVERITY_WEIGHT = {
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
}


def _as_dict(item: Union[Issue, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize an Issue/dataclass or dict into a dict.
    """
    if isinstance(item, dict):
        return cast(Dict[str, Any], item)
    # dataclass: try attribute access
    d: Dict[str, Any] = {}
    for k in (
        "language",
        "category",
        "pattern",
        "file",
        "line",
        "evidence",
        "preconditions",
        "trigger_path",
        "consequences",
        "suggestions",
        "confidence",
        "severity",
    ):
        v = getattr(item, k, None)
        if v is not None:
            d[k] = v
    return d


def _normalize_issue(i: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize fields and fill in default values.
    """
    j = {
        "language": i.get(
            "language",
            "c/cpp"
            if str(i.get("file", "")).endswith((".c", ".cpp", ".h", ".hpp"))
            else "rust",
        ),
        "category": i.get("category", "error_handling"),
        "pattern": i.get("pattern", ""),
        "file": i.get("file", ""),
        "line": int(i.get("line", 0) or 0),
        "evidence": i.get("evidence", ""),
        "preconditions": i.get("preconditions", ""),
        "trigger_path": i.get("trigger_path", ""),
        "consequences": i.get("consequences", ""),
        "suggestions": i.get("suggestions", ""),
        "confidence": float(i.get("confidence", 0.6)),
        "severity": i.get("severity", "medium"),
    }
    # Compute a stable ID (based on a file/line/category/pattern hash)
    base = f"{j['file']}:{j['line']}:{j['category']}:{j['pattern']}"
    j["id"] = _make_issue_id(base, j["language"])
    # Score: confidence * severity_weight
    j["score"] = round(j["confidence"] * _SEVERITY_WEIGHT.get(j["severity"], 1.0), 2)
    return j


def _make_issue_id(base: str, lang: str) -> str:
    h = hashlib.sha1(base.encode("utf-8"), usedforsecurity=False).hexdigest()[:6]
    prefix = "C" if lang.startswith("c") else "R"
    return f"{prefix}{h.upper()}"


# ---------------------------
# Aggregation and scoring
# ---------------------------


def aggregate_issues(
    issues: List[Union[Issue, Dict[str, Any]]],
    scanned_root: Optional[str] = None,
    scanned_files: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregate the issue list and generate a JSON report.
    """
    # Normalize all issues
    normalized_items = [_normalize_issue(_as_dict(it)) for it in issues]

    # Deduplicate: deduplicate by gid (if present), otherwise by file:line:category:pattern
    # Keep the first occurrence of an issue (because load_analysis_results already keeps the latest)
    seen_items: Dict[str, Dict[str, Any]] = {}
    for item in normalized_items:
        # Prefer gid as the unique identifier
        gid = item.get("gid")
        if gid:
            key = f"gid:{gid}"
        else:
            # If there is no gid, use file:line:category:pattern as the unique identifier
            key = f"{item.get('file')}:{item.get('line')}:{item.get('category')}:{item.get('pattern')}"

        if key not in seen_items:
            seen_items[key] = item

    items = list(seen_items.values())

    summary: Dict[str, Any] = {
        "total": len(items),
        "by_language": {"c/cpp": 0, "rust": 0},
        "by_category": {k: 0 for k in _CATEGORY_ORDER},
        "top_risk_files": [],
    }
    if scanned_root is not None:
        summary["scanned_root"] = scanned_root
    if scanned_files is not None:
        summary["scanned_files"] = scanned_files

    file_score: Dict[str, float] = {}
    for it in items:
        lang = it["language"]
        summary["by_language"][lang] = summary["by_language"].get(lang, 0) + 1
        cat = it["category"]
        summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
        file_score[it["file"]] = file_score.get(it["file"], 0.0) + it["score"]

    # Top risk files are sorted by cumulative score, which is more stable and interpretable
    summary["top_risk_files"] = [
        f for f, _ in sorted(file_score.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    report = {
        "summary": summary,
        "issues": items,
    }
    return report


# ---------------------------
# Markdown rendering
# ---------------------------


def format_markdown_report(report_json: Dict[str, Any]) -> str:
    """
    Render the aggregated JSON report as Markdown.
    """
    s = report_json.get("summary", {})
    issues: List[Dict[str, Any]] = report_json.get("issues", [])
    lines: List[str] = []

    lines.append("# Security Issue Analysis Report (Aggregated)")
    lines.append("")
    if "scanned_root" in s:
        lines.append(f"- Scanned root directory: {s.get('scanned_root')}")
    if "scanned_files" in s:
        lines.append(f"- Number of scanned files: {s.get('scanned_files')}")
    lines.append(f"- Total number of issues detected: {s.get('total', 0)}")
    lines.append("")

    # Overview
    lines.append("## Statistics Overview")
    by_lang = s.get("by_language", {})
    lines.append(
        f"- By language: c/cpp={by_lang.get('c/cpp', 0)}, rust={by_lang.get('rust', 0)}"
    )
    lines.append("- By category:")
    by_cat = s.get("by_category", {})
    for k in _CATEGORY_ORDER:
        v = by_cat.get(k, 0)
        lines.append(f"  - {k}: {v}")
    if s.get("top_risk_files"):
        lines.append("- Top risk files:")
        for f in s["top_risk_files"]:
            lines.append(f"  - {f}")
    lines.append("")

    # Detailed issues
    lines.append("## Detailed Issues")
    for i, it in enumerate(issues, start=1):
        lines.append(
            f"### [{i}] {it.get('file')}:{it.get('line')} ({it.get('language')}, {it.get('category')})"
        )
        lines.append(f"- Pattern: {it.get('pattern')}")
        lines.append(f"- Evidence: `{it.get('evidence')}`")
        lines.append(f"- Preconditions: {it.get('preconditions')}")
        lines.append(f"- Trigger path: {it.get('trigger_path')}")
        lines.append(f"- Consequences: {it.get('consequences')}")
        lines.append(f"- Suggestions: {it.get('suggestions')}")
        lines.append(
            f"- Confidence: {it.get('confidence')}, Severity: {it.get('severity')}, Score: {it.get('score')}"
        )
        lines.append("")

    return "\n".join(lines)


def format_csv_report(report_json: Dict[str, Any]) -> str:
    """
    Render the aggregated JSON report as CSV format.
    """
    issues: List[Dict[str, Any]] = report_json.get("issues", [])

    # Define the CSV columns
    fieldnames = [
        "id",
        "language",
        "category",
        "pattern",
        "file",
        "line",
        "evidence",
        "preconditions",
        "trigger_path",
        "consequences",
        "suggestions",
        "confidence",
        "severity",
        "score",
    ]

    # Use StringIO to build the CSV string
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")

    # Write the header
    writer.writeheader()

    # Write the data rows
    for it in issues:
        row = {field: str(it.get(field, "")) for field in fieldnames}
        writer.writerow(row)

    return output.getvalue()


def build_json_and_markdown(
    issues: List[Union[Issue, Dict[str, Any]]],
    scanned_root: Optional[str] = None,
    scanned_files: Optional[int] = None,
    meta: Optional[List[Dict[str, Any]]] = None,
    output_file: Optional[str] = None,
) -> str:
    """
    Generate the report text in one pass.
    If output_file has the .csv suffix, output CSV format; otherwise output Markdown format.

    Args:
        issues: Issue list
        scanned_root: Scan root directory
        scanned_files: Number of scanned files
        meta: Optional metadata
        output_file: Output file name (optional), used to determine the output format

    Returns:
        Report text (Markdown or CSV format)
    """
    report = aggregate_issues(
        issues, scanned_root=scanned_root, scanned_files=scanned_files
    )
    if meta is not None:
        try:
            report["meta"] = (
                meta  # Inject optional audit information (only retained for JSON, for future compatibility)
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.report", function="build_json_and_markdown"
            )
            pass

    # Select the format based on the output file name suffix
    if output_file and output_file.lower().endswith(".csv"):
        return format_csv_report(report)
    else:
        return format_markdown_report(report)


__all__ = [
    "aggregate_issues",
    "format_markdown_report",
    "format_csv_report",
    "build_json_and_markdown",
]
