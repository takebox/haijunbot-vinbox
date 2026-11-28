from abc import abstractmethod
from typing import List
from typing import Optional

from tree_sitter import Language
from tree_sitter import Node
from tree_sitter import Parser
from tree_sitter import Query
from tree_sitter import QueryCursor

from haijunbot.haijunbot_utils.output import PrettyOutput

from .symbol_extractor import Symbol
from .symbol_extractor import SymbolExtractor


class TreeSitterExtractor(SymbolExtractor):
    """
    A generic symbol extractor that uses tree-sitter for parsing.
    Subclasses must provide the language-specific details, such as the
    tree-sitter Language object and the symbol query.
    """

    def __init__(self, language: Language, symbol_query: str):
        self.language = language
        self.parser = Parser()
        # Set the language (tree-sitter's Parser needs a Language object)
        try:
            # Try using the set_language method (if available)
            if hasattr(self.parser, "set_language"):
                self.parser.set_language(self.language)
            else:
                # Otherwise assign the language attribute directly
                self.parser.language = self.language
        except (AttributeError, TypeError):
            # If both fail, try creating a Language object
            try:
                from tree_sitter import Language as LangClass

                try:
                    lang_obj = LangClass(language)
                    self.parser.language = lang_obj
                    self.language = lang_obj
                except Exception:
                    self.parser.language = language
            except Exception:
                # Final fallback: assign directly
                self.parser.language = language
        self.symbol_query = symbol_query

    def extract_symbols(self, file_path: str, content: str) -> List[Symbol]:
        """
        Parses the code with tree-sitter and extracts symbols based on the query.
        """
        # Check whether the content is empty or contains only whitespace
        if not content or not content.strip():
            return []

        symbols = []

        try:
            # Parse the code (tree-sitter can partially parse even with syntax errors)
            tree = self.parser.parse(bytes(content, "utf8"))

            # The tree-sitter parse method always returns a valid tree object
            # No need to check for a None value, continue processing

            # Try to construct the query
            query = None
            try:
                query = Query(self.language, self.symbol_query)
            except Exception as query_error:
                # Query construction failed (possibly a query syntax issue), silently return an empty list
                import os

                if os.getenv("DEBUG_TREE_SITTER", "").lower() in ("1", "true", "yes"):
                    PrettyOutput.auto_print(
                        f"Error creating query for {file_path}: {query_error}"
                    )
                return []

            # Use QueryCursor to execute the query
            # Even with syntax errors, tree-sitter can parse partially, so some symbols can still be extracted
            cursor = QueryCursor(query)
            matches = cursor.matches(tree.root_node)

            # matches is returned in the format: [(pattern_index, {capture_name: [nodes]})]
            for pattern_index, captures_dict in matches:
                for capture_name, nodes in captures_dict.items():
                    for node in nodes:
                        try:
                            # Skip error nodes (tree-sitter marks syntax errors with ERROR nodes)
                            # Error nodes usually do not have valid text content or location information
                            if node.type == "ERROR":
                                continue

                            symbol = self._create_symbol_from_capture(
                                node, capture_name, file_path
                            )
                            if symbol:
                                symbols.append(symbol)
                        except Exception:
                            # A single symbol extraction failure, continue processing other symbols
                            # This ensures that even if some symbol extractions fail, the successfully extracted symbols are still returned
                            continue

            # Even with syntax errors, return the symbols that were successfully extracted
            return symbols
        except Exception as e:
            # If parsing completely fails (not a syntax error, but another serious error), return an empty list
            # Only print the error message in debug mode
            import os

            if os.getenv("DEBUG_TREE_SITTER", "").lower() in ("1", "true", "yes"):
                PrettyOutput.auto_print(
                    f"Error extracting symbols from {file_path} with tree-sitter: {e}"
                )
            # Even if parsing fails, return the symbols already extracted (if any)
            return symbols

    @abstractmethod
    def _create_symbol_from_capture(
        self, node: Node, name: str, file_path: str
    ) -> Optional[Symbol]:
        """
        Creates a Symbol object from a tree-sitter query capture.
        This method must be implemented by subclasses to map capture names
        (e.g., "function.name") to Symbol attributes.
        """
        raise NotImplementedError
