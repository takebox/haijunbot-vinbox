"""Language support module.

Provides language detection and factory functions, using the language registry to manage all language support.
"""

from haijunbot.haijunbot_utils.output import PrettyOutput

from typing import Optional

from .dependency_analyzer import DependencyAnalyzer
from .language_registry import detect_language as _detect_language
from .language_registry import get_dependency_analyzer as _get_dependency_analyzer
from .language_registry import get_symbol_extractor as _get_symbol_extractor
from .language_registry import register_language
from .symbol_extractor import SymbolExtractor

# Automatically register all language support
# Use try-except so that a failure to import one language support does not affect the others

# Python language support (required, because it is the core language)
try:
    from .languages import PythonLanguageSupport

    register_language(PythonLanguageSupport())
except ImportError as e:
    PrettyOutput.auto_print(f"⚠️ Warning: Failed to import PythonLanguageSupport: {e}")

# Rust language support (optional, requires tree-sitter)
try:
    from .languages import RustLanguageSupport

    register_language(RustLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# Go language support (optional, requires tree-sitter)
try:
    from .languages import GoLanguageSupport

    register_language(GoLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# C language support (optional, requires tree-sitter)
try:
    from .languages import CLanguageSupport

    register_language(CLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# C++ language support (optional, requires tree-sitter)
try:
    from .languages import CppLanguageSupport

    register_language(CppLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# JavaScript language support (optional, requires tree-sitter)
try:
    from .languages import JavaScriptLanguageSupport

    register_language(JavaScriptLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# TypeScript language support (optional, requires tree-sitter)
try:
    from .languages import TypeScriptLanguageSupport

    register_language(TypeScriptLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable

# Java language support (optional, requires tree-sitter)
try:
    from .languages import JavaLanguageSupport

    register_language(JavaLanguageSupport())
except (ImportError, RuntimeError):
    pass  # Fail silently, tree-sitter may be unavailable


def detect_language(file_path: str) -> Optional[str]:
    """Detect the programming language of the file.

    Args:
        file_path: the file path

    Returns:
        The language name, or None if it cannot be detected
    """
    return _detect_language(file_path)


def get_symbol_extractor(language: str) -> Optional[SymbolExtractor]:
    """Get the symbol extractor for the given language.

    Args:
        language: the language name

    Returns:
        A SymbolExtractor instance, or None if not supported
    """
    return _get_symbol_extractor(language)


def get_dependency_analyzer(language: str) -> Optional[DependencyAnalyzer]:
    """Get the dependency analyzer for the given language.

    Args:
        language: the language name

    Returns:
        A DependencyAnalyzer instance, or None if not supported
    """
    return _get_dependency_analyzer(language)
