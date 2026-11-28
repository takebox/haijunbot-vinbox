"""
Tool for reading symbols.jsonl on demand.

Purpose:
- Avoid the Agent reading the often-large symbol table file in full directly;
- By providing the symbol table path and a list of symbol names, return only matching symbol records.

Arguments:
- symbols_file (str): Symbol table file path (.jsonl), or the project root / a directory containing .haijunbot/c2rust
- symbols (List[str]): List of symbol names to read (supports matching by name and qualified_name)

Returns:
- success (bool)
- stdout (str): JSON text containing the query results
- stderr (str)
"""

import json
import os

from haijunbot.haijunbot_utils.config import (
    detect_file_encoding,
    get_default_encoding,
    save_exception,
)
from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List


class ReadSymbolsTool:
    # The file name must match the tool name so the registry can auto-load it
    name = "read_symbols"
    description = "Read the definition records of specified symbols from symbols.jsonl on demand."
    parameters = {
        "type": "object",
        "properties": {
            "symbols_file": {
                "type": "string",
                "description": "Symbol table file path (.jsonl). If it is a directory, it is resolved to <dir>/.haijunbot/c2rust/symbols.jsonl",
            },
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of symbol names to search for (supports exact matching by name or qualified_name)",
            },
        },
        "required": ["symbols_file", "symbols"],
    }

    @staticmethod
    def check() -> bool:
        """
        Check whether the tool is available.
        Enabled only in the c2rust environment (determined by the c2rust_enabled environment variable).
        """
        return os.environ.get("c2rust_enabled") == "1"

    @staticmethod
    def _resolve_symbols_jsonl_path(path_hint: str) -> Path:
        """
        Resolve the symbol table path:
        - If it is a directory, return <dir>/.haijunbot/c2rust/symbols.jsonl
        - If it is a file, return it directly
        """
        p = Path(os.path.abspath(os.path.expanduser(path_hint)))
        if p.is_dir():
            candidate = p / ".haijunbot" / "c2rust" / "symbols.jsonl"
            return candidate
        return p

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            symbols_file_arg = args.get("symbols_file")
            symbols_arg = args.get("symbols")

            if not isinstance(symbols_file_arg, str) or not symbols_file_arg.strip():
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing or invalid symbols_file argument",
                }

            if not isinstance(symbols_arg, list) or not all(
                isinstance(s, str) for s in symbols_arg
            ):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "The symbols argument must be a list of strings",
                }

            symbols_path = self._resolve_symbols_jsonl_path(symbols_file_arg)
            PrettyOutput.auto_print(
                f"[read_symbols] Resolved symbols file path: {symbols_path}"
            )
            if not symbols_path.exists():
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Symbol table file does not exist: {symbols_path}",
                }
            if not symbols_path.is_file():
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Symbol table path is not a file: {symbols_path}",
                }

            # Use a set to improve matching efficiency; keep the original request order for output
            requested: List[str] = [s.strip() for s in symbols_arg if s and s.strip()]
            wanted_set = set(requested)
            PrettyOutput.auto_print(
                f"[read_symbols] Requested {len(wanted_set)} unique symbols."
            )

            results: Dict[str, List[Dict[str, Any]]] = {s: [] for s in requested}

            # Stream the read to avoid loading the entire large file (detect encoding first)
            enc = detect_file_encoding(str(symbols_path)) or get_default_encoding()
            with open(symbols_path, "r", encoding=enc) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception as e:
                        save_exception(
                            e, module="haijunbot_tools.read_symbols", function="execute"
                        )
                        continue

                    name = obj.get("name") or ""
                    qname = obj.get("qualified_name") or ""

                    # Only record when a requested symbol is matched
                    if name in wanted_set:
                        results[name].append(obj)
                    if qname in wanted_set and qname != name:
                        results[qname].append(obj)

            not_found = [s for s in requested if not results.get(s)]
            if not_found:
                PrettyOutput.auto_print(
                    f"[read_symbols] Symbols not found: {not_found}"
                )
            found_counts = {s: len(results.get(s, [])) for s in requested}

            out_obj: Dict[str, Any] = {
                "symbols_file": str(symbols_path),
                "requested": requested,
                "found_counts": found_counts,
                "not_found": not_found,
                "items": results,
            }

            stdout = json.dumps(out_obj, ensure_ascii=False, indent=2)
            # Brief status print (does not include specific content)
            try:
                status_lines = []
                for s in requested:
                    cnt = found_counts.get(s, 0)
                    status_lines.append(f"[read_symbols] {s}: {cnt} matches")
                if status_lines:
                    PrettyOutput.auto_print("".join(status_lines))
            except Exception as e:
                save_exception(
                    e, module="haijunbot_tools.read_symbols", function="execute"
                )
                pass

            return {"success": True, "stdout": stdout, "stderr": ""}

        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to read symbol table: {str(e)}",
            }
