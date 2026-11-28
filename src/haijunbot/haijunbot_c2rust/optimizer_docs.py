# -*- coding: utf-8 -*-
"""Documentation enhancement optimization module."""

import os
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


class DocsOptimizer:
    """Documentation enhancement optimizer."""

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

    def code_agent_opt_docs(self, target_files: List[Path]) -> None:
        """
        Use CodeAgent for documentation enhancement.

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

        prompt_lines: List[str] = [
            "You are a senior Rust code engineer. Perform documentation enhancement optimization in the current crate and output changes as a patch:",
            f"- crate root directory: {crate}",
            "",
            "This optimization may only modify the following file scope (strictly limited):",
            *[f"- {rel}" for rel in file_list],
            "",
            "Optimization objectives:",
            "1) Documentation enhancement:",
            "   - Add `//! ...` module doc comments (placed at the beginning of the file) to files missing module-level documentation;",
            "   - Add `/// ...` doc comments to public functions (pub or pub(crate)) missing function documentation;",
            "   - The documentation content may be placeholder comments (such as `//! TODO: Add module-level documentation` or `/// TODO: Add documentation`), or brief explanations based on the function signature and implementation.",
            "",
            "2) Fix problems in existing implementations:",
            "   - If, during documentation enhancement, you find problems in the existing implementation (such as logic errors, potential bugs, performance issues, memory safety issues, etc.), fix them as well;",
            "   - These problems may include but are not limited to: incorrect algorithm implementations, unchecked boundary conditions, resource leaks, race conditions, etc.;",
            "   - When fixing, follow the principle of minimal changes and fix the most serious problems first.",
            "",
            "Constraints and scope:",
            "- Only modify the files listed above; do not modify other files unless necessary (such as fixing reference paths).",
            "- Keep changes minimal; do not perform refactoring or formatting unrelated to documentation enhancement.",
            "- After modification, `cargo test` must pass; if a few supporting changes are needed, include them in the patch to ensure it passes.",
            "- Output only the patch; do not output explanations or extra text.",
            "",
            "Priority notes:",
            "- **If test failures or compile errors occur during optimization, these problems must be resolved first**;",
            "- Before performing documentation enhancement, first ensure the code compiles normally and passes tests;",
            "- If documentation enhancement causes compile errors or test failures, these errors must be fixed immediately before continuing optimization.",
            "",
            "Self-check requirement: after outputting each patch, use the execute_script tool to run `cargo test -q` in the crate root directory for verification;",
            "If compile errors or test failures occur, fix these problems first before continuing documentation enhancement;",
            "If it does not pass, continue outputting new patches for minimal fixes and self-check again until `cargo test` passes.",
        ]
        prompt = "\n".join(prompt_lines)
        prompt = self.append_additional_notes(prompt)
        # Switch to the crate directory to ensure CodeAgent is created and executed in the correct context
        prev_cwd = os.getcwd()
        PrettyOutput.auto_print(
            "📝 [c2rust-optimizer][code_agent][doc] Calling CodeAgent for documentation enhancement..."
        )
        try:
            os.chdir(str(crate))
            # Run cargo fmt before fixing
            run_cargo_fmt(crate)

            # Record the commit id before running
            commit_before = self.progress_manager.get_crate_commit_hash()

            # Create and execute CodeAgent in the crate directory
            agent = create_code_agent(
                name="DocumentationAgent",
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
                self.progress_manager._agent_before_commits[agent_key] = initial_commit
            agent.run(prompt, prefix="[c2rust-optimizer][code_agent][doc]", suffix="")

            # Detect and handle test code deletion
            if self.progress_manager.check_and_handle_test_deletion(
                commit_before, agent
            ):
                # If rolled back, re-run the agent
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-optimizer][code_agent][doc] Test code deletion detected; rolled back; re-running agent"
                )
                commit_before = self.progress_manager.get_crate_commit_hash()
                agent.run(
                    prompt,
                    prefix="[c2rust-optimizer][code_agent][doc][retry]",
                    suffix="",
                )
                # Detect again
                if self.progress_manager.check_and_handle_test_deletion(
                    commit_before, agent
                ):
                    PrettyOutput.auto_print(
                        "❌ [c2rust-optimizer][code_agent][doc] Test code deletion detected again; rolled back"
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
                file_paths = [crate / f for f in file_list if (crate / f).exists()]
                self.progress_manager.save_fix_progress(
                    "doc_opt", "batch", file_paths if file_paths else None
                )
                PrettyOutput.auto_print(
                    "✅ [c2rust-optimizer][code_agent][doc] Documentation enhancement succeeded; progress saved"
                )
            else:
                # Test failed; roll back to the commit before running
                if commit_before:
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-optimizer][code_agent][doc] Tests failed after documentation enhancement; rolling back to the commit before running: {commit_before[:8]}"
                    )
                    if self.progress_manager.reset_to_commit(commit_before):
                        PrettyOutput.auto_print(
                            f"ℹ️ [c2rust-optimizer][code_agent][doc] Successfully rolled back to commit: {commit_before[:8]}"
                        )
                    else:
                        PrettyOutput.auto_print(
                            "❌ [c2rust-optimizer][code_agent][doc] Rollback failed; please check the code state manually"
                        )
                else:
                    PrettyOutput.auto_print(
                        "⚠️ [c2rust-optimizer][code_agent][doc] Tests failed after documentation enhancement, but the pre-run commit could not be obtained"
                    )
        finally:
            os.chdir(prev_cwd)
