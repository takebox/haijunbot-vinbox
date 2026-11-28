from __future__ import annotations

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import List
from typing import Protocol

from haijunbot.haijunbot_c2rust.models import FnRecord


class _CodeAgentProtocol(Protocol):
    """Protocol interface for the code agent"""

    def run(self, prompt: str, prefix: str = ..., suffix: str = ...) -> None:
        """Run the code agent"""
        ...


class _TranspilerProtocol(Protocol):
    """Protocol interface for the Transpiler class, used to avoid circular imports"""

    @property
    def data_dir(self) -> Path:
        """Data directory"""
        ...

    @property
    def crate_dir(self) -> Path:
        """crate directory"""
        ...

    @property
    def project_root(self) -> Path:
        """Project root directory"""
        ...

    @property
    def disabled_libraries(self) -> list[str]:
        """Disabled libraries list"""
        ...

    def _is_root_symbol(self, rec: FnRecord) -> bool:
        """Check whether it is a root symbol"""
        ...

    def _append_additional_notes(self, prompt: str) -> str:
        """Append extra notes"""
        ...

    def _extract_compile_flags(self, file_path: str) -> str:
        """Extract compile flags"""
        ...

    def _get_crate_commit_hash(self) -> str:
        """Get the crate's commit hash"""
        ...

    def _get_code_agent(self) -> _CodeAgentProtocol:
        """Get the code agent"""
        ...

    def _compose_prompt_with_context(self, prompt: str) -> str:
        """Compose the prompt with context"""
        ...

    def _check_and_handle_test_deletion(
        self, before_commit: str, agent: _CodeAgentProtocol
    ) -> bool:
        """Check and handle test code deletion"""
        ...

    def _ensure_top_level_pub_mod(self, top_mod: str) -> None:
        """Ensure the top-level module is pub"""
        ...


