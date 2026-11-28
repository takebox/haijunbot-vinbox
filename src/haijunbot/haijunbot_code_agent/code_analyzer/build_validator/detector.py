"""
Build system detector module

Provides automatic build system detection.
"""

import os
import re
import subprocess

from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output
from haijunbot.haijunbot_utils.input import get_single_line_input

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List
from typing import Optional
from typing import Tuple

from .base import BuildSystem


class BuildSystemDetector:
    """Build system detector"""

    def __init__(self, project_root: str):
        self.project_root = project_root

    def _get_file_statistics(self) -> str:
        """Get file count statistics

        Use the loc tool to get file statistics.

        Returns:
            The raw string output by the loc tool, or an empty string on failure
        """
        try:
            # Call the loc tool to get statistics
            result = subprocess.run(
                ["loc"],
                cwd=self.project_root,
                capture_output=True,
                text=False,
                check=False,
            )
            stdout = decode_output(result.stdout)

            if result.returncode == 0 and stdout:
                return stdout.strip()
            else:
                return ""
        except FileNotFoundError:
            # loc tool not installed, return an empty string
            PrettyOutput.auto_print("⚠️ loc tool not installed, unable to get file statistics")
            return ""
        except Exception as e:
            # Other errors, return an empty string
            PrettyOutput.auto_print(f"⚠️ Failed to call loc tool: {e}")
            return ""

    def _get_git_root_file_list(self, max_files: int = 100) -> str:
        """Get the file list of the git root directory (limited in number)

        First identify the git root directory, then list the files under the root directory.

        Args:
            max_files: maximum number of files to return

        Returns:
            A string representation of the file list, one file per line, or an empty string on failure
        """
        try:
            # First identify the git root directory
            git_root_result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.project_root,
                capture_output=True,
                text=False,
                check=False,
            )
            git_root_stdout = decode_output(git_root_result.stdout)

            if git_root_result.returncode != 0:
                # If it is not a git repository, try reading the current directory directly
                git_root = self.project_root
            else:
                git_root = git_root_stdout.strip()

            # List the files under the git root directory
            file_list: List[str] = []

            # Use git ls-files to get the list of git-tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=git_root,
                capture_output=True,
                text=False,
                check=False,
            )
            ls_files_stdout = decode_output(result.stdout)

            if result.returncode == 0:
                files = ls_files_stdout.strip().split("\n")
                # Only take files directly under the root directory (excluding subdirectories)
                for file_path in files:
                    if not file_path.strip():
                        continue
                    # Only take files under the root directory (without path separators)
                    if "/" not in file_path:
                        file_list.append(file_path)
                        if len(file_list) >= max_files:
                            break
            else:
                # If the git command fails, try reading the root directory directly
                try:
                    for item in os.listdir(git_root):
                        item_path = os.path.join(git_root, item)
                        if os.path.isfile(item_path) and not item.startswith("."):
                            file_list.append(item)
                            if len(file_list) >= max_files:
                                break
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_code_agent.code_analyzer.build_validator.detector",
                        function="_get_git_root_file_list",
                    )
                    pass

            # Return the formatted string
            if file_list:
                return "\n".join(file_list)
            else:
                return ""
        except Exception as e:
            # Return an empty string when an error occurs
            PrettyOutput.auto_print(f"⚠️ Failed to get the git root file list: {e}")
            return ""

    def _get_supported_build_systems(self) -> List[str]:
        """Get the list of currently supported build systems

        Returns:
            List of build system names
        """
        return [
            "rust (Cargo.toml)",
            "go (go.mod)",
            "java_maven (pom.xml)",
            "java_gradle (build.gradle/build.gradle.kts)",
            "nodejs (package.json)",
            "python (setup.py/pyproject.toml/requirements.txt, etc.)",
            "c_cmake (CMakeLists.txt)",
            "c_makefile (Makefile)",
            "custom (user-defined build command)",
            "unknown (unknown/unrecognized)",
        ]

    def detect_with_llm(self) -> Optional[List[Tuple[BuildSystem, float]]]:
        """Detect the build system using an LLM (based on file statistics and file list)

        Returns:
            The detected build system list (with probabilities), sorted by probability descending, or None if detection is impossible
            Format: [(BuildSystem, probability), ...]
        """
        # Check whether a build system has already been saved in the config file
        from haijunbot.haijunbot_code_agent.build_validation_config import (
            BuildValidationConfig,
        )

        config = BuildValidationConfig(self.project_root)
        saved_system = config.get_selected_build_system()
        if saved_system:
            try:
                saved_enum = BuildSystem(saved_system)
                PrettyOutput.auto_print(
                    f"ℹ️ Using the build system saved in the config file: {saved_system}"
                )
                return [(saved_enum, 1.0)]
            except ValueError:
                # The build system saved in the config file is invalid, continue detection
                pass

        # Get file statistics
        file_stats = self._get_file_statistics()

        # Get the git root file list
        root_files = self._get_git_root_file_list(max_files=50)

        # Get the list of supported build systems
        supported_systems = self._get_supported_build_systems()

        # Build the context
        stats_text = file_stats if file_stats else "  (no statistics)"
        # Format the file list, prefixing each line with "  - "
        if root_files:
            files_lines = root_files.split("\n")[:30]  # Limit to the first 30 files
            files_text = "\n".join([f"  - {f}" for f in files_lines])
        else:
            files_text = "  (no file list)"
        systems_text = "\n".join([f"  - {sys}" for sys in supported_systems])

        context = f"""Please determine the project's build system based on the following information:

File count statistics (by extension, first 20 items):
{stats_text}

Git root file list (first 30 items):
{files_text}

Currently supported build systems:
{systems_text}

Please carefully analyze the file statistics and file list to determine the build system used by the project.
For each possible build system, give a probability value (between 0.0-1.0) indicating the likelihood of that build system.
If it cannot be determined, you may return "unknown".

Please answer using the following format (must contain and only contain the following markers, separate multiple build systems with newlines):
- If it is determined to be a Rust project, answer: <BUILD_SYSTEM>rust:0.95</BUILD_SYSTEM>
- If it is determined to be a Go project, answer: <BUILD_SYSTEM>go:0.90</BUILD_SYSTEM>
- If it is determined to be a Java Maven project, answer: <BUILD_SYSTEM>java_maven:0.85</BUILD_SYSTEM>
- If it is determined to be a Java Gradle project, answer: <BUILD_SYSTEM>java_gradle:0.80</BUILD_SYSTEM>
- If it is determined to be a Node.js project, answer: <BUILD_SYSTEM>nodejs:0.75</BUILD_SYSTEM>
- If it is determined to be a Python project, answer: <BUILD_SYSTEM>python:0.70</BUILD_SYSTEM>
- If it is determined to be a CMake project, answer: <BUILD_SYSTEM>c_cmake:0.65</BUILD_SYSTEM>
- If it is determined to be a Makefile project, answer: <BUILD_SYSTEM>c_makefile:0.60</BUILD_SYSTEM>
- If it cannot be determined, answer: <BUILD_SYSTEM>unknown:0.50</BUILD_SYSTEM>

Format description:
- One build system per line, format is <BUILD_SYSTEM>system name:probability value</BUILD_SYSTEM>
- Probability value range: 0.0-1.0, the larger the value the higher the likelihood
- Multiple build systems may be returned, one per line, sorted by probability descending
- Example:
  <BUILD_SYSTEM>python:0.85</BUILD_SYSTEM>
  <BUILD_SYSTEM>nodejs:0.30</BUILD_SYSTEM>

Please answer strictly following the protocol format, do not add other content.
"""

        try:
            # Use the cheap platform for the determination
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            platform = PlatformRegistry().get_cheap_platform()

            PrettyOutput.auto_print("🤖 Using LLM to determine the build system...")
            response = platform.chat_until_success(context)

            # Parse the response
            detected_systems_with_prob: List[Tuple[BuildSystem, float]] = []
            unknown_probabilities: List[float] = []  # Collect probabilities of invalid build systems

            # Extract all BUILD_SYSTEM markers
            matches = re.findall(r"<BUILD_SYSTEM>(.*?)</BUILD_SYSTEM>", response)

            for match in matches:
                match = match.strip()
                # Parse the format: system name:probability value
                if ":" in match:
                    parts = match.split(":", 1)
                    system_str = parts[0].strip()
                    try:
                        prob_str = parts[1].strip()
                        probability = float(prob_str)
                        # Ensure the probability is between 0.0-1.0
                        probability = max(0.0, min(1.0, probability))

                        try:
                            system_enum = BuildSystem(system_str)
                            detected_systems_with_prob.append(
                                (system_enum, probability)
                            )
                        except ValueError:
                            # Invalid build system name, convert to unknown
                            unknown_probabilities.append(probability)
                    except (ValueError, IndexError):
                        # If parsing fails, try the format without probability (backward compatible)
                        try:
                            system_enum = BuildSystem(system_str)
                            # Default probability is 0.5
                            detected_systems_with_prob.append((system_enum, 0.5))
                        except ValueError:
                            # Invalid build system name, convert to unknown (default probability 0.5)
                            unknown_probabilities.append(0.5)
                else:
                    # Format without probability (backward compatible)
                    try:
                        system_enum = BuildSystem(match)
                        # Default probability is 0.5
                        detected_systems_with_prob.append((system_enum, 0.5))
                    except ValueError:
                        # Invalid build system name, convert to unknown (default probability 0.5)
                        unknown_probabilities.append(0.5)

            # If there are invalid build systems, merge them into unknown
            if unknown_probabilities:
                # Use the average probability, or if there is only one, use it directly
                avg_prob = (
                    sum(unknown_probabilities) / len(unknown_probabilities)
                    if unknown_probabilities
                    else 0.5
                )
                # Check whether there is already an unknown, if so use the maximum probability
                existing_unknown = None
                for i, (sys, prob) in enumerate(detected_systems_with_prob):
                    if sys == BuildSystem.UNKNOWN:
                        existing_unknown = i
                        break

                if existing_unknown is not None:
                    # If there is already an unknown, use the maximum probability
                    max_prob = max(
                        detected_systems_with_prob[existing_unknown][1], avg_prob
                    )
                    detected_systems_with_prob[existing_unknown] = (
                        BuildSystem.UNKNOWN,
                        max_prob,
                    )
                else:
                    # If there is no unknown, add one
                    detected_systems_with_prob.append((BuildSystem.UNKNOWN, avg_prob))

            if detected_systems_with_prob:
                # Sort by probability descending
                detected_systems_with_prob.sort(key=lambda x: x[1], reverse=True)
                return detected_systems_with_prob
            else:
                # If no valid build system was found, return unknown
                return [(BuildSystem.UNKNOWN, 0.5)]

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ LLM failed to determine the build system: {e}, using unknown")
            return [(BuildSystem.UNKNOWN, 0.5)]

    def detect_with_llm_and_confirm(self) -> Optional[List[BuildSystem]]:
        """Detect the build system using an LLM and let the user confirm

        Returns:
            The build system list after user confirmation, or None if the user cancels
        """

        # Check whether it is in non-interactive mode
        def _is_non_interactive() -> bool:
            try:
                from haijunbot.haijunbot_utils.config import is_non_interactive

                return bool(is_non_interactive())
            except Exception:
                return False

        detected_systems_with_prob = self.detect_with_llm()

        if not detected_systems_with_prob:
            return None

        # Extract the build system list (sorted by probability)
        detected_systems = [sys for sys, _ in detected_systems_with_prob]

        # Non-interactive mode: directly select the build system with the highest probability
        if _is_non_interactive():
            system, prob = detected_systems_with_prob[0]
            PrettyOutput.auto_print(
                f"ℹ️ Non-interactive mode: automatically selecting the highest-probability build system: {system.value} (probability: {prob:.2%})"
            )
            from haijunbot.haijunbot_code_agent.build_validation_config import (
                BuildValidationConfig,
            )

            config = BuildValidationConfig(self.project_root)
            config.set_selected_build_system(system.value)
            return detected_systems

        # If unknown is detected, use it directly without asking the user
        if len(detected_systems) == 1 and detected_systems[0] == BuildSystem.UNKNOWN:
            prob = detected_systems_with_prob[0][1]
            PrettyOutput.auto_print(
                f"ℹ️ LLM determination: unable to determine the build system (unknown, probability: {prob:.2%}), using unknown directly"
            )
            from haijunbot.haijunbot_code_agent.build_validation_config import (
                BuildValidationConfig,
            )

            config = BuildValidationConfig(self.project_root)
            config.set_selected_build_system("unknown")
            return detected_systems

        # Show the detection results (sorted by probability descending)
        PrettyOutput.auto_print("🤖 LLM determination results (sorted by probability descending):")
        for idx, (system, prob) in enumerate(detected_systems_with_prob, start=1):
            PrettyOutput.auto_print(f"  {idx}. {system.value} (probability: {prob:.2%})")

        # Show the detection result
        if len(detected_systems) == 1:
            system, prob = detected_systems_with_prob[0]
            from haijunbot.haijunbot_code_agent.build_validation_config import (
                BuildValidationConfig,
            )
            from haijunbot.haijunbot_utils.input import user_confirm

            config = BuildValidationConfig(self.project_root)

            if user_confirm(
                f"Confirm using {system.value} as the build system? (probability: {prob:.2%})",
                default=True,
            ):
                config.set_selected_build_system(system.value)
                return detected_systems
            else:
                # User did not confirm, let the user choose (pass in info with probability to preserve sorting)
                return self._let_user_select_build_system_with_prob(
                    detected_systems_with_prob
                )
        else:
            # Multiple build systems detected, let the user choose (pass in info with probability to preserve sorting)
            return self._let_user_select_build_system_with_prob(
                detected_systems_with_prob
            )

    def _let_user_select_build_system_with_prob(
        self, detected_systems_with_prob: List[Tuple[BuildSystem, float]]
    ) -> Optional[List[BuildSystem]]:
        """Let the user select the build system (with probability info, sorted by probability)

        Args:
            detected_systems_with_prob: detected build system list (with probabilities), already sorted by probability

        Returns:
            The build system list selected by the user, or None if the user cancels
        """

        # Check whether it is in non-interactive mode
        def _is_non_interactive() -> bool:
            try:
                from haijunbot.haijunbot_utils.config import is_non_interactive

                return bool(is_non_interactive())
            except Exception:
                return False

        from haijunbot.haijunbot_code_agent.build_validation_config import (
            BuildValidationConfig,
        )

        config = BuildValidationConfig(self.project_root)

        # Non-interactive mode: directly select the build system with the highest probability
        if _is_non_interactive():
            if detected_systems_with_prob:
                selected, prob = detected_systems_with_prob[0]
                PrettyOutput.auto_print(
                    f"ℹ️ Non-interactive mode: automatically selecting the highest-probability build system: {selected.value} (probability: {prob:.2%})"
                )
                config.set_selected_build_system(selected.value)
                return [selected]
            else:
                PrettyOutput.auto_print("ℹ️ Non-interactive mode: no build system detected, using unknown")
                config.set_selected_build_system("unknown")
                return [BuildSystem.UNKNOWN]

        PrettyOutput.auto_print("Please select the build system (sorted by probability descending):")
        for idx, (system, prob) in enumerate(detected_systems_with_prob, start=1):
            PrettyOutput.auto_print(f"  {idx}. {system.value} (probability: {prob:.2%})")
        PrettyOutput.auto_print(
            f"  {len(detected_systems_with_prob) + 1}. Cancel (use unknown)"
        )

        while True:
            try:
                choice = get_single_line_input(
                    f"\nPlease select (1-{len(detected_systems_with_prob) + 1}): "
                ).strip()
                choice_num = int(choice)

                if 1 <= choice_num <= len(detected_systems_with_prob):
                    selected, prob = detected_systems_with_prob[choice_num - 1]
                    # Save the user's choice
                    config.set_selected_build_system(selected.value)
                    PrettyOutput.auto_print(
                        f"ℹ️ User selected build system: {selected.value} (probability: {prob:.2%})"
                    )
                    return [selected]
                elif choice_num == len(detected_systems_with_prob) + 1:
                    PrettyOutput.auto_print("ℹ️ User canceled the selection, using unknown")
                    config.set_selected_build_system("unknown")
                    return [BuildSystem.UNKNOWN]
                else:
                    PrettyOutput.auto_print(
                        f"Invalid choice, please enter 1-{len(detected_systems_with_prob) + 1}"
                    )
            except ValueError:
                PrettyOutput.auto_print("Please enter a valid number")
            except (KeyboardInterrupt, EOFError):
                PrettyOutput.auto_print("User canceled, using unknown")
                config.set_selected_build_system("unknown")
                return [BuildSystem.UNKNOWN]

    def _let_user_select_build_system(
        self, detected_systems: Optional[List[BuildSystem]] = None
    ) -> Optional[List[BuildSystem]]:
        """Let the user select the build system (compatible with the old interface)

        Args:
            detected_systems: detected build system list, if None shows all supported build systems

        Returns:
            The build system list selected by the user, or None if the user cancels
        """

        # Check whether it is in non-interactive mode
        def _is_non_interactive() -> bool:
            try:
                from haijunbot.haijunbot_utils.config import is_non_interactive

                return bool(is_non_interactive())
            except Exception:
                return False

        from haijunbot.haijunbot_code_agent.build_validation_config import (
            BuildValidationConfig,
        )

        config = BuildValidationConfig(self.project_root)

        if detected_systems is None:
            # Show all supported build systems
            all_systems = [
                BuildSystem.RUST,
                BuildSystem.GO,
                BuildSystem.JAVA_MAVEN,
                BuildSystem.JAVA_GRADLE,
                BuildSystem.NODEJS,
                BuildSystem.PYTHON,
                BuildSystem.C_CMAKE,
                BuildSystem.C_MAKEFILE,
                BuildSystem.CUSTOM,
                BuildSystem.UNKNOWN,
            ]
            detected_systems = all_systems

        # Non-interactive mode: directly select the first build system (or unknown)
        if _is_non_interactive():
            if detected_systems and detected_systems[0] != BuildSystem.UNKNOWN:
                selected_system: BuildSystem = detected_systems[0]
                PrettyOutput.auto_print(
                    f"ℹ️ Non-interactive mode: automatically selecting build system: {selected_system.value}"
                )
                config.set_selected_build_system(selected_system.value)
                return [selected_system]
            else:
                PrettyOutput.auto_print("ℹ️ Non-interactive mode: no build system detected, using unknown")
                config.set_selected_build_system("unknown")
                return [BuildSystem.UNKNOWN]

        PrettyOutput.auto_print("Please select the build system:")
        for idx, system in enumerate(detected_systems, start=1):
            PrettyOutput.auto_print(f"  {idx}. {system.value}")
        PrettyOutput.auto_print(f"  {len(detected_systems) + 1}. Cancel (use unknown)")

        while True:
            try:
                choice = get_single_line_input(
                    f"\nPlease select (1-{len(detected_systems) + 1}): "
                ).strip()
                choice_num = int(choice)

                if 1 <= choice_num <= len(detected_systems):
                    selected_build_system: BuildSystem = detected_systems[
                        choice_num - 1
                    ]
                    # Save the user's choice
                    config.set_selected_build_system(selected_build_system.value)
                    PrettyOutput.auto_print(
                        f"ℹ️ User selected build system: {selected_build_system.value}"
                    )
                    return [selected_build_system]
                elif choice_num == len(detected_systems) + 1:
                    PrettyOutput.auto_print("ℹ️ User canceled the selection, using unknown")
                    config.set_selected_build_system("unknown")
                    return [BuildSystem.UNKNOWN]
                else:
                    PrettyOutput.auto_print(
                        f"Invalid choice, please enter 1-{len(detected_systems) + 1}"
                    )
            except ValueError:
                PrettyOutput.auto_print("Please enter a valid number")
            except (KeyboardInterrupt, EOFError):
                PrettyOutput.auto_print("User canceled, using unknown")
                config.set_selected_build_system("unknown")
                return [BuildSystem.UNKNOWN]
