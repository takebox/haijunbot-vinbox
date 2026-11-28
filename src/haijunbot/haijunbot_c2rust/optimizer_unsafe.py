# -*- coding: utf-8 -*-
"""Unsafe cleanup optimization module."""

import os
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
from haijunbot.haijunbot_c2rust.optimizer_utils import check_missing_safety_doc_warnings
from haijunbot.haijunbot_c2rust.optimizer_utils import run_cargo_fmt
from haijunbot.haijunbot_c2rust.agent_factory import create_code_agent


class UnsafeOptimizer:
    """Unsafe cleanup optimizer."""

    def __init__(
        self,
        crate_dir: Path,
        options: OptimizeOptions,
        stats: OptimizeStats,
        progress_manager: ProgressManager,
        append_additional_notes_func: Callable[[str], str],
        extract_warnings_by_file_func: Callable[[str], Dict[str, List[Dict]]],
        format_warnings_for_prompt_func: Callable[[List[Dict], int], str],
    ):
        self.crate_dir = crate_dir
        self.options = options
        self.stats = stats
        self.progress_manager = progress_manager
        self.append_additional_notes = append_additional_notes_func
        self.extract_warnings_by_file = extract_warnings_by_file_func
        self.format_warnings_for_prompt = format_warnings_for_prompt_func

    def code_agent_opt_unsafe_cleanup(self, target_files: List[Path]) -> None:
        """
        Use CodeAgent for unsafe cleanup optimization.
        Use clippy's missing_safety_doc checker to find unsafe warnings; process by file, handling all warnings in one file at a time.

        Note: CodeAgent must be created and executed in the crate directory to ensure that all file operations and command executions happen in the correct context.
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

            # Loop fixing unsafe warnings, processing by file
            while True:
                iteration += 1

                # Check the current missing_safety_doc warnings
                has_warnings, current_clippy_output = check_missing_safety_doc_warnings(
                    crate
                )
                if not has_warnings:
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][unsafe-cleanup] All missing_safety_doc warnings eliminated (total iterations: {iteration - 1})"
                    )
                    return  # All warnings eliminated

                # Extract warnings by file
                warnings_by_file = self.extract_warnings_by_file(current_clippy_output)
                if not warnings_by_file:
                    PrettyOutput.auto_print(
                        "[c2rust-optimizer][code_agent][unsafe-cleanup] Unable to extract warnings; stopping fixes"
                    )
                    return  # Warnings still remain

                # Find the first file with warnings (prioritize files in the target file list)
                target_file_path = None
                target_warnings = None

                # Prioritize files in the target file list
                for file_rel in file_list:
                    # Try to match the file path (may be a relative or absolute path)
                    for file_path, warnings in warnings_by_file.items():
                        if file_rel in file_path or file_path.endswith(file_rel):
                            target_file_path = file_path
                            target_warnings = warnings
                            break
                    if target_file_path:
                        break

                # If there are no warnings in the target file list, choose the first file with warnings
                if not target_file_path:
                    target_file_path = next(iter(warnings_by_file.keys()))
                    target_warnings = warnings_by_file[target_file_path]

                # Get all warnings for that file (process all warnings in one file at a time)
                warnings_to_fix = target_warnings
                warning_count = (
                    len(warnings_to_fix) if warnings_to_fix is not None else 0
                )

                PrettyOutput.auto_print(
                    f"[c2rust-optimizer][code_agent][unsafe-cleanup] Iteration {iteration}: fixing {warning_count} missing_safety_doc warnings in file {target_file_path}"
                )

                # Format the warning information
                formatted_warnings = self.format_warnings_for_prompt(
                    warnings_to_fix or [], warning_count
                )

                # Build the prompt to fix all missing_safety_doc warnings in that file
                prompt_lines: List[str] = [
                    "You are a senior Rust code engineer. Fix the missing_safety_doc warnings in the specified file in the current crate and output the changes as a patch:",
                    f"- crate root directory: {crate}",
                    "",
                    "This optimization may only modify the following file (strictly limited; handle only this one file):",
                    f"- {target_file_path}",
                    "",
                    f"Important: this fix only fixes the {warning_count} missing_safety_doc warnings in that file.",
                    "",
                    "Optimization objectives:",
                    f"1) Fix the {warning_count} missing_safety_doc warnings in file {target_file_path}:",
                    "   **Fixing principle: eliminate if possible; only add a SAFETY comment when it cannot be eliminated**",
                    "",
                    "   Priority 1 (try first): eliminate unsafe",
                    "   - If an unsafe function or method does not actually need to be unsafe, remove the unsafe keyword;",
                    "   - If an unsafe block can be removed, remove the entire unsafe block;",
                    "   - If an unsafe block's scope can be narrowed, narrow it;",
                    "   - Analyze the code carefully to determine whether unsafe is really needed; if it can be implemented in a safe way, prefer the safe way.",
                    "",
                    "   Priority 2 (when it cannot be eliminated): add a SAFETY comment",
                    "   - Only when it is confirmed that unsafe cannot be eliminated, add a `/// SAFETY: ...` doc comment to the unsafe function or method;",
                    "   - The SAFETY comment must explain in detail why the function or method is unsafe, including:",
                    "     * which invariants must be maintained by the caller;",
                    "     * which preconditions must be satisfied;",
                    "     * situations that may cause undefined behavior;",
                    "     * why a safe alternative cannot be used;",
                    "   - If an unsafe block cannot be removed but its scope can be narrowed, narrow it and add a `/// SAFETY: ...` comment immediately adjacent.",
                    "",
                    "2) Fix problems in existing implementations:",
                    "   - If, while fixing missing_safety_doc warnings, you find problems in the existing implementation (such as logic errors, potential bugs, performance issues, memory safety issues, etc.), fix them as well;",
                    "   - These problems may include but are not limited to: incorrect use of unsafe, unchecked boundary conditions, resource leaks, race conditions, data races, etc.;",
                    "   - When fixing, follow the principle of minimal changes and fix the most serious problems first.",
                    "",
                    "Constraints and scope:",
                    f"- **Only modify file {target_file_path}; do not modify other files**; do not modify other files unless necessary (such as fixing reference paths).",
                    "- Keep changes minimal; do not perform refactoring or formatting unrelated to fixing missing_safety_doc warnings.",
                    f"- **Only fix the {warning_count} missing_safety_doc warnings in that file; do not fix other warnings**.",
                    "- After modification, `cargo test` must pass; if a few supporting changes are needed, include them in the patch to ensure it passes.",
                    "- Output only the patch; do not output explanations or extra text.",
                    "",
                    "Priority notes:",
                    "- **Priority for fixing unsafe: eliminate if possible; only add a SAFETY comment when it cannot be eliminated**;",
                    "- For each unsafe, first analyze whether it can be safely removed; only add a SAFETY comment when it is confirmed it cannot be removed;",
                    "- **If test failures or compile errors occur during optimization, these problems must be resolved first**;",
                    "- Before fixing warnings, first ensure the code compiles normally and passes tests;",
                    "- If fixing warnings causes compile errors or test failures, these errors must be fixed immediately before continuing optimization.",
                    "",
                    "Self-check requirement: after outputting each patch, use the execute_script tool to run `cargo test -q` in the crate root directory for verification;",
                    "If compile errors or test failures occur, fix these problems first before continuing to fix warnings;",
                    "If it does not pass, continue outputting new patches for minimal fixes and self-check again until `cargo test` passes.",
                    "",
                    f"The missing_safety_doc warning information for file {target_file_path} is as follows:",
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

                # Create and execute CodeAgent in the crate directory
                agent = create_code_agent(
                    name=f"UnsafeCleanupAgent-iter{iteration}",
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
                # Record the commit id at Agent creation time (as the initial value)
                agent_id = id(agent)
                agent_key = f"agent_{agent_id}"
                initial_commit = self.progress_manager.get_crate_commit_hash()
                if initial_commit:
                    self.progress_manager._agent_before_commits[agent_key] = (
                        initial_commit
                    )
                agent.run(
                    prompt,
                    prefix=f"[c2rust-optimizer][code_agent][unsafe-cleanup][iter{iteration}]",
                    suffix="",
                )

                # Detect and handle test code deletion
                if self.progress_manager.check_and_handle_test_deletion(
                    commit_before, agent
                ):
                    # If rolled back, re-run the agent
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][unsafe-cleanup] Test code deletion detected; rolled back; re-running agent (iter={iteration})"
                    )
                    commit_before = self.progress_manager.get_crate_commit_hash()
                    agent.run(
                        prompt,
                        prefix=f"[c2rust-optimizer][code_agent][unsafe-cleanup][iter{iteration}][retry]",
                        suffix="",
                    )
                    # Detect again
                    if self.progress_manager.check_and_handle_test_deletion(
                        commit_before, agent
                    ):
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][unsafe-cleanup] Test code deletion detected again; rolled back (iter={iteration})"
                        )

                # Verify whether the fix succeeded (via cargo test)
                ok, _ = cargo_check_full(
                    crate,
                    self.stats,
                    self.options.max_checks,
                    timeout=self.options.cargo_test_timeout,
                )
                if ok:
                    # Fix succeeded; save progress and commit id
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
                                "unsafe_cleanup",
                                f"{target_file_path}-iter{iteration}",
                                [file_path_to_save],
                            )
                        else:
                            self.progress_manager.save_fix_progress(
                                "unsafe_cleanup",
                                f"{target_file_path}-iter{iteration}",
                                None,
                            )
                    except Exception:
                        self.progress_manager.save_fix_progress(
                            "unsafe_cleanup",
                            f"{target_file_path}-iter{iteration}",
                            None,
                        )
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][unsafe-cleanup] The {warning_count} warnings in file {target_file_path} were fixed successfully; progress saved"
                    )
                else:
                    # Test failed; roll back to the commit before running
                    if commit_before:
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][unsafe-cleanup] Tests failed after fixing file {target_file_path}; rolling back to the commit before running: {commit_before[:8]}"
                        )
                        if self.progress_manager.reset_to_commit(commit_before):
                            PrettyOutput.auto_print(
                                f"[c2rust-optimizer][code_agent][unsafe-cleanup] Successfully rolled back to commit: {commit_before[:8]}"
                            )
                        else:
                            PrettyOutput.auto_print(
                                "[c2rust-optimizer][code_agent][unsafe-cleanup] Rollback failed; please check the code state manually"
                            )
                    else:
                        PrettyOutput.auto_print(
                            f"[c2rust-optimizer][code_agent][unsafe-cleanup] Tests failed after fixing file {target_file_path}, but the pre-run commit could not be obtained; continuing fixes"
                        )

                # Check warnings again after fixing
                has_warnings_after, _ = check_missing_safety_doc_warnings(crate)
                if not has_warnings_after:
                    PrettyOutput.auto_print(
                        f"[c2rust-optimizer][code_agent][unsafe-cleanup] All missing_safety_doc warnings eliminated (total iterations: {iteration})"
                    )
                    return  # All warnings eliminated

        finally:
            os.chdir(prev_cwd)
