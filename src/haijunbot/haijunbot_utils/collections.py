"""
Case-insensitive dictionary and other collection utility classes.

This module provides a case-insensitive dictionary implementation, used for handling configuration key access,
ensuring that the same key-value can be accessed correctly regardless of the case form.
"""

from typing import Any
from typing import Dict
from typing import Iterator
from typing import Mapping
from typing import Optional
from typing import Tuple
from typing import Union

from collections.abc import ItemsView
from collections.abc import KeysView
from collections.abc import ValuesView


class CaseInsensitiveDict(Mapping[str, Any]):
    """
    Case-insensitive dictionary class.

    This dictionary class allows accessing the same value using keys in any case form.
    It stores keys internally in lowercase, but preserves the original key names for iteration and display.

    Example:
        >>> d = CaseInsensitiveDict({'Content-Type': 'text/plain'})
        >>> d['content-type']
        'text/plain'
        >>> d['CONTENT-TYPE']
        'text/plain'
        >>> d['Content-Type']
        'text/plain'
        >>> list(d.keys())
        ['Content-Type']
    """

    def __init__(
        self, data: Optional[Union[Dict[str, Any], "CaseInsensitiveDict"]] = None
    ) -> None:
        """
        Initialize CaseInsensitiveDict.

        Args:
            data: Optional initial data, which can be a dictionary or another CaseInsensitiveDict
        """
        self._data: Dict[str, Any] = {}
        self._case_map: Dict[str, str] = {}  # Mapping of lowercase key -> original key

        if data is not None:
            if isinstance(data, CaseInsensitiveDict):
                # Copy from another CaseInsensitiveDict
                self._data = data._data.copy()
                self._case_map = data._case_map.copy()
            elif hasattr(data, "items"):
                # Initialize from a normal dictionary or other mapping type
                for key, value in data.items():
                    self[key] = value

    def __getitem__(self, key: str) -> Any:
        """
        Get a value by key, case-insensitively.

        Args:
            key: The key to look up

        Returns:
            The corresponding value

        Raises:
            KeyError: If the key does not exist
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string type, got {type(key).__name__}")

        lower_key = key.lower()
        if lower_key not in self._case_map:
            raise KeyError(key)

        return self._data[lower_key]

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set a key-value pair, case-insensitively.

        Args:
            key: The key to set
            value: The value to set
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string type, got {type(key).__name__}")

        lower_key = key.lower()
        # If the key already exists, keep the original key name; otherwise use the new key name
        if lower_key not in self._case_map:
            self._case_map[lower_key] = key  # Preserve the original key name
        self._data[lower_key] = value

    def __delitem__(self, key: str) -> None:
        """
        Delete a key-value pair, case-insensitively.

        Args:
            key: The key to delete

        Raises:
            KeyError: If the key does not exist
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string type, got {type(key).__name__}")

        lower_key = key.lower()
        if lower_key not in self._case_map:
            raise KeyError(key)

        del self._case_map[lower_key]
        del self._data[lower_key]

    def __contains__(self, key: object) -> bool:
        """
        Check whether a key exists, case-insensitively.

        Args:
            key: The key to check

        Returns:
            True if the key exists, otherwise False
        """
        if not isinstance(key, str):
            return False
        return key.lower() in self._case_map

    def __iter__(self) -> Iterator[str]:
        """
        Return an iterator over the keys, preserving the original case.

        Returns:
            An iterator over the keys
        """
        return iter(self._case_map.values())

    def __len__(self) -> int:
        """
        Return the number of key-value pairs in the dictionary.

        Returns:
            The number of key-value pairs
        """
        return len(self._data)

    def __repr__(self) -> str:
        """
        Return the string representation of the dictionary.

        Returns:
            The string representation
        """
        items = []
        for original_key in self._case_map.values():
            value = self._data[original_key.lower()]
            items.append(f"{original_key!r}: {value!r}")
        return f"CaseInsensitiveDict({{{', '.join(items)}}})"

    def __eq__(self, other: object) -> bool:
        """
        Compare whether two dictionaries are equal.

        Args:
            other: The object to compare

        Returns:
            True if equal, otherwise False
        """
        if not isinstance(other, CaseInsensitiveDict):
            return NotImplemented
        return self._data == other._data

    def copy(self) -> "CaseInsensitiveDict":
        """
        Create a shallow copy of the dictionary.

        Returns:
            A new CaseInsensitiveDict instance
        """
        return CaseInsensitiveDict(self)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get the value corresponding to a key, returning the default value if the key does not exist.

        Args:
            key: The key to look up
            default: The default value to return if the key does not exist

        Returns:
            The value corresponding to the key, or the default value
        """
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self) -> KeysView[str]:
        """
        Return a view of all keys, preserving the original case.

        Returns:
            A view object of the keys
        """
        return KeysView(self)

    def values(self) -> ValuesView[Any]:
        """
        Return a view of all values.

        Returns:
            A view object of the values
        """
        return ValuesView(self)

    def items(self) -> ItemsView[str, Any]:
        """
        Return a view of all key-value pairs, with keys preserving the original case.

        Returns:
            A view object of the key-value pairs
        """
        return ItemsView(self)

    def pop(self, key: str, *args: Any) -> Any:
        """
        Remove and return the value of the specified key.

        Args:
            key: The key to remove
            *args: The default value if the key does not exist (optional)

        Returns:
            The value corresponding to the key

        Raises:
            KeyError: If the key does not exist and no default value is provided
        """
        if not isinstance(key, str):
            raise TypeError(f"Key must be a string type, got {type(key).__name__}")

        lower_key = key.lower()
        if lower_key not in self._case_map:
            if args:
                return args[0]
            raise KeyError(key)

        self._case_map.pop(lower_key)
        value = self._data.pop(lower_key)
        return value

    def popitem(self) -> Tuple[str, Any]:
        """
        Remove and return the last key-value pair.

        Returns:
            The key-value pair

        Raises:
            KeyError: If the dictionary is empty
        """
        if not self._data:
            raise KeyError("Dictionary is empty")

        lower_key, value = self._data.popitem()
        original_key = self._case_map.pop(lower_key)
        return original_key, value

    def setdefault(self, key: str, default: Any = None) -> Any:
        """
        If the key exists, return the corresponding value; otherwise set the key's value to the default and return the default.

        Args:
            key: The key to look up
            default: The default value

        Returns:
            The value corresponding to the key, or the default value
        """
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def update(self, *args: Any, **kwargs: Any) -> None:
        """
        Update the dictionary.

        Args:
            *args: Can be another dictionary or an iterable of key-value pairs
            **kwargs: Key-value pairs in the form of keyword arguments (underscores will be converted to hyphens)
        """
        if args:
            other = args[0]
            if hasattr(other, "items"):
                for key, value in other.items():
                    self[key] = value
            else:
                for key, value in other:
                    self[key] = value

        for key, value in kwargs.items():
            # Convert underscores in keyword arguments to hyphens (for scenarios such as HTTP headers)
            normalized_key = key.replace("_", "-")
            self[normalized_key] = value

    def clear(self) -> None:
        """
        Clear the dictionary.
        """
        self._data.clear()
        self._case_map.clear()

    def lower_keys(self) -> Iterator[str]:
        """
        Return an iterator over the lowercase form of all keys.

        Returns:
            An iterator over the lowercase keys
        """
        return iter(self._case_map.keys())
