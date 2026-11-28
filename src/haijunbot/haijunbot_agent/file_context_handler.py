# -*- coding: utf-8 -*-
import os
import re
from typing import Any

from haijunbot.haijunbot_utils.config import detect_file_encoding, read_text_file
from typing import Callable


from typing import Optional
from typing import Tuple
from typing import Union

# Language extractor registry (exported for use by other modules)
_LANGUAGE_EXTRACTORS: dict[str, Callable[[], Optional[Any]]] = {}


def is_text_file(filepath: str) -> bool:
    """
    Check if a file is a text file. Detects encoding first, then attempts to read.
    """
    try:
        enc = detect_file_encoding(filepath, sample_size=1024)
        if enc:
            with open(filepath, "r", encoding=enc, errors="strict") as f:
                f.read(1024)
            return True
    except (UnicodeDecodeError, IOError):
        pass
    return False


def count_lines(filepath: str) -> int:
    """
    Count the number of lines in a file. Detects encoding first, then reads.
    """
    try:
        content = read_text_file(filepath, errors="ignore")
        return len(content.splitlines()) if content else 0
    except IOError:
        return 0


def register_language_extractor(
    extensions: Union[str, list[str]],
    extractor_factory: Optional[Callable[[], Optional[Any]]] = None,
) -> Optional[Callable[[Callable[[], Optional[Any]]], Callable[[], Optional[Any]]]]:
    """
    Register a symbol extractor for one or more file extensions.

    Can be used as a decorator or a regular function.

    Args:
        extensions: List of file extensions (e.g.: ['.py', '.pyw']) or a single extension string.
                   If used as a decorator, this is the first argument.
        extractor_factory: A callable that returns an extractor instance, or None if unavailable.
                          The extractor must have an extract_symbols(file_path: str, content: str) method
                          that returns a list of Symbol objects.
                          If used as a decorator, this is the decorated function.

    Examples:
        # As a decorator:
        @register_language_extractor(['.py', '.pyw'])
        def create_python_extractor():
            from haijunbot.haijunbot_code_agent.code_analyzer.languages.python_language import PythonSymbolExtractor
            return PythonSymbolExtractor()

        # As a regular function:
        def create_java_extractor():
            # ... create extractor ...
            return JavaExtractor()

        register_language_extractor('.java', create_java_extractor)
    """
    # Supports both decorator and function call syntax
    if extractor_factory is None:
        # Used as decorator: @register_language_extractor(['.ext'])
        def decorator(func: Callable[[], Optional[Any]]) -> Callable[[], Optional[Any]]:
            if isinstance(extensions, str):
                exts = [extensions]
            else:
                exts = extensions

            for ext in exts:
                ext_lower = ext.lower()
                if not ext_lower.startswith("."):
                    ext_lower = "." + ext_lower
                _LANGUAGE_EXTRACTORS[ext_lower] = func

            return func

        return decorator
    else:
        # Used as regular function: register_language_extractor(['.ext'], factory)
        if isinstance(extensions, str):
            extensions = [extensions]

        for ext in extensions:
            ext_lower = ext.lower()
            if not ext_lower.startswith("."):
                ext_lower = "." + ext_lower
            _LANGUAGE_EXTRACTORS[ext_lower] = extractor_factory
        return None


def _get_symbol_extractor(filepath: str) -> Optional[Any]:
    """Get a suitable symbol extractor based on the file extension"""
    ext = os.path.splitext(filepath)[1].lower()

    # Check the registered extractors
    if ext in _LANGUAGE_EXTRACTORS:
        try:
            return _LANGUAGE_EXTRACTORS[ext]()
        except Exception:
            return None

    return None


# Initialize the built-in extractors at module load time
# Import the language_extractors module to trigger automatic registration
try:
    import haijunbot.haijunbot_agent.language_extractors  # noqa: F401
except (ImportError, Exception):
    pass


def extract_symbols_from_file(filepath: str) -> list[dict[str, Any]]:
    """Extract symbols from a file using tree-sitter or AST"""
    extractor = _get_symbol_extractor(filepath)
    if not extractor:
        return []

    try:
        content = read_text_file(filepath, errors="ignore")
        symbols = extractor.extract_symbols(filepath, content)

        # Convert Symbol objects to dict format
        result = []
        for symbol in symbols:
            result.append(
                {
                    "name": symbol.name,
                    "type": symbol.kind,
                    "line": symbol.line_start,
                    "signature": symbol.signature or f"{symbol.kind} {symbol.name}",
                }
            )

        return result
    except Exception:
        return []


