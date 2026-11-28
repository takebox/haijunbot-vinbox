# -*- coding: utf-8 -*-
"""Test helper functions"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict


def create_temp_file(content: str, suffix: str = ".py") -> Path:
    """Create a temporary file"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return Path(path)


def create_temp_directory() -> Path:
    """Create a temporary directory"""
    return Path(tempfile.mkdtemp())


def assert_dict_contains(subset: Dict[str, Any], superset: Dict[str, Any]) -> None:
    """Assert that a dictionary contains a subset"""
    for key, value in subset.items():
        assert key in superset, f"Key '{key}' not found in superset"
        assert superset[key] == value, (
            f"Value mismatch for key '{key}': expected {value}, got {superset[key]}"
        )
