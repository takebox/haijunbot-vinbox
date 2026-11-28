# -*- coding: utf-8 -*-
"""
C2Rust transpiler data loader
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import time
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
from haijunbot.haijunbot_c2rust.constants import SYMBOLS_JSONL
from haijunbot.haijunbot_c2rust.models import FnRecord


class _DbLoader:
    """Read symbols.jsonl and provide id/name queries and source snippet reads"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.data_dir = self.project_root / C2RUST_DIRNAME

        self.symbols_path = self.data_dir / SYMBOLS_JSONL
        # Unified flow: only use symbols.jsonl; functions.jsonl is no longer supported
        if not self.symbols_path.exists():
            raise FileNotFoundError(f"symbols.jsonl not found in directory: {self.data_dir}")

        self.fn_by_id: Dict[int, FnRecord] = {}
        self.name_to_id: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        """
        Read the unified symbols.jsonl.
        It does not distinguish function and type definitions; all are loaded as generic records (location and reference info).
        """

        def _iter_records_from_file(path: Path) -> Any:
            try:
                with path.open("r", encoding="utf-8") as f:
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
                                module="haijunbot_c2rust.loaders",
                                function="_iter_records_from_file",
                            )
                            continue
                        idx += 1
                        yield idx, obj
            except FileNotFoundError:
                return

        # Load all symbol records (functions, types, etc.)
        for idx, obj in _iter_records_from_file(self.symbols_path):
            fid = int(obj.get("id") or idx)
            nm = obj.get("name") or ""
            qn = obj.get("qualified_name") or ""
            fp = obj.get("file") or ""
            refs = obj.get("ref")
            # Uniformly use a list-typed ref field
            if not isinstance(refs, list):
                refs = []
            refs = [c for c in refs if isinstance(c, str) and c]
            sr = int(obj.get("start_line") or 0)
            sc = int(obj.get("start_col") or 0)
            er = int(obj.get("end_line") or 0)
            ec = int(obj.get("end_col") or 0)
            lr = (
                obj.get("lib_replacement")
                if isinstance(obj.get("lib_replacement"), dict)
                else None
            )
            rec = FnRecord(
                id=fid,
                name=nm,
                qname=qn,
                file=fp,
                start_line=sr,
                start_col=sc,
                end_line=er,
                end_col=ec,
                refs=refs,
                lib_replacement=lr,
            )
            self.fn_by_id[fid] = rec
            if nm:
                self.name_to_id.setdefault(nm, fid)
            if qn:
                self.name_to_id.setdefault(qn, fid)

    def get(self, fid: int) -> Optional[FnRecord]:
        return self.fn_by_id.get(fid)

    def get_id_by_name(self, name_or_qname: str) -> Optional[int]:
        return self.name_to_id.get(name_or_qname)

    def read_source_span(self, rec: FnRecord) -> str:
        """Read a source snippet by start/end line (ignore column boundaries, be as complete as possible)"""
        try:
            p = Path(rec.file)
            # If the record is a relative path, resolve it against project_root
            if not p.is_absolute():
                p = (self.project_root / p).resolve()
            if not p.exists():
                return ""
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            s = max(1, rec.start_line)
            e = min(len(lines), max(rec.end_line, s))
            # Python indices start at 0; the end line is inclusive
            chunk = "\n".join(lines[s - 1 : e])
            return chunk
        except Exception:
            return ""


class _SymbolMapJsonl:
    """
    Symbol mapping management in JSONL form:
    - One record per line, supporting multiple mappings for the same function name (to handle overloads/same-name symbols)
    - Record fields:
      {
        "c_name": "<simple name>",
        "c_qname": "<qualified name, may be an empty string>",
        "c_file": "<source file path>",
        "start_line": <int>,
        "end_line": <int>,
        "module": "src/xxx.rs or src/xxx/mod.rs",
        "rust_symbol": "<Rust function name>",
        "updated_at": "YYYY-MM-DDTHH:MM:SS"
      }
    - Provides the ability to query by name (c_name/c_qname) and to determine whether something is already recorded by source location
    """

    def __init__(self, jsonl_path: Path) -> None:
        self.jsonl_path = jsonl_path
        self.records: List[Dict[str, Any]] = []
        # Index: name -> list of record indices
        self.by_key: Dict[str, List[int]] = {}
        # Unique location (to avoid same-name conflicts): (c_file, start_line, end_line, c_qname or c_name) -> list of record indices
        self.by_pos: Dict[Tuple[str, int, int, str], List[int]] = {}
        self._load()

    def _load(self) -> None:
        self.records = []
        self.by_key = {}
        self.by_pos = {}
        # Read JSONL
        if self.jsonl_path.exists():
            try:
                with self.jsonl_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception as e:
                            save_exception(
                                e, module="haijunbot_c2rust.loaders", function="_load"
                            )
                            continue
                        self._add_record_in_memory(obj)
            except Exception as e:
                save_exception(e, module="haijunbot_c2rust.loaders", function="_load")
                pass

    def _add_record_in_memory(self, rec: Dict[str, Any]) -> None:
        idx = len(self.records)
        self.records.append(rec)
        for key in [rec.get("c_name") or "", rec.get("c_qname") or ""]:
            k = str(key or "").strip()
            if not k:
                continue
            self.by_key.setdefault(k, []).append(idx)
        pos_key = (
            str(rec.get("c_file") or ""),
            int(rec.get("start_line") or 0),
            int(rec.get("end_line") or 0),
            str(rec.get("c_qname") or rec.get("c_name") or ""),
        )
        self.by_pos.setdefault(pos_key, []).append(idx)

    def has_symbol(self, sym: str) -> bool:
        return bool(self.by_key.get(sym))

    def get(self, sym: str) -> List[Dict[str, Any]]:
        idxs = self.by_key.get(sym) or []
        return [self.records[i] for i in idxs]

    def get_any(self, sym: str) -> Optional[Dict[str, Any]]:
        recs = self.get(sym)
        return recs[-1] if recs else None

    def has_rec(self, rec: FnRecord) -> bool:
        key = (
            str(rec.file or ""),
            int(rec.start_line or 0),
            int(rec.end_line or 0),
            str(rec.qname or rec.name or ""),
        )
        return bool(self.by_pos.get(key))

    def add(self, rec: FnRecord, module: str, rust_symbol: str) -> None:
        obj = {
            "c_name": rec.name or "",
            "c_qname": rec.qname or "",
            "c_file": rec.file or "",
            "start_line": int(rec.start_line or 0),
            "end_line": int(rec.end_line or 0),
            "module": str(module or ""),
            "rust_symbol": str(rust_symbol or (rec.name or f"fn_{rec.id}")),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        }
        # Write to disk first, then update the in-memory index
        try:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception as e:
            save_exception(e, module="haijunbot_c2rust.loaders", function="add")
            pass
        self._add_record_in_memory(obj)
