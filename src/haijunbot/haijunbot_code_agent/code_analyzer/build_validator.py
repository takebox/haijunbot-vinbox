#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Build validation module (backward-compatible import)

This file remains backward compatible; the actual implementation has been migrated into the build_validator package.
"""

# Import all content from the new module to maintain backward compatibility
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildResult
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildSystem
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildSystemDetector
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildValidatorBase
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import CMakeBuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import (
    FallbackBuildValidator,
)
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import GoBuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import (
    JavaGradleBuildValidator,
)
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import (
    JavaMavenBuildValidator,
)
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import (
    MakefileBuildValidator,
)
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import NodeJSBuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import PythonBuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import RustBuildValidator

__all__ = [
    "BuildSystem",
    "BuildResult",
    "BuildValidatorBase",
    "BuildSystemDetector",
    "BuildValidator",
    "RustBuildValidator",
    "PythonBuildValidator",
    "NodeJSBuildValidator",
    "JavaMavenBuildValidator",
    "JavaGradleBuildValidator",
    "GoBuildValidator",
    "CMakeBuildValidator",
    "MakefileBuildValidator",
    "FallbackBuildValidator",
]
