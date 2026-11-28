# -*- coding: utf-8 -*-
"""Prompt building module for library replacer."""

from typing import Any
from typing import Dict
from typing import List
from typing import Set

from haijunbot.haijunbot_c2rust.constants import MAX_CHILD_SAMPLES
from haijunbot.haijunbot_c2rust.constants import MAX_DOT_EDGES
from haijunbot.haijunbot_c2rust.constants import MAX_SUBTREE_EDGES
from haijunbot.haijunbot_c2rust.constants import MAX_SUBTREE_NODES_META
from haijunbot.haijunbot_c2rust.constants import SUBTREE_SOURCE_SNIPPET_MAX_LINES
from haijunbot.haijunbot_c2rust.library_replacer_utils import read_source_snippet


def build_subtree_prompt(
    fid: int,
    desc: Set[int],
    by_id: Dict[int, Dict[str, Any]],
    adj_func: Dict[int, List[int]],
    disabled_display: str,
    additional_notes: str = "",
) -> str:
    """Build the subtree evaluation hint prompt"""
    root_rec = by_id.get(fid, {})
    root_name = root_rec.get("qualified_name") or root_rec.get("name") or f"sym_{fid}"
    root_sig = root_rec.get("signature") or ""
    root_lang = root_rec.get("language") or ""
    root_src = read_source_snippet(root_rec)

    # Subtree summary (limit the length to avoid excessive size)
    nodes_meta: List[str] = []
    for nid in sorted(desc):
        r = by_id.get(nid, {})
        nm = r.get("qualified_name") or r.get("name") or f"sym_{nid}"
        sg = r.get("signature") or ""
        if sg and sg != nm:
            nodes_meta.append(f"- {nm} | {sg}")
        else:
            nodes_meta.append(f"- {nm}")
    if len(nodes_meta) > MAX_SUBTREE_NODES_META:
        nodes_meta = nodes_meta[:MAX_SUBTREE_NODES_META] + [
            f"...({len(desc) - MAX_SUBTREE_NODES_META} more)"
        ]

    # Select representative leaf/internal node source code (at most MAX_SOURCE_SAMPLES)
    samples: List[str] = []
    sample_ids: List[int] = [fid]
    for ch in adj_func.get(fid, [])[:MAX_CHILD_SAMPLES]:
        sample_ids.append(ch)
    for sid in sample_ids:
        rec = by_id.get(sid, {})
        nm = rec.get("qualified_name") or rec.get("name") or f"sym_{sid}"
        sg = rec.get("signature") or ""
        src = read_source_snippet(rec, max_lines=SUBTREE_SOURCE_SNIPPET_MAX_LINES)
        samples.append(f"--- BEGIN {nm} ---\n{sg}\n{src}\n--- END {nm} ---")

    # Build the dependency graph (directed call edges within the subtree)
    def _label(nid: int) -> str:
        r = by_id.get(nid, {})
        return r.get("qualified_name") or r.get("name") or f"sym_{nid}"

    edges_list: List[str] = []
    for u in sorted(desc):
        for v in adj_func.get(u, []):
            if v in desc:
                edges_list.append(f"{_label(u)} -> {_label(v)}")
    edges_text: str
    if len(edges_list) > MAX_SUBTREE_EDGES:
        edges_text = "\n".join(
            edges_list[:MAX_SUBTREE_EDGES]
            + [f"...({len(edges_list) - MAX_SUBTREE_EDGES} more edges)"]
        )
    else:
        edges_text = "\n".join(edges_list)

    # Provide DOT when appropriate (when the edge count is small), so the model can view the graph intuitively
    dot_text = ""
    if len(edges_list) <= MAX_DOT_EDGES:
        dot_lines: List[str] = ["digraph subtree {", "  rankdir=LR;"]
        for u in sorted(desc):
            for v in adj_func.get(u, []):
                if v in desc:
                    dot_lines.append(f'  "{_label(u)}" -> "{_label(v)}";')
        dot_lines.append("}")
        dot_text = "\n".join(dot_lines)

    disabled_hint = (
        f"Important constraint: the following libraries are forbidden (if these libraries are the only viable option, judge it as non-replaceable): {disabled_display}\n"
        if disabled_display
        else ""
    )

    return (
        "Please evaluate whether the following C/C++ function subtree can be wholly replaced by one or more mature Rust libraries (with equivalent or stronger semantics)."
        "Multiple APIs within a library may work together, and multiple libraries may be used in combination; if it must depend on an unfamiliar/obscure library or a non-Rust library, judge it as non-replaceable."
        "If the called function cannot directly use the capabilities provided by the crate and must be wrapped/adapted, treat it as non-replaceable.\n"
        f"{disabled_hint}"
        "Output format: output only a single <SUMMARY> block, containing just a JSON object (no extra tags needed), with fields: replaceable(bool), libraries(list[str]), confidence(float 0..1),"
        "Optional fields: library(str, preferred primary library), api(str) or apis(list), notes(str: briefly describe how the libraries cooperate to implement it).\n\n"
        f"Root function (root of the evaluated subtree): {root_name}\n"
        f"Signature: {root_sig}\n"
        f"Language: {root_lang}\n"
        "Root function source snippet (possibly truncated):\n"
        f"{root_src}\n\n"
        f"Subtree size: {len(desc)} functions\n"
        "Subtree function list (name|signature):\n" + "\n".join(nodes_meta) + "\n\n"
        "Dependency graph (call edges, caller -> callee):\n"
        f"{edges_text}\n\n"
        + (f"DOT representation (provided when there are few edges):\n```dot\n{dot_text}\n```\n\n" if dot_text else "")
        + "Representative source samples (partial nodes, possibly truncated, for judgment reference only):\n"
        + "\n".join(samples)
        + "\n"
        + (
            f"\n[Additional Notes (User-Defined)]\n{additional_notes}\n"
            if additional_notes
            else ""
        )
    )
