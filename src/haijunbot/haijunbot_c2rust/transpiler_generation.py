# -*- coding: utf-8 -*-
"""
Code generation module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import re
from pathlib import Path
from typing import Any, Callable, List

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.models import FnRecord


class GenerationManager:
    """Code generation manager"""

    def __init__(
        self,
        project_root: Path,
        crate_dir: Path,
        data_dir: Path,
        disabled_libraries: List[str],
        extract_compile_flags_func: Callable[[str], List[str]],
        append_additional_notes_func: Callable[[str, str], str],
        is_root_symbol_func: Callable[[str], bool],
        get_generation_agent_func: Callable[[], Any],
        compose_prompt_with_context_func: Callable[[str, Any], str],
        check_and_handle_test_deletion_func: Callable[[str, str], bool],
        get_crate_commit_hash_func: Callable[[], str],
        ensure_top_level_pub_mod_func: Callable[[str], None],
        enable_ffi_export_validation: bool = False,
    ) -> None:
        self.project_root = project_root
        self.crate_dir = crate_dir
        self.data_dir = data_dir
        self.disabled_libraries = disabled_libraries
        self.extract_compile_flags = extract_compile_flags_func
        self.append_additional_notes = append_additional_notes_func
        self.is_root_symbol = is_root_symbol_func
        self.get_generation_agent = get_generation_agent_func
        self.compose_prompt_with_context = compose_prompt_with_context_func
        self.check_and_handle_test_deletion = check_and_handle_test_deletion_func
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.ensure_top_level_pub_mod = ensure_top_level_pub_mod_func
        self.enable_ffi_export_validation = enable_ffi_export_validation

    def build_generate_impl_prompt(
        self,
        rec: FnRecord,
        c_code: str,
        module: str,
        rust_sig: str,
        unresolved: List[str],
    ) -> str:
        """
        Build the code generation prompt.

        Return the complete prompt string.
        """
        symbols_path = str((self.data_dir / "symbols.jsonl").resolve())
        is_root = self.is_root_symbol(rec.qname or rec.name)
        is_main = rec.name == "main" or rec.qname == "main"
        is_root_not_main = is_root and not is_main
        # Get the C source file location information
        c_file_location = ""
        if hasattr(rec, "file") and rec.file:
            if (
                hasattr(rec, "start_line")
                and hasattr(rec, "end_line")
                and rec.start_line
                and rec.end_line
            ):
                c_file_location = f"{rec.file}:{rec.start_line}-{rec.end_line}"
            else:
                c_file_location = str(rec.file)

        requirement_lines = [
            f"Goal: in {module}, use the TDD method to generate a Rust implementation for C function {rec.qname or rec.name}.",
            f"Function signature: {rust_sig}",
            f"crate directory: {self.crate_dir.resolve()}",
            f"C project directory: {self.project_root.resolve()}",
            *([f"C source file location: {c_file_location}"] if c_file_location else []),
            *(
                ["Root symbol requirement: the `pub` keyword must be used, and the module must be exported in src/lib.rs"]
                if is_root
                else []
            ),
            *(
                [
                    "FFI export requirement: this function is a root symbol (other than main) and FFI export validation is enabled. The function must be named and exported as an FFI interface:",
                    "  * The function must use the `#[no_mangle]` attribute to ensure the symbol name is not modified by the Rust compiler",
                    '  * The function must be declared with `pub extern "C"`, using the C ABI calling convention',
                    "  * The function signature should use C-compatible types (such as `*const c_char`, `c_int`, `c_void`, etc.) so it can be called from C code",
                    "  * The function name should stay consistent with the original C function name (or follow C naming conventions) so it is correctly exported in the generated cdylib",
                    '  * Note: although `extern "C"` is used, the function implementation should still follow Rust safety practices and may internally use native Rust types and safe APIs',
                ]
                if (is_root_not_main and self.enable_ffi_export_validation)
                else []
            ),
            "",
            "[TDD workflow]",
            "1. Red: write the test first (#[cfg(test)] mod tests), designing test cases based on the C function behavior",
            "2. Green: write the implementation so the test passes, ensuring semantic equivalence with C",
            "3. Refactor: optimize the code while keeping the tests passing",
            "   - If existing test cases are found to be wrong, fix them rather than deleting them",
            "",
            "[Core requirements]",
            "- Write the test before the implementation; the test must compile and pass",
            "- ⚠️ Important: the values of constants and macros must stay consistent with the original C program; they must not be changed or derived arbitrarily.",
            "- ⚠️ Important: if existing test cases are found to be wrong (such as incorrect test logic, incorrect assertions, improper test case design, etc.), fix the test cases rather than deleting them. Delete only when the test cases are completely duplicated, outdated, or genuinely unnecessary.",
            "- ⚠️ Important: do not write production code in the test area. All production function implementations, type definitions, constants, etc. should be written outside the `#[cfg(test)] mod tests { ... }` block. Only test code (test functions, test helper functions, etc.) should be written inside the `#[cfg(test)] mod tests { ... }` block.",
            "- ⚠️ Important: test cases must be as complete as possible, because the later review stage checks test case completeness to avoid rework. Test cases should include:",
            "  * Tests for the main functional path: cover the function's core functionality and expected behavior",
            "  * Edge case tests: empty input (empty string, empty array, null pointer, etc.), extreme input (maximum, minimum, zero, etc.), boundary values (array boundaries, string length boundaries, etc.), special values (negative numbers, NaN, infinity, etc., if applicable)",
            "  * Error case tests: if the C implementation has error handling (such as returning error codes, setting errno, etc.), the test cases should cover these error cases. If the Rust implementation uses Result<T, E> or Option<T> for error handling, the test cases should verify the error cases",
            "  * Consistency with the C implementation behavior: the expected results of the test cases should match the behavior of the C implementation",
            "  * Test case quality: clear test names, appropriate assertions, correct test logic, and the ability to truly verify the function's functionality",
            "  * Note: if the function is a resource-release function (such as fclose, free, etc.) that is automatically managed via RAII in Rust, the test cases can be very simple (such as merely verifying the function can be called without crashing), which is acceptable",
            "- The use of todo!/unimplemented! is forbidden; the full functionality must be implemented",
            "- Use native Rust types (i32/u32, &str/String, &[T]/&mut [T], Result<T,E>) and avoid C-style types",
            '- The use of extern "C" is forbidden; use the standard Rust calling convention',
            "- Keep changes minimal and avoid unrelated refactoring",
            "- Comments should be in Chinese; wildcard imports (use ...::*) are forbidden",
            "- Resource-release functions (fclose/free, etc.) can be automatically managed via RAII; provide an empty implementation and document it",
            *(
                [f"- Disabled libraries: {', '.join(self.disabled_libraries)}"]
                if self.disabled_libraries
                else []
            ),
            "",
            "[Dependency handling]",
            "- Check whether dependency functions are already implemented; complete any that are not (following TDD: test first, then implement)",
            "- Use read_symbols/read_code to get the C source",
            "- Handle low-level dependencies first to ensure all tests pass",
            "",
            "[Tools]",
            f'- read_symbols: {{"symbols_file": "{symbols_path}", "symbols": [...]}}',
            "- read_code: read the C source or a Rust module",
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
            "Output only the patch, without explanation.",
        ]
        # If a library replacement context exists, append it to the implementation prompt for the generator's reference (multi-library combinations, reference APIs, notes, etc.)
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
        # Add compile arguments (if present)
        compile_flags = None
        if hasattr(rec, "file") and rec.file:
            compile_flags = self.extract_compile_flags(rec.file)
        if compile_flags:
            requirement_lines.extend(
                [
                    "",
                    "C file compile arguments (from compile_commands.json):",
                    "\n".join(compile_flags),
                    "",
                ]
            )
        prompt = "\n".join(requirement_lines)
        return self.append_additional_notes(prompt, "")

    def extract_rust_fn_name_from_sig(self, rust_sig: str) -> str:
        """
        Extract the function name from a rust signature, supporting lifetime and generic parameters.
        For example: 'pub fn foo(a: i32) -> i32 { ... }' -> 'foo'
        For example: 'pub fn foo<'a>(bzf: &'a mut BzFile) -> Result<&'a [u8], BzError>' -> 'foo'
        """
        # Support lifetime and generic parameters: fn name<'a, T>(...)
        m = re.search(
            r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*\(", rust_sig or ""
        )
        return m.group(1) if m else ""

    def code_agent_generate_impl(
        self,
        rec: FnRecord,
        c_code: str,
        module: str,
        rust_sig: str,
        unresolved: List[str],
    ) -> None:
        """
        Use a CodeAgent to generate/update the function implementation in the target module.
        Constraint: minimal changes, generate a compilable placeholder implementation, and preserve as much room for later refinement as possible.
        """
        # Build the prompt
        prompt = self.build_generate_impl_prompt(
            rec, c_code, module, rust_sig, unresolved
        )

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
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][gen] auto-created module file: {mp}"
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_generation",
                        function="code_agent_generate_impl",
                    )
                    pass
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_generation",
                function="code_agent_generate_impl",
            )
            pass

        # Since transpile() already switched to the crate directory at the start, there is no need to switch again here
        # Record the commit before running
        before_commit = self.get_crate_commit_hash()
        # Use the generation Agent (can be reused)
        agent = self.get_generation_agent()
        agent.run(
            self.compose_prompt_with_context(prompt, agent),
            prefix="[c2rust-transpiler][gen]",
            suffix="",
        )

        # Detect and handle test code deletion
        if self.check_and_handle_test_deletion(before_commit, agent):
            # If it was rolled back, the agent needs to be run again
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][gen] Test code deletion detected; rolled back and re-running the agent"
            )
            before_commit = self.get_crate_commit_hash()
            # Use the same prompt on retry (it already contains the C source file location information)
            agent.run(
                self.compose_prompt_with_context(prompt, agent),
                prefix="[c2rust-transpiler][gen][retry]",
                suffix="",
            )
            # Detect again
            if self.check_and_handle_test_deletion(before_commit, agent):
                PrettyOutput.auto_print(
                    "❌ [c2rust-transpiler][gen] Test code deletion detected again; rolled back"
                )

        # If it is a root symbol, ensure its module is exposed in lib.rs
        if self.is_root_symbol(rec.qname or rec.name):
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
                            self.ensure_top_level_pub_mod(top_mod)
                            PrettyOutput.auto_print(
                                f"📋 [c2rust-transpiler][gen] The module {top_mod} for root symbol {rec.qname or rec.name} is already exposed in lib.rs"
                            )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_generation",
                    function="code_agent_generate_impl",
                )
                pass
