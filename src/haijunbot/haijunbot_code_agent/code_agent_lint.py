"""CodeAgent static analysis module"""

import os
import shlex
import subprocess

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_code_agent.lint import LINT_AUTO_FIX_COMMANDS
from haijunbot.haijunbot_code_agent.lint import LINT_COMMAND_TEMPLATES_BY_FILE
from haijunbot.haijunbot_code_agent.lint import get_lint_commands_for_files
from haijunbot.haijunbot_code_agent.lint import group_commands_by_template
from haijunbot.haijunbot_utils.config import is_enable_static_analysis
from haijunbot.haijunbot_utils.vinbox_runtime import pwsh_argv


class LintManager:
    """Static analysis manager"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    @staticmethod
    def _clean_surrogates(text: str) -> str:
        """Clean surrogate characters from a string

        On Windows, the output returned by subprocess may contain surrogates (U+DC80-U+DCFF),
        which cannot be encoded as UTF-8 and cause exceptions when printed.
        This method replaces surrogates with the replacement character.

        Args:
            text: a string that may contain surrogates

        Returns:
            The cleaned string
        """
        # Use the errors='replace' parameter of encode to replace surrogates with ?
        # then decode back to a string
        return text.encode("utf-8", errors="replace").decode("utf-8")

    def run_static_analysis(
        self, modified_files: List[str]
    ) -> List[Tuple[str, str, int, str]]:
        """Run static analysis

        Args:
            modified_files: list of modified files

        Returns:
            A result list in the format [(file_path, command, returncode, output), ...]
            Only results with errors or warnings are returned (returncode != 0)
        """
        if not modified_files:
            return []

        # Get all lint commands
        commands = get_lint_commands_for_files(modified_files, self.root_dir)
        if not commands:
            return []

        # Output static check log
        file_count = len(modified_files)
        files_str = ", ".join(os.path.basename(f) for f in modified_files[:3])
        if file_count > 3:
            files_str += f" and {file_count} files"
        # Extract the tool name (first word) from the command
        tool_names = list(set(cmd[1].split()[0] for cmd in commands if cmd[1].split()))
        tools_str = ", ".join(tool_names[:3])
        if len(tool_names) > 3:
            tools_str += f" and {len(tool_names)} tools"
        # Feed the static check info back to the LLM instead of outputting it to the user
        # PrettyOutput.auto_print("🔍 Static checking...")

        results = []
        # Record the check result for each file
        file_results = []  # [(file_name, command, status, message), ...]

        # Group by command template, the same tool can be executed in batches
        grouped = group_commands_by_template(commands)

        for template_key, file_commands in grouped.items():
            for file_path, command in file_commands:
                file_name = os.path.basename(file_path)
                try:
                    # Check whether the file exists
                    abs_file_path = (
                        os.path.join(self.root_dir, file_path)
                        if not os.path.isabs(file_path)
                        else file_path
                    )
                    if not os.path.exists(abs_file_path):
                        file_results.append((file_name, command, "skipped", "file does not exist"))
                        continue

                    # Still show the executed command to the user
                    PrettyOutput.auto_print(f"ℹ️ Executing: {command}")

                    # Execute the command (static analysis tools: ruff/ty, etc., command comes from config)
                    # Dijalankan lewat pwsh dengan argv list, bukan shell=True.
                    result = subprocess.run(
                        pwsh_argv(command),
                        shell=False,
                        cwd=self.root_dir,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=600,  # 600 second timeout
                    )

                    # Only record results with errors or warnings
                    if result.returncode != 0:
                        output = result.stdout + result.stderr
                        if output.strip():  # Only record if there is output
                            results.append(
                                (
                                    file_path,
                                    command,
                                    result.returncode,
                                    output,
                                )
                            )
                            file_results.append(
                                (file_name, command, "failed", "issues found")
                            )
                            # Print the check result on failure
                            output_preview = (
                                output[:2000] if len(output) > 2000 else output
                            )
                            # Clean up any surrogate characters to avoid encoding errors on Windows
                            output_preview = self._clean_surrogates(output_preview)
                            PrettyOutput.auto_print(
                                f"⚠️ Check failed ({file_name}):\n{output_preview}"
                            )
                            if len(output) > 2000:
                                PrettyOutput.auto_print(
                                    f"⚠️ ... (output truncated, {len(output)} characters total)"
                                )
                        else:
                            file_results.append((file_name, command, "passed", ""))
                    else:
                        file_results.append((file_name, command, "passed", ""))

                except subprocess.TimeoutExpired:
                    results.append((file_path, command, -1, "execution timed out (600s)"))
                    file_results.append(
                        (file_name, command, "timeout", "execution timed out (600s)")
                    )
                    PrettyOutput.auto_print(
                        f"⚠️ Check timed out ({file_name}): execution timed out (600s)"
                    )
                except FileNotFoundError:
                    # Tool not installed, skip
                    file_results.append((file_name, command, "skipped", "tool not installed"))
                    continue
                except Exception as e:
                    # Other errors, record but continue
                    # Clean up surrogate characters in the exception message
                    e_msg = self._clean_surrogates(str(e))
                    PrettyOutput.auto_print(
                        f"⚠ Failed to execute lint command: {command}, error: {e_msg}"
                    )
                    file_results.append(
                        (file_name, command, "failed", f"execution failed: {str(e)[:50]}")
                    )
                    continue

        # Print all check results at once
        if file_results:
            total_files = len(file_results)
            passed_count = sum(
                1 for _, _, status, _ in file_results if status == "passed"
            )
            failed_count = sum(
                1 for _, _, status, _ in file_results if status == "failed"
            )
            timeout_count = sum(
                1 for _, _, status, _ in file_results if status == "timeout"
            )
            sum(1 for _, _, status, _ in file_results if status == "skipped")

            # Condensed one-line result summary
            summary = f"🔍 Static check: {total_files} files"
            if failed_count > 0:
                summary += f", {failed_count} failed"
            if timeout_count > 0:
                summary += f", {timeout_count} timed out"
            if passed_count == total_files:
                summary += " ✅ all passed"

            if failed_count > 0 or timeout_count > 0:
                PrettyOutput.auto_print(f"⚠️ {summary}")
            else:
                PrettyOutput.auto_print(f"✅ {summary}")
        else:
            PrettyOutput.auto_print("✅ Static check completed")

        return results

    def format_lint_results(self, results: List[Tuple[str, str, int, str]]) -> str:
        """Format lint results

        Args:
            results: [(file_path, command, returncode, output), ...]

        Returns:
            The formatted error information string
        """
        if not results:
            return ""

        lines = []
        for file_path, command, returncode, output in results:
            # Extract the tool name (first word) from the command
            tool_name = command.split()[0] if command.split() else "unknown"
            lines.append(f"Tool: {tool_name}")
            lines.append(f"File: {file_path}")
            lines.append(f"Command: {command}")
            if returncode == -1:
                lines.append(f"Error: {output}")
            else:
                # Limit the output length to avoid it being too long
                output_preview = output[:1000] if len(output) > 1000 else output
                lines.append(f"Output:\n{output_preview}")
                if len(output) > 1000:
                    lines.append(f"... (output truncated, {len(output)} characters total)")
            lines.append("")  # blank line separator

        return "\n".join(lines)

    def _get_auto_fix_suggestions(
        self, lint_results: List[Tuple[str, str, int, str]]
    ) -> str:
        """Generate auto-fix suggestions based on lint results

        Args:
            lint_results: [(file_path, command, returncode, output), ...]

        Returns:
            The auto-fix command suggestion string, or an empty string if no auto-fix tool is available
        """
        # Collect all involved files and tools
        file_tool_map: Dict[str, set] = {}  # {file_path: set(tool_names)}
        for file_path, command, _, _ in lint_results:
            command_parts = command.split()
            tool_name = command_parts[0] if command_parts else "unknown"
            if file_path not in file_tool_map:
                file_tool_map[file_path] = set()
            file_tool_map[file_path].add(tool_name)

        # Generate auto-fix commands
        suggestions = []
        for file_path, tool_names in file_tool_map.items():
            for tool_name in tool_names:
                # Look up the auto-fix commands for this tool
                auto_fix_cmds = LINT_AUTO_FIX_COMMANDS.get(tool_name, [])
                for cmd_template in auto_fix_cmds:
                    # Replace placeholders
                    if "{file_path}" in cmd_template:
                        cmd = cmd_template.replace(
                            "{file_path}", shlex.quote(file_path)
                        )
                    else:
                        cmd = cmd_template
                    suggestions.append(f"  {cmd}")

        if suggestions:
            return "\n".join(suggestions)
        return ""

    def handle_static_analysis(
        self,
        modified_files: List[str],
        build_validation_result: Optional[Any],
        config: Any,
        agent: Any,
        final_ret: str,
    ) -> str:
        """Handle static analysis

        Returns:
            The updated result string
        """
        # Check whether static analysis is enabled
        if not is_enable_static_analysis():
            PrettyOutput.auto_print("ℹ️ Static analysis is disabled, skipping static check")
            return final_ret

        # Check whether any lint tool is available
        def get_lint_tool_names(file_path: str) -> List[str]:
            """Get the list of lint tool names for a file"""
            filename = os.path.basename(file_path)
            filename_lower = filename.lower()
            templates = LINT_COMMAND_TEMPLATES_BY_FILE.get(filename_lower, [])
            if not templates:
                ext = os.path.splitext(filename)[1]
                if ext:
                    templates = LINT_COMMAND_TEMPLATES_BY_FILE.get(ext.lower(), [])
            # Extract the tool name (first word of the command template)
            return [
                template.split()[0] if template.split() else "unknown"
                for template in templates
            ]

        lint_tools_info = "\n".join(
            f"   - {file}: using {', '.join(get_lint_tool_names(file))}"
            for file in modified_files
            if get_lint_tool_names(file)
        )

        if not lint_tools_info:
            PrettyOutput.auto_print("ℹ️ No available static check tool found, skipping static check")
            return final_ret

        # If build validation failed and is not disabled, skip static analysis (to avoid duplicate errors)
        # If build validation is disabled, perform static analysis (since only basic static checks were done)
        should_skip_static = (
            build_validation_result
            and not build_validation_result.success
            and not config.is_build_validation_disabled()
        )

        if should_skip_static:
            PrettyOutput.auto_print("ℹ️ Build validation failed, skipping static analysis (to avoid duplicate errors)")
            return final_ret

        # Run the static scan directly
        lint_results = self.run_static_analysis(modified_files)
        if lint_results:
            # There are errors or warnings, first check whether there is an auto-fix tool
            auto_fix_suggestions = self._get_auto_fix_suggestions(lint_results)

            # Print auto-fix suggestions
            if auto_fix_suggestions:
                PrettyOutput.auto_print(
                    f"💡 Static check warnings detected, it is recommended to use the auto-fix tool first:\n{auto_fix_suggestions}"
                )

            # Print the complete check results
            errors_summary = self.format_lint_results(lint_results)

            # Build the prompt message
            if auto_fix_suggestions:
                addon_prompt = f"""
The static scan found the following issues, it is recommended to use the auto-fix tool first:

{auto_fix_suggestions}

If the auto-fix tool cannot resolve all issues, then fix them manually. Static check details:

{errors_summary}

Please try the auto-fix commands above first, then check the remaining issues.
                """
            else:
                addon_prompt = f"""
The static scan found the following issues, please fix the code according to the error information:

{errors_summary}

Please carefully check and fix all issues.
                """
            agent.set_addon_prompt(addon_prompt)
            final_ret += "\n\n⚠️ Static scan found issues, fix has been prompted\n"
        else:
            final_ret += "\n\n✅ Static scan passed\n"

        return final_ret
