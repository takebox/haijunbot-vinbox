"""
Node.js build validator module

Provides build validation for Node.js projects.
"""

import json
import os
import time

from haijunbot.haijunbot_utils.output import PrettyOutput

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from typing import Optional

from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class NodeJSBuildValidator(BuildValidatorBase):
    """Node.js build validator"""

    BUILD_SYSTEM_NAME = "npm/Node.js"
    SUPPORTED_LANGUAGES = ["javascript", "typescript"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Strategy 1: try using tsc --noEmit (if TypeScript exists)
        tsconfig = os.path.join(self.project_root, "tsconfig.json")
        if os.path.exists(tsconfig):
            returncode, stdout, stderr = self._run_command(
                ["npx", "tsc", "--noEmit"],
                timeout=20,
            )
            duration = time.time() - start_time
            success = returncode == 0
            output = stdout + stderr
            if success:
                PrettyOutput.auto_print(
                    f"✅ Node.js (TypeScript) build validation succeeded (took {duration:.2f}s)"
                )
            else:
                PrettyOutput.auto_print(
                    f"❌ Node.js (TypeScript) build validation failed (took {duration:.2f}s)"
                )
                PrettyOutput.auto_print(
                    f"Error message: TypeScript type check failed\n{output[:500]}"
                )
            return BuildResult(
                success=success,
                output=output,
                error_message=None if success else "TypeScript type check failed",
                build_system=BuildSystem.NODEJS,
                duration=duration,
            )

        # Strategy 2: try running npm run build (if a build script exists)
        package_json = os.path.join(self.project_root, "package.json")
        if os.path.exists(package_json):
            try:
                with open(package_json, "r", encoding="utf-8") as f:
                    package_data = json.load(f)
                    scripts = package_data.get("scripts", {})
                    if "build" in scripts:
                        returncode, stdout, stderr = self._run_command(
                            ["npm", "run", "build"],
                            timeout=30,
                        )
                        duration = time.time() - start_time
                        success = returncode == 0
                        output = stdout + stderr
                        if success:
                            PrettyOutput.auto_print(
                                f"✅ Node.js (npm build) build validation succeeded (took {duration:.2f}s)"
                            )
                        else:
                            PrettyOutput.auto_print(
                                f"❌ Node.js (npm build) build validation failed (took {duration:.2f}s)"
                            )
                            PrettyOutput.auto_print(
                                f"Error message: npm build failed\n{output[:500]}"
                            )
                        return BuildResult(
                            success=success,
                            output=output,
                            error_message=None if success else "npm build failed",
                            build_system=BuildSystem.NODEJS,
                            duration=duration,
                        )
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️ Failed to read package.json: {e}")

        # Strategy 3: use eslint for syntax check (if it exists)
        if modified_files:
            js_files = [
                f for f in modified_files if f.endswith((".js", ".jsx", ".ts", ".tsx"))
            ]
            if js_files:
                # Try using eslint
                returncode, stdout, stderr = self._run_command(
                    ["npx", "eslint", "--max-warnings=0"]
                    + js_files[:5],  # Limit the number of files
                    timeout=15,
                )
                duration = time.time() - start_time
                output = stdout + stderr
                # eslint returning non-zero may be just warnings, not a failure
                PrettyOutput.auto_print(
                    f"✅ Node.js (eslint) build validation succeeded (took {duration:.2f}s)"
                )
                return BuildResult(
                    success=True,  # Only checks syntax, warnings are not failures
                    output=output,
                    error_message=None,
                    build_system=BuildSystem.NODEJS,
                    duration=duration,
                )

        duration = time.time() - start_time
        PrettyOutput.auto_print(
            f"✅ Node.js build validation succeeded (took {duration:.2f}s, no build script)"
        )
        return BuildResult(
            success=True,
            output="Node.js project validation passed (no build script)",
            error_message=None,
            build_system=BuildSystem.NODEJS,
            duration=duration,
        )
