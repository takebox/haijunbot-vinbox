"""
Fallback build validator module

The fallback validator used when the build system cannot be detected.
"""

import os
import time
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional

from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class FallbackBuildValidator(BuildValidatorBase):
    """Fallback validator: used when the build system cannot be detected"""

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Strategy 1: perform basic syntax checks based on file extensions
        if modified_files:
            errors = []
            for file_path in modified_files:
                ext = os.path.splitext(file_path)[1].lower()
                full_path = os.path.join(self.project_root, file_path)

                if not os.path.exists(full_path):
                    continue

                # Python files: use py_compile
                if ext == ".py":
                    returncode, _, stderr = self._run_command(
                        ["python", "-m", "py_compile", full_path],
                        timeout=5,
                    )
                    if returncode != 0:
                        errors.append(f"{file_path}: {stderr}")

                # JavaScript files: try checking the syntax with node
                elif ext in (".js", ".mjs", ".cjs"):
                    returncode, _, stderr = self._run_command(
                        ["node", "--check", full_path],
                        timeout=5,
                    )
                    if returncode != 0:
                        errors.append(f"{file_path}: {stderr}")

            if errors:
                duration = time.time() - start_time
                PrettyOutput.auto_print(
                    f"❌ Basic syntax check failed (took {duration:.2f}s)"
                )
                PrettyOutput.auto_print(
                    f"Error message: syntax check failed\n{chr(10).join(errors[:5])}"
                )
                return BuildResult(
                    success=False,
                    output="\n".join(errors),
                    error_message="syntax check failed",
                    build_system=BuildSystem.UNKNOWN,
                    duration=duration,
                )

        duration = time.time() - start_time
        PrettyOutput.auto_print(
            f"✅ Basic syntax check passed (took {duration:.2f}s, no build system detected)"
        )
        return BuildResult(
            success=True,
            output="Basic syntax check passed (no build system detected)",
            error_message=None,
            build_system=BuildSystem.UNKNOWN,
            duration=duration,
        )
