#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Custom build validator module

Supports users defining a custom build command in the configuration file for validation.
"""

import time
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.output import PrettyOutput

from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class CustomBuildValidator(BuildValidatorBase):
    """Custom build validator"""

    BUILD_SYSTEM_NAME = "Custom"
    SUPPORTED_LANGUAGES = ["*"]  # Supports all languages

    def __init__(
        self, project_root: str, timeout: int = 30, command: Optional[str] = None
    ):
        super().__init__(project_root, timeout)
        self.custom_command = command
        # Import the configuration manager
        from haijunbot.haijunbot_code_agent.build_validation_config import (
            BuildValidationConfig,
        )

        self.config = BuildValidationConfig(project_root)
        # If no command was passed in, read it from the config file
        if self.custom_command is None:
            self.custom_command = self.config.get_custom_build_command()

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        """Validate the build

        Args:
            modified_files: list of modified files (this validator does not use this parameter)

        Returns:
            BuildResult: validation result
        """
        start_time = time.time()

        # Check whether a custom command is configured
        if not self.custom_command:
            duration = time.time() - start_time
            error_msg = "No custom build command configured, please set build_validation.custom_build_command in .haijunbot/config.yaml"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return BuildResult(
                success=False,
                output="",
                error_message=error_msg,
                build_system=BuildSystem.CUSTOM,
                duration=duration,
            )

        PrettyOutput.auto_print(f"🔧 Executing custom build command: {self.custom_command}")

        # Parse the command (supports complex commands, e.g. "make && make test")
        try:
            # Execute the command with bash to support shell features (such as &&, ||, pipes, etc.)
            returncode, stdout, stderr = self._run_command(
                ["bash", "-c", self.custom_command],
                cwd=self.project_root,
                timeout=self.timeout,
                capture_output=True,
            )
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Error while executing custom build command: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return BuildResult(
                success=False,
                output="",
                error_message=error_msg,
                build_system=BuildSystem.CUSTOM,
                duration=duration,
            )

        duration = time.time() - start_time
        success = returncode == 0
        output = stdout + stderr

        if success:
            PrettyOutput.auto_print(f"✅ Custom build validation succeeded (took {duration:.2f}s)")
        else:
            PrettyOutput.auto_print(
                f"❌ Custom build validation failed (took {duration:.2f}s, return code: {returncode})"
            )
            # Show the output (limit the length)
            output_preview = output[:1000] if len(output) > 1000 else output
            PrettyOutput.auto_print(f"Output:\n{output_preview}")
            if len(output) > 1000:
                PrettyOutput.auto_print(
                    f"... (output truncated, full output is {len(output)} characters total)"
                )

        return BuildResult(
            success=success,
            output=output,
            error_message=None
            if success
            else f"Custom build command returned error code: {returncode}",
            build_system=BuildSystem.CUSTOM,
            duration=duration,
        )
