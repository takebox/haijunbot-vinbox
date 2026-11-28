# -*- coding: utf-8 -*-
"""Optimizer configuration management module."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path


def load_additional_notes(crate_dir: Path) -> str:
    """Load additional notes from the configuration file."""
    try:
        from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON

        # Try to read the configuration from the project root (parent or sibling of crate_dir)
        # First try the parent directory of crate_dir
        project_root = crate_dir.parent
        config_path = project_root / ".haijunbot" / "c2rust" / CONFIG_JSON
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    return str(config.get("additional_notes", "") or "").strip()
        # If not found in the parent directory, try the current directory
        config_path = crate_dir / ".haijunbot" / "c2rust" / CONFIG_JSON
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    return str(config.get("additional_notes", "") or "").strip()
    except Exception as e:
        save_exception(
            e, module="haijunbot_c2rust.optimizer_config", function="load_additional_notes"
        )
        pass
    return ""


def append_additional_notes(prompt: str, additional_notes: str) -> str:
    """
    Append additional notes to the end of the prompt (if present).

    Args:
        prompt: Original prompt
        additional_notes: Additional notes

    Returns:
        The prompt with the additional notes appended
    """
    if additional_notes and additional_notes.strip():
        return (
            prompt + "\n\n" + "[Additional Notes (User-Defined)]\n" + additional_notes.strip()
        )
    return prompt
