# -*- coding: utf-8 -*-
"""
Symbol mapping module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.transpiler_modules import ModuleManager


class SymbolMapper:
    """Symbol mapping manager"""

    def __init__(
        self,
        symbol_map: Any,  # _SymbolMapJsonl
        progress: Dict[str, Any],
        config_manager: Any,  # ConfigManager
        git_manager: Any,  # GitManager
    ) -> None:
        self.symbol_map = symbol_map
        self.progress = progress
        self.config_manager = config_manager
        self.git_manager = git_manager

    def should_skip(self, rec: FnRecord) -> bool:
        """Determine whether the function should be skipped"""
        # Skip already-translated ones (judged by source location and name uniqueness, to avoid misjudging same-name symbols at different locations)
        if self.symbol_map.has_rec(rec):
            return True
        return False

    def mark_converted(self, rec: FnRecord, module: str, rust_sig: str) -> None:
        """Record a mapping: C symbol -> Rust symbol and module path (JSONL, one per line, supports overloads/same names)"""
        rust_symbol = ""
        # Extract the function name from the signature (supports lifetime parameters and generic parameters)
        # Supports lifetime parameters and generic parameters: fn name<'a, T>(...)
        m = re.search(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*\(", rust_sig)
        if m:
            rust_symbol = m.group(1)
        # Write the JSONL mapping (with source location, to distinguish same-name symbols)
        self.symbol_map.add(rec, module, rust_symbol or (rec.name or f"fn_{rec.id}"))

        # Get the current commit id and record it
        current_commit = self.git_manager.get_crate_commit_hash()

        # Update progress: the converted set
        converted = self.progress.get("converted") or []
        if rec.id not in converted:
            converted.append(rec.id)
        self.progress["converted"] = converted
        self.progress["current"] = None

        # Record the commit id of each converted function
        converted_commits = self.progress.get("converted_commits") or {}
        if current_commit:
            converted_commits[str(rec.id)] = current_commit
            self.progress["converted_commits"] = converted_commits
            PrettyOutput.auto_print(
                f"🔍 [c2rust-transpiler][progress] Recorded commit for function {rec.id}: {current_commit}"
            )

        self.config_manager.save_progress()

    def resolve_pending_todos_for_symbol(
        self,
        symbol: str,
        callee_module: str,
        callee_rust_fn: str,
        callee_rust_sig: str,
        crate_dir: Path,
        get_code_agent_func: Callable[[], Any],
        compose_prompt_func: Callable[[str], str],
        check_and_handle_test_deletion_func: Callable[[str, Any], bool],
    ) -> None:
        """
        After the function corresponding to a C symbol has been converted to Rust:
        - Scan all .rs files in the entire crate (preferring the src/ directory) for placeholders: todo!("symbol name") or unimplemented!("symbol name")
        - For each matched file, create a CodeAgent to replace the placeholder with a real call to the converted function (can use a fully-qualified crate::... path or a use import)
        - Minimize changes and avoid unrelated refactoring

        Note: todos.json is no longer used; this method directly searches the source code for todo!("xxxx") / unimplemented!("xxxx").
        """
        if not symbol:
            return

        # Compute the crate path prefix of the callee function to provide call path suggestions in the prompt
        module_manager = ModuleManager(crate_dir)
        callee_path = module_manager.module_file_to_crate_path(callee_module)

        # Scan .rs files under src for todo!("symbol") or unimplemented!("symbol") placeholders
        matches: List[str] = []
        src_root = (crate_dir / "src").resolve()
        if src_root.exists():
            for p in sorted(src_root.rglob("*.rs")):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_symbols",
                        function="resolve_pending_todos_for_symbol",
                    )
                    continue
                pat_todo = re.compile(
                    r'todo\s*!\s*\(\s*["\']' + re.escape(symbol) + r'["\']\s*\)'
                )
                pat_unimpl = re.compile(
                    r'unimplemented\s*!\s*\(\s*["\']'
                    + re.escape(symbol)
                    + r'["\']\s*\)'
                )
                if pat_todo.search(text) or pat_unimpl.search(text):
                    try:
                        # Record the absolute path to avoid depending on the current working directory
                        abs_path = str(p.resolve())
                    except Exception:
                        abs_path = str(p)
                    matches.append(abs_path)

        if not matches:
            PrettyOutput.auto_print(
                f'🔍 [c2rust-transpiler][todo] No occurrences of todo!("{symbol}") or unimplemented!("{symbol}") found in src/'
            )
            return

        # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
        PrettyOutput.auto_print(
            f'🔍 [c2rust-transpiler][todo] Found {len(matches)} files containing todo!("{symbol}") or unimplemented!("{symbol}")'
        )
        for target_file in matches:
            prompt = "\n".join(
                [
                    f"In the file {target_file}, locate all of the following placeholders and replace them with real calls to the converted function:",
                    f'- todo!("{symbol}")',
                    f'- unimplemented!("{symbol}")',
                    "Requirements:",
                    f"- Name of the converted target function: {callee_rust_fn}",
                    f"- Its module (crate path hint): {callee_path}",
                    f"- Function signature hint: {callee_rust_sig}",
                    f"- Current crate root directory path: {crate_dir.resolve()}",
                    "- Prefer fully-qualified paths (e.g. crate::...::function(...)); if a use import is needed at the top of the file, only exact imports are allowed, wildcards are not (e.g. use ...::*);",
                    "- Keep changes minimal; do not perform refactoring or formatting unrelated to this fix;",
                    "- If the argument list is not yet clear, you may use reasonable placeholder variables to ensure it compiles.",
                    "",
                    f"Only modify code related to the above placeholders in {target_file}; do not change other locations.",
                    "Output only the patch; do not output explanations or extraneous text.",
                ]
            )
            # Record the commit before running
            before_commit = self.git_manager.get_crate_commit_hash()
            agent = get_code_agent_func()
            agent.run(
                compose_prompt_func(prompt),
                prefix=f"[c2rust-transpiler][todo-fix:{symbol}]",
                suffix="",
            )

            # Detect and handle test code deletion
            if check_and_handle_test_deletion_func(before_commit, agent):
                # If it rolled back, the agent needs to be re-run
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][todo-fix] Test code deletion issue detected; rolled back, re-running agent (symbol={symbol})"
                )
                before_commit = self.git_manager.get_crate_commit_hash()
                agent.run(
                    compose_prompt_func(prompt),
                    prefix=f"[c2rust-transpiler][todo-fix:{symbol}][retry]",
                    suffix="",
                )
                # Detect again
                if check_and_handle_test_deletion_func(before_commit, agent):
                    PrettyOutput.auto_print(
                        f"❌ [c2rust-transpiler][todo-fix] Test code deletion issue detected again; rolled back (symbol={symbol})"
                    )
