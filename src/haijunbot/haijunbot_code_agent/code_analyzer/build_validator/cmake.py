"""
CMake build validator module

Provides build validation for CMake projects.
"""

import os
import tempfile
import time

from haijunbot.haijunbot_utils.output import PrettyOutput

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from typing import Optional

from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class CMakeBuildValidator(BuildValidatorBase):
    """CMake build validator"""

    BUILD_SYSTEM_NAME = "CMake"
    SUPPORTED_LANGUAGES = ["c", "cpp"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Strategy 1: try using cmake --build (if a build directory already exists)
        build_dirs = ["build", "cmake-build-debug", "cmake-build-release"]
        for build_dir in build_dirs:
            build_path = os.path.join(self.project_root, build_dir)
            if os.path.exists(build_path):
                returncode, stdout, stderr = self._run_command(
                    ["cmake", "--build", build_path],
                    timeout=60,
                )
                duration = time.time() - start_time
                success = returncode == 0
                output = stdout + stderr
                if success:
                    PrettyOutput.auto_print(
                        f"✅ CMake build validation succeeded (took {duration:.2f}s)"
                    )
                else:
                    PrettyOutput.auto_print(
                        f"❌ CMake build validation failed (took {duration:.2f}s)"
                    )
                    PrettyOutput.auto_print(f"Error message: CMake build failed\n{output[:500]}")
                return BuildResult(
                    success=success,
                    output=output,
                    error_message=None if success else "CMake build failed",
                    build_system=BuildSystem.C_CMAKE,
                    duration=duration,
                )

        # Strategy 2: only validate the CMakeLists.txt syntax
        with tempfile.TemporaryDirectory(prefix="cmake_check_") as tmpdir:
            returncode, stdout, stderr = self._run_command(
                ["cmake", "-S", ".", "-B", tmpdir],
                timeout=10,
            )
        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr
        if success:
            PrettyOutput.auto_print(f"✅ CMake configuration validation succeeded (took {duration:.2f}s)")
        else:
            PrettyOutput.auto_print(f"❌ CMake configuration validation failed (took {duration:.2f}s)")
            PrettyOutput.auto_print(f"Error message: CMake configuration failed\n{output[:500]}")
        return BuildResult(
            success=success,
            output=output,
            error_message=None if success else "CMake configuration failed",
            build_system=BuildSystem.C_CMAKE,
            duration=duration,
        )
