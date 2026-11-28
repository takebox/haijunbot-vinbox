# -*- coding: utf-8 -*-
"""Output writing module for library replacer."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def write_output_symbols(
    all_records: List[Dict[str, Any]],
    pruned_funcs: Set[int],
    selected_roots: List[Tuple[int, Dict[str, Any]]],
    out_symbols_path: Path,
    out_symbols_prune_path: Path,
) -> List[Dict[str, Any]]:
    """Write out the new symbol table and return the replacement mapping list"""
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    kept_ids: Set[int] = set()
    for rec in all_records:
        rec_id = rec.get("id")
        if rec_id is None:
            continue
        fid = int(rec_id)
        cat = rec.get("category") or ""
        if cat == "function":
            if fid in pruned_funcs:
                continue
            kept_ids.add(fid)
        else:
            kept_ids.add(fid)

    sel_root_ids = set(fid for fid, _ in selected_roots)
    replacements: List[Dict[str, Any]] = []

    with (
        open(out_symbols_path, "w", encoding="utf-8") as fo,
        open(out_symbols_prune_path, "w", encoding="utf-8") as fo2,
    ):
        for rec in all_records:
            rec_id = rec.get("id")
            if rec_id is None:
                continue
            fid = int(rec_id)
            if fid not in kept_ids:
                continue

            rec_out = dict(rec)
            if (rec.get("category") or "") == "function" and fid in sel_root_ids:
                # Semantics are library-level replacement: no specific API is required; set the root ref to a library placeholder (supports combining multiple libraries)
                conf = 0.0
                api = ""
                apis = None
                libraries_out: List[str] = []
                notes_out: str = ""
                lib_single: str = ""
                is_entry = False
                for rf, rres in selected_roots:
                    if rf == fid:
                        api = str(rres.get("api") or rres.get("function") or "")
                        apis = rres.get("apis")
                        libs_val = rres.get("libraries")
                        if isinstance(libs_val, list):
                            libraries_out = [str(x) for x in libs_val if str(x)]
                        lib_single = str(rres.get("library") or "").strip()
                        try:
                            conf = float(rres.get("confidence") or 0.0)
                        except Exception:
                            conf = 0.0
                        notes_val = rres.get("notes")
                        if isinstance(notes_val, str):
                            notes_out = notes_val
                        is_entry = bool(rres.get("is_entry_function", False))
                        break
                # Entry function protection: do not modify the ref field (keep the original value, which needs translation), but keep the replacement info for translation reference
                if not is_entry:
                    # Non-entry function: change ref to a library placeholder
                    if libraries_out:
                        lib_markers = [f"lib::{lb}" for lb in libraries_out]
                    elif lib_single:
                        lib_markers = [f"lib::{lib_single}"]
                    else:
                        lib_markers = []
                    rec_out["ref"] = lib_markers
                # Entry function: keep ref unchanged (do not modify), but lib_replacement metadata will still be saved afterward
                try:
                    rec_out["updated_at"] = now_ts
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.library_replacer_output",
                        function="write_output_symbols",
                    )
                    pass
                # Save library replacement metadata into the symbol table for use as context in the later translation stage
                try:
                    meta_apis = (
                        apis if isinstance(apis, list) else ([api] if api else [])
                    )
                    lib_primary = libraries_out[0] if libraries_out else lib_single
                    rec_out["lib_replacement"] = {
                        "libraries": libraries_out,
                        "library": lib_primary or "",
                        "apis": meta_apis,
                        "api": api,
                        "confidence": float(conf)
                        if isinstance(conf, (int, float))
                        else 0.0,
                        "notes": notes_out,
                        "mode": "llm",
                        "is_entry_function": is_entry,
                        "updated_at": now_ts,
                    }
                except Exception:
                    # Ignore metadata write failures; do not block the main flow
                    pass
                rep_obj: Dict[str, Any] = {
                    "id": fid,
                    "name": rec.get("name") or "",
                    "qualified_name": rec.get("qualified_name") or "",
                    "library": (libraries_out[0] if libraries_out else lib_single),
                    "libraries": libraries_out,
                    "function": api,
                    "confidence": conf,
                    "mode": "llm",
                    "is_entry_function": is_entry,
                }
                if isinstance(apis, list):
                    rep_obj["apis"] = apis
                if notes_out:
                    rep_obj["notes"] = notes_out
                replacements.append(rep_obj)

            line = json.dumps(rec_out, ensure_ascii=False) + "\n"
            fo.write(line)
            fo2.write(line)
            # Do not overwrite symbols.jsonl (keep the original scan/cleanup results as the baseline)

    return replacements
