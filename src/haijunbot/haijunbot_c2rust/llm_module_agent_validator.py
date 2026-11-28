# -*- coding: utf-8 -*-
"""Validator for the LLM module planning Agent."""

import re
from typing import Any
from typing import Callable
from typing import List
from typing import Optional
from typing import Tuple


class ProjectValidator:
    """Project structure validator."""

    def __init__(
        self,
        crate_name_func: Callable[[], str],
        has_original_main_func: Callable[[], bool],
    ):
        self.crate_name_func = crate_name_func
        self.has_original_main_func = has_original_main_func

    def extract_json_from_project(self, text: str) -> str:
        """
        Extract the content from the <PROJECT> block as the final JSON; if there is no match, return the original text (fallback).

        Args:
            text: Text containing the <PROJECT> block

        Returns:
            The extracted JSON text
        """
        if not isinstance(text, str) or not text:
            return ""
        m_proj = re.search(r"<PROJECT>([\s\S]*?)</PROJECT>", text, flags=re.IGNORECASE)
        if m_proj:
            return m_proj.group(1).strip()
        return text.strip()

    def validate_project_entries(self, entries: List[Any]) -> Tuple[bool, str]:
        """
        Validate whether the directory structure satisfies the hard constraints:
        - src/lib.rs must exist
        - If the original project contains main:
          * src/main.rs is not allowed
          * src/bin/<crate_name>.rs must be included
        - If the original project does not contain main:
          * src/main.rs is not allowed
          * the src/bin/ directory must not exist
        Returns (whether it passed, reason for the error)
        """
        if not isinstance(entries, list) or not entries:
            return False, "JSON is unparsable or is an empty array"

        # Extract the src directory's child items
        src_children: Optional[List[Any]] = None
        for it in entries:
            if isinstance(it, dict) and len(it) == 1:
                k, v = next(iter(it.items()))
                kk = str(k).rstrip("/").strip().lower()
                if kk == "src":
                    if isinstance(v, list):
                        src_children = v
                    else:
                        src_children = []
                    break
        if src_children is None:
            return False, "Missing src directory"

        # Build convenience lookups
        def has_file(name: str) -> bool:
            for ch in src_children or []:
                if isinstance(ch, str) and ch.strip().lower() == name.lower():
                    return True
            return False

        def find_dir(name: str) -> Optional[List[Any]]:
            for ch in src_children or []:
                if isinstance(ch, dict) and len(ch) == 1:
                    k, v = next(iter(ch.items()))
                    kk = str(k).rstrip("/").strip().lower()
                    if kk == name.lower():
                        return v if isinstance(v, list) else []
            return None

        # 1) lib.rs must be included
        if not has_file("lib.rs"):
            return False, "The src directory must contain lib.rs"

        has_main = self.has_original_main_func()
        crate_name = self.crate_name_func()

        # 2) Entry point constraints
        if has_main:
            # src/main.rs is not allowed
            if has_file("main.rs"):
                return (
                    False,
                    "The original project contains main: src/main.rs should not be generated; use src/bin/<crate>.rs instead",
                )
            # src/bin/<crate_name>.rs must be included
            bin_children = find_dir("bin")
            if bin_children is None:
                return False, f"The original project contains main: src/bin/{crate_name}.rs must be included"
            expect_bin = f"{crate_name}.rs".lower()
            if not any(
                isinstance(ch, str) and ch.strip().lower() == expect_bin
                for ch in bin_children
            ):
                return False, f"The original project contains main: src/bin/{crate_name}.rs must be included"
        else:
            # src/main.rs is not allowed
            if has_file("main.rs"):
                return False, "The original project does not contain main: src/main.rs should not be generated"
            # The bin directory is not allowed
            if find_dir("bin") is not None:
                return False, "The original project does not contain main: the src/bin/ directory should not be generated"

        return True, ""
