# -*- coding: utf-8 -*-
"""
Context collection module
"""

from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from haijunbot.haijunbot_c2rust.models import FnRecord


class ContextCollector:
    """Context collector"""

    def __init__(
        self,
        project_root: Path,
        fn_index_by_id: Dict[int, FnRecord],
        fn_name_to_id: Dict[str, int],
        symbol_map: Any,  # _SymbolMapJsonl
    ) -> None:
        self.project_root = project_root
        self.fn_index_by_id = fn_index_by_id
        self.fn_name_to_id = fn_name_to_id
        self.symbol_map = symbol_map

    def read_source_span(self, rec: FnRecord) -> str:
        """Read a source snippet by start/end line (ignore column boundaries, be as complete as possible)"""
        try:
            p = Path(rec.file)
            if not p.is_absolute():
                p = (self.project_root / p).resolve()
            if not p.exists():
                return ""
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            s = max(1, int(rec.start_line or 1))
            e = min(len(lines), max(int(rec.end_line or s), s))
            chunk = "\n".join(lines[s - 1 : e])
            return chunk
        except Exception:
            return ""

    def collect_callees_context(self, rec: FnRecord) -> List[Dict[str, Any]]:
        """
        Generate the list of referenced-symbol contexts (without distinguishing functions from types):
        - If already translated: provide {name, qname, translated: true, rust_module, rust_symbol, ambiguous?}
        - If not translated but a scan record exists: provide {name, qname, translated: false, file, start_line, end_line}
        - If only a name: provide {name, qname, translated: false}
        Note: if multiple records map to the same name (overloads/same-name symbols), mark ambiguous=true here and pick the most recent one as a hint.
        """
        ctx: List[Dict[str, Any]] = []
        for callee in rec.refs or []:
            entry: Dict[str, Any] = {"name": callee, "qname": callee}
            # Already-translated mapping
            if self.symbol_map.has_symbol(callee):
                recs = self.symbol_map.get(callee)
                m = recs[-1] if recs else None
                entry.update(
                    {
                        "translated": True,
                        "rust_module": (m or {}).get("module"),
                        "rust_symbol": (m or {}).get("rust_symbol"),
                    }
                )
                if len(recs) > 1:
                    entry["ambiguous"] = True
                ctx.append(entry)
                continue
            # Resolve the ID by name using the order index (function or type)
            cid = self.fn_name_to_id.get(callee)
            if cid:
                crec = self.fn_index_by_id.get(cid)
                if crec:
                    entry.update(
                        {
                            "translated": False,
                            "file": crec.file,
                            "start_line": crec.start_line,
                            "end_line": crec.end_line,
                        }
                    )
            else:
                entry.update({"translated": False})
            ctx.append(entry)
        return ctx

    def untranslated_callee_symbols(self, rec: FnRecord) -> List[str]:
        """
        Return the callee symbols not yet converted (using the name/qualified name from the scan records as keys)
        """
        syms: List[str] = []
        for callee in rec.refs or []:
            if not self.symbol_map.has_symbol(callee):
                syms.append(callee)
        # Deduplicate
        try:
            syms = list(dict.fromkeys(syms))
        except Exception:
            syms = sorted(list(set(syms)))
        return syms

    def append_additional_notes(self, prompt: str, additional_notes: str) -> str:
        """
        Append additional notes to the end of the prompt (if present).

        Args:
            prompt: Original prompt
            additional_notes: Additional notes

        Returns:
            The prompt with the additional notes appended
        """
        if additional_notes and additional_notes.strip():
            return (
                prompt
                + "\n\n"
                + "[Additional Notes (User-Defined)]\n"
                + additional_notes.strip()
            )
        return prompt
