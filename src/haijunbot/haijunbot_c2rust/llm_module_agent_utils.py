"""Utility functions for the LLM module planning Agent."""

import json
import shutil

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from haijunbot.haijunbot_utils.input import user_confirm
from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads


def perform_pre_cleanup_for_planner(project_root: Union[Path, str]) -> None:
    """
    Pre-cleanup: if present, delete the crate directory to be generated, the workspace file Cargo.toml in the current directory,
    and progress.json and symbol_map.jsonl under project_root/.haijunbot/c2rust.
    If the user does not agree, exit directly.
    """
    try:
        cwd = Path(".").resolve()
    except (OSError, ValueError) as e:
        raise RuntimeError(f"Unable to resolve the current working directory: {e}") from e

    try:
        requested_root = Path(project_root).resolve()
    except (OSError, ValueError):
        requested_root = Path(project_root)

    created_dir = (
        cwd.parent / f"{cwd.name}_rs" if requested_root == cwd else requested_root
    )

    cargo_path = cwd / "Cargo.toml"
    data_dir = requested_root / ".haijunbot" / "c2rust"
    progress_path = data_dir / "progress.json"
    symbol_map_jsonl_path = data_dir / "symbol_map.jsonl"

    targets: List[str] = []
    if created_dir.exists():
        targets.append(f"- Delete the crate directory (if present): {created_dir}")
    if cargo_path.exists():
        targets.append(f"- Delete the workspace file: {cargo_path}")
    if progress_path.exists():
        targets.append(f"- Delete the progress file: {progress_path}")
    if symbol_map_jsonl_path.exists():
        targets.append(f"- Delete the symbol mapping file: {symbol_map_jsonl_path}")

    if not targets:
        return

    tip_lines = ["The following cleanup operations will be performed:"] + targets + ["", "Continue?"]
    if not user_confirm("\n".join(tip_lines), default=False):
        PrettyOutput.auto_print("[c2rust-llm-planner] User cancelled the cleanup operation; exiting.")
        sys.exit(0)

    # Perform the cleanup operations
    try:
        if created_dir.exists():
            shutil.rmtree(created_dir, ignore_errors=True)
        if cargo_path.exists():
            cargo_path.unlink()
        if progress_path.exists():
            progress_path.unlink()
        if symbol_map_jsonl_path.exists():
            symbol_map_jsonl_path.unlink()
    except (OSError, PermissionError) as e:
        raise RuntimeError(f"Cleanup operation failed: {e}") from e


def resolve_created_dir(target_root: Union[Path, str]) -> Path:
    """
    Resolve the crate directory path:
    - If target_root is "." or resolves to the current working directory, return the "<cwd.name>_rs" directory;
    - Otherwise return the resolved target path;
    - If resolution fails, fall back to Path(target_root).
    """
    try:
        cwd = Path(".").resolve()
        try:
            resolved_target = Path(target_root).resolve()
        except Exception:
            resolved_target = Path(target_root)
        if target_root == "." or resolved_target == cwd:
            return cwd.parent / f"{cwd.name}_rs"
        return resolved_target
    except Exception:
        return Path(target_root)


def parse_project_json_entries_fallback(json_text: str) -> List[Any]:
    """
    Fallback parser: when jsonnet parsing fails, try parsing with standard json.
    Note: this function is mainly for compatibility; under normal circumstances jsonnet parsing should be used.
    """
    try:
        import json as std_json

        data = std_json.loads(json_text)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def parse_project_json_entries(json_text: str) -> Tuple[List[Any], Optional[str]]:
    """
    Use jsonnet to parse the directory structure JSON in the <PROJECT> block into a list structure:
    - File entries: strings, e.g. "lib.rs"
    - Directory entries: dicts, shaped like {"src/": [ ... ]} or {"src": [ ... ]}
    Returns (parse result, error message)
    If parsing succeeds, return (data, None)
    If parsing fails, return ([], error message)
    Uses jsonnet parsing, which supports looser JSON syntax (such as trailing commas, comments, etc.).
    """
    try:
        try:
            data = json_loads(json_text)
            if isinstance(data, list):
                return data, None
            # If the parse result is not a list
            return [], f"The JSON parse result is not an array, but {type(data).__name__}"
        except Exception as json_err:
            # JSON parsing error
            error_msg = f"JSON parsing failed: {str(json_err)}"
            return [], error_msg
    except Exception as e:
        # Other unknown errors
        return [], f"An exception occurred during parsing: {str(e)}"


def entries_to_json(entries: List[Any]) -> str:
    """
    Serialize the parsed entries list into JSON text (directories are represented as objects, files as strings)

    Args:
        entries: The parsed directory structure list

    Returns:
        JSON text
    """
    return json.dumps(entries, ensure_ascii=False, indent=2)
