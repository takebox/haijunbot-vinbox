# -*- coding: utf-8 -*-
"""Clippy warning fix module. """

import json
import os
import subprocess
from pathlib import Path
from typing import Callable
from typing import Dict
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeOptions
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeStats
from haijunbot.haijunbot_c2rust.optimizer_progress import ProgressManager
from haijunbot.haijunbot_c2rust.optimizer_utils import cargo_check_full
from haijunbot.haijunbot_c2rust.optimizer_utils import check_clippy_warnings
from haijunbot.haijunbot_c2rust.optimizer_utils import git_toplevel
from haijunbot.haijunbot_c2rust.optimizer_utils import iter_rust_files
from haijunbot.haijunbot_c2rust.optimizer_utils import run_cargo_fmt
from haijunbot.haijunbot_c2rust.optimizer_utils import run_cmd

# Use an abstract interface to decouple from the concrete implementation
from haijunbot.haijunbot_c2rust.agent_factory import create_code_agent


class ClippyOptimizer:
    """Clippy warning fix optimizer. """

    def __init__(
        self,
        crate_dir: Path,
        options: OptimizeOptions,
        stats: OptimizeStats,
        progress_manager: ProgressManager,
        append_additional_notes_func: Callable[[str], str],
        verify_and_fix_after_step_func: Callable[[str, List[Path]], bool],
    ):
        self.crate_dir = crate_dir
        self.options = options
        self.stats = stats
        self.progress_manager = progress_manager
        self.append_additional_notes = append_additional_notes_func
        self.verify_and_fix_after_step = verify_and_fix_after_step_func

    def try_clippy_auto_fix(self) -> bool:
        """
        Try using `cargo clippy --fix` to automatically fix clippy warnings.
        When fixing, also include test code (--tests) to avoid deleting variables used in tests.
        Run tests after fixing to verify; if the tests fail, revert the fix.

        Returns:
            True: automatic fix succeeded and tests passed
            False: automatic fix failed or tests did not pass (fix reverted)
        """
        crate = self.crate_dir.resolve()
        PrettyOutput.auto_print(
            "🔄 [c2rust-optimizer][clippy-auto-fix] Trying to use clippy --fix for automatic fix (including test code)...",
        )

        # Record the commit id before the fix
        commit_before = self.progress_manager.get_crate_commit_hash()
        if not commit_before:
            PrettyOutput.auto_print(
                "⚠️ [c2rust-optimizer][clippy-auto-fix] Unable to obtain commit id, skipping automatic fix",
            )
            return False

        # Run cargo clippy --fix, adding the --tests flag to include test code
        try:
            res = subprocess.run(
                [
                    "cargo",
                    "clippy",
                    "--fix",
                    "--tests",
                    "--allow-dirty",
                    "--allow-staged",
                    "--",
                    "-W",
                    "clippy::all",
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(crate),
                timeout=300,  # 5-minute timeout
            )

            if res.returncode != 0:
                PrettyOutput.auto_print(
                    f"❌ [c2rust-optimizer][clippy-auto-fix] clippy --fix failed (return code: {res.returncode})",
                )
                if res.stderr:
                    PrettyOutput.auto_print(
                        f"📄 [c2rust-optimizer][clippy-auto-fix] Error output: {res.stderr[:500]}",
                    )
                return False

            # Check whether any file was modified (via git status or direct check)
            # If there are no modifications, clippy --fix did not fix anything
            repo_root = git_toplevel(crate)
            has_changes = False
            if repo_root:
                try:
                    code, out, _ = run_cmd(
                        ["git", "diff", "--quiet", "--exit-code"], repo_root
                    )
                    has_changes = code != 0  # Non-zero means there are modifications
                except Exception:
                    # If the git status cannot be checked, assume there are modifications
                    has_changes = True
            else:
                # Not in a git repository; assume there are modifications
                has_changes = True

            if not has_changes:
                PrettyOutput.auto_print(
                    "📊 [c2rust-optimizer][clippy-auto-fix] clippy --fix did not modify any file",
                )
                return False

            PrettyOutput.auto_print(
                "🔍 [c2rust-optimizer][clippy-auto-fix] clippy --fix executed, verifying tests...",
            )

            # Run cargo test to verify
            ok, diag_full = cargo_check_full(
                self.crate_dir,
                self.stats,
                self.options.max_checks,
                timeout=self.options.cargo_test_timeout,
            )

            if ok:
                PrettyOutput.auto_print(
                    "✅ [c2rust-optimizer][clippy-auto-fix] Automatic fix succeeded and tests passed",
                )
                return True
            else:
                PrettyOutput.auto_print(
                    "🔙 [c2rust-optimizer][clippy-auto-fix] Tests failed after automatic fix, reverting the fix...",
                )
                # Revert the fix: roll back to the commit before the fix
                if commit_before and self.progress_manager.reset_to_commit(
                    commit_before
                ):
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][clippy-auto-fix] Successfully reverted the automatic fix, rolled back to commit: {commit_before[:8]}",
                    )
                else:
                    PrettyOutput.auto_print(
                        "[c2rust-optimizer][clippy-auto-fix] Failed to revert the fix, please check the code state manually",
                    )
                return False

        except subprocess.TimeoutExpired:
            PrettyOutput.auto_print(
                "[c2rust-optimizer][clippy-auto-fix] clippy --fix timed out, checking for modifications and reverting...",
            )
            # Check whether there are modifications; if so, roll back
            if commit_before:
                repo_root = git_toplevel(crate)
                if repo_root:
                    try:
                        code, _, _ = run_cmd(
                            ["git", "diff", "--quiet", "--exit-code"], repo_root
                        )
                        has_changes = code != 0  # Non-zero means there are modifications
                        if has_changes:
                            if self.progress_manager.reset_to_commit(commit_before):
                                PrettyOutput.auto_print(
                                    f"✅ [c2rust-optimizer][clippy-auto-fix] Reverted the modifications made before the timeout, rolled back to commit: {commit_before[:8]}",
                                )
                            else:
                                PrettyOutput.auto_print(
                                    "❌ [c2rust-optimizer][clippy-auto-fix] Failed to revert the modifications, please check the code state manually",
                                )
                    except Exception:
                        # Unable to check the state; try to roll back directly
                        self.progress_manager.reset_to_commit(commit_before)
            return False
        except Exception as e:
            PrettyOutput.auto_print(
                f"[c2rust-optimizer][clippy-auto-fix] clippy --fix raised an exception: {e}, checking for modifications and reverting...",
            )
            # Check whether there are modifications; if so, roll back
            if commit_before:
                repo_root = git_toplevel(crate)
                if repo_root:
                    try:
                        code, _, _ = run_cmd(
                            ["git", "diff", "--quiet", "--exit-code"], repo_root
                        )
                        has_changes = code != 0  # Non-zero means there are modifications
                        if has_changes:
                            if self.progress_manager.reset_to_commit(commit_before):
                                PrettyOutput.auto_print(
                                    f"✅ [c2rust-optimizer][clippy-auto-fix] Reverted the modifications made before the exception, rolled back to commit: {commit_before[:8]}",
                                )
                            else:
                                PrettyOutput.auto_print(
                                    "❌ [c2rust-optimizer][clippy-auto-fix] Failed to revert the modifications, please check the code state manually",
                                )
                    except Exception:
                        # Unable to check the state; try to roll back directly
                        self.progress_manager.reset_to_commit(commit_before)
            return False

    def code_agent_eliminate_clippy_warnings(
        self, target_files: List[Path], clippy_output: str
    ) -> bool:
        """
        Use CodeAgent to eliminate clippy warnings.
        Fix by file; each time fix the first 10 warnings of a single file (provide all if fewer than 10), then rescan after fixing, iterating continuously.

        Note: CodeAgent must be created and executed under the crate directory to ensure all file operations and command executions occur in the correct context.

        Returns:
            True: all warnings eliminated
            False: there are still warnings not eliminated (reached the maximum iteration count or unable to extract warnings)
        """
        crate = self.crate_dir.resolve()
        file_list: List[str] = []
        for p in target_files:
            try:
                rel = p.resolve().relative_to(crate).as_posix()
            except Exception:
                rel = p.as_posix()
            file_list.append(rel)
            self.stats.files_scanned += 1

        # Switch to the crate directory to ensure CodeAgent is created and executed in the correct context
        prev_cwd = os.getcwd()
        iteration = 0

        try:
            os.chdir(str(crate))

            # Loop to fix warnings, processing by file
            while True:
                iteration += 1

                # Check the current warnings
                has_warnings, current_clippy_output = check_clippy_warnings(crate)
                if not has_warnings:
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][clippy] All warnings eliminated ({iteration - 1} iterations in total)",
                    )
                    return True  # All warnings eliminated

                # Extract warnings by file
                warnings_by_file = self.extract_warnings_by_file(current_clippy_output)
                if not warnings_by_file:
                    PrettyOutput.auto_print(
                        "[c2rust-optimizer][code_agent][clippy] Unable to extract warnings, stopping the fix",
                    )
                    return False  # There are still warnings not eliminated

                # Find the first file with warnings (prioritize files in the target file list)
                target_file_path = None
                target_warnings = None

                # Prioritize files in the target file list
                for file_rel in file_list:
                    # Try to match the file path (may be a relative path or an absolute path)
                    for file_path, warnings in warnings_by_file.items():
                        if file_rel in file_path or file_path.endswith(file_rel):
                            target_file_path = file_path
                            target_warnings = warnings
                            break
                    if target_file_path:
                        break

                # If the target file list has no warnings, select the first file with warnings
                if not target_file_path:
                    target_file_path = next(iter(warnings_by_file.keys()))
                    target_warnings = warnings_by_file[target_file_path]

                # Get the first 10 warnings of this file (provide all if fewer than 10)
                warnings_to_fix = (
                    target_warnings[:10] if target_warnings is not None else []
                )
                warning_count = len(warnings_to_fix)
                total_warnings_in_file = (
                    len(target_warnings) if target_warnings is not None else 0
                )

                PrettyOutput.auto_print(
                    f"🔧 [c2rust-optimizer][code_agent][clippy] Iteration {iteration}: fixing the first {warning_count} warnings of file {target_file_path} ({total_warnings_in_file} in total)",
                )

                # Format the warning information
                formatted_warnings = self.format_warnings_for_prompt(
                    warnings_to_fix, max_count=10
                )

                # Build the hint to fix the first 10 warnings of this file
                prompt_lines: List[str] = [
                    "You are a senior Rust code engineer. Please fix the Clippy warnings in the specified file under the current crate, and output the modifications in the form of a patch: ",
                    f"- crate root directory: {crate}",
                    "",
                    "This fix is only allowed to modify the following file (strictly limited to this single file): ",
                    f"- {target_file_path}",
                    "",
                    f"important: this fix only fixes the first {warning_count} warnings in this file; do not fix other warnings. ",
                    "",
                    "Optimization goals: ",
                    f"1) Fix the {warning_count} Clippy warnings in file {target_file_path}: ",
                    "   - Based on the following Clippy warning information, fix these warnings; ",
                    "   - The warning information includes the file path, line number, warning type, message, and suggestion; use this information to perform the fix; ",
                    "   - For warnings that cannot be fixed automatically, perform a manual fix based on Clippy's suggestion; ",
                    "   - **If it is confirmed to be a false positive** (for example: the modification suggested by the warning would degrade performance, reduce code readability, or conflict with the project's design intent), you may add a `#[allow(clippy::...)]` comment to suppress the warning; ",
                    "   - When using `#[allow(...)]`, you must explain in a comment why it is a false positive, for example: `#[allow(clippy::unnecessary_wraps)] // Keep API consistency; the return type needs to match the interface definition`; ",
                    "   - Prioritize trying to fix the warning; only use `#[allow(...)]` to suppress it when it is confirmed to be a false positive. ",
                    "",
                    "2) Fix problems in existing implementations: ",
                    "   - If, while fixing warnings, you find problems in the existing implementation (such as logic errors, potential bugs, performance issues, memory safety issues, etc), fix them as well; ",
                    "   - These problems may include but are not limited to: null pointer dereference, array out of bounds, uninitialized variables, resource leaks, race conditions, etc; ",
                    "   - When fixing, adhere to the principle of minimal changes and prioritize fixing the most severe problems. ",
                    "",
                    "Constraints and scope: ",
                    f"- **Only modify file {target_file_path}; do not modify other files**; unless necessary (such as fixing a reference path), do not modify other files. ",
                    "- Keep changes minimal; do not perform refactoring or formatting unrelated to eliminating warnings. ",
                    f"- **Only fix the first {warning_count} warnings in this file; do not fix other warnings**. ",
                    "- After modification, ensure `cargo test` passes; if a small amount of related changes is needed, include them in the patch to ensure it passes. ",
                    "- Output only the patch; do not output explanations or extra text. ",
                    "",
                    "Priority notes: ",
                    "- **If test failures or compilation errors occur during optimization, these problems must be resolved first**; ",
                    "- Before fixing warnings, first ensure the code compiles normally and passes tests; ",
                    "- If fixing warnings causes compilation errors or test failures, fix these errors immediately before continuing the optimization. ",
                    "",
                    "Self-check requirement: after outputting each patch, use the execute_script tool to run `cargo test -q` in the crate root directory for verification; ",
                    "If compilation errors or test failures occur, fix these problems first, then continue fixing warnings; ",
                    "If it does not pass, continue outputting new patches for minimal fixes and self-check again, until `cargo test` passes. ",
                    "",
                    f"The Clippy warning information in file {target_file_path} is as follows: ",
                    "<WARNINGS>",
                    formatted_warnings,
                    "</WARNINGS>",
                ]
                prompt = "\n".join(prompt_lines)
                prompt = self.append_additional_notes(prompt)

                # Run cargo fmt before fixing
                run_cargo_fmt(crate)

                # Record the commit id before running
                commit_before = self.progress_manager.get_crate_commit_hash()

                # CodeAgent is created and executed under the crate directory
                agent = create_code_agent(
                    name=f"ClippyWarningEliminator-iter{iteration}",
                    need_summary=False,
                    non_interactive=self.options.non_interactive,
                    enable_task_list_manager=False,
                    disable_review=True,
                    quick_mode=self.options.quick_mode,
                )
                # Subscribe to BEFORE_TOOL_CALL and AFTER_TOOL_CALL events for fine-grained detection of test code deletion
                agent.event_bus.subscribe(
                    BEFORE_TOOL_CALL, self.progress_manager.on_before_tool_call
                )
                agent.event_bus.subscribe(
                    AFTER_TOOL_CALL, self.progress_manager.on_after_tool_call
                )
                # Record the commit id when the Agent was created (as the initial value)
                agent_id = id(agent)
                agent_key = f"agent_{agent_id}"
                initial_commit = self.progress_manager.get_crate_commit_hash()
                if initial_commit:
                    self.progress_manager._agent_before_commits[agent_key] = (
                        initial_commit
                    )
                agent.run(
                    prompt, prefix="[c2rust-optimizer][code_agent][clippy]", suffix=""
                )

                # Detect and handle test code deletion
                if self.progress_manager.check_and_handle_test_deletion(
                    commit_before, agent
                ):
                    # If rolled back, the agent needs to be run again
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][clippy] Test code deletion detected, rolled back, re-running agent (iter={iteration})",
                    )
                    commit_before = self.progress_manager.get_crate_commit_hash()
                    agent.run(
                        prompt,
                        prefix="[c2rust-optimizer][code_agent][clippy][retry]",
                        suffix="",
                    )
                    # Detect again
                    if self.progress_manager.check_and_handle_test_deletion(
                        commit_before, agent
                    ):
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][clippy] Test code deletion detected again, rolled back (iter={iteration})",
                        )

                # Verify whether the fix succeeded (via cargo test)
                ok, _ = cargo_check_full(
                    crate,
                    self.stats,
                    self.options.max_checks,
                    timeout=self.options.cargo_test_timeout,
                )
                if ok:
                    # Fix succeeded; save progress and the commit id
                    try:
                        # Ensure target_file_path is a Path object
                        target_file_path_obj = Path(target_file_path)
                        file_path_to_save: Path = (
                            crate / target_file_path_obj
                            if not target_file_path_obj.is_absolute()
                            else target_file_path_obj
                        )
                        if file_path_to_save.exists():
                            self.progress_manager.save_fix_progress(
                                "clippy_elimination",
                                f"{target_file_path}-iter{iteration}",
                                [file_path_to_save],
                            )
                        else:
                            self.progress_manager.save_fix_progress(
                                "clippy_elimination",
                                f"{target_file_path}-iter{iteration}",
                                None,
                            )
                    except Exception:
                        self.progress_manager.save_fix_progress(
                            "clippy_elimination",
                            f"{target_file_path}-iter{iteration}",
                            None,
                        )
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][clippy] The first {warning_count} warnings of file {target_file_path} were fixed successfully, progress saved",
                    )
                else:
                    # Tests failed; roll back to the commit before running
                    if commit_before:
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][clippy] Tests failed after fixing file {target_file_path}, rolling back to the commit before running: {commit_before[:8]}",
                        )
                        if self.progress_manager.reset_to_commit(commit_before):
                            PrettyOutput.auto_print(
                                f"[c2rust-optimizer][code_agent][clippy] Successfully rolled back to commit: {commit_before[:8]}",
                            )
                        else:
                            PrettyOutput.auto_print(
                                "[c2rust-optimizer][code_agent][clippy] Rollback failed, please check the code state manually",
                            )
                    else:
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][clippy] Tests failed after fixing file {target_file_path}, but the commit before running is unavailable; continuing the fix",
                        )

                # Check warnings again after the fix; if the number of warnings did not decrease, it may be necessary to stop
                has_warnings_after, _ = check_clippy_warnings(crate)
                if not has_warnings_after:
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][clippy] All warnings eliminated ({iteration} iterations in total)",
                    )
                    return True  # All warnings eliminated
        finally:
            os.chdir(prev_cwd)

    def extract_warnings_by_file(
        self, clippy_json_output: str
    ) -> Dict[str, List[Dict]]:
        """
        Extract all warnings from the clippy JSON output and group them by file.

        Returns:
            A dictionary whose keys are file paths and whose values are the lists of warnings for that file
        """
        if not clippy_json_output:
            return {}

        warnings_by_file: Dict[str, List[Dict]] = {}

        for line in clippy_json_output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                # Only process messages of type warning
                if (
                    msg.get("reason") == "compiler-message"
                    and msg.get("message", {}).get("level") == "warning"
                ):
                    message = msg.get("message", {})
                    spans = message.get("spans", [])
                    if spans:
                        primary_span = spans[0]
                        file_path = primary_span.get("file_name", "")
                        if file_path:
                            if file_path not in warnings_by_file:
                                warnings_by_file[file_path] = []
                            warnings_by_file[file_path].append(msg)
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        return warnings_by_file

    def format_warnings_for_prompt(
        self, warnings: List[Dict], max_count: int = 10
    ) -> str:
        """
        Format the warning list for the hint.

        Args:
            warnings: list of warning messages
            max_count: maximum number of warnings to format (default 10)

        Returns:
            the formatted warning information string
        """
        if not warnings:
            return ""

        # Take only the first max_count warnings
        warnings_to_format = warnings[:max_count]
        formatted_warnings = []

        for idx, warning_msg in enumerate(warnings_to_format, 1):
            message = warning_msg.get("message", {})
            spans = message.get("spans", [])

            warning_parts = [f"Warning {idx}:"]

            # Warning type and message
            code = message.get("code", {})
            code_str = code.get("code", "") if code else ""
            message_text = message.get("message", "")
            warning_parts.append(f"  Warning type: {code_str}")
            warning_parts.append(f"  Message: {message_text}")

            # file position
            if spans:
                primary_span = spans[0]
                line_start = primary_span.get("line_start", 0)
                column_start = primary_span.get("column_start", 0)
                line_end = primary_span.get("line_end", 0)
                column_end = primary_span.get("column_end", 0)

                if line_start == line_end:
                    warning_parts.append(
                        f"  Position: {line_start}:{column_start}-{column_end}"
                    )
                else:
                    warning_parts.append(
                        f"  Position: {line_start}:{column_start} - {line_end}:{column_end}"
                    )

                # Code snippet
                label = primary_span.get("label", "")
                if label:
                    warning_parts.append(f"  Code: {label}")

            # Suggestions (help messages)
            children = message.get("children", [])
            for child in children:
                if child.get("level") == "help":
                    help_message = child.get("message", "")
                    help_spans = child.get("spans", [])
                    if help_message:
                        warning_parts.append(f"  Suggestion: {help_message}")
                    if help_spans:
                        help_span = help_spans[0]
                        help_label = help_span.get("label", "")
                        if help_label:
                            warning_parts.append(f"  Suggested code: {help_label}")

            formatted_warnings.append("\n".join(warning_parts))

        if len(warnings) > max_count:
            formatted_warnings.append(
                f"\n (This file has {len(warnings) - max_count} more warnings, which will be handled in subsequent iterations)"
            )

        return "\n\n".join(formatted_warnings)

    def handle_clippy_after_auto_fix(
        self, clippy_targets: List[Path], clippy_output: str
    ) -> bool:
        """
        Handle the clippy warning check after the automatic fix.
        If there are still warnings, continue fixing with CodeAgent.

        Args:
            clippy_targets: list of target files
            clippy_output: the current clippy output

        Returns:
            True: all warnings eliminated
            False: there are still warnings not eliminated (the step is not complete)
        """
        PrettyOutput.auto_print(
            "[c2rust-optimizer] There are still warnings after the automatic fix; continuing to fix with CodeAgent...",
        )
        all_warnings_eliminated = self.code_agent_eliminate_clippy_warnings(
            clippy_targets, clippy_output
        )

        # Verify whether there are still warnings after the fix
        if not self.verify_and_fix_after_step("clippy_elimination", clippy_targets):
            return False

        # Check again whether there are still warnings
        has_warnings_after, _ = check_clippy_warnings(self.crate_dir)
        if not has_warnings_after and all_warnings_eliminated:
            PrettyOutput.auto_print("[c2rust-optimizer] All Clippy warnings eliminated")
            self.progress_manager.save_step_progress(
                "clippy_elimination", clippy_targets
            )
            return True
        else:
            PrettyOutput.auto_print(
                "[c2rust-optimizer] Some Clippy warnings still cannot be eliminated automatically; the step is not complete, stopping subsequent optimization steps",
            )
            return False

    def run_clippy_elimination_step(self) -> bool:
        """
        Run the Clippy warning fix step (step 0).

        Returns:
            True: step completed (no warnings or already fixed)
            False: step not completed (there are still unfixed warnings; subsequent steps should be stopped)
        """
        if self.options.dry_run:
            return True

        PrettyOutput.auto_print("🔍 [c2rust-optimizer] Checking Clippy warnings...")
        has_warnings, clippy_output = check_clippy_warnings(self.crate_dir)

        # If the step is marked as completed but there are still warnings, the previous completion mark is wrong and needs to be cleared
        if (
            "clippy_elimination" in self.progress_manager.steps_completed
            and has_warnings
        ):
            PrettyOutput.auto_print(
                "[c2rust-optimizer] The step is marked as completed but there are still Clippy warnings; clearing the completion mark and continuing the fix",
            )
            self.progress_manager.steps_completed.discard("clippy_elimination")
            if "clippy_elimination" in self.progress_manager._step_commits:
                del self.progress_manager._step_commits["clippy_elimination"]

        if not has_warnings:
            PrettyOutput.auto_print(
                "[c2rust-optimizer] No Clippy warnings found; skipping the elimination step",
            )
            # If there are no warnings, mark clippy_elimination as completed (skipped state)
            if "clippy_elimination" not in self.progress_manager.steps_completed:
                clippy_targets = list(iter_rust_files(self.crate_dir))
                if clippy_targets:
                    self.progress_manager.save_step_progress(
                        "clippy_elimination", clippy_targets
                    )
            return True

        # There are warnings; a fix is needed
        PrettyOutput.auto_print(
            "[c2rust-optimizer] Step 0: eliminate Clippy warnings (this step must be completed before other optimizations can continue)",
        )
        self.progress_manager.snapshot_commit()

        clippy_targets = list(iter_rust_files(self.crate_dir))
        if not clippy_targets:
            PrettyOutput.auto_print(
                "[c2rust-optimizer] Warning: no Rust file found; unable to fix Clippy warnings",
            )
            return False

        # First try to use clippy --fix for automatic fixing
        auto_fix_success = self.try_clippy_auto_fix()
        if auto_fix_success:
            PrettyOutput.auto_print(
                "[c2rust-optimizer] clippy automatic fix succeeded; continuing to check whether there are still warnings...",
            )
            # Re-check the warnings
            has_warnings, clippy_output = check_clippy_warnings(self.crate_dir)
            if not has_warnings:
                PrettyOutput.auto_print(
                    "[c2rust-optimizer] All Clippy warnings eliminated via automatic fix",
                )
                self.progress_manager.save_step_progress(
                    "clippy_elimination", clippy_targets
                )
                return True
            else:
                # There are still warnings; continue fixing with CodeAgent
                return self.handle_clippy_after_auto_fix(clippy_targets, clippy_output)
        else:
            # Automatic fix failed or was not executed; continue fixing with CodeAgent
            PrettyOutput.auto_print(
                "[c2rust-optimizer] clippy automatic fix did not succeed; continuing to fix with CodeAgent...",
            )
            all_warnings_eliminated = self.code_agent_eliminate_clippy_warnings(
                clippy_targets, clippy_output
            )

            # Verify whether there are still warnings after the fix
            if not self.verify_and_fix_after_step("clippy_elimination", clippy_targets):
                return False

            # Check again whether there are still warnings
            has_warnings_after, _ = check_clippy_warnings(self.crate_dir)
            if not has_warnings_after and all_warnings_eliminated:
                PrettyOutput.auto_print("[c2rust-optimizer] All Clippy warnings eliminated")
                self.progress_manager.save_step_progress(
                    "clippy_elimination", clippy_targets
                )
                return True
            else:
                PrettyOutput.auto_print(
                    "[c2rust-optimizer] Some Clippy warnings still cannot be eliminated automatically; the step is not complete, stopping subsequent optimization steps",
                )
                return False
