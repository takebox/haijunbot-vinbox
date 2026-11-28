# -*- coding: utf-8 -*-
"""
C2Rust transpiler data model
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


@dataclass
class FnRecord:
    id: int
    name: str
    qname: str
    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    refs: List[str]
    # Extra metadata (from symbols/items): function signature, return type and parameters (optional)
    signature: str = ""
    return_type: str = ""
    params: Optional[List[Dict[str, str]]] = None
    # Context metadata from the library replacement stage (if present)
    lib_replacement: Optional[Dict[str, Any]] = None
