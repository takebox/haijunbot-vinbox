"""
Java Maven build validator module

Provides build validation for Java Maven projects.
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


class JavaMavenBuildValidator(BuildValidatorBase):
    """Java Maven build validator"""

    BUILD_SYSTEM_NAME = "Maven"
    SUPPORTED_LANGUAGES = ["java"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Use mvn compile for compilation validation
        cmd = ["mvn", "compile", "-q"]  # -q unattended mode

        returncode, stdout, stderr = self._run_command(cmd, timeout=60)
        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr

        if success:
            PrettyOutput.auto_print(f"✅ Maven build validation succeeded (took {duration:.2f}s)")
        else:
            PrettyOutput.auto_print(f"❌ Maven build validation failed (took {duration:.2f}s)")
            PrettyOutput.auto_print(f"Error message: Maven compilation failed\n{output[:500]}")

        return BuildResult(
            success=success,
            output=output,
            error_message=None if success else "Maven compilation failed",
            build_system=BuildSystem.JAVA_MAVEN,
            duration=duration,
        )
