# -*- coding: utf-8 -*-
"""Rust language symbol extractor."""

from typing import Any
from typing import Optional

from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor


def create_rust_extractor() -> Optional[Any]:
    """Create Rust symbol extractor using tree-sitter."""
    try:
        from haijunbot.haijunbot_code_agent.code_analyzer.languages.rust_language import (
            RustSymbolExtractor,
        )

        return RustSymbolExtractor()
    except (ImportError, RuntimeError, Exception):
        return None


def register_rust_extractor() -> None:
    """Register Rust extractor for .rs files."""
    register_language_extractor(".rs", create_rust_extractor)
