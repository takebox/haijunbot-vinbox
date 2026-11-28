# -*- coding: utf-8 -*-
"""Data types and utility functions for the LLM module planning Agent."""

from dataclasses import dataclass
from typing import List


@dataclass
class FnMeta:
    """Function metadata."""

    id: int
    name: str
    qname: str
    signature: str
    file: str
    refs: List[str]

    @property
    def label(self) -> str:
        """Return the function's label (for display)."""
        base = self.qname or self.name or f"fn_{self.id}"
        if self.signature and self.signature != base:
            return f"{base}\n{self.signature}"
        return base

    @property
    def top_namespace(self) -> str:
        """
        Extract the top-level namespace/class name:
        - If qualified_name looks like ns1::ns2::Class::method -> return ns1
        - C function or no namespace -> return "c"
        """
        if self.qname and "::" in self.qname:
            return self.qname.split("::", 1)[0] or "c"
        return "c"


def sanitize_mod_name(s: str) -> str:
    """
    Sanitize the module name so it conforms to Rust module naming conventions.

    Args:
        s: Original name

    Returns:
        The sanitized module name
    """
    s = (s or "").replace("::", "__")
    safe = []
    for ch in s:
        if ch.isalnum() or ch == "_":
            safe.append(ch.lower())
        else:
            safe.append("_")
    out = "".join(safe).strip("_")
    return out[:80] or "mod"
