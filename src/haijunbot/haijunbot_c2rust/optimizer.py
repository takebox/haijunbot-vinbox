# -*- coding: utf-8 -*-
"""
Rust code optimizer: performs several conservative optimization steps on a transpiled or generated Rust project.

All optimization steps are performed using CodeAgent, ensuring they are intelligent, accurate, and reversible.

Goals and strategy (conservative, reversible):
1) unsafe cleanup:
   - Use CodeAgent to identify removable `unsafe { ... }` wrappers; after removal, run `cargo test` to verify
   - If unsafe must be kept, narrow its scope and add a `/// SAFETY: ...` doc comment immediately adjacent explaining the reason
2) Visibility optimization (minimize visibility as much as possible):
   - Use CodeAgent to demote `pub fn` to `pub(crate) fn` (if the function is only used within the crate)
   - Keep external interfaces (interfaces used across crates, such as top-level exports in lib.rs) as `pub`
3) Documentation enhancement:
   - Use CodeAgent to add `//! ...` module doc comments to files missing module-level documentation
   - Add `/// ...` doc comments to public functions missing function documentation (may be placeholder comments or brief explanations)

Implementation notes:
- All optimization steps are performed via CodeAgent; after each step `cargo test` is run for verification
- If verification fails, enter the build-fix loop (using CodeAgent for minimal fixes) until it passes or the retry limit is reached
- All modifications keep the minimal necessary textual changes; on failure, automatically roll back to the snapshot (when git_guard is enabled)
- The result summary and log are written to <crate_dir>/.haijunbot/c2rust/optimize_report.json
- Progress record (resumable): <crate_dir>/.haijunbot/c2rust/optimize_progress.json
  - field processed: files that have been optimized (path relative to the crate root, with posix slashes)

Limitations:
- Relies on CodeAgent's intelligent analysis capability; complex syntax, macros, conditional compilation, etc. are handled by CodeAgent
- All optimization steps are verified via `cargo test` to ensure the modified code compiles and runs normally
- Provides Git protection (git_guard); on failure, automatically rolls back to the snapshot

Entry point:
- optimize_project(project_root: Optional[Path], crate_dir: Optional[Path], ...) as a simple external entry point
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict
from typing import List
from typing import Callable
from typing import Optional

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.optimizer_build_fix import BuildFixOptimizer
from haijunbot.haijunbot_c2rust.optimizer_clippy import ClippyOptimizer
from haijunbot.haijunbot_c2rust.optimizer_config import (
    append_additional_notes as append_notes,
)
from haijunbot.haijunbot_c2rust.optimizer_config import load_additional_notes
from haijunbot.haijunbot_c2rust.optimizer_docs import DocsOptimizer

# Import the split-out modules
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeOptions
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeStats
from haijunbot.haijunbot_c2rust.optimizer_progress import ProgressManager
from haijunbot.haijunbot_c2rust.optimizer_report import get_report_display_path
from haijunbot.haijunbot_c2rust.optimizer_report import write_final_report
from haijunbot.haijunbot_c2rust.optimizer_unsafe import UnsafeOptimizer
from haijunbot.haijunbot_c2rust.optimizer_utils import compute_target_files
from haijunbot.haijunbot_c2rust.optimizer_utils import detect_crate_dir
from haijunbot.haijunbot_c2rust.optimizer_utils import ensure_report_dir
from haijunbot.haijunbot_c2rust.optimizer_utils import find_project_root
from haijunbot.haijunbot_c2rust.optimizer_utils import iter_rust_files
from haijunbot.haijunbot_c2rust.optimizer_visibility import VisibilityOptimizer

# Utility functions have been moved to optimizer_utils.py


class Optimizer:
    def __init__(
        self,
        crate_dir: Path,
        options: OptimizeOptions,
        project_root: Optional[Path] = None,
    ):
        self.crate_dir = crate_dir
        self.project_root = (
            project_root if project_root else crate_dir.parent
        )  # Default to the parent directory of crate_dir
        self.options = options
        self.stats = OptimizeStats()
        # Progress file
        self.report_dir = ensure_report_dir(self.crate_dir)
        self.progress_path = self.report_dir / "optimize_progress.json"
        self._target_files: List[Path] = []

        # Initialize the progress manager
        self.progress_manager = ProgressManager(
            self.crate_dir, self.options, self.progress_path
        )
        self.progress_manager.load_or_reset_progress()

        # Read additional notes
        self.additional_notes = load_additional_notes(self.crate_dir)

        # Initialize each optimizer module
        self.build_fix_optimizer = BuildFixOptimizer(
            self.crate_dir,
            self.options,
            self.stats,
            self.progress_manager,
            lambda p: append_notes(p, self.additional_notes),
        )

        self.clippy_optimizer = ClippyOptimizer(
            self.crate_dir,
            self.options,
            self.stats,
            self.progress_manager,
            lambda p: append_notes(p, self.additional_notes),
            self.build_fix_optimizer.verify_and_fix_after_step,
        )

        self.unsafe_optimizer = UnsafeOptimizer(
            self.crate_dir,
            self.options,
            self.stats,
            self.progress_manager,
            lambda p: append_notes(p, self.additional_notes),
            self.clippy_optimizer.extract_warnings_by_file,
            self.clippy_optimizer.format_warnings_for_prompt,
        )

        self.visibility_optimizer = VisibilityOptimizer(
            self.crate_dir,
            self.options,
            self.stats,
            self.progress_manager,
            lambda p: append_notes(p, self.additional_notes),
        )

        self.docs_optimizer = DocsOptimizer(
            self.crate_dir,
            self.options,
            self.stats,
            self.progress_manager,
            lambda p: append_notes(p, self.additional_notes),
        )

    # Configuration loading methods have been moved to optimizer_config.py
    # Git snapshot methods have been moved to ProgressManager
    # File selection methods have been moved to optimizer_utils.py
    # Report methods have been moved to optimizer_report.py
    # Verification and fix methods have been moved to BuildFixOptimizer

    def _run_optimization_step(
        self,
        step_name: str,
        step_display_name: str,
        step_num: int,
        target_files: List[Path],
        opt_func: Callable[[List[Path]], None],
    ) -> Optional[int]:
        """
        Execute a single optimization step (unsafe_cleanup, visibility_opt, doc_opt).

        Args:
            step_name: step name (used for progress saving and error messages)
            step_display_name: step display name (used in logs)
            step_num: step number
            target_files: list of target files
            opt_func: optimization function (accepts target_files as an argument)

        Returns:
            the next step number; returns None on failure
        """
        PrettyOutput.auto_print(
            f"🔧 [c2rust-optimizer] Step {step_num}: {step_display_name}",
        )
        self.progress_manager.snapshot_commit()
        if not self.options.dry_run:
            opt_func(target_files)
            if not self.build_fix_optimizer.verify_and_fix_after_step(
                step_name, target_files
            ):
                # Verification failed and a rollback occurred; return None to indicate failure
                return None
            # Save step progress
            self.progress_manager.save_step_progress(step_name, target_files)
        return step_num + 1

    # Clippy-related methods have been moved to ClippyOptimizer

    def run(self) -> OptimizeStats:
        """
        Main entry point for running the optimization flow.

        Returns:
            optimization statistics
        """
        report_path = self.report_dir / "optimize_report.json"
        PrettyOutput.auto_print(
            f"🚀 [c2rust-optimizer][start] Starting optimization of crate: {self.crate_dir}"
        )
        try:
            # Record a snapshot before the batch starts
            self.progress_manager.snapshot_commit()

            # ========== Step 0: Clippy warning fixes (must be the first step, and must complete) ==========
            # Note: clippy warning fixes do not depend on whether there are new files to process; even if all files have been processed, warnings should still be checked and fixed
            if not self.clippy_optimizer.run_clippy_elimination_step():
                # Clippy warning fixes are not complete; stop subsequent steps
                return self.stats

            # ========== Subsequent optimization steps (only executed after clippy warning fixes complete) ==========
            # Compute the target file list for this batch (by include/exclude/resume/max_files)
            targets = compute_target_files(
                self.crate_dir, self.options, self.progress_manager.processed
            )
            self._target_files = targets

            # Check whether there are incomplete steps to execute
            has_pending_steps = False
            if (
                self.options.enable_unsafe_cleanup
                and "unsafe_cleanup" not in self.progress_manager.steps_completed
            ):
                has_pending_steps = True
            if (
                self.options.enable_visibility_opt
                and "visibility_opt" not in self.progress_manager.steps_completed
            ):
                has_pending_steps = True
            if (
                self.options.enable_doc_opt
                and "doc_opt" not in self.progress_manager.steps_completed
            ):
                has_pending_steps = True

            # If there are no new files but there are incomplete steps, use all Rust files as targets
            if not targets and has_pending_steps:
                PrettyOutput.auto_print(
                    "📝 [c2rust-optimizer] No new files to process, but incomplete steps were detected; using all Rust files as targets."
                )
                targets = list(iter_rust_files(self.crate_dir))

            if not targets:
                PrettyOutput.auto_print(
                    "✅ [c2rust-optimizer] Based on the current options, there are no new files to process, and all steps are complete."
                )
            else:
                PrettyOutput.auto_print(
                    f"📊 [c2rust-optimizer] This batch found {len(targets)} files to process."
                )

                # All optimization steps use CodeAgent
                step_num = 1

                if self.options.enable_unsafe_cleanup:
                    result_step_num = self._run_optimization_step(
                        "unsafe_cleanup",
                        "unsafe cleanup",
                        step_num,
                        targets,
                        self.unsafe_optimizer.code_agent_opt_unsafe_cleanup,
                    )
                    if result_step_num is None:  # Step failed and a rollback occurred
                        return self.stats
                    step_num = result_step_num

                if self.options.enable_visibility_opt:
                    result_step_num = self._run_optimization_step(
                        "visibility_opt",
                        "visibility optimization",
                        step_num,
                        targets,
                        self.visibility_optimizer.code_agent_opt_visibility,
                    )
                    if result_step_num is None:  # Step failed and a rollback occurred
                        return self.stats
                    step_num = result_step_num

                if self.options.enable_doc_opt:
                    result_step_num = self._run_optimization_step(
                        "doc_opt",
                        "documentation enhancement",
                        step_num,
                        targets,
                        self.docs_optimizer.code_agent_opt_docs,
                    )
                    if result_step_num is None:  # Step failed and a rollback occurred
                        return self.stats
                    step_num = result_step_num

                # Final progress save (ensure the progress of all steps is recorded)
                self.progress_manager.save_progress_for_batch(targets)

        except Exception as e:
            if self.stats.errors is not None:
                self.stats.errors.append(f"fatal: {e}")
        finally:
            # Write a brief report
            report_display = get_report_display_path(
                report_path, self.project_root, self.crate_dir
            )
            PrettyOutput.auto_print(
                f"✅ [c2rust-optimizer] Optimization flow finished. Report generated at: {report_display}"
            )
            write_final_report(report_path, self.stats)
        return self.stats

    # Clippy, Unsafe, Visibility, Docs, and BuildFix-related methods have been moved to their own modules
    # Backward-compatibility methods have been removed; use the corresponding methods in each module directly


def optimize_project(
    project_root: Optional[Path] = None,
    crate_dir: Optional[Path] = None,
    enable_unsafe_cleanup: bool = True,
    enable_visibility_opt: bool = True,
    enable_doc_opt: bool = True,
    max_checks: int = 0,
    dry_run: bool = False,
    include_patterns: Optional[str] = None,
    exclude_patterns: Optional[str] = None,
    max_files: int = 0,
    resume: bool = True,
    reset_progress: bool = False,
    build_fix_retries: int = 3,
    git_guard: bool = True,
    cargo_test_timeout: int = 300,
    non_interactive: bool = True,
    quick_mode: bool = False,
) -> Dict:
    """
    Run optimization on the specified crate. Returns a result summary dict.
    - project_root: original C project root (containing .haijunbot/c2rust); auto-detected when None
    - crate_dir: crate root (containing Cargo.toml); auto-detected when None
    - enable_*: switches for each optimization step
    - max_checks: limit the number of cargo check invocations (0 = unlimited)
    - dry_run: do not write back; only tally potential modifications
    - include_patterns/exclude_patterns: comma-separated globs; relative to the crate root (such as src/**/*.rs)
    - max_files: maximum number of files to process this run (0 = unlimited)
    - resume: enable resuming (skip already processed files)
    - reset_progress: clear progress (the processed list)
    """
    # If project_root is None, try to find it from the current directory
    if project_root is None:
        project_root = find_project_root()
        if project_root is None:
            # If the project root cannot be found, use the current directory
            project_root = Path(".").resolve()
    else:
        project_root = Path(project_root).resolve()

    # If crate_dir is None, use detect_crate_dir to auto-detect
    # detect_crate_dir already contains the logic to infer from the project root
    crate = detect_crate_dir(crate_dir)
    opts = OptimizeOptions(
        enable_unsafe_cleanup=enable_unsafe_cleanup,
        enable_visibility_opt=enable_visibility_opt,
        enable_doc_opt=enable_doc_opt,
        max_checks=max_checks,
        dry_run=dry_run,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_files=max_files,
        resume=resume,
        reset_progress=reset_progress,
        build_fix_retries=build_fix_retries,
        git_guard=git_guard,
        cargo_test_timeout=cargo_test_timeout,
        non_interactive=non_interactive,
        quick_mode=quick_mode,
    )
    optimizer = Optimizer(crate, opts, project_root=project_root)
    stats = optimizer.run()
    return asdict(stats)
