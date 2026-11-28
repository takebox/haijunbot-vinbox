# -*- coding: utf-8 -*-
"""Utility functions for library replacer."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import os
import re
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional

from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON
from haijunbot.haijunbot_c2rust.constants import DEFAULT_MAPPING_OUTPUT
from haijunbot.haijunbot_c2rust.constants import DEFAULT_SOURCE_SNIPPET_MAX_LINES
from haijunbot.haijunbot_c2rust.constants import DEFAULT_SYMBOLS_OUTPUT
from haijunbot.haijunbot_c2rust.constants import ORDER_ALIAS_OUTPUT
from haijunbot.haijunbot_c2rust.constants import ORDER_PRUNE_OUTPUT
from haijunbot.haijunbot_c2rust.constants import SYMBOLS_PRUNE_OUTPUT


def resolve_symbols_jsonl_path(hint: Path) -> Path:
    """Resolve the symbols.jsonl path"""
    p = Path(hint)
    if p.is_file() and p.suffix.lower() == ".jsonl":
        return p
    if p.is_dir():
        # Check whether it is already the .haijunbot/c2rust directory
        if p.name == "c2rust" and p.parent.name == ".haijunbot":
            return p / "symbols.jsonl"
        return p / ".haijunbot" / "c2rust" / "symbols.jsonl"
    return Path(".") / ".haijunbot" / "c2rust" / "symbols.jsonl"


def setup_output_paths(
    data_dir: Path,
    out_symbols_path: Optional[Path],
    out_mapping_path: Optional[Path],
) -> tuple[Path, Path, Path, Path, Path]:
    """Set up output paths, returning (symbol table path, mapping path, compatibility symbol table path, order path, alias order path)"""
    if out_symbols_path is None:
        out_symbols_path = data_dir / DEFAULT_SYMBOLS_OUTPUT
    else:
        out_symbols_path = Path(out_symbols_path)
    if out_mapping_path is None:
        out_mapping_path = data_dir / DEFAULT_MAPPING_OUTPUT
    else:
        out_mapping_path = Path(out_mapping_path)

    # Compatibility output
    out_symbols_prune_path = data_dir / SYMBOLS_PRUNE_OUTPUT
    order_prune_path = data_dir / ORDER_PRUNE_OUTPUT
    alias_order_path = data_dir / ORDER_ALIAS_OUTPUT

    return (
        out_symbols_path,
        out_mapping_path,
        out_symbols_prune_path,
        order_prune_path,
        alias_order_path,
    )


def read_source_snippet(
    rec: dict, max_lines: int = DEFAULT_SOURCE_SNIPPET_MAX_LINES
) -> str:
    """Read a source code snippet"""
    path = rec.get("file") or ""
    try:
        if not path:
            return ""
        p = Path(path)
        if not p.exists():
            return ""
        sl = int(rec.get("start_line") or 1)
        el = int(rec.get("end_line") or sl)
        if el < sl:
            el = sl
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start_idx = max(sl - 1, 0)
        end_idx = min(el, len(lines))
        snippet_lines = lines[start_idx:end_idx]
        if len(snippet_lines) > max_lines:
            snippet_lines = snippet_lines[:max_lines]
        return "\n".join(snippet_lines)
    except Exception:
        return ""


def normalize_disabled_libraries(
    disabled_libraries: Optional[List[str]],
) -> tuple[List[str], str]:
    """Normalize the disabled library list, returning (normalized list, display string)"""
    disabled_norm: List[str] = []
    disabled_display: str = ""
    if isinstance(disabled_libraries, list):
        disabled_norm = [
            str(x).strip().lower() for x in disabled_libraries if str(x).strip()
        ]
        disabled_display = ", ".join(
            [str(x).strip() for x in disabled_libraries if str(x).strip()]
        )
    return disabled_norm, disabled_display


def load_additional_notes(data_dir: Path) -> str:
    """Load additional notes from the config file"""
    try:
        config_path = data_dir / CONFIG_JSON
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    return str(config.get("additional_notes", "") or "").strip()
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_c2rust.library_replacer_utils",
            function="load_additional_notes",
        )
        pass
    return ""


def normalize_list(items: Any) -> List[str]:
    """Normalize a list, deduplicate and sort"""
    if not isinstance(items, list):
        return []
    vals: List[str] = []
    for x in items:
        try:
            s = str(x).strip()
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.library_replacer_utils",
                function="normalize_list",
            )
            continue
        if s:
            vals.append(s)
    # Deduplicate and sort
    try:
        vals = sorted(set(vals))
    except Exception:
        # If sorting fails, at least deduplicate (preserve order)
        vals = list(dict.fromkeys(vals))
    return vals


def normalize_list_lower(items: Optional[List[str]]) -> List[str]:
    """Normalize a list and convert to lowercase (lowercase first, then deduplicate and sort)"""
    if not isinstance(items, list):
        return []
    # Lowercase first, then normalize
    lower_items = []
    for x in items:
        try:
            s = str(x).strip().lower()
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.library_replacer_utils",
                function="normalize_list_lower",
            )
            continue
        if s:
            lower_items.append(s)
    # Deduplicate and sort
    try:
        return sorted(set(lower_items))
    except Exception:
        # If sorting fails, at least deduplicate (preserve order)
        return list(dict.fromkeys(lower_items))


def is_entry_function(rec_meta: dict) -> bool:
    """Determine whether it is an entry function"""
    nm = str(rec_meta.get("name") or "")
    qn = str(rec_meta.get("qualified_name") or "")
    # Configurable entry detection (avoid hard-coding 'main'):
    # Honor env vars: c2rust_delay_entry_symbols / c2rust_delay_entries / C2RUST_DELAY_ENTRIES
    entries_env = (
        os.environ.get("c2rust_delay_entry_symbols")
        or os.environ.get("c2rust_delay_entries")
        or os.environ.get("C2RUST_DELAY_ENTRIES")
        or ""
    )
    entries_set = set()
    if entries_env:
        try:
            parts = re.split(r"[,\s;]+", entries_env.strip())
        except Exception:
            parts = [p.strip() for p in entries_env.replace(";", ",").split(",")]
        entries_set = {p.strip().lower() for p in parts if p and p.strip()}
    if entries_set:
        is_entry = (
            (nm.lower() in entries_set)
            or (qn.lower() in entries_set)
            or any(qn.lower().endswith(f"::{e}") for e in entries_set)
        )
    else:
        is_entry = (
            (nm.lower() == "main")
            or (qn.lower() == "main")
            or qn.lower().endswith("::main")
        )
    return is_entry
