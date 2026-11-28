# -*- coding: utf-8 -*-
"""Build fix loop module."""

import os
import subprocess
from pathlib import Path
from typing import Callable
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeOptions
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeStats
from haijunbot.haijunbot_c2rust.optimizer_progress import ProgressManager
from haijunbot.haijunbot_c2rust.optimizer_utils import cargo_check_full
from haijunbot.haijunbot_c2rust.optimizer_utils import run_cargo_fmt
from haijunbot.haijunbot_c2rust.agent_factory import create_code_agent


class BuildFixOptimizer:
    """Build fix loop optimizer."""

    def __init__(
        self,
        crate_dir: Path,
        options: OptimizeOptions,
        stats: OptimizeStats,
        progress_manager: ProgressManager,
        append_additional_notes_func: Callable[[str], str],
    ):
        self.crate_dir = crate_dir
        self.options = options
        self.stats = stats
        self.progress_manager = progress_manager
        self.append_additional_notes = append_additional_notes_func

    def build_fix_loop(self, scope_files: List[Path]) -> bool:
        """
        Loop cargo check and use CodeAgent for minimal fixes until it passes, the retry limit is reached, or the check budget is exhausted.
        Only (preferentially) allow modifying scope_files (unless truly necessary), to support batched optimization.
        Returns True if the build was successfully fixed and passes; False if it could not be fixed within the limits.

        Note: CodeAgent must be created and executed in the crate directory to ensure that all file operations and command executions happen in the correct context.
        """
        maxr = int(self.options.build_fix_retries or 0)
        if maxr <= 0:
            return False
        crate = self.crate_dir.resolve()
        allowed: List[str] = []
        for p in scope_files:
            try:
                rel = p.resolve().relative_to(crate).as_posix()
            except Exception:
                rel = p.as_posix()
            allowed.append(rel)

        attempt = 0
        while True:
            # Check the budget
            if (
                self.options.max_checks
                and self.stats.cargo_checks >= self.options.max_checks
            ):
                return False
            # Run the build
            output = ""
            try:
                res = subprocess.run(
                    ["cargo", "test", "-q"],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(crate),
                    timeout=self.options.cargo_test_timeout
                    if self.options.cargo_test_timeout > 0
                    else None,
                )
                self.stats.cargo_checks += 1
                if res.returncode == 0:
                    PrettyOutput.auto_print(
                        "✅ [c2rust-optimizer][build-fix] Build fix succeeded."
                    )
                    return True
                output = ((res.stdout or "") + ("\n" + (res.stderr or ""))).strip()
            except subprocess.TimeoutExpired as e:
                self.stats.cargo_checks += 1
                out_s = e.stdout.decode("utf-8", errors="ignore") if e.stdout else ""
                err_s = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
                output = f"cargo test timed out after {self.options.cargo_test_timeout} seconds"
                full_output = (out_s + ("\n" + err_s if err_s else "")).strip()
                if full_output:
                    output += f"\nOutput:\n{full_output}"
            except Exception as e:
                self.stats.cargo_checks += 1
                output = f"cargo test exception: {e}"

            # Fail if the retry limit is reached
            attempt += 1
            if attempt > maxr:
                PrettyOutput.auto_print(
                    "❌ [c2rust-optimizer][build-fix] Build fix retry count exhausted."
                )
                return False

            PrettyOutput.auto_print(
                f"⚠️ [c2rust-optimizer][build-fix] Build failed. Attempting to fix using CodeAgent (attempt {attempt}/{maxr})..."
            )
            # Generate the minimal fix prompt
            prompt_lines = [
                "Make the minimal necessary fixes to the crate based on the following test/build errors so that `cargo test` passes:",
                f"- crate root directory: {crate}",
                "",
                "This fix preferentially and only allows modifying the following files (do not modify files outside the scope unless truly necessary):",
                *[f"- {rel}" for rel in allowed],
                "",
                "Constraints and scope:",
                "- Keep changes minimal; do not perform refactoring or formatting unrelated to the error;",
                "- Output only the patch; do not output explanations or extra text.",
                "",
                "Optimization objectives:",
                "1) Fix build/test errors:",
                "   - All compile errors and test failures must be resolved first;",
                "   - When fixing, resolve compile errors first, then resolve test failures;",
                "   - If new errors are introduced during the fix, these new errors must be fixed immediately.",
                "",
                "2) Fix problems in existing implementations:",
                "   - If, while fixing build/test errors, you find problems in the existing implementation (such as logic errors, potential bugs, performance issues, memory safety issues, etc.), fix them as well;",
                "   - These problems may include but are not limited to: incorrect algorithm implementations, unchecked boundary conditions, resource leaks, race conditions, data races, etc.;",
                "   - When fixing, follow the principle of minimal changes and fix the most serious problems first.",
                "",
                "Priority notes:",
                "- **All compile errors and test failures must be resolved first**;",
                "- When fixing, resolve compile errors first, then resolve test failures;",
                "- If new errors are introduced during the fix, these new errors must be fixed immediately.",
                "",
                "Self-check requirement: after outputting each patch, use the execute_script tool to run `cargo test -q` in the crate root directory for verification;",
                "If compile errors or test failures occur, fix these problems first;",
                "If it does not pass, continue outputting new patches for minimal fixes and self-check again until `cargo test` passes.",
                "",
                "The build error is as follows:",
                "<BUILD_ERROR>",
                output,
                "</BUILD_ERROR>",
            ]
            prompt = "\n".join(prompt_lines)
            prompt = self.append_additional_notes(prompt)
            # Switch to the crate directory to ensure CodeAgent is created and executed in the correct context
            prev_cwd = os.getcwd()
            try:
                os.chdir(str(crate))
                # Run cargo fmt before fixing
                run_cargo_fmt(crate)

                # Record the commit id before running
                commit_before = self.progress_manager.get_crate_commit_hash()

                # Create and execute CodeAgent in the crate directory
                agent = create_code_agent(
                    name=f"BuildFixAgent-iter{attempt}",
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
                    prefix=f"[c2rust-optimizer][build-fix iter={attempt}]",
                    suffix="",
                )

                # Detect and handle test code deletion
                if self.progress_manager.check_and_handle_test_deletion(
                    commit_before, agent
                ):
                    # If rolled back, re-run the agent
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-optimizer][build-fix] Test code deletion detected; rolled back; re-running agent (iter={attempt})"
                    )
                    commit_before = self.progress_manager.get_crate_commit_hash()
                    agent.run(
                        prompt,
                        prefix=f"[c2rust-optimizer][build-fix iter={attempt}][retry]",
                        suffix="",
                    )
                    # Detect again
                    if self.progress_manager.check_and_handle_test_deletion(
                        commit_before, agent
                    ):
                        PrettyOutput.auto_print(
                            f"❌ [c2rust-optimizer][build-fix] Test code deletion detected again; rolled back (iter={attempt})"
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
                    file_paths = [crate / f for f in allowed if (crate / f).exists()]
                    self.progress_manager.save_fix_progress(
                        "build_fix",
                        f"iter{attempt}",
                        file_paths if file_paths else None,
                    )
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-optimizer][build-fix] Fix attempt {attempt} succeeded; progress saved"
                    )
                    # Return True to indicate the fix succeeded
                    return True
                else:
                    # Test failed; roll back to the commit before running
                    if commit_before:
                        PrettyOutput.auto_print(
                            f"⚠️ [c2rust-optimizer][build-fix] Tests failed after fix attempt {attempt}; rolling back to the commit before running: {commit_before[:8]}"
                        )
                        if self.progress_manager.reset_to_commit(commit_before):
                            PrettyOutput.auto_print(
                                f"ℹ️ [c2rust-optimizer][build-fix] Successfully rolled back to commit: {commit_before[:8]}"
                            )
                        else:
                            PrettyOutput.auto_print(
                                "❌ [c2rust-optimizer][build-fix] Rollback failed; please check the code state manually"
                            )
                    else:
                        PrettyOutput.auto_print(
                            f"⚠️ [c2rust-optimizer][build-fix] Tests failed after fix attempt {attempt}, but the pre-run commit could not be obtained; continuing"
                        )
            finally:
                os.chdir(prev_cwd)

    def verify_and_fix_after_step(
        self, step_name: str, target_files: List[Path]
    ) -> bool:
        """
        Verify the tests after the step executed; if it fails, attempt a fix.

        Args:
            step_name: step name (used in error messages)
            target_files: list of target files (used for the fix scope)

        Returns:
            True: tests pass or the fix succeeded
            False: tests failed and the fix failed (already rolled back)
        """
        ok, diag_full = cargo_check_full(
            self.crate_dir,
            self.stats,
            self.options.max_checks,
            timeout=self.options.cargo_test_timeout,
        )
        if not ok:
            fixed = self.build_fix_loop(target_files)
            if not fixed:
                first = (
                    diag_full.splitlines()[0]
                    if isinstance(diag_full, str) and diag_full
                    else "failed"
                )
                if self.stats.errors is not None:
                    self.stats.errors.append(f"test after {step_name} failed: {first}")
                try:
                    self.progress_manager.reset_to_snapshot()
                finally:
                    return False
        return True
