# -*- coding: utf-8 -*-

"""
Transpiler executor module

Responsible for executing the main transpilation flow, including:
- Initialize the crate directory and configuration
- Load and process the order file
- Iterate over functions and execute the transpilation flow
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import os
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple


from haijunbot.haijunbot_c2rust.constants import MAX_FUNCTION_RETRIES
from haijunbot.haijunbot_c2rust.library_replacer_utils import is_entry_function
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.utils import ensure_order_file
from haijunbot.haijunbot_c2rust.utils import iter_order_steps
from haijunbot.haijunbot_utils.output import PrettyOutput


class TranspilerExecutor:
    """Transpiler executor, responsible for executing the main transpilation flow"""

    def __init__(
        self,
        project_root: Path,
        crate_dir: Path,
        progress: Dict[str, Any],
        resume: bool,
        fn_index_by_id: Dict[int, FnRecord],
        # Dependency-injected methods
        load_order_index_func: Callable[[Path], Dict[str, Any]],
        should_skip_func: Callable[[Any], bool],
        read_source_span_func: Callable[[Any], str],
        plan_module_and_signature_func: Callable[[Any, str], Tuple[str, str, bool]],
        update_progress_current_func: Callable[[Any, str, str], None],
        mark_converted_func: Callable[[Any, str, str], None],
        reset_function_context_func: Callable[[Any, str, str, str], None],
        ensure_mod_chain_for_module_func: Callable[[str], None],
        ensure_top_level_pub_mod_func: Callable[[str], None],
        get_crate_commit_hash_func: Callable[[], str],
        reset_to_commit_func: Callable[[str], None],
        run_cargo_fmt_func: Callable[[str], None],
        untranslated_callee_symbols_func: Callable[[Any], List[str]],
        code_agent_generate_impl_func: Callable[[Any, str, str, str, List[str]], str],
        refresh_compact_context_func: Callable[[Any, str, str], None],
        cargo_build_loop_func: Callable[[], bool],
        review_and_optimize_func: Callable[[Any, str, str], bool],
        extract_rust_fn_name_from_sig_func: Callable[[str], str],
        resolve_pending_todos_for_symbol_func: Callable[[str, str, str, str], None],
        save_progress_func: Callable[[], None],
        consecutive_fix_failures_getter: Callable[[], int],
        consecutive_fix_failures_setter: Callable[[int], None],
        current_function_start_commit_getter: Callable[[], str],
        current_function_start_commit_setter: Callable[[str], None],
        get_build_loop_has_fixes_func: Callable[[], bool],
        ensure_cargo_toml_bin_func: Callable[[str], None],
    ) -> None:
        self.project_root = project_root
        self.crate_dir = crate_dir
        self.progress = progress
        self.resume = resume
        self.fn_index_by_id = fn_index_by_id

        # Injected methods
        self.load_order_index = load_order_index_func
        self.should_skip = should_skip_func
        self.read_source_span = read_source_span_func
        self.plan_module_and_signature = plan_module_and_signature_func
        self.update_progress_current = update_progress_current_func
        self.mark_converted = mark_converted_func
        self.reset_function_context = reset_function_context_func
        self.ensure_mod_chain_for_module = ensure_mod_chain_for_module_func
        self.ensure_top_level_pub_mod = ensure_top_level_pub_mod_func
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.reset_to_commit = reset_to_commit_func
        self.run_cargo_fmt = run_cargo_fmt_func
        self.untranslated_callee_symbols = untranslated_callee_symbols_func
        self.code_agent_generate_impl = code_agent_generate_impl_func
        self.refresh_compact_context = refresh_compact_context_func
        self.cargo_build_loop = cargo_build_loop_func
        self.review_and_optimize = review_and_optimize_func
        self.extract_rust_fn_name_from_sig = extract_rust_fn_name_from_sig_func
        self.resolve_pending_todos_for_symbol = resolve_pending_todos_for_symbol_func
        self.save_progress = save_progress_func
        self.consecutive_fix_failures_getter = consecutive_fix_failures_getter
        self.consecutive_fix_failures_setter = consecutive_fix_failures_setter
        self.current_function_start_commit_getter = current_function_start_commit_getter
        self.current_function_start_commit_setter = current_function_start_commit_setter
        self.get_build_loop_has_fixes = get_build_loop_has_fixes_func
        self.ensure_cargo_toml_bin = ensure_cargo_toml_bin_func

    def execute(self) -> None:
        """Execute the main transpilation flow"""
        PrettyOutput.auto_print("🚀 [c2rust-transpiler][start] Starting transpilation")
        # Switch to the crate root directory; the entire transpilation process runs in this directory
        prev_cwd = os.getcwd()
        try:
            os.chdir(str(self.crate_dir))
            PrettyOutput.auto_print(
                f"📁 [c2rust-transpiler][start] Switched to crate directory: {os.getcwd()}"
            )
            # Accuracy fallback: when prepare has not been run, ensure the crate directory and minimal Cargo configuration exist
            self._ensure_crate_structure()

            order_path = ensure_order_file(self.project_root)
            steps = iter_order_steps(order_path)
            if not steps:
                PrettyOutput.auto_print("⚠️ [c2rust-transpiler] No translation steps found.")
                return

            # Build a self-contained order index (id -> FnRecord, name/qname -> id)
            self.load_order_index(order_path)

            # Flatten the order and process function by function (preserving the original order)
            seq: List[int] = []
            for grp in steps:
                seq.extend(grp)

            # If resume is supported, skip those already completed in progress['converted']
            done: Set[int] = set(self.progress.get("converted") or [])
            # Compute the total number of functions to process (excluding completed ones)
            total_to_process = len([fid for fid in seq if fid not in done])
            current_index = 0

            # On resume, reset to the commit id of the last converted function
            self._handle_resume(seq, done)

            PrettyOutput.auto_print(
                f"📊 [c2rust-transpiler][order] Order info: steps={len(steps)} total IDs={sum(len(g) for g in steps)} converted={len(done)} to process={total_to_process}"
            )

            for fid in seq:
                if fid in done:
                    continue
                rec = self.fn_index_by_id.get(fid)
                if not rec:
                    continue
                if self.should_skip(rec):
                    PrettyOutput.auto_print(
                        f"⏭️ [c2rust-transpiler][skip] Skipping {rec.qname or rec.name} (id={rec.id}) at {rec.file}:{rec.start_line}-{rec.end_line}"
                    )
                    continue

                # Update the progress index
                current_index += 1
                progress_info = (
                    f"({current_index}/{total_to_process})"
                    if total_to_process > 0
                    else ""
                )

                # Process a single function
                if not self._process_function(rec, progress_info):
                    # Processing failed; keep the current state to allow resuming next time
                    return

            PrettyOutput.auto_print(
                "📋 [c2rust-transpiler] All eligible functions have been processed."
            )
        finally:
            os.chdir(prev_cwd)
            PrettyOutput.auto_print(
                f"🏁 [c2rust-transpiler][end] Restored working directory: {os.getcwd()}"
            )

    def _ensure_crate_structure(self) -> None:
        """Ensure the crate directory and minimal Cargo configuration exist"""
        try:
            cd = self.crate_dir.resolve()
            cd.mkdir(parents=True, exist_ok=True)
            cargo = cd / "Cargo.toml"
            src_dir = cd / "src"
            lib_rs = src_dir / "lib.rs"
            gitignore = cd / ".gitignore"
            # Minimal Cargo.toml (does not overwrite an existing one); edition uses 2021 for broader compatibility
            if not cargo.exists():
                pkg_name = cd.name
                content = (
                    f'[package]\nname = "{pkg_name}"\nversion = "0.1.0"\nedition = "2021"\n\n'
                    '[lib]\npath = "src/lib.rs"\n'
                )
                try:
                    cargo.write_text(content, encoding="utf-8")
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][init] created Cargo.toml at {cargo}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_executor",
                        function="_ensure_crate_structure",
                    )
                    pass
            # Ensure src/lib.rs exists
            src_dir.mkdir(parents=True, exist_ok=True)
            if not lib_rs.exists():
                try:
                    lib_rs.write_text(
                        "// Auto-created by c2rust transpiler\n", encoding="utf-8"
                    )
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][init] created src/lib.rs at {lib_rs}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_executor",
                        function="_ensure_crate_structure",
                    )
                    pass
            # Ensure .gitignore exists (does not overwrite an existing one)
            if not gitignore.exists():
                try:
                    gitignore_content = "# Generated by c2rust transpiler\n/target/\n*.o\n*.so\n*.dylib\n*.dll\n*.a\n*.lib\n*.exe\n*.out\n*.dSYM/\n.DS_Store\n.haijunbot/\n"
                    gitignore.write_text(gitignore_content, encoding="utf-8")
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][init] created .gitignore at {gitignore}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_executor",
                        function="_ensure_crate_structure",
                    )
                    pass
        except Exception:
            # Stay robust; a failure does not block the main flow
            pass

    def _handle_resume(self, seq: List[int], done: Set[int]) -> None:
        """Handle resume logic: reset to the commit id of the last converted function"""
        if not (self.resume and done):
            return

        converted_commits = self.progress.get("converted_commits") or {}
        if not converted_commits:
            return

        # Find the commit id of the last converted function
        last_commit = None
        for fid in reversed(seq):
            if fid in done:
                commit_id = converted_commits.get(str(fid))
                if commit_id:
                    last_commit = commit_id
                    break

        if not last_commit:
            return

        current_commit = self.get_crate_commit_hash()
        if current_commit != last_commit:
            PrettyOutput.auto_print(
                f"🔄 [c2rust-transpiler][resume] Detected inconsistent code state; resetting to the commit of the last converted function: {last_commit}"
            )
            if self.reset_to_commit(last_commit):
                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][resume] Reset to commit: {last_commit}"
                )
            else:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][resume] Reset failed; continuing with the current code state"
                )
        else:
            PrettyOutput.auto_print(
                "✅ [c2rust-transpiler][resume] Code state is consistent; no reset needed"
            )

    def _process_function(self, rec: FnRecord, progress_info: str) -> bool:
        """Handle the transpilation flow of a single function

        Returns:
            bool: True means success, False means processing should stop (failure or retry limit reached)
        """
        # Run cargo fmt before starting transpilation of each function
        workspace_root = str(self.crate_dir)
        self.run_cargo_fmt(workspace_root)

        # Read the C function source code
        PrettyOutput.auto_print(
            f"📖 [c2rust-transpiler][read] {progress_info} Reading C source: {rec.qname or rec.name} (id={rec.id}) from {rec.file}:{rec.start_line}-{rec.end_line}"
        )
        c_code = self.read_source_span(rec)
        PrettyOutput.auto_print(
            f"📊 [c2rust-transpiler][read] Loaded {len(c_code.splitlines()) if c_code else 0} lines"
        )

        # If the source snippet is missing and signature/parameter information is also lacking, skip this function and record progress for later processing
        if not c_code and not (
            getattr(rec, "signature", "") or getattr(rec, "params", None)
        ):
            skipped = self.progress.get("skipped_missing_source") or []
            if rec.id not in skipped:
                skipped.append(rec.id)
            self.progress["skipped_missing_source"] = skipped
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler] {progress_info} Skipping: missing source and signature information -> {rec.qname or rec.name} (id={rec.id})"
            )
            self.save_progress()
            return True  # Skipping does not count as failure

        # 1) Planning: module path and Rust signature
        PrettyOutput.auto_print(
            f"📝 [c2rust-transpiler][plan] {progress_info} Planning module and signature: {rec.qname or rec.name} (id={rec.id})"
        )
        module, rust_sig, skip_implementation = self.plan_module_and_signature(
            rec, c_code
        )
        PrettyOutput.auto_print(
            f"✅ [c2rust-transpiler][plan] Selected module={module}, signature={rust_sig}"
        )

        # Record the current progress
        self.update_progress_current(rec, module, rust_sig)
        PrettyOutput.auto_print(
            f"📝 [c2rust-transpiler][progress] Updated the current progress record id={rec.id}"
        )

        # Detect the main function and update Cargo.toml
        if is_entry_function(rec.__dict__):
            # Check whether the module path is under src/bin/
            module_path_clean = module.replace("\\", "/")
            if module_path_clean.startswith("src/bin/") or "/bin/" in module_path_clean:
                # Extract the path relative to the crate root directory
                if not module_path_clean.startswith("src/"):
                    # If it is an absolute path, convert it to a relative path
                    try:
                        mp = Path(module)
                        if mp.is_absolute():
                            rel = mp.relative_to(self.crate_dir.resolve())
                            module_path_clean = str(rel).replace("\\", "/")
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_c2rust.transpiler_executor",
                            function="_process_function",
                        )
                        pass
                # Ensure the path starts with src/
                if module_path_clean.startswith("src/"):
                    PrettyOutput.auto_print(
                        f"⚙️ [c2rust-transpiler][main] Detected the main function; updating Cargo.toml to add the [[bin]] configuration: {module_path_clean}"
                    )
                    self.ensure_cargo_toml_bin(module_path_clean)

        # If marked to skip implementation, mark it as converted directly
        if skip_implementation:
            PrettyOutput.auto_print(
                f"⏭️ [c2rust-transpiler][skip-impl] Function {rec.qname or rec.name} was evaluated as not requiring an implementation; skipping the implementation stage"
            )
            # Mark it as converted directly, skipping the code generation, build, and review stages
            self.mark_converted(rec, module, rust_sig)
            PrettyOutput.auto_print(
                f"✅ [c2rust-transpiler][mark] Marked and mapped: {rec.qname or rec.name} -> {module} (implementation skipped, treated as implemented)"
            )
            return True

        # Initialize the function context and the code-writing/fixing Agent reuse cache (executed only once at the start of each function)
        self.reset_function_context(rec, module, rust_sig, c_code)

        # 1.5) Ensure the module declaration chain (moved ahead of implementation generation to avoid generated code being unable to be referenced correctly)
        self._ensure_module_structure(module)

        # Before processing the function, record the current commit id (used for rollback on failure)
        self.current_function_start_commit_setter(self.get_crate_commit_hash())
        if self.current_function_start_commit_getter():
            PrettyOutput.auto_print(
                f"🔖 [c2rust-transpiler][commit] Recorded the commit at function start: {self.current_function_start_commit_getter()}"
            )
        else:
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][commit] Warning: unable to get the commit id; rollback on failure will not be possible"
            )

        # Reset the consecutive failure count (reset at the start of each new function)
        self.consecutive_fix_failures_setter(0)

        # Use a loop to process the function, supporting a restart after rollback on failure
        function_retry_count = 0
        max_function_retries = MAX_FUNCTION_RETRIES
        build_has_fixes = False  # Defined outside the loop to ensure it is still available after break
        while function_retry_count <= max_function_retries:
            if function_retry_count > 0:
                PrettyOutput.auto_print(
                    f"🔁 [c2rust-transpiler][retry] Restarting function processing (retry #{function_retry_count})"
                )
                # Re-record the commit id (the new commit after rollback)
                self.current_function_start_commit_setter(self.get_crate_commit_hash())
                if self.current_function_start_commit_getter():
                    PrettyOutput.auto_print(
                        f"📝 [c2rust-transpiler][commit] Re-recorded the commit at function start: {self.current_function_start_commit_getter()}"
                    )
                # Reset the consecutive failure count (reset on restart)
                self.consecutive_fix_failures_setter(0)

            # 2) Generate the implementation
            unresolved = self.untranslated_callee_symbols(rec)
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][deps] {progress_info} Unresolved callee symbols: {', '.join(unresolved) if unresolved else '(none)'}"
            )
            PrettyOutput.auto_print(
                f"📋 [c2rust-transpiler][gen] {progress_info} Generating Rust implementation for {rec.qname or rec.name}"
            )
            self.code_agent_generate_impl(rec, c_code, module, rust_sig, unresolved)
            PrettyOutput.auto_print(
                f"📋 [c2rust-transpiler][gen] Generated or updated the implementation in {module}"
            )
            # Refresh the compact context (to prevent the prompt from being out of sync after signature/module adjustments)
            try:
                self.refresh_compact_context(rec, module, rust_sig)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_executor",
                    function="_process_function",
                )
                pass

            # 3) Build and fix
            PrettyOutput.auto_print("📋 [c2rust-transpiler][build] Starting the cargo test loop")
            ok = self.cargo_build_loop()

            # Check whether fixes were made in the build loop (accumulate the fix flag; do not reset it)
            current_build_has_fixes = (
                self.get_build_loop_has_fixes()
                if hasattr(self, "get_build_loop_has_fixes")
                else False
            )
            # Accumulate the fix flag: mark as fixed if there was a fix this time or previously
            build_has_fixes = build_has_fixes or current_build_has_fixes

            # Check whether a restart is needed (after rollback)
            if ok is None:
                # A restart is needed
                function_retry_count += 1
                if function_retry_count > max_function_retries:
                    PrettyOutput.auto_print(
                        f"🔄 [c2rust-transpiler] The function restart count has reached the limit ({max_function_retries}); stopping processing of this function"
                    )
                    # Keep the current state to allow resuming next time
                    return False
                # Reset the consecutive failure count
                self.consecutive_fix_failures_setter(0)
                # Continue the loop and restart processing
                continue

            PrettyOutput.auto_print(
                f"📊 [c2rust-transpiler][build] Build result: {'passed' if ok else 'failed'}"
            )
            if not ok:
                PrettyOutput.auto_print(
                    "🔁 [c2rust-transpiler] The build did not succeed within the retry limit; stopped."
                )
                # Keep the current state to allow resuming next time
                return False

            # Build succeeded; break out of the loop and continue with the subsequent flow
            # If fixes were made during the build, a review must be performed again
            if build_has_fixes:
                PrettyOutput.auto_print(
                    "👀 [c2rust-transpiler][build] Fixes were made during the build; a code review must be performed again"
                )
            break

        # 4) Review and optimization (reuse the Review Agent)
        # If fixes were made during the build, a review must be performed again to ensure the fixes did not introduce new problems
        if build_has_fixes:
            PrettyOutput.auto_print(
                f"🔄 [c2rust-transpiler][review] {progress_info} Restarting code review after build fixes: {rec.qname or rec.name}"
            )
        else:
            PrettyOutput.auto_print(
                f"👀 [c2rust-transpiler][review] {progress_info} Starting code review: {rec.qname or rec.name}"
            )
        self.review_and_optimize(rec, module, rust_sig)
        PrettyOutput.auto_print("🔍 [c2rust-transpiler][review] Code review complete")

        # 5) Mark as converted and record the mapping (JSONL)
        self.mark_converted(rec, module, rust_sig)
        PrettyOutput.auto_print(
            f"📋 [c2rust-transpiler][mark] {progress_info} Marked and mapped: {rec.qname or rec.name} -> {module}"
        )

        # 6) If other functions earlier placed todo!("<symbol>") in the source because they depended on the current symbol, immediately go back and resolve them (reuse the code-writing/fixing Agent)
        current_rust_fn = self.extract_rust_fn_name_from_sig(rust_sig)
        # Collect the symbols that need processing (deduplicate to avoid double processing when qname and name are the same)
        symbols_to_resolve = []
        if rec.qname:
            symbols_to_resolve.append(rec.qname)
        if rec.name and rec.name != rec.qname:  # Only add if name differs from qname
            symbols_to_resolve.append(rec.name)
        # Process each symbol (after deduplication)
        for sym in symbols_to_resolve:
            PrettyOutput.auto_print(
                f"📋 [c2rust-transpiler][todo] Cleaning up occurrences of todo!('{sym}')"
            )
            self.resolve_pending_todos_for_symbol(
                sym, module, current_rust_fn, rust_sig
            )
        # If any symbol was processed, run cargo test once in a unified way (to avoid repeated runs)
        if symbols_to_resolve:
            PrettyOutput.auto_print(
                "📋 [c2rust-transpiler][build] Re-running cargo test after processing todos"
            )
            self.cargo_build_loop()

        return True

    def _ensure_module_structure(self, module: str) -> None:
        """Ensure the module declaration chain and top-level module exports"""
        try:
            self.ensure_mod_chain_for_module(module)
            PrettyOutput.auto_print(
                f"📋 [c2rust-transpiler][mod] Completed the mod.rs declaration chain for {module}"
            )
            # Ensure the top-level module is exposed in src/lib.rs
            mp = Path(module)
            crate_root = self.crate_dir.resolve()
            rel = (
                mp.resolve().relative_to(crate_root)
                if mp.is_absolute()
                else Path(module)
            )
            rel_s = str(rel).replace("\\", "/")
            if rel_s.startswith("./"):
                rel_s = rel_s[2:]
            if rel_s.startswith("src/"):
                parts = rel_s[len("src/") :].strip("/").split("/")
                if parts and parts[0]:
                    top_mod = parts[0]
                    # Filter out the "mod" and "bin" keywords and .rs files
                    if top_mod not in ("mod", "bin") and not top_mod.endswith(".rs"):
                        self.ensure_top_level_pub_mod(top_mod)
                        PrettyOutput.auto_print(
                            f"📋 [c2rust-transpiler][mod] Ensured top-level pub mod {top_mod} in src/lib.rs"
                        )
            cur = self.progress.get("current") or {}
            cur["mod_chain_fixed"] = True
            cur["mod_visibility_fixed"] = True
            self.progress["current"] = cur
            self.save_progress()
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_executor",
                function="_ensure_module_structure",
            )
            pass
