"""
Build validation configuration management module

Manages project-level build validation configuration, supporting disabling build validation and performing only basic static checks.

The configuration uses read/write separation:
- Static user configuration (disable_build_validation / disable_reason / custom_build_command)
  is merged into the config.yaml build_validation config items, decided proactively by the user;
- Runtime state (has_been_asked / selected_build_system / disabled_at)
  is stored in a separate build_validation_state.yaml, recorded automatically by the program.
"""

import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import cast

import yaml  # type: ignore[import-untyped]

from haijunbot.haijunbot_utils.config import get_build_validation_config
from haijunbot.haijunbot_utils.config import update_build_validation_config
from haijunbot.haijunbot_utils.output import PrettyOutput

STATE_FILE_NAME = "build_validation_state.yaml"


class BuildValidationConfig:
    """Build validation configuration manager"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.config_dir = os.path.join(project_root, ".haijunbot")
        self.state_path = os.path.join(self.config_dir, STATE_FILE_NAME)
        self._state: Optional[Dict[str, Any]] = None

    # ---------- Runtime state (separate file) ----------

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        """Load the runtime state file"""
        if self._state is not None:
            return self._state

        if not os.path.exists(self.state_path):
            self._state = {}
            return self._state

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._state = yaml.safe_load(f) or {}
            return self._state
        except Exception as e:
            # If the config file is corrupted, return an empty config
            PrettyOutput.auto_print(f"⚠️ Failed to load build validation runtime state: {e}, using default config")
            self._state = {}
            return self._state

    def _save_state(self) -> bool:
        """Save the runtime state file"""
        try:
            self._ensure_config_dir()
            with open(self.state_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    self._state, f, allow_unicode=True, default_flow_style=False
                )
            return True
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to save build validation runtime state: {e}")
            return False

    # ---------- Static user configuration (config.yaml) ----------

    def is_build_validation_disabled(self) -> bool:
        """Check whether build validation is disabled"""
        config = get_build_validation_config()
        return cast(bool, config.get("disable_build_validation", False))

    def disable_build_validation(self, reason: Optional[str] = None) -> bool:
        """Disable build validation

        Args:
            reason: reason for disabling (optional)

        Returns:
            bool: whether the config was saved successfully
        """
        updates: Dict[str, Any] = {"disable_build_validation": True}
        if reason:
            updates["disable_reason"] = reason
        ok = update_build_validation_config(self.project_root, updates)
        if ok:
            # Record the project path at time of disabling (runtime state)
            state = self._load_state()
            state["disabled_at"] = str(Path(self.project_root).resolve())
            self._state = state
            self._save_state()
        return ok

    def enable_build_validation(self) -> bool:
        """Re-enable build validation"""
        ok = update_build_validation_config(
            self.project_root, {"disable_build_validation": False}
        )
        # Keep historical information, but clear the disable flag
        return ok

    def get_disable_reason(self) -> Optional[str]:
        """Get the reason for disabling"""
        config = get_build_validation_config()
        return config.get("disable_reason")

    def get_custom_build_command(self) -> Optional[str]:
        """Get the user's custom build command

        Returns:
            The build command string (e.g. "make && make test"), or None if not configured
        """
        config = get_build_validation_config()
        return config.get("custom_build_command")

    def set_custom_build_command(self, command: str) -> bool:
        """Save the user's custom build command

        Args:
            command: build command string (e.g. "make && make test")

        Returns:
            bool: whether the config was saved successfully
        """
        return update_build_validation_config(
            self.project_root, {"custom_build_command": command}
        )

    # ---------- Runtime state (separate file) ----------

    def has_been_asked(self) -> bool:
        """Check whether the user has already been asked"""
        state = self._load_state()
        return cast(bool, state.get("has_been_asked", False))

    def mark_as_asked(self) -> bool:
        """Mark as already asked"""
        state = self._load_state()
        state["has_been_asked"] = True
        self._state = state
        return self._save_state()

    def get_selected_build_system(self) -> Optional[str]:
        """Get the build system selected by the user

        Returns:
            The build system name (e.g. "rust", "python"), or None if not selected
        """
        state = self._load_state()
        return state.get("selected_build_system")

    def set_selected_build_system(self, build_system: str) -> bool:
        """Save the build system selected by the user

        Args:
            build_system: build system name (e.g. "rust", "python")

        Returns:
            bool: whether the config was saved successfully
        """
        state = self._load_state()
        state["selected_build_system"] = build_system
        self._state = state
        return self._save_state()
