# -*- coding: utf-8 -*-
"""Java language symbol extractor."""

from typing import Any
from typing import Optional

from haijunbot.haijunbot_agent.file_context_handler import register_language_extractor


def create_java_extractor() -> Optional[Any]:
    """Create Java symbol extractor using tree-sitter."""
    try:
        from haijunbot.haijunbot_code_agent.code_analyzer.languages.java_language import (
            JavaSymbolExtractor,
        )

        return JavaSymbolExtractor()
    except (ImportError, RuntimeError, Exception):
        # If there is no Java support in code_analyzer, try using tree-sitter directly
        try:
            import tree_sitter_java
            from tree_sitter import Language
            from tree_sitter import Parser

            from haijunbot.haijunbot_code_agent.code_analyzer.symbol_extractor import Symbol

            JAVA_LANGUAGE = tree_sitter_java.language()
            JAVA_SYMBOL_QUERY = """
            (method_declaration
              name: (identifier) @method.name)
            
            (class_declaration
              name: (identifier) @class.name)
            
            (interface_declaration
              name: (identifier) @interface.name)
            
            (field_declaration
              (variable_declarator
                name: (identifier) @field.name))
            """

            class TreeSitterJavaSymbolExtractor:
                def __init__(self) -> None:
                    # If a PyCapsule is passed in, it must be converted to a Language object
                    if not isinstance(JAVA_LANGUAGE, Language):
                        self.language = Language(JAVA_LANGUAGE)
                    else:
                        self.language = JAVA_LANGUAGE
                    self.parser = Parser()
                    # Use the language property instead of the set_language method
                    self.parser.language = self.language
                    self.symbol_query = JAVA_SYMBOL_QUERY

                def extract_symbols(
                    self, file_path: str, content: str
                ) -> list[dict[str, str]]:
                    try:
                        from tree_sitter import Query, QueryCursor

                        tree = self.parser.parse(bytes(content, "utf8"))
                        query = Query(self.language, self.symbol_query)
                        cursor = QueryCursor(query)
                        captures = cursor.captures(tree.root_node)

                        kind_map = {
                            "method.name": "method",
                            "class.name": "class",
                            "interface.name": "interface",
                            "field.name": "field",
                        }
                        symbols = []
                        for name, nodes in captures.items():
                            symbol_kind = kind_map.get(name)
                            if not symbol_kind:
                                continue
                            for node in nodes:
                                symbol = Symbol(
                                    name=(node.text or b"").decode("utf8"),
                                    kind=symbol_kind,
                                    file_path=file_path,
                                    line_start=node.start_point[0] + 1,
                                    line_end=node.end_point[0] + 1,
                                )
                                symbols.append(
                                    {
                                        "name": symbol.name,
                                        "kind": symbol.kind,
                                        "file_path": symbol.file_path,
                                        "line_start": str(symbol.line_start),
                                        "line_end": str(symbol.line_end),
                                    }
                                )
                        return symbols
                    except Exception:
                        return []

            return TreeSitterJavaSymbolExtractor()
        except (ImportError, Exception):
            return None


def register_java_extractor() -> None:
    """Register Java extractor for .java files."""
    register_language_extractor(".java", create_java_extractor)
