#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build validation module

Provides post-edit compilation/build validation, supports multiple build systems, and features good extensibility and a fallback mechanism.
"""

# Export main interfaces
from .base import BuildResult
from .base import BuildSystem
from .base import BuildValidatorBase
from .cmake import CMakeBuildValidator
from .custom import CustomBuildValidator
from .detector import BuildSystemDetector
from .fallback import FallbackBuildValidator
from .go import GoBuildValidator
from .java_gradle import JavaGradleBuildValidator
from .java_maven import JavaMavenBuildValidator
from .makefile import MakefileBuildValidator
from .nodejs import NodeJSBuildValidator
from .python import PythonBuildValidator

# Export validators for each language (for easy extension)
from .rust import RustBuildValidator
from .validator import BuildValidator

__all__ = [
    # Main interfaces
    "BuildSystem",
    "BuildResult",
    "BuildValidatorBase",
    "BuildSystemDetector",
    "BuildValidator",
    # Validators for each language
    "RustBuildValidator",
    "PythonBuildValidator",
    "NodeJSBuildValidator",
    "JavaMavenBuildValidator",
    "JavaGradleBuildValidator",
    "GoBuildValidator",
    "CMakeBuildValidator",
    "MakefileBuildValidator",
    "CustomBuildValidator",
    "FallbackBuildValidator",
]
