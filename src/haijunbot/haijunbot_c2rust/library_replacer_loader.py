# -*- coding: utf-8 -*-
"""Symbol table loading and graph construction module for library replacer."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_c2rust.scanner import find_root_function_ids


def load_symbols(
    sjsonl: Path,
) -> tuple[
    List[Dict[str, Any]],
    Dict[int, Dict[str, Any]],
    Dict[str, int],
    Set[int],
    Dict[int, List[str]],
]:
    """Load the symbol table, returning (all records, id-to-record mapping, name-to-id mapping, set of function ids, id-to-referenced-names mapping)"""
    all_records: List[Dict[str, Any]] = []
    by_id: Dict[int, Dict[str, Any]] = {}
    name_to_id: Dict[str, int] = {}
    func_ids: Set[int] = set()
    id_refs_names: Dict[int, List[str]] = {}

    with open(sjsonl, "r", encoding="utf-8") as f:
        idx = 0
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.library_replacer_loader",
                    function="load_symbols",
                )
                continue
            idx += 1
            fid = int(obj.get("id") or idx)
            obj["id"] = fid
            nm = obj.get("name") or ""
            qn = obj.get("qualified_name") or ""
            cat = obj.get("category") or ""  # "function" | "type"
            refs = obj.get("ref")
            if not isinstance(refs, list):
                refs = []
            refs = [r for r in refs if isinstance(r, str) and r]

            all_records.append(obj)
            by_id[fid] = obj
            id_refs_names[fid] = refs
            if nm:
                name_to_id.setdefault(nm, fid)
            if qn:
                name_to_id.setdefault(qn, fid)
            if cat == "function":
                func_ids.add(fid)

    return all_records, by_id, name_to_id, func_ids, id_refs_names


def build_function_graph(
    func_ids: Set[int],
    id_refs_names: Dict[int, List[str]],
    name_to_id: Dict[str, int],
) -> Dict[int, List[int]]:
    """Build the function dependency graph, returning a mapping from id to the list of dependency ids"""
    adj_func: Dict[int, List[int]] = {}
    for fid in func_ids:
        internal: List[int] = []
        for target in id_refs_names.get(fid, []):
            tid = name_to_id.get(target)
            if tid is not None and tid in func_ids and tid != fid:
                internal.append(tid)
        try:
            internal = list(dict.fromkeys(internal))
        except Exception:
            internal = sorted(list(set(internal)))
        adj_func[fid] = internal
    return adj_func


def build_evaluation_order(
    sjsonl: Path,
    func_ids: Set[int],
    adj_func: Dict[int, List[int]],
) -> List[int]:
    """Build the evaluation order (breadth-first, parents before children)"""
    # Evaluation queue: start with all functions with no incoming edges as seeds, traverse the whole graph level by level so that parents are evaluated before children;
    # If there are no nodes with no incoming edges (e.g. a strongly connected cycle), fall back to the full set of functions.
    try:
        roots_all = find_root_function_ids(sjsonl)
    except Exception:
        roots_all = []
    seeds = [rid for rid in roots_all if rid in func_ids]
    if not seeds:
        seeds = sorted(list(func_ids))

    visited: Set[int] = set()
    order: List[int] = []
    q: List[int] = list(seeds)
    qi = 0
    while qi < len(q):
        u = q[qi]
        qi += 1
        if u in visited or u not in func_ids:
            continue
        visited.add(u)
        order.append(u)
        for v in adj_func.get(u, []):
            if v not in visited and v in func_ids:
                q.append(v)
    # If isolated/cyclic components remain uncovered, add their nodes (to ensure every function node will participate in evaluation as a "candidate root")
    if len(visited) < len(func_ids):
        leftovers = [fid for fid in sorted(func_ids) if fid not in visited]
        order.extend(leftovers)

    return order


def collect_descendants(
    start: int,
    adj_func: Dict[int, List[int]],
    desc_cache: Dict[int, Set[int]],
) -> Set[int]:
    """Collect all descendant nodes starting from start (using a cache)"""
    if start in desc_cache:
        return desc_cache[start]
    visited: Set[int] = set()
    stack: List[int] = [start]
    visited.add(start)
    while stack:
        u = stack.pop()
        for v in adj_func.get(u, []):
            if v not in visited:
                visited.add(v)
                stack.append(v)
    desc_cache[start] = visited
    return visited


def process_candidate_scope(
    candidates: Optional[List[str]],
    all_records: List[Dict[str, Any]],
    root_funcs: List[int],
    func_ids: Set[int],
    adj_func: Dict[int, List[int]],
    desc_cache: Dict[int, Set[int]],
) -> tuple[List[int], Set[int]]:
    """Process candidate roots and scope, returning (filtered list of root functions, set of unreachable functions)"""

    scope_unreachable_funcs: Set[int] = set()
    if not candidates:
        return root_funcs, scope_unreachable_funcs

    cand_ids: Set[int] = set()
    # Support overloads: the same name/qualified name may correspond to multiple function IDs, all of which must be included as candidates
    key_set = set(candidates)
    for rec in all_records:
        if (rec.get("category") or "") != "function":
            continue
        nm = rec.get("name") or ""
        qn = rec.get("qualified_name") or ""
        if nm in key_set or qn in key_set:
            try:
                rec_id = rec.get("id")
                if rec_id is not None:
                    cand_ids.add(int(rec_id))
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.library_replacer_loader",
                    function="process_candidate_scope",
                )
                continue

    if not cand_ids:
        return root_funcs, scope_unreachable_funcs

    filtered_roots = [rid for rid in root_funcs if rid in cand_ids]
    # Compute the set of functions reachable from the candidate roots (including the roots)
    reachable_all: Set[int] = set()
    for rid in filtered_roots:
        reachable_all.update(collect_descendants(rid, adj_func, desc_cache))
    # Unreachable functions (function category only) will be deleted outright
    scope_unreachable_funcs = {fid for fid in func_ids if fid not in reachable_all}
    if scope_unreachable_funcs:
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-library] Based on the root list, marking unreachable functions for deletion: {len(scope_unreachable_funcs)}"
        )

    return filtered_roots, scope_unreachable_funcs
