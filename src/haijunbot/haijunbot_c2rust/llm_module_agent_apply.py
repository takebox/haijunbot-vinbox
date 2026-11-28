# -*- coding: utf-8 -*-
"""Project structure application module for the LLM module planning Agent."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Set
from typing import Union
from typing import cast

from haijunbot.haijunbot_c2rust.llm_module_agent_utils import parse_project_json_entries


def ensure_pub_mod_declarations(existing_text: str, child_mods: List[str]) -> str:
    """
    Ensure that submodule declarations exist in the given text and upgrade them to `pub mod <name>;`:
    - Parse existing `mod`/`pub mod`/`pub(...) mod` declarations;
    - Existing same-name declarations that are not pub are upgraded in place to `pub mod`, preserving the original line's indentation;
    - For module names that do not exist, append a line `pub mod <name>;` at the end;
    - Return the updated full text (preserving the trailing newline).
    """
    try:
        lines = cast(List[str], (existing_text or "").splitlines())
    except Exception:
        lines = []
    mod_decl_pattern = re.compile(
        r"^\s*(pub(?:\s*\([^)]+\))?\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;\s*$"
    )
    name_to_indices: Dict[str, List[int]] = {}
    name_has_pub: Set[str] = set()
    for i, ln in enumerate(lines):
        m = mod_decl_pattern.match(ln.strip())
        if not m:
            continue
        mod_name = m.group(2)
        name_to_indices.setdefault(mod_name, []).append(i)
        if m.group(1):
            name_has_pub.add(mod_name)
    for mod_name in sorted(set(child_mods or [])):
        if mod_name in name_to_indices:
            if mod_name not in name_has_pub:
                for idx in name_to_indices[mod_name]:
                    ws_match = re.match(r"^(\s*)", lines[idx])
                    leading_ws = ws_match.group(1) if ws_match else ""
                    lines[idx] = f"{leading_ws}pub mod {mod_name};"
        else:
            lines.append(f"pub mod {mod_name};")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def apply_entries_with_mods(entries: List[Any], base_path: Path) -> None:
    """
    Create the directory and file structure based on the parsed entries (do not write/update any Rust source file content at this stage):
    - For directory entries: create the directory and recursively create its children;
    - For file entries: create an empty file if it does not exist;
    Constraints and conventions:
    - The crate root's src directory: do not generate src/mod.rs, and do not write module declarations into src/lib.rs;
    - Non-src directories: do not create or update mod.rs; if mod.rs needs to be created, list it explicitly in the YAML;
    - Completing module declarations is done in the later CodeAgent stage (scan the directory structure and minimally complete pub mod declarations).
    """

    def apply_item(item: Any, dir_path: Path) -> None:
        if isinstance(item, str):
            # File
            file_path = dir_path / item
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                try:
                    file_path.touch(exist_ok=True)
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.llm_module_agent_apply",
                        function="apply_item",
                    )
                    pass
            return

        if isinstance(item, dict) and len(item) == 1:
            dir_name, children = next(iter(item.items()))
            name = str(dir_name).rstrip("/").strip()
            new_dir = dir_path / name
            new_dir.mkdir(parents=True, exist_ok=True)

            child_mods: List[str] = []
            # Whether this is the src directory under the crate root
            is_src_root_dir = new_dir == base_path / "src"

            # Create the child items first
            for child in cast(List[Any], children or []):
                if isinstance(child, str):
                    apply_item(child, new_dir)
                    # Collect .rs files as submodules
                    if child.endswith(".rs") and child != "mod.rs":
                        stem = Path(child).stem
                        # Under the src root directory, ignore the self-references lib.rs and main.rs
                        if is_src_root_dir and stem in ("lib", "main"):
                            pass
                        else:
                            child_mods.append(stem)
                    if child == "mod.rs":
                        pass
                elif isinstance(child, dict):
                    # Subdirectory
                    sub_name = list(child.keys())[0]
                    sub_mod_name = str(sub_name).rstrip("/").strip()
                    child_mods.append(sub_mod_name)
                    apply_item(child, new_dir)

            # For the crate root's src directory, use lib.rs to aggregate submodules; do not create/update src/mod.rs
            if is_src_root_dir:
                # Do not write any file content in the src root directory; only the child items create the corresponding empty files (if any)
                return

            # Non-src directories:
            # To avoid overwriting existing implementations, this stage does not create or update mod.rs content.
            # If mod.rs needs to be created, specify it explicitly as a file entry in the JSON;
            # If module declarations need to be completed, the later CodeAgent stage will automatically complete them based on the directory structure.
            return

    for entry in entries:
        apply_item(entry, base_path)


def ensure_cargo_toml(base_dir: Path, package_name: str) -> None:
    """
    Ensure that a reasonable Cargo.toml exists under base_dir:
    - If it does not exist, create a minimal usable Cargo.toml and set package.name = package_name
    - If it already exists, do not overwrite the existing content (to avoid accidental changes)
    """
    cargo_path = base_dir / "Cargo.toml"
    if cargo_path.exists():
        return
    try:
        cargo_path.touch(exist_ok=True)
    except (OSError, PermissionError):
        # If the file cannot be created, record the error but do not interrupt the flow
        # The later CodeAgent may handle the creation of Cargo.toml
        pass


def apply_project_structure_from_json(
    json_text: str, project_root: Union[Path, str] = "."
) -> None:
    """
    Create the actual directories and files based on the directory structure JSON in the <PROJECT> returned by the Agent (do not write or update any Rust source file content at this stage).
    - project_root: Target application path; when it is "." (the default), "parent directory/current directory name_rs" is used as the crate root directory
    Note: completing module declarations (mod/pub mod) is done in the later CodeAgent step. Per the new strategy, the workspace is no longer created or updated (builds are performed directly inside the crate directory).
    """
    entries, parse_error = parse_project_json_entries(json_text)
    if parse_error:
        raise ValueError(f"JSON parsing failed: {parse_error}")
    if not entries:
        # Strict mode: on parse failure, raise an error and exit directly; the upper-level CLI catches and prints the error
        raise ValueError("[c2rust-llm-planner] Failed to parse the directory structure from the LLM output. Aborting.")
    requested_root = Path(project_root).resolve()
    try:
        cwd = Path(".").resolve()
        if requested_root == cwd:
            # The default crate cannot be set to .; set it to parent directory/current directory name_rs (a sibling of the current directory)
            base_dir = cwd.parent / f"{cwd.name}_rs"
        else:
            base_dir = requested_root
    except Exception:
        base_dir = requested_root
    base_dir.mkdir(parents=True, exist_ok=True)
    # Keep the crate name consistent with the directory name (used for the Cargo package name; hyphens allowed)
    crate_pkg_name = base_dir.name
    apply_entries_with_mods(entries, base_dir)
    # Ensure Cargo.toml exists and set the package name
    ensure_cargo_toml(base_dir, crate_pkg_name)

    # Deprecated: the crate is no longer added to the workspace (the workspace was removed per the new strategy)
    # Builds and tool runs are performed directly inside the crate directory