def build_generate_impl_prompt(
    self: _TranspilerProtocol,
    rec: FnRecord,
    c_code: str,
    module: str,
    rust_sig: str,
    unresolved: List[str],
) -> str:
    """
    Implementation extracted from Transpiler._build_generate_impl_prompt, keeping the signature and logic exactly consistent.
    """
    symbols_path = str((self.data_dir / "symbols.jsonl").resolve())
    is_root = self._is_root_symbol(rec)
    requirement_lines = [
        f"Goal: In {module}, use the TDD method to generate a Rust implementation for the C function {rec.qname or rec.name}.",
        f"Function signature: {rust_sig}",
        f"crate directory: {self.crate_dir.resolve()}",
        f"C project directory: {self.project_root.resolve()}",
        *(
            ["Root symbol requirement: the `pub` keyword must be used, and the module must be exported in src/lib.rs"]
            if is_root
            else []
        ),
        "",
        "[TDD Process]",
        "1. Red: write tests first (#[cfg(test)] mod tests), designing test cases based on the C function's behavior",
        "2. Green: write the implementation to make the tests pass, ensuring semantic equivalence with the C code",
        "3. Refactor: optimize the code while keeping the tests passing",
        "",
        "[Core Requirements]",
        "- Write tests before the implementation; the tests must compile and pass",
        "- todo!/unimplemented! are forbidden; you must implement the full functionality",
        "- Use native Rust types (i32/u32, &str/String, &[T]/&mut [T], Result<T,E>); avoid C-style types",
        '- extern "C" is forbidden; use standard Rust calling conventions',
        "- Keep changes minimal and avoid unrelated refactoring",
        "- Comments should be in Chinese; wildcard imports (use ...::*) are forbidden",
        "- Resource-releasing functions (fclose/free, etc.) can be managed automatically via RAII; provide an empty implementation and explain it in the documentation",
        *(
            [f"- Disabled libraries: {', '.join(self.disabled_libraries)}"]
            if self.disabled_libraries
            else []
        ),
        "",
        "[Dependency Handling]",
        "- Check whether the dependency functions are already implemented; fill in any that are missing as well (follow TDD: test first, then implement)",
        "- Use read_symbols/read_code to retrieve the C source",
        "- Handle lower-level dependencies first to ensure all tests pass",
        "- If there are many dependencies or the relationships are complex, you may create a task list to plan the translation order (e.g. translate global variables first -> then type definitions -> finally functions)",
        "",
        "[Tools]",
        f'- read_symbols: {{"symbols_file": "{symbols_path}", "symbols": [...]}}',
        "- read_code: read C source or a Rust module",
        "",
        *([f"Unconverted symbols: {', '.join(unresolved)}"] if unresolved else []),
        "",
        "C source:",
        "<C_SOURCE>",
        c_code,
        "</C_SOURCE>",
        "",
        "Signature reference:",
        json.dumps(
            {
                "signature": getattr(rec, "signature", ""),
                "params": getattr(rec, "params", None),
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "Output only the patch; do not explain.",
    ]
    # If library replacement context exists, append it to the implementation prompt for the generator's reference (multi-library combinations, reference APIs, notes, etc.)
    librep_ctx = None
    try:
        librep_ctx = getattr(rec, "lib_replacement", None)
    except Exception:
        librep_ctx = None
    if isinstance(librep_ctx, dict) and librep_ctx:
        requirement_lines.extend(
            [
                "",
                "Library replacement context (if present):",
                json.dumps(librep_ctx, ensure_ascii=False, indent=2),
                "",
            ]
        )
    # Add compile flags (if present)
    compile_flags = self._extract_compile_flags(rec.file)
    if compile_flags:
        requirement_lines.extend(
            [
                "",
                "C file compile flags (from compile_commands.json):",
                compile_flags,
                "",
            ]
        )
    prompt = "\n".join(requirement_lines)
    return self._append_additional_notes(prompt)


def code_agent_generate_impl(
    self: _TranspilerProtocol,
    rec: FnRecord,
    c_code: str,
    module: str,
    rust_sig: str,
    unresolved: List[str],
) -> None:
    """
    Implementation extracted from Transpiler._code_agent_generate_impl, keeping the logic consistent.
    """
    # Build the prompt
    prompt = build_generate_impl_prompt(self, rec, c_code, module, rust_sig, unresolved)

    # Ensure the target module file exists (to make patch application and implementation persistence more deterministic)
    try:
        mp = Path(module)
        if not mp.is_absolute():
            mp = (self.crate_dir / module).resolve()
        mp.parent.mkdir(parents=True, exist_ok=True)
        if not mp.exists():
            try:
                mp.write_text(
                    "// Auto-created by c2rust transpiler\n", encoding="utf-8"
                )
                from haijunbot.haijunbot_utils.output import PrettyOutput

                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][gen] auto-created module file: {mp}",
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_codegen",
                    function="code_agent_generate_impl",
                )
                pass
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_c2rust.transpiler_codegen",
            function="code_agent_generate_impl",
        )
        pass

    # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
    # Record the commit before running
    before_commit = self._get_crate_commit_hash()
    agent = self._get_code_agent()
    agent.run(
        self._compose_prompt_with_context(prompt),
        prefix="[c2rust-transpiler][gen]",
        suffix="",
    )

    # Detect and handle test code deletion
    if self._check_and_handle_test_deletion(before_commit, agent):
        # If it rolled back, the agent needs to be re-run
        from haijunbot.haijunbot_utils.output import PrettyOutput

        PrettyOutput.auto_print(
            "⚠️ [c2rust-transpiler][gen] Test code deletion issue detected; rolled back, re-running agent",
        )
        before_commit = self._get_crate_commit_hash()
        agent.run(
            self._compose_prompt_with_context(prompt),
            prefix="[c2rust-transpiler][gen][retry]",
            suffix="",
        )
        # Detect again
        if self._check_and_handle_test_deletion(before_commit, agent):
            PrettyOutput.auto_print(
                "❌ [c2rust-transpiler][gen] Test code deletion issue detected again; rolled back",
            )

    # If it is a root symbol, ensure its module is exposed in lib.rs
    if self._is_root_symbol(rec):
        try:
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
                    # Filter out the "mod" keyword and .rs files
                    if top_mod != "mod" and not top_mod.endswith(".rs"):
                        self._ensure_top_level_pub_mod(top_mod)
                        from haijunbot.haijunbot_utils.output import PrettyOutput

                        PrettyOutput.auto_print(
                            f"📋 [c2rust-transpiler][gen] Module {top_mod} of root symbol {rec.qname or rec.name} is exposed in lib.rs",
                        )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_codegen",
                function="code_agent_generate_impl",
            )
            pass
