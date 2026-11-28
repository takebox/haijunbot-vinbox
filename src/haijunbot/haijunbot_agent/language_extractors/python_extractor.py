# -*- coding: utf-8 -*-
"""Python language symbol extractor."""

from typing import Any
from typing import Optional

from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor


def create_python_extractor() -> Optional[Any]:
    """Create Python symbol extractor using AST."""
    try:
        from haijunbot.haijunbot_code_agent.code_analyzer.languages.python_language import (
            PythonSymbolExtractor,
        )

        return PythonSymbolExtractor()
    except (ImportError, Exception):
        return None


def register_python_extractor() -> None:
    """Register Python extractor for .py and .pyw files."""
    register_language_extractor([".py", ".pyw"], create_python_extractor)
