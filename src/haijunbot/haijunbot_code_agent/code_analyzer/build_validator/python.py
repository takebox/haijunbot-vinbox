"""
Python build validator module

Provides build validation for Python projects.
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


class PythonBuildValidator(BuildValidatorBase):
    """Python build validator (including compilation and testing)"""

    BUILD_SYSTEM_NAME = "Python"
    SUPPORTED_LANGUAGES = ["python"]

    def _extract_python_errors(self, output: str) -> str:
        """Extract Python error information (including compilation errors and test failures)"""
        if not output:
            return ""

        lines = output.split("\n")
        errors = []
        in_error = False

        for line in lines:
            line_lower = line.lower()
            # Detect error keywords (including compilation errors and test failures)
            if any(
                keyword in line_lower
                for keyword in [
                    "error",
                    "failed",
                    "exception",
                    "traceback",
                    "syntaxerror",
                    "indentationerror",
                    "assertionerror",
                    "failed:",
                    "failures:",
                    "test",
                    "assert",
                ]
            ):
                in_error = True
                errors.append(line.strip())
            elif in_error and line.strip():
                # Continue collecting error-related lines
                if line.strip().startswith(
                    ("File", "  File", "    ", "E ", "FAILED", "FAILURES", "assert")
                ):
                    errors.append(line.strip())
                elif not line.strip().startswith("="):
                    # If a non-error-related line is encountered, stop collecting
                    if len(errors) > 0 and not any(
                        keyword in line_lower
                        for keyword in [
                            "error",
                            "failed",
                            "exception",
                            "assert",
                            "test",
                        ]
                    ):
                        break

        # If errors were collected, return the first 20 lines (limit the length)
        if errors:
            error_text = "\n".join(errors[:20])
            # If too long, truncate
            if len(error_text) > 1000:
                error_text = error_text[:1000] + "\n... (error message truncated)"
            return error_text

        # If no structured error was extracted, return the first 500 characters of the original output
        return output[:500] if output else ""

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Strategy 1: try using py_compile to compile the modified files
        if modified_files:
            errors = []
            error_outputs = []
            for file_path in modified_files:
                if not file_path.endswith(".py"):
                    continue
                full_path = os.path.join(self.project_root, file_path)
                if os.path.exists(full_path):
                    returncode, stdout, stderr = self._run_command(
                        ["python", "-m", "py_compile", full_path],
                        timeout=5,
                    )
                    if returncode != 0:
                        file_error_msg = f"{file_path}: {stderr}".strip()
                        errors.append(file_error_msg)
                        error_outputs.append(stdout + stderr)

            if errors:
                duration = time.time() - start_time
                # Merge all error outputs
                full_output = "\n".join(error_outputs)
                # Extract key error information
                error_message = self._extract_python_errors(full_output)
                if not error_message:
                    # If no structured error was extracted, use a simplified error list
                    error_message = "\n".join(errors[:5])  # Show errors for at most 5 files
                    if len(errors) > 5:
                        error_message += f"\n... there are also {len(errors) - 5} files with errors"
                PrettyOutput.auto_print(
                    f"❌ Python build validation failed (took {duration:.2f}s)"
                )
                PrettyOutput.auto_print(f"Error message:\n{error_message}")
                return BuildResult(
                    success=False,
                    output=full_output,
                    error_message=error_message,
                    build_system=BuildSystem.PYTHON,
                    duration=duration,
                )

        # Strategy 2: try running pytest (it will automatically compile and run tests, and automatically discover tests even without a config file)
        # First try pytest
        returncode, stdout, stderr = self._run_command(
            ["python", "-m", "pytest", "-v"],
            timeout=30,
        )
        # If the pytest command itself fails (e.g. not installed), try unittest
        if returncode == 1 and "No module named pytest" in stderr:
            # pytest not installed, try using unittest
            returncode, stdout, stderr = self._run_command(
                ["python", "-m", "unittest", "discover", "-v"],
                timeout=30,
            )

        duration = time.time() - start_time
        success = returncode == 0
        output = stdout + stderr

        # If it failed, extract key error information (including compilation errors and test failures)
        error_msg: Optional[str] = None
        if not success:
            error_msg = self._extract_python_errors(output)
            if not error_msg:
                # Check whether it is the "no tests found" case (this does not count as a failure)
                if (
                    "no tests ran" in output.lower()
                    or "no tests found" in output.lower()
                ):
                    # No test files, but the syntax check passed, treat it as success
                    PrettyOutput.auto_print(
                        f"✅ Python build validation succeeded (took {duration:.2f}s, no test files found)"
                    )
                    return BuildResult(
                        success=True,
                        output="Python syntax check passed (no test files found)",
                        error_message=None,
                        build_system=BuildSystem.PYTHON,
                        duration=duration,
                    )
                error_msg = "Python project validation failed (compilation or test failure)"
            PrettyOutput.auto_print(f"❌ Python build validation failed (took {duration:.2f}s)")
            if error_msg:
                PrettyOutput.auto_print(f"Error message:\n{error_msg}")
            else:
                PrettyOutput.auto_print(f"Output:\n{output[:500]}")
        else:
            PrettyOutput.auto_print(f"✅ Python build validation succeeded (took {duration:.2f}s)")

        return BuildResult(
            success=success,
            output=output,
            error_message=error_msg,
            build_system=BuildSystem.PYTHON,
            duration=duration,
        )
