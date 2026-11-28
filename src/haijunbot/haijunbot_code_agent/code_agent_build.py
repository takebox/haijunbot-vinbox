"""CodeAgent build validation module"""

from typing import Any
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_code_agent.build_validation_config import BuildValidationConfig
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildResult
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import BuildValidator
from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import (
    FallbackBuildValidator,
)
from haijunbot.haijunbot_utils.config import get_build_validation_timeout
from haijunbot.haijunbot_utils.config import is_enable_build_validation
from haijunbot.haijunbot_utils.input import user_confirm


def format_build_error(result: BuildResult, max_len: int = 2000) -> str:
    """Format build error information, limiting output length"""
    error_msg = result.error_message or ""
    output = result.output or ""

    full_error = f"{error_msg}\n{output}".strip()

    if len(full_error) > max_len:
        return full_error[:max_len] + "\n... (output truncated)"
    return full_error


class BuildValidationManager:
    """Build validation manager"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def validate_build_after_edit(
        self, modified_files: List[str]
    ) -> Optional[BuildResult]:
        """Validate the build after editing

        Args:
            modified_files: list of modified files

        Returns:
            BuildResult: validation result, or None if validation is disabled or an error occurred
        """
        if not is_enable_build_validation():
            return None

        # Check project configuration to see if build validation is disabled
        config = BuildValidationConfig(self.root_dir)
        if config.is_build_validation_disabled():
            # Already disabled, return None, the caller handles basic static checks
            return None

        # Output build check log
        import os

        file_count = len(modified_files)
        files_str = ", ".join(os.path.basename(f) for f in modified_files[:3])
        if file_count > 3:
            files_str += f" and {file_count} files"
        PrettyOutput.auto_print(f"🔨 Performing build check ({files_str})...")

        try:
            timeout = get_build_validation_timeout()
            validator = BuildValidator(self.root_dir, timeout=timeout)
            result = validator.validate(modified_files)
            return result
        except Exception as e:
            # Build validation failure should not affect the main flow, only log it
            PrettyOutput.auto_print(f"⚠️ Build validation execution failed: {e}")
            return None

    def handle_build_validation_disabled(
        self, modified_files: List[str], config: Any, agent: Any, final_ret: str
    ) -> str:
        """Handle the case where build validation is disabled

        Returns:
            The updated result string
        """
        reason = config.get_disable_reason()
        reason_text = f" (reason: {reason})" if reason else ""
        final_ret += f"\n\nℹ️ Build validation is disabled{reason_text}, performing only basic static checks\n"

        # Output basic static check log
        import os

        file_count = len(modified_files)
        files_str = ", ".join(os.path.basename(f) for f in modified_files[:3])
        if file_count > 3:
            files_str += f" and {file_count} files"

        # Use the fallback validator to perform basic static checks
        fallback_validator = FallbackBuildValidator(
            self.root_dir, timeout=get_build_validation_timeout()
        )
        static_check_result = fallback_validator.validate(modified_files)
        if not static_check_result.success:
            final_ret += f"\n⚠️ Basic static check failed:\n{static_check_result.error_message or static_check_result.output}\n"
            agent.set_addon_prompt(
                f"Basic static check failed, please fix the code according to the following error information:\n{static_check_result.error_message or static_check_result.output}\n"
            )
        else:
            final_ret += (
                f"\n✅ Basic static check passed (took {static_check_result.duration:.2f}s)\n"
            )

        return final_ret

    def handle_build_validation_failure(
        self,
        build_validation_result: Any,
        config: Any,
        modified_files: List[str],
        agent: Any,
        final_ret: str,
    ) -> str:
        """Handle the case where build validation fails

        Returns:
            The updated result string
        """
        if not config.has_been_asked():
            # First failure, ask the user
            error_preview = format_build_error(build_validation_result)
            PrettyOutput.auto_print(f"⚠️ Build validation failed:\n{error_preview}\n")
            PrettyOutput.auto_print(
                "ℹ️ Tip: If this project needs to be built in a special environment (such as a container), or uses a standalone build script, "
                "you can choose to disable build validation, after which only basic static checks will be performed."
            )

            if user_confirm(
                "Do you want to disable build validation and perform only basic static checks from now on?",
                default=True,
            ):
                # User chose to disable
                config.disable_build_validation(
                    reason="User chose to disable (the project may need to be built in a special environment)"
                )
                config.mark_as_asked()
                final_ret += "\n\nℹ️ Build validation has been disabled, only basic static checks will be performed from now on\n"

                # Output basic static check log
                import os

                file_count = len(modified_files)
                files_str = ", ".join(os.path.basename(f) for f in modified_files[:3])
                if file_count > 3:
                    files_str += f" and {file_count} files"

                # Perform basic static checks immediately
                fallback_validator = FallbackBuildValidator(
                    self.root_dir, timeout=get_build_validation_timeout()
                )
                static_check_result = fallback_validator.validate(modified_files)
                if not static_check_result.success:
                    final_ret += f"\n⚠️ Basic static check failed:\n{static_check_result.error_message or static_check_result.output}\n"
                    agent.set_addon_prompt(
                        f"Basic static check failed, please fix the code according to the following error information:\n{static_check_result.error_message or static_check_result.output}\n"
                    )
                else:
                    final_ret += f"\n✅ Basic static check passed (took {static_check_result.duration:.2f}s)\n"
            else:
                # User chose to continue validation, mark as asked
                config.mark_as_asked()
                final_ret += f"\n\n⚠️ Build validation failed:\n{format_build_error(build_validation_result)}\n"
                # If the build failed, add a fix prompt
                agent.set_addon_prompt(
                    f"Build validation failed, please fix the code according to the following error information:\n{format_build_error(build_validation_result)}\n"
                    "Please carefully check the error information and resubmit after fixing the compilation/build errors."
                )
        else:
            # Already asked, show the error directly
            final_ret += (
                f"\n\n⚠️ Build validation failed:\n{format_build_error(build_validation_result)}\n"
            )
            # If the build failed, add a fix prompt
            agent.set_addon_prompt(
                f"Build validation failed, please fix the code according to the following error information:\n{format_build_error(build_validation_result)}\n"
                "Please carefully check the error information and resubmit after fixing the compilation/build errors."
            )

        return final_ret

    def handle_build_validation(
        self, modified_files: List[str], agent: Any, final_ret: str
    ) -> Tuple[Optional[Any], str]:
        """Handle build validation

        Returns:
            (build_validation_result, updated_final_ret)
        """
        if not is_enable_build_validation():
            return None, final_ret

        config = BuildValidationConfig(self.root_dir)

        # Check whether build validation is disabled
        if config.is_build_validation_disabled():
            final_ret = self.handle_build_validation_disabled(
                modified_files, config, agent, final_ret
            )
            return None, final_ret

        # Not disabled, perform build validation
        build_validation_result = self.validate_build_after_edit(modified_files)
        if build_validation_result:
            if not build_validation_result.success:
                final_ret = self.handle_build_validation_failure(
                    build_validation_result, config, modified_files, agent, final_ret
                )
            else:
                build_system_info = (
                    f" ({build_validation_result.build_system.value})"
                    if build_validation_result.build_system
                    else ""
                )
                final_ret += f"\n\n✅ Build validation passed{build_system_info} (took {build_validation_result.duration:.2f}s)\n"

        return build_validation_result, final_ret