def format_symbols_output(filepath: str, symbols: list[dict[str, Any]]) -> str:
    """Format a symbol list into an output string"""
    if not symbols:
        return ""

    # Group symbols by type
    by_type: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols:
        symbol_type = symbol["type"]
        if symbol_type not in by_type:
            by_type[symbol_type] = []
        by_type[symbol_type].append(symbol)

    # Sort symbols by line number within each type
    for symbol_type in by_type:
        by_type[symbol_type].sort(key=lambda x: x["line"])

    output_lines = [f"\n📋 File symbols: {filepath}"]
    output_lines.append("─" * 60)

    # Type display names
    type_names = {
        "function": "function",
        "async_function": "async function",
        "class": "class",
        "struct": "struct",
        "enum": "enum",
        "interface": "interface",
        "trait": "trait",
        "variable": "variable",
        "constant": "constant",
    }

    for symbol_type, type_symbols in sorted(by_type.items()):
        type_name = type_names.get(symbol_type, symbol_type)
        output_lines.append(f"\n{type_name} ({len(type_symbols)} items):")
        for symbol in type_symbols:
            line_info = f"  line {symbol['line']:4d}: {symbol['name']}"
            if "signature" in symbol and symbol["signature"]:
                sig = symbol["signature"].strip()
                if len(sig) > 50:
                    sig = sig[:47] + "..."
                line_info += f" - {sig}"
            output_lines.append(line_info)

    output_lines.append("─" * 60)
    output_lines.append("")

    return "\n".join(output_lines)


def file_context_handler(user_input: str, agent_: Any) -> Tuple[str, bool]:
    """
    Extract file paths from the input, extract symbols from these files, and append the symbol list to the input.

    Args:
        user_input: The user input string.
        agent_: The Agent instance.

    Returns:
        A tuple containing the modified user input and a boolean indicating whether further processing should be skipped.
    """
    # Regular expression to find paths within single quotes
    raw_paths = re.findall(r"'([^']+)'", user_input)
    # Convert to absolute paths and deduplicate by absolute path while preserving order
    abs_to_raws: dict[str, list[str]] = {}
    file_paths = []
    for _raw in raw_paths:
        abs_path = os.path.abspath(_raw)
        if abs_path not in abs_to_raws:
            abs_to_raws[abs_path] = []
            file_paths.append(abs_path)
        abs_to_raws[abs_path].append(_raw)

    if not file_paths:
        return user_input, False

    added_context = ""

    for abs_path in file_paths:
        if os.path.isfile(abs_path) and is_text_file(abs_path):
            # Extract symbols from the file
            symbols = extract_symbols_from_file(abs_path)

            if symbols:
                # Keep the original path marker and append the symbol information as supplementary context
                # This preserves the user's original reference to the file while adding symbol details
                added_context += format_symbols_output(abs_path, symbols)

    if added_context:
        user_input = user_input.strip() + added_context

    return user_input, False


# ============================================================================
# How to add support for a new language
# ============================================================================
#
# Recommended approach: create a new file in the language_extractors/ directory
#
# 1. Create a new file: haijunbot_agent/language_extractors/java_extractor.py
#
#    # -*- coding: utf-8 -*-
#    """Java language symbol extractor."""
#
#    from typing import Optional, Any, List
#    from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor
#    from haijunbot.haijunbot_code_agent.code_analyzer.symbol_extractor import Symbol
#
#    def create_java_extractor() -> Optional[Any]:
#        try:
#            from tree_sitter import Language, Parser
#            import tree_sitter_java
#
#            JAVA_LANGUAGE = tree_sitter_java.language()
#            JAVA_SYMBOL_QUERY = """
#            (method_declaration
#              name: (identifier) @method.name)
#
#            (class_declaration
#              name: (identifier) @class.name)
#            """
#
#            class JavaSymbolExtractor:
#                def __init__(self):
#                    self.language = JAVA_LANGUAGE
#                    self.parser = Parser()
#                    self.parser.set_language(self.language)
#                    self.symbol_query = JAVA_SYMBOL_QUERY
#
#                def extract_symbols(self, file_path: str, content: str) -> List[Any]:
#                    try:
#                        tree = self.parser.parse(bytes(content, "utf8"))
#                        query = self.language.query(self.symbol_query)
#                        captures = query.captures(tree.root_node)
#
#                        symbols = []
#                        for node, name in captures:
#                            kind_map = {
#                                "method.name": "method",
#                                "class.name": "class",
#                            }
#                            symbol_kind = kind_map.get(name)
#                            if symbol_kind:
#                                symbols.append(Symbol(
#                                    name=node.text.decode('utf8'),
#                                    kind=symbol_kind,
#                                    file_path=file_path,
#                                    line_start=node.start_point[0] + 1,
#                                    line_end=node.end_point[0] + 1,
#                                ))
#                        return symbols
#                    except Exception:
#                        return []
#
#            return JavaSymbolExtractor()
#        except (ImportError, Exception):
#            return None
#
#    def register_java_extractor() -> None:
#        register_language_extractor(['.java', '.jav'], create_java_extractor)
#
#
# 2. Add the import and registration in language_extractors/__init__.py:
#
#    try:
#        from .java_extractor import register_java_extractor
#        register_java_extractor()
#    except (ImportError, Exception):
#        pass
#
#
# Method 2: register dynamically at runtime (not recommended, but usable)
#
# from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor
#
# def create_ruby_extractor():
#     # ... implement the extractor ...
#     return RubyExtractor()
#
# register_language_extractor('.rb', create_ruby_extractor)
#
# ============================================================================
