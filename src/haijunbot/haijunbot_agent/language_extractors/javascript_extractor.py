# -*- coding: utf-8 -*-
"""JavaScript language symbol extractor."""

from typing import Any
from typing import List
from typing import Optional

from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor


def create_javascript_extractor() -> Optional[Any]:
    """Create JavaScript symbol extractor using tree-sitter."""
    try:
        import tree_sitter_javascript
        from tree_sitter import Language
        from tree_sitter import Parser

        from haijunbot.haijunbot_code_agent.code_analyzer.symbol_extractor import Symbol

        JS_LANGUAGE = tree_sitter_javascript.language()
        JS_SYMBOL_QUERY = """
        (function_declaration
          name: (identifier) @function.name)
        
        (method_definition
          name: (property_identifier) @method.name)
        
        (class_declaration
          name: (identifier) @class.name)
        
        (variable_declaration
          (variable_declarator
            name: (identifier) @variable.name))
        """

        class JSSymbolExtractor:
            def __init__(self) -> None:
                # If a PyCapsule is passed in, it must be converted to a Language object
                if not isinstance(JS_LANGUAGE, Language):
                    self.language = Language(JS_LANGUAGE)
                else:
                    self.language = JS_LANGUAGE
                self.parser = Parser()
                # Use the language property instead of the set_language method
                self.parser.language = self.language
                self.symbol_query = JS_SYMBOL_QUERY

            def extract_symbols(self, file_path: str, content: str) -> List[Any]:
                try:
                    from tree_sitter import Query, QueryCursor

                    tree = self.parser.parse(bytes(content, "utf8"))
                    query = Query(self.language, self.symbol_query)
                    cursor = QueryCursor(query)
                    captures = cursor.captures(tree.root_node)

                    kind_map = {
                        "function.name": "function",
                        "method.name": "method",
                        "class.name": "class",
                        "variable.name": "variable",
                    }
                    symbols = []
                    for name, nodes in captures.items():
                        symbol_kind = kind_map.get(name)
                        if not symbol_kind:
                            continue
                        for node in nodes:
                            symbols.append(
                                Symbol(
                                    name=(node.text or b"").decode("utf8"),
                                    kind=symbol_kind,
                                    file_path=file_path,
                                    line_start=node.start_point[0] + 1,
                                    line_end=node.end_point[0] + 1,
                                )
                            )
                    return symbols
                except Exception:
                    return []

        return JSSymbolExtractor()
    except (ImportError, Exception):
        return None


def register_javascript_extractor() -> None:
    """Register JavaScript extractor for .js and .jsx files."""
    register_language_extractor([".js", ".jsx"], create_javascript_extractor)
