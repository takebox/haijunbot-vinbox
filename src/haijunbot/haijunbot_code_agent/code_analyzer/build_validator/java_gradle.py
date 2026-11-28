"""
Java Gradle build validator module

Provides build validation for Java Gradle projects.
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


class JavaGradleBuildValidator(BuildValidatorBase):
    """Java Gradle build validator"""

    BUILD_SYSTEM_NAME = "Gradle"
    SUPPORTED_LANGUAGES = ["java"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Use gradle compileJava for compilation validation
        # Prefer gradlew (if it exists)
        gradlew = os.path.join(self.project_root, "gradlew")
        if os.path.exists(gradlew):
            cmd = ["./gradlew", "compileJava", "--quiet"]
        else:
            cmd = ["gradle", "compileJava", "--quiet"]

        returncode, stdout, stderr = self._run_command(cmd, timeout=60)
        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr

        if success:
            PrettyOutput.auto_print(f"✅ Gradle build validation succeeded (took {duration:.2f}s)")
        else:
            PrettyOutput.auto_print(f"❌ Gradle build validation failed (took {duration:.2f}s)")
            PrettyOutput.auto_print(f"Error message: Gradle compilation failed\n{output[:500]}")

        return BuildResult(
            success=success,
            output=output,
            error_message=None if success else "Gradle compilation failed",
            build_system=BuildSystem.JAVA_GRADLE,
            duration=duration,
        )
