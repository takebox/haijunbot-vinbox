# -*- coding: utf-8 -*-
"""
A lightweight tool that uses libclang to collect function names from header files.

Purpose:
- Given one or more C/C++ header files (.h/.hh/.hpp/.hxx), use libclang to parse each file and collect function names
- Prefer qualified names; otherwise fall back to unqualified names
- Write the unique names (deduplicated, preserving first-occurrence order) to the specified output file (one per line)

Design:
- Reuses the scan tools:
  - _try_import_libclang()
  - find_compile_commands()
  - load_compile_commands()
  - scan_file() (Note: scan_file only collects definitions; inline header files are usually definitions)
- If compile_commands.json exists, use its arguments; otherwise fall back to a minimal argument set containing the file's parent directory
- For header parsing, ensure the language flag (-x c-header / -x c++-header) is present if not already specified in the arguments

Notes:
- This module prioritizes correctness/robustness over performance
- Does not attempt to discover transitive includes; only assists the parser by adding -I <file.parent>
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Any

from haijunbot.haijunbot_c2rust.constants import HEADER_EXTS
from haijunbot.haijunbot_c2rust.scanner import _try_import_libclang
from haijunbot.haijunbot_c2rust.scanner import find_compile_commands
from haijunbot.haijunbot_c2rust.scanner import load_compile_commands
from haijunbot.haijunbot_c2rust.scanner import scan_file


def _guess_lang_header_flag(file: Path) -> List[str]:
    """
    Guess a suitable -x language flag for the header file if it is not specified in the compile arguments
    """
    ext = file.suffix.lower()
    if ext in {".hh", ".hpp", ".hxx"}:
        return ["-x", "c++-header"]
    # For .h files, default to the C header (a conservative choice)
    return ["-x", "c-header"]


def _ensure_parse_args_for_header(
    file: Path, base_args: Optional[List[str]]
) -> List[str]:
    """
    Ensure the minimal argument set required for header parsing:
    - Include the file.parent directory via -I
    - Add -x c-header/c++-header if there is no language flag
    """
    args = list(base_args or [])
    # Detect whether a language flag (-x <lang>) already exists
    has_lang = False
    for i, a in enumerate(args):
        if a == "-x":
            # If '-x' exists and is followed by a value, consider the language already specified
            if i + 1 < len(args):
                has_lang = True
                break
        elif a.startswith("-x"):
            has_lang = True
            break

    if not has_lang:
        args.extend(_guess_lang_header_flag(file))

    # Ensure -I <file.parent> is present
    inc_dir = str(file.parent)
    has_inc = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-I":
            if i + 1 < len(args) and args[i + 1] == inc_dir:
                has_inc = True
                break
            i += 2
            continue
        elif a.startswith("-I"):
            # Possibly the -I/path format
            if a[2:] == inc_dir:
                has_inc = True
                break
        i += 1
    if not has_inc:
        args.extend(["-I", inc_dir])

    return args


def _collect_decl_function_names(cindex: Any, file: Path, args: List[str]) -> List[str]:
    """
    Fallback for header files that have no inline definitions:
    Collect the function declarations (prototypes/methods) defined in this header file
    """
    try:
        index = cindex.Index.create()
        tu = index.parse(str(file), args=args, options=0)
    except Exception:
        return []
    names: List[str] = []
    seen = set()

    def visit(node: Any) -> None:
        try:
            kind = node.kind.name
        except Exception:
            kind = ""
        if kind in {
            "FUNCTION_DECL",
            "CXX_METHOD",
            "FUNCTION_TEMPLATE",
            "CONSTRUCTOR",
            "DESTRUCTOR",
        }:
            loc_file = getattr(getattr(node, "location", None), "file", None)
            try:
                same_file = (
                    loc_file is not None
                    and Path(loc_file.name).resolve() == file.resolve()
                )
            except Exception:
                same_file = False
            if same_file:
                try:
                    nm = str(node.spelling or "").strip()
                except Exception:
                    nm = ""
                if nm and nm not in seen:
                    seen.add(nm)
                    names.append(nm)
        for ch in node.get_children():
            visit(ch)

    try:
        visit(tu.cursor)
    except Exception as e:
        save_exception(e, module="haijunbot_c2rust.collector", function="visit")
        pass
    return names


def collect_function_names(
    files: List[Path],
    out_path: Path,
    compile_commands_root: Optional[Path] = None,
) -> Path:
    """
    Collect function names from the given header files and write the unique names to out_path

    Args:
    - files: List of header file paths (.h/.hh/.hpp/.hxx). Non-header files are skipped
    - out_path: Output file path. It will be created (including parent directories) and overwritten
    - compile_commands_root: Optional; the root directory to search for compile_commands.json
      If not provided, search upward from each file's directory

    Returns:
    - The out_path path that was written
    """
    # Normalize and filter header files
    hdrs: List[Path] = []
    for p in files or []:
        try:
            fp = Path(p).resolve()
        except Exception as e:
            save_exception(
                e, module="haijunbot_c2rust.collector", function="collect_function_names"
            )
            continue
        if fp.is_file() and fp.suffix.lower() in HEADER_EXTS:
            hdrs.append(fp)

    if not hdrs:
        raise ValueError("No valid header files (.h/.hh/.hpp/.hxx) were provided")

    # Prepare libclang
    cindex = _try_import_libclang()
    if cindex is None:
        from clang import cindex as _ci

        cindex = _ci

    # Prepare the compile_commands argument map (once globally if a root directory is provided, otherwise per file)
    cc_args_map_global: Optional[Dict[str, List[str]]] = None
    if compile_commands_root is not None:
        cc_file = find_compile_commands(Path(compile_commands_root))
        if cc_file:
            cc_args_map_global = load_compile_commands(cc_file)

    # Collect names (preserving order)
    seen = set()
    ordered_names: List[str] = []

    for hf in hdrs:
        # Determine the arguments for this file
        cc_args_map = cc_args_map_global
        if cc_args_map is None:
            # Try to find compile_commands.json near this file
            cc_file_local = find_compile_commands(hf.parent)
            if cc_file_local:
                try:
                    cc_args_map = load_compile_commands(cc_file_local)
                except Exception:
                    cc_args_map = None

        base_args = None
        if cc_args_map:
            base_args = cc_args_map.get(str(hf))
        if base_args is None:
            base_args = ["-I", str(hf.parent)]

        args = _ensure_parse_args_for_header(hf, base_args)

        # Try scanning. If it errors, try the fallback with a minimal argument set
        try:
            funcs = scan_file(cindex, hf, args)
        except Exception:
            try:
                funcs = scan_file(
                    cindex,
                    hf,
                    _ensure_parse_args_for_header(hf, ["-I", str(hf.parent)]),
                )
            except Exception:
                funcs = []

        # Extract the preferred name from the definition (qualified_name or name)
        added_count = 0
        for fn in funcs:
            name = ""
            try:
                qn = getattr(fn, "qualified_name", "") or ""
                nm = getattr(fn, "name", "") or ""
                name = qn or nm
                name = str(name).strip()
            except Exception:
                name = ""
            if not name or name in seen:
                continue
            seen.add(name)
            ordered_names.append(name)
            added_count += 1

        # Fallback: if no definitions were found in this header file, collect declarations
        if not funcs or added_count == 0:
            try:
                decl_names = _collect_decl_function_names(cindex, hf, args)
            except Exception:
                decl_names = []
            for nm in decl_names:
                name = str(nm).strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                ordered_names.append(name)

    # Write the file (one per line)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        out_path.write_text(
            "\n".join(ordered_names) + ("\n" if ordered_names else ""), encoding="utf-8"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to write the output file: {out_path}: {e}")

    return out_path
