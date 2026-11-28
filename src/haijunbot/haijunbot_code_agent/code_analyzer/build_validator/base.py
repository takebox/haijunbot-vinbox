#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build validator base module

Provides base classes and enum definitions.
"""

import subprocess
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.utils import decode_output


class BuildSystem(Enum):
    """Supported build system types"""

    UNKNOWN = "unknown"
    PYTHON = "python"
    NODEJS = "nodejs"
    RUST = "rust"
    JAVA_MAVEN = "java_maven"
    JAVA_GRADLE = "java_gradle"
    GO = "go"
    C_MAKEFILE = "c_makefile"
    C_CMAKE = "c_cmake"
    C_MAKEFILE_CMAKE = "c_makefile_cmake"  # Both Makefile and CMakeLists.txt exist
    CUSTOM = "custom"  # User-defined build command


@dataclass
class BuildResult:
    """Build validation result"""

    success: bool
    output: str
    error_message: Optional[str] = None
    build_system: Optional[BuildSystem] = None
    duration: float = 0.0  # Validation duration (seconds)


class BuildValidatorBase(ABC):
    """Build validator base class"""

    # Class variables that subclasses need to define
    BUILD_SYSTEM_NAME: str = ""  # Build system name, e.g. "CMake", "Makefile", "Cargo"
    SUPPORTED_LANGUAGES: List[str] = []  # List of supported languages, e.g. ["c", "cpp"]

    def __init__(self, project_root: str, timeout: int = 30):
        self.project_root = project_root
        self.timeout = timeout

    @abstractmethod
    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        """Validate the build

        Args:
            modified_files: list of modified files (optional, used for incremental validation)

        Returns:
            BuildResult: validation result
        """
        pass

    def _run_command(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
    ) -> Tuple[int, str, str]:
        """Run a command

        Args:
            cmd: command list
            cwd: working directory
            timeout: timeout (seconds)
            capture_output: whether to capture output

        Returns:
            (return code, stdout, stderr)
        """
        if cwd is None:
            cwd = self.project_root
        if timeout is None:
            timeout = self.timeout

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=False,
            )
            stdout = decode_output(result.stdout) if capture_output else ""
            stderr = decode_output(result.stderr) if capture_output else ""
            return result.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command execution timed out ({timeout}s)"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", f"Error while executing command: {str(e)}"
