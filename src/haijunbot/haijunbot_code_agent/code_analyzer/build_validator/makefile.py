"""
Makefile build validator module

Provides build validation for Makefile projects.
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


class MakefileBuildValidator(BuildValidatorBase):
    """Makefile build validator"""

    BUILD_SYSTEM_NAME = "Makefile"
    SUPPORTED_LANGUAGES = ["c", "cpp"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Try running make (if a Makefile exists)
        makefile = os.path.join(self.project_root, "Makefile")
        if not os.path.exists(makefile):
            duration = time.time() - start_time
            PrettyOutput.auto_print(
                f"❌ Makefile build validation failed (took {duration:.2f}s)"
            )
            PrettyOutput.auto_print("Error message: Makefile does not exist")
            return BuildResult(
                success=False,
                output="Makefile does not exist",
                error_message="Makefile does not exist",
                build_system=BuildSystem.C_MAKEFILE,
                duration=duration,
            )

        # Try make -n (dry-run) to validate the syntax
        returncode, stdout, stderr = self._run_command(
            ["make", "-n"],
            timeout=10,
        )
        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr
        if success:
            PrettyOutput.auto_print(
                f"✅ Makefile build validation succeeded (took {duration:.2f}s)"
            )
        else:
            PrettyOutput.auto_print(
                f"❌ Makefile build validation failed (took {duration:.2f}s)"
            )
            PrettyOutput.auto_print(f"Error message: Makefile syntax check failed\n{output[:500]}")
        return BuildResult(
            success=success,
            output=output,
            error_message=None if success else "Makefile syntax check failed",
            build_system=BuildSystem.C_MAKEFILE,
            duration=duration,
        )
