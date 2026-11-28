"""
Go build validator module

Provides build validation for Go projects.
"""

import time
from typing import List
from typing import Optional
from haijunbot.haijunbot_utils.output import PrettyOutput

#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class GoBuildValidator(BuildValidatorBase):
    """Go build validator (uses go test, including compilation and testing)"""

    BUILD_SYSTEM_NAME = "Go Build"
    SUPPORTED_LANGUAGES = ["go"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Use go test for build and test validation (it will automatically compile and run tests)
        cmd = ["go", "test", "./..."]

        returncode, stdout, stderr = self._run_command(cmd, timeout=30)
        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr

        if not success:
            # Try to parse the error information (including compilation errors and test failures)
            error_message = self._parse_go_errors(output)
            PrettyOutput.auto_print(f"❌ Go build validation failed (took {duration:.2f}s)")
            if error_message:
                PrettyOutput.auto_print(f"Error message:\n{error_message}")
            else:
                PrettyOutput.auto_print(f"Output:\n{output[:500]}")
        else:
            error_message = None
            PrettyOutput.auto_print(f"✅ Go build validation succeeded (took {duration:.2f}s)")

        return BuildResult(
            success=success,
            output=output,
            error_message=error_message,
            build_system=BuildSystem.GO,
            duration=duration,
        )

    def _parse_go_errors(self, output: str) -> str:
        """Parse Go's error output (including compilation errors and test failures)"""
        # Simplified handling: extract key error information
        lines = output.split("\n")
        errors = []
        for line in lines:
            # Match compilation errors
            if "error:" in line.lower() or "cannot" in line.lower():
                errors.append(line.strip())
            # Match test failures
            elif "--- FAIL:" in line or "FAIL" in line:
                errors.append(line.strip())
            # Match assertion failures
            elif "got" in line.lower() and "want" in line.lower():
                errors.append(line.strip())
        return "\n".join(errors[:10]) if errors else output[:500]  # Limit the length
