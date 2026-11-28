import json
import os
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional


@dataclass
class Symbol:
    """Represents a single symbol in the code."""

    name: str
    kind: str  # e.g.: 'function', 'class', 'variable', 'import'
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    # Add more fields as needed, e.g. parent scope
    parent: Optional[str] = None
    # Definition location (for references/calls, points to the symbol's definition location)
    definition_location: Optional["Symbol"] = None  # Reference pointing to the definition Symbol
    is_definition: bool = False  # True if this symbol is a definition, False if it is a reference/call


class SymbolTable:
    """Stores and provides access to symbols in the project."""

    def __init__(self, cache_dir: Optional[str] = None):
        # Dictionary storing symbols by name, for fast lookup
        # A symbol name may appear in multiple files, so a list is used
        self.symbols_by_name: Dict[str, List[Symbol]] = {}
        # Dictionary storing symbols by file
        self.symbols_by_file: Dict[str, List[Symbol]] = {}
        # Tracks file modification times for cache invalidation
        self._file_mtimes: Dict[str, float] = {}
        # Cache directory for persistent storage
        self.cache_dir = cache_dir or ".haijunbot/symbol_cache"
        # Load cached data if available
        self._load_from_cache()

    def _get_cache_file(self) -> str:
        """Get the cache file path."""
        return os.path.join(self.cache_dir, "symbol_table.json")

    def _load_from_cache(self) -> None:
        """Load the symbol table data from the cache file."""
        cache_file = self._get_cache_file()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Convert the JSON data back into Symbol objects
                self.symbols_by_name = self._deserialize_symbols(
                    data.get("symbols_by_name", {})
                )
                self.symbols_by_file = self._deserialize_symbols(
                    data.get("symbols_by_file", {})
                )
                # Load the file modification times
                self._file_mtimes = data.get("file_mtimes", {})
            except Exception:
                # Start with an empty table if the cache fails to load
                pass

    def _save_to_cache(self) -> None:
        """Save the symbol table data to the cache file."""
        try:
            # Ensure the cache directory exists
            os.makedirs(self.cache_dir, exist_ok=True)
            cache_file = self._get_cache_file()

            # Update the file modification times before saving
            self._update_file_mtimes()

            # Serialize the symbols for JSON storage
            data = {
                "symbols_by_name": self._serialize_symbols(self.symbols_by_name),
                "symbols_by_file": self._serialize_symbols(self.symbols_by_file),
                "file_mtimes": self._file_mtimes,
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            # Continue without caching if saving fails
            pass

    def _serialize_symbols(
        self, symbol_dict: Dict[str, List[Symbol]]
    ) -> Dict[str, List[dict]]:
        """Convert Symbol objects into serializable dictionaries."""
        serialized = {}
        for key, symbols in symbol_dict.items():
            serialized[key] = [self._symbol_to_dict(symbol) for symbol in symbols]
        return serialized

    def _deserialize_symbols(
        self, symbol_dict: Dict[str, List[dict]]
    ) -> Dict[str, List[Symbol]]:
        """Convert serialized dictionaries back into Symbol objects."""
        deserialized = {}
        for key, symbol_data_list in symbol_dict.items():
            deserialized[key] = [
                self._dict_to_symbol(data) for data in symbol_data_list
            ]
        return deserialized

    def _symbol_to_dict(self, symbol: Symbol) -> dict:
        """Convert a Symbol object into a dictionary."""
        result = {
            "name": symbol.name,
            "kind": symbol.kind,
            "file_path": symbol.file_path,
            "line_start": symbol.line_start,
            "line_end": symbol.line_end,
            "signature": symbol.signature,
            "docstring": symbol.docstring,
            "parent": symbol.parent,
            "is_definition": getattr(symbol, "is_definition", False),
        }
        # Serialize the definition location (only save basic info to avoid circular references)
        if hasattr(symbol, "definition_location") and symbol.definition_location:
            result["definition_location"] = {
                "file_path": symbol.definition_location.file_path,
                "line_start": symbol.definition_location.line_start,
                "line_end": symbol.definition_location.line_end,
                "name": symbol.definition_location.name,
            }
        return result

    def _dict_to_symbol(self, data: dict) -> Symbol:
        """Convert a dictionary back into a Symbol object."""
        symbol = Symbol(
            name=data["name"],
            kind=data["kind"],
            file_path=data["file_path"],
            line_start=data["line_start"],
            line_end=data["line_end"],
            signature=data.get("signature"),
            docstring=data.get("docstring"),
            parent=data.get("parent"),
            is_definition=data.get("is_definition", False),
        )
        # Restore the definition location (create a temporary Symbol object)
        if "definition_location" in data and data["definition_location"]:
            def_loc = data["definition_location"]
            symbol.definition_location = Symbol(
                name=def_loc["name"],
                kind="",  # Unknown type
                file_path=def_loc["file_path"],
                line_start=def_loc["line_start"],
                line_end=def_loc["line_end"],
            )
        return symbol

    def add_symbol(self, symbol: Symbol, save_to_cache: bool = False) -> None:
        """Add a symbol to the table.

        Args:
            symbol: the symbol to add
            save_to_cache: if True, save to cache immediately. Defaults to False for performance.
                          Use save_cache() after batch operations to save all symbols at once.
        """
        if symbol.name not in self.symbols_by_name:
            self.symbols_by_name[symbol.name] = []
        self.symbols_by_name[symbol.name].append(symbol)

        if symbol.file_path not in self.symbols_by_file:
            self.symbols_by_file[symbol.file_path] = []
        self.symbols_by_file[symbol.file_path].append(symbol)

        # Only save to cache when explicitly requested (for performance reasons)
        if save_to_cache:
            self._save_to_cache()

    def save_cache(self) -> None:
        """Save the entire symbol table to cache. Call this method after batch operations."""
        self._save_to_cache()

    def find_symbol(self, name: str, file_path: Optional[str] = None) -> List[Symbol]:
        """
        Find a symbol by name.
        If file_path is provided, the search is limited to that file.
        """
        if file_path:
            return [s for s in self.get_file_symbols(file_path) if s.name == name]
        return self.symbols_by_name.get(name, [])

    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """Get all symbols in a specific file."""
        return self.symbols_by_file.get(file_path, [])

    def clear_file_symbols(self, file_path: str) -> None:
        """Remove all symbols associated with a specific file."""
        if file_path in self.symbols_by_file:
            symbols_to_remove = self.symbols_by_file.pop(file_path)
            for symbol in symbols_to_remove:
                if symbol.name in self.symbols_by_name:
                    self.symbols_by_name[symbol.name] = [
                        s
                        for s in self.symbols_by_name[symbol.name]
                        if s.file_path != file_path
                    ]
                    if not self.symbols_by_name[symbol.name]:
                        del self.symbols_by_name[symbol.name]

            # Remove the file modification time tracking
            if file_path in self._file_mtimes:
                del self._file_mtimes[file_path]

            # Save to cache after clearing
            self._save_to_cache()

    def _update_file_mtimes(self) -> None:
        """Update the modification times of all tracked files."""
        for file_path in list(self.symbols_by_file.keys()):
            if os.path.exists(file_path):
                try:
                    self._file_mtimes[file_path] = os.path.getmtime(file_path)
                except Exception:
                    # Remove from tracking if the modification time cannot be obtained
                    self._file_mtimes.pop(file_path, None)

    def is_file_stale(self, file_path: str) -> bool:
        """Check whether the file has been modified since it was cached.

        Args:
            file_path: the file path to check

        Returns:
            True if the file is newer than the cache, otherwise False
        """
        if file_path not in self.symbols_by_file:
            # The file is not in the cache, treat it as stale (needs loading)
            return True

        if file_path not in self._file_mtimes:
            # No recorded modification time, treat it as stale
            return True

        if not os.path.exists(file_path):
            # The file does not exist, do not treat it as stale (it will be handled by clear_file_symbols)
            return False

        try:
            current_mtime = os.path.getmtime(file_path)
            cached_mtime = self._file_mtimes.get(file_path, 0)
            return current_mtime > cached_mtime
        except Exception:
            # If the modification time cannot be obtained, assume it is not stale
            return False


class SymbolExtractor:
    """Extracts symbols from source code files."""

    def extract_symbols(self, file_path: str, content: str) -> List[Symbol]:
        """
        Extract symbols from the code (functions, classes, variables, etc.).
        This method should be implemented by subclasses for specific languages.
        """
        raise NotImplementedError("Subclasses must implement this method.")
