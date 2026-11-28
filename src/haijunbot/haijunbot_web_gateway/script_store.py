"""File storage for browser extension scripts.

Purpose: lets the Agent export user scripts from the extension to the gateway data directory, or read script content
from that directory and install it back into the extension, avoiding transferring large blocks of raw script text.

Directory convention: ``{get_data_dir()}/browser_scripts/{name}.js``

Security convention: script names allow only safe characters, and the final path must remain within the
``browser_scripts`` directory to prevent directory traversal (``../``, absolute paths, etc.).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

# Allowed character set for script names: letters, digits, underscores, hyphens, dots
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

# Script file extension
_SCRIPT_EXT = ".js"

# browser_scripts subdirectory name
_SCRIPTS_DIR_NAME = "browser_scripts"


class ScriptStoreError(Exception):
    """Errors related to script storage (invalid name, path escape, file not found, etc.)."""


def _get_scripts_dir() -> str:
    """Return the script storage directory (absolute path), creating it automatically if it does not exist."""
    # Lazy import to avoid module-level circular dependencies
    from haijunbot.haijunbot_utils.config import get_data_dir

    scripts_dir = os.path.join(get_data_dir(), _SCRIPTS_DIR_NAME)
    os.makedirs(scripts_dir, exist_ok=True)
    return os.path.realpath(scripts_dir)


def sanitize_script_name(name: Any) -> str:
    """Validate and normalize the script name, returning a safe name without the extension.

    Rules:
    - Must be a non-empty string;
    - Only ``[A-Za-z0-9_.-]`` is allowed;
    - Reject ``.``, ``..``, and hidden names starting with ``.``;
    - Reject names containing path separators or the ``..`` substring;
    - A trailing ``.js`` is stripped to avoid ``a.js.js``.

    Args:
        name: The original script name (may include a ``.js`` suffix)

    Returns:
        str: The normalized safe name (without extension)

    Raises:
        ScriptStoreError: raised when the name is invalid
    """
    if not isinstance(name, str):
        raise ScriptStoreError("name must be a string")
    raw = name.strip()
    if not raw:
        raise ScriptStoreError("name is required")
    # Strip one trailing .js (case-insensitive) to avoid a.js.js
    if raw.lower().endswith(_SCRIPT_EXT):
        raw = raw[: -len(_SCRIPT_EXT)].strip()
    if not raw:
        raise ScriptStoreError("name is required")
    if raw in (".", ".."):
        raise ScriptStoreError(f"invalid script name: {name}")
    if "/" in raw or "\\" in raw:
        raise ScriptStoreError(f"invalid script name: {name}")
    if ".." in raw:
        raise ScriptStoreError(f"invalid script name: {name}")
    if raw.startswith("."):
        raise ScriptStoreError(f"invalid script name: {name}")
    if not _SAFE_NAME_RE.match(raw):
        raise ScriptStoreError(f"invalid script name: {name}")
    return raw


def resolve_script_path(name: Any) -> str:
    """Resolve the script name to an absolute file path and verify it lies within the script directory.

    Args:
        name: The script name (may include a ``.js`` suffix)

    Returns:
        str: The absolute path to the script file

    Raises:
        ScriptStoreError: raised when the name is invalid or the path escapes the directory
    """
    safe_name = sanitize_script_name(name)
    scripts_dir = _get_scripts_dir()
    candidate = os.path.realpath(os.path.join(scripts_dir, safe_name + _SCRIPT_EXT))
    # Double-check: the resolved path must still be inside the script directory
    if os.path.dirname(candidate) != scripts_dir:
        raise ScriptStoreError(f"path escapes scripts dir: {name}")
    if not candidate.startswith(scripts_dir + os.sep):
        raise ScriptStoreError(f"path escapes scripts dir: {name}")
    return candidate


def save_script(name: Any, content: Any) -> Dict[str, Any]:
    """Write the script content into the script directory (overwriting same-named files).

    Args:
        name: The script name
        content: The script source code

    Returns:
        Dict[str, Any]: ``{"name": str, "path": str, "size": int}``

    Raises:
        ScriptStoreError: raised when the name is invalid or the content is not a string
    """
    if not isinstance(content, str):
        raise ScriptStoreError("content must be a string")
    if not content.strip():
        raise ScriptStoreError("content is required")
    path = resolve_script_path(name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {
        "name": sanitize_script_name(name),
        "path": path,
        "size": len(content.encode("utf-8")),
    }


def load_script(name: Any) -> Dict[str, Any]:
    """Read script content.

    Args:
        name: The script name

    Returns:
        Dict[str, Any]: ``{"name": str, "content": str, "size": int}``

    Raises:
        ScriptStoreError: raised when the name is invalid or the file does not exist
    """
    path = resolve_script_path(name)
    if not os.path.isfile(path):
        raise ScriptStoreError(f"script not found: {sanitize_script_name(name)}")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return {
        "name": sanitize_script_name(name),
        "content": content,
        "size": len(content.encode("utf-8")),
    }


def list_scripts() -> List[Dict[str, Any]]:
    """List all scripts in the script directory, ordered by modification time descending.

    Returns:
        List[Dict[str, Any]]: each item is ``{"name", "size", "updated_at"}``
    """
    scripts_dir = _get_scripts_dir()
    items: List[Dict[str, Any]] = []
    try:
        entries = os.listdir(scripts_dir)
    except OSError:
        return items
    for entry in entries:
        if not entry.lower().endswith(_SCRIPT_EXT):
            continue
        full = os.path.join(scripts_dir, entry)
        if not os.path.isfile(full):
            continue
        try:
            stat = os.stat(full)
        except OSError:
            continue
        items.append(
            {
                "name": entry[: -len(_SCRIPT_EXT)],
                "size": stat.st_size,
                "updated_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return items
