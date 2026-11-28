"""
Build validator main module

Provides the main build validator class, responsible for coordinating the validators of each language.
"""

from typing import Dict
from typing import List
from typing import Optional
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.input import get_single_line_input

#!/usr/bin/env python3
# -*- coding: utf-8 -*-


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
from .rust import RustBuildValidator


class BuildValidator:
    """Build validator main class"""

    def __init__(self, project_root: str, timeout: int = 30):
        self.project_root = project_root
        self.timeout = timeout
        self.detector = BuildSystemDetector(project_root)

        # Import the configuration manager
        from haijunbot.haijunbot_code_agent.build_validation_config import (
            BuildValidationConfig,
        )

        self.config = BuildValidationConfig(project_root)

        # Register build system validators
        self._validators: Dict[BuildSystem, BuildValidatorBase] = {
            BuildSystem.RUST: RustBuildValidator(project_root, timeout),
            BuildSystem.PYTHON: PythonBuildValidator(project_root, timeout),
            BuildSystem.NODEJS: NodeJSBuildValidator(project_root, timeout),
            BuildSystem.JAVA_MAVEN: JavaMavenBuildValidator(project_root, timeout),
            BuildSystem.JAVA_GRADLE: JavaGradleBuildValidator(project_root, timeout),
            BuildSystem.GO: GoBuildValidator(project_root, timeout),
            BuildSystem.C_CMAKE: CMakeBuildValidator(project_root, timeout),
            BuildSystem.C_MAKEFILE: MakefileBuildValidator(project_root, timeout),
            BuildSystem.C_MAKEFILE_CMAKE: CMakeBuildValidator(project_root, timeout),
            BuildSystem.CUSTOM: CustomBuildValidator(project_root, timeout),
        }

        # Fallback validator
        self._fallback_validator = FallbackBuildValidator(project_root, timeout)

    def _select_build_system(
        self, detected_systems: List[BuildSystem]
    ) -> Optional[BuildSystem]:
        """Let the user select the build system

        Args:
            detected_systems: list of all detected build systems

        Returns:
            The build system selected by the user, or None if the user cancels
        """
        if not detected_systems:
            return None

        if len(detected_systems) == 1:
            # Only one build system, return it directly
            return detected_systems[0]

        # Check whether a selection already exists in the config file
        saved_system = self.config.get_selected_build_system()
        if saved_system:
            try:
                saved_enum = BuildSystem(saved_system)
                if saved_enum in detected_systems:
                    PrettyOutput.auto_print(
                        f"ℹ️ Using the build system saved in the config file: {saved_system}"
                    )
                    return saved_enum
            except ValueError:
                # The build system saved in the config file is invalid, ignore it
                pass

        # Multiple build systems, the user needs to choose
        PrettyOutput.auto_print("Multiple build systems detected, please select the build system to use:")
        for idx, system in enumerate(detected_systems, start=1):
            PrettyOutput.auto_print(f"  {idx}. {system.value}")
        PrettyOutput.auto_print(
            f"  {len(detected_systems) + 1}. Cancel (use fallback validator)"
        )

        while True:
            try:
                choice = get_single_line_input(
                    f"\nPlease select (1-{len(detected_systems) + 1}): "
                ).strip()
                choice_num = int(choice)

                if 1 <= choice_num <= len(detected_systems):
                    selected = detected_systems[choice_num - 1]
                    # Save the user's choice
                    self.config.set_selected_build_system(selected.value)
                    PrettyOutput.auto_print(f"ℹ️ User selected build system: {selected.value}")
                    return selected
                elif choice_num == len(detected_systems) + 1:
                    PrettyOutput.auto_print("ℹ️ User canceled the selection, using fallback validator")
                    return None
                else:
                    PrettyOutput.auto_print(
                        f"Invalid choice, please enter 1-{len(detected_systems) + 1}"
                    )
            except ValueError:
                PrettyOutput.auto_print("Please enter a valid number")
            except (KeyboardInterrupt, EOFError):
                PrettyOutput.auto_print("User canceled, using fallback validator")
                return None

    def validate(self, modified_files: Optional[List[str]] = None) -> BuildResult:
        """Validate the build

        Args:
            modified_files: list of modified files (optional, used for incremental validation)

        Returns:
            BuildResult: validation result
        """
        # First check whether a build system is already saved in the config file
        saved_system = self.config.get_selected_build_system()
        if saved_system:
            try:
                saved_enum = BuildSystem(saved_system)
                if saved_enum in self._validators:
                    validator = self._validators[saved_enum]
                    PrettyOutput.auto_print(
                        f"ℹ️ Using the build system saved in the config file: {saved_system}"
                    )
                    try:
                        return validator.validate(modified_files)
                    except Exception as e:
                        PrettyOutput.auto_print(
                            f"⚠️ Validator {validator.__class__.__name__} execution failed: {e}, using fallback validator"
                        )
                        return self._fallback_validator.validate(modified_files)
                elif saved_enum == BuildSystem.UNKNOWN:
                    PrettyOutput.auto_print(
                        "ℹ️ Using the build system saved in the config file: unknown, using fallback validator"
                    )
                    return self._fallback_validator.validate(modified_files)
            except ValueError:
                # The build system saved in the config file is invalid, continue detection
                pass

        # No build system saved in the config file, use the fallback validator directly
        PrettyOutput.auto_print("ℹ️ No build system specified in the config file, using fallback validator")
        return self._fallback_validator.validate(modified_files)

    def register_validator(
        self, build_system: BuildSystem, validator: BuildValidatorBase
    ) -> None:
        """Register a custom validator (extension point)

        Args:
            build_system: build system type
            validator: validator instance
        """
        self._validators[build_system] = validator
        PrettyOutput.auto_print(
            f"ℹ️ Registered custom validator: {build_system.value} -> {validator.__class__.__name__}"
        )
