"""
Rust build validator module

Provides build validation for Rust projects.
"""

import os
import subprocess
import time

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from typing import Optional

from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase


class RustBuildValidator(BuildValidatorBase):
    """Rust build validator (uses cargo test, including compilation and testing)"""

    BUILD_SYSTEM_NAME = "Cargo"
    SUPPORTED_LANGUAGES = ["rust"]

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        start_time = time.time()

        # Use cargo test for build and test validation (it will automatically compile and run tests, including doc tests)
        # Set RUST_BACKTRACE=1 to enable call stack backtrace
        # Set RUSTFLAGS="-A warnings" to suppress warnings and show only errors
        cmd = ["cargo", "test", "--", "--nocapture"]

        # Prepare environment variables (inherit the current environment and set RUST_BACKTRACE and RUSTFLAGS)
        env = os.environ.copy()
        env["RUST_BACKTRACE"] = "1"
        # If RUSTFLAGS already exists, append to it; otherwise create it
        if "RUSTFLAGS" in env:
            env["RUSTFLAGS"] = env["RUSTFLAGS"] + " -A warnings"
        else:
            env["RUSTFLAGS"] = "-A warnings"

        # Directly use subprocess.run to support environment variables
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                timeout=self.timeout,
                capture_output=True,
                text=False,
                env=env,
            )
            returncode = result.returncode
            stdout = decode_output(result.stdout)
            stderr = decode_output(result.stderr)
        except subprocess.TimeoutExpired:
            returncode = -1
            stdout = ""
            stderr = f"Command execution timed out ({self.timeout}s)"
        except FileNotFoundError:
            returncode = -1
            stdout = ""
            stderr = f"Command not found: {cmd[0]}"
        except Exception as e:
            returncode = -1
            stdout = ""
            stderr = f"Error while executing command: {str(e)}"

        duration = time.time() - start_time

        success = returncode == 0
        output = stdout + stderr

        if not success:
            # Try to parse the error information (including compilation errors and test failures)
            error_message = self._parse_cargo_errors(output)
            PrettyOutput.auto_print(f"❌ Rust build validation failed (took {duration:.2f}s)")
            if error_message:
                PrettyOutput.auto_print(f"Error message:\n{error_message}")
            else:
                PrettyOutput.auto_print(f"Output:\n{output[:500]}")
        else:
            error_message = None
            PrettyOutput.auto_print(f"✅ Rust build validation succeeded (took {duration:.2f}s)")

        return BuildResult(
            success=success,
            output=output,
            error_message=error_message,
            build_system=BuildSystem.RUST,
            duration=duration,
        )

    def _parse_cargo_errors(self, output: str, context_lines: int = 20) -> str:
        """Parse cargo's error output (including compilation errors and test failures)

        Args:
            output: the complete output of cargo test
            context_lines: number of context lines to keep around each error (default 20)

        Returns:
            The extracted error information, including the failed test cases and their context
        """
        lines = output.split("\n")
        error_sections = []

        # 1. Find the failed test cases
        failed_tests = []
        for i, line in enumerate(lines):
            # Match failed test case lines, such as "test tests::test_name ... FAILED"
            if "test" in line and "FAILED" in line:
                # Extract the test name
                if "test " in line:
                    parts = line.split()
                    for j, part in enumerate(parts):
                        if part == "test" and j + 1 < len(parts):
                            test_name = parts[j + 1]
                            if "..." in test_name:
                                test_name = test_name.replace("...", "")
                            failed_tests.append((i, test_name, line))
                            break

        # 2. Extract the complete output block for each failed test
        if failed_tests:
            for test_idx, (line_idx, test_name, test_line) in enumerate(failed_tests):
                # Find the start position of this test (search upward, find "running" or the test name)
                start_idx = max(0, line_idx - 10)
                # Search upward to find the test start marker
                for i in range(line_idx - 1, max(0, line_idx - 100), -1):
                    # Find the "running" line, usually formatted as "running 1 test" or containing the test name
                    if "running" in lines[i].lower():
                        start_idx = i
                        break
                    # Or find the end marker of the previous test
                    if (
                        i > 0
                        and "test " in lines[i]
                        and ("ok" in lines[i].lower() or "FAILED" in lines[i])
                    ):
                        start_idx = i + 1
                        break

                # Find the end position of this test (search downward, find the next test or the test summary)
                end_idx = min(len(lines), line_idx + context_lines)
                # Search downward to find the end of the test block
                for i in range(line_idx + 1, min(len(lines), line_idx + 500)):
                    # Encounter the next test case line (format: test xxx ... ok/FAILED)
                    if "test " in lines[i] and "..." in lines[i]:
                        end_idx = i
                        break
                    # Encounter the test summary line
                    if "test result:" in lines[i].lower():
                        end_idx = i
                        break
                    # Encounter a new "running" line, meaning the next group of tests begins
                    if "running" in lines[i].lower() and i > line_idx + 5:
                        end_idx = i
                        break

                # Extract the complete output of this test
                test_output = "\n".join(lines[start_idx:end_idx])
                if test_output.strip():
                    error_sections.append(
                        f"=== Failed test: {test_name} ===\n{test_output}"
                    )

        # 3. If no failed test was found, find compilation errors
        if not error_sections:
            error_lines = []
            in_error_block = False
            error_start = -1

            for i, line in enumerate(lines):
                # Detect the error start
                if "error[" in line or (
                    "error:" in line.lower() and "error[" not in line
                ):
                    if not in_error_block:
                        error_start = max(0, i - 2)  # Include 2 lines of context before the error
                        in_error_block = True
                elif in_error_block:
                    # Error block end condition: a blank line followed by a non-error line, or encountering a new error
                    if line.strip() == "":
                        # Check whether the next line is a new error
                        if i + 1 < len(lines) and (
                            "error[" not in lines[i + 1]
                            and "error:" not in lines[i + 1].lower()
                        ):
                            # End the current error block
                            error_lines.extend(lines[error_start : i + 1])
                            in_error_block = False
                    elif i - error_start > context_lines:
                        # Error block too long, truncate
                        error_lines.extend(lines[error_start:i])
                        in_error_block = False
                        if "error[" in line or "error:" in line.lower():
                            error_start = max(0, i - 2)
                            in_error_block = True

            # Handle the last error block
            if in_error_block:
                error_lines.extend(
                    lines[error_start : min(len(lines), error_start + context_lines)]
                )

            if error_lines:
                error_sections.append("\n".join(error_lines))

        # 4. If still no error was found, look for other error patterns
        if not error_sections:
            for i, line in enumerate(lines):
                if (
                    "panic" in line.lower()
                    or ("assertion" in line.lower() and "failed" in line.lower())
                    or "thread" in line.lower()
                    and "panicked" in line.lower()
                ):
                    start = max(0, i - 3)
                    end = min(len(lines), i + context_lines)
                    error_sections.append("\n".join(lines[start:end]))
                    break

        # 5. If error information was found, return it; otherwise return the first 500 characters of the original output
        if error_sections:
            result = "\n\n".join(error_sections)
            # Limit the total length to avoid it being too long
            if len(result) > 5000:
                result = result[:5000] + "\n... (output truncated)"
            return result
        else:
            return output[:500]  # If no specific error was found, return the first 500 characters
