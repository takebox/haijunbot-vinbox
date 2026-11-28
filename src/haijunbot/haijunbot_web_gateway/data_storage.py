"""
Data storage module

Provides a unified Key-Value storage facility to support the data persistence needs of the Agent gateway.
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from haijunbot.haijunbot_utils.config import get_data_dir


# Key regex pattern: only letters, digits, underscores, and hyphens are allowed
KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _get_storage_dir() -> Path:
    """
    Get the data storage directory path.

    Returns:
        Path: The storage directory path
    """
    storage_dir = Path(get_data_dir()) / "data_store"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def _validate_key(key: str) -> tuple[bool, Optional[str]]:
    """
    Validate the Key format.

    Args:
        key: The Key value to validate

    Returns:
        tuple[bool, Optional[str]]: (whether valid, error message)
    """
    if not key:
        return False, "Key cannot be empty"

    if not KEY_PATTERN.match(key):
        return (
            False,
            "Key contains invalid characters. Only alphanumeric, underscore, and hyphen are allowed.",
        )

    return True, None


def _get_file_path(key: str) -> Path:
    """
    Get the file path corresponding to the Key.

    Args:
        key: Data Key

    Returns:
        Path: The file path
    """
    return _get_storage_dir() / f"{key}.json"


def save_data(key: str, value: Any) -> tuple[bool, Optional[str]]:
    """
    Save data to storage.

    Args:
        key: Data Key
        value: The value to store (must be JSON-serializable)

    Returns:
        tuple[bool, Optional[str]]: (whether successful, error message)
    """
    # Validate the Key
    is_valid, error = _validate_key(key)
    if not is_valid:
        return False, error

    try:
        file_path = _get_file_path(key)

        # Use atomic write: write to a temp file first, then rename
        temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)

            # Atomic rename
            os.replace(temp_path, file_path)
            return True, None
        except Exception as e:
            # Clean up the temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    except Exception as e:
        return False, f"Failed to save data: {str(e)}"


def load_data(key: str) -> tuple[bool, Any, Optional[str]]:
    """
    Read data from storage.

    Args:
        key: Data Key

    Returns:
        tuple[bool, Any, Optional[str]]: (whether successful, data value, error message)
    """
    # Validate the Key
    is_valid, error = _validate_key(key)
    if not is_valid:
        return False, None, error

    try:
        file_path = _get_file_path(key)

        if not file_path.exists():
            return False, None, "Key not found"

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return True, data, None
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON format: {str(e)}"
    except Exception as e:
        return False, None, f"Failed to load data: {str(e)}"


def delete_data(key: str) -> tuple[bool, Optional[str]]:
    """
    Delete data from storage.

    Args:
        key: Data Key

    Returns:
        tuple[bool, Optional[str]]: (whether successful, error message)
    """
    # Validate the Key
    is_valid, error = _validate_key(key)
    if not is_valid:
        return False, error

    try:
        file_path = _get_file_path(key)

        if not file_path.exists():
            return False, "Key not found"

        file_path.unlink()
        return True, None
    except Exception as e:
        return False, f"Failed to delete data: {str(e)}"
