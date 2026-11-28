# -*- coding: utf-8 -*-

"""
Build and fix module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
import subprocess
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple


from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_c2rust.constants import CONSECUTIVE_FIX_FAILURE_THRESHOLD
from haijunbot.haijunbot_c2rust.constants import ERROR_SUMMARY_MAX_LENGTH
from haijunbot.haijunbot_c2rust.utils import truncate_git_diff_with_context_limit


class BuildManager:
    """Build and fix manager"""

    def __init__(
        self,
        crate_dir: Path,
        project_root: Path,
        data_dir: Path,
        test_max_retries: int,
        disabled_libraries: List[str],
        root_symbols: List[str],
        progress: Dict[str, Any],
        save_progress_func: Callable[[], None],
        extract_compile_flags_func: Callable[[str], List[str]],
        get_current_function_context_func: Callable[[], Dict[str, Any]],
        get_fix_agent_func: Callable[[], Any],
        compose_prompt_with_context_func: Callable[[str], str],
        check_and_handle_test_deletion_func: Callable[[str, Any], bool],
        get_crate_commit_hash_func: Callable[[], str],
        reset_to_commit_func: Callable[[str], None],
        append_additional_notes_func: Callable[[str], str],
        consecutive_fix_failures_getter: Callable[[], int],
        consecutive_fix_failures_setter: Callable[[int], None],
        current_function_start_commit_getter: Callable[[], Optional[str]],
        get_git_diff_func: Optional[Callable[[Optional[str]], str]] = None,
        enable_ffi_export_validation: bool = False,
    ) -> None:
        self.crate_dir = crate_dir
        self.project_root = project_root
        self.data_dir = data_dir
        self.test_max_retries = test_max_retries
        self.disabled_libraries = disabled_libraries
        self.root_symbols = root_symbols
        self.progress = progress
        self.save_progress = save_progress_func
        self.extract_compile_flags = extract_compile_flags_func
        self.get_current_function_context = get_current_function_context_func
        self.get_fix_agent = get_fix_agent_func
        self.compose_prompt_with_context = compose_prompt_with_context_func
        self.check_and_handle_test_deletion = check_and_handle_test_deletion_func
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.reset_to_commit = reset_to_commit_func
        self.append_additional_notes = append_additional_notes_func
        self._consecutive_fix_failures_getter = consecutive_fix_failures_getter
        self._consecutive_fix_failures_setter = consecutive_fix_failures_setter
        self._current_function_start_commit_getter = (
            current_function_start_commit_getter
        )
        self.get_git_diff = get_git_diff_func
        self.enable_ffi_export_validation = enable_ffi_export_validation
        self._build_loop_has_fixes = False  # mark whether a fix was performed in the build loop

    def classify_rust_error(self, text: str) -> List[str]:
        """
        Naive error classification, used to hint CodeAgent to focus on fixes:
        - missing_import: unresolved import / not found in this scope / cannot find ...
        - type_mismatch: mismatched types / expected ... found ...
        - visibility: private module/field/function
        - borrow_checker: does not live long enough / borrowed data escapes / cannot borrow as mutable
        - dependency_missing: failed to select a version / could not find crate
        - module_not_found: file not found for module / unresolved module
        """
        tags: List[str] = []
        t = (text or "").lower()

        def has(s: str) -> bool:
            return s in t

        if (
            ("unresolved import" in t)
            or ("not found in this scope" in t)
            or ("cannot find" in t)
            or ("use of undeclared crate or module" in t)
        ):
            tags.append("missing_import")
        if ("mismatched types" in t) or ("expected" in t and "found" in t):
            tags.append("type_mismatch")
        if (
            ("private" in t and "module" in t)
            or ("private" in t and "field" in t)
            or ("private" in t and "function" in t)
        ):
            tags.append("visibility")
        if (
            ("does not live long enough" in t)
            or ("borrowed data escapes" in t)
            or ("cannot borrow" in t)
        ):
            tags.append("borrow_checker")
        if (
            ("failed to select a version" in t)
            or ("could not find crate" in t)
            or ("no matching package named" in t)
        ):
            tags.append("dependency_missing")
        if ("file not found for module" in t) or ("unresolved module" in t):
            tags.append("module_not_found")
        # deduplicate
        try:
            tags = list(dict.fromkeys(tags))
        except Exception:
            tags = list(set(tags))
        return tags

    def detect_crate_kind(self) -> str:
        """
        Detect crate type: lib, bin, or mixed.
        Decision rules (as conservative as possible to avoid misjudgment):
        - if src/lib.rs exists or Cargo.toml contains [lib], consider it as containing lib
        - if src/main.rs exists or Cargo.toml contains [[bin]] (or [bin] for compatibility), consider it as containing bin
        - if both exist, return mixed
        - when neither is clear, default to returning lib (consistent with the default template)
        """
        try:
            cargo_path = (self.crate_dir / "Cargo.toml").resolve()
            txt = ""
            if cargo_path.exists():
                try:
                    txt = cargo_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    txt = ""
            txt_lower = txt.lower()
            has_lib = (self.crate_dir / "src" / "lib.rs").exists() or bool(
                re.search(r"(?m)^\s*\[lib\]\s*$", txt_lower)
            )
            # compatibility: [[bin]] is an array of tables, very few projects also write it as [bin]
            has_bin = (self.crate_dir / "src" / "main.rs").exists() or bool(
                re.search(r"(?m)^\s*\[\[bin\]\]\s*$", txt_lower)
                or re.search(r"(?m)^\s*\[bin\]\s*$", txt_lower)
            )
            if has_lib and has_bin:
                return "mixed"
            if has_bin:
                return "bin"
            if has_lib:
                return "lib"
        except Exception as e:
            save_exception(
                e, module="haijunbot_c2rust.transpiler_build", function="detect_crate_kind"
            )
            pass
        # default assumption is lib
        return "lib"

    def run_cargo_fmt(self, workspace_root: str) -> None:
        """Execute cargo fmt to format code"""
        try:
            res = subprocess.run(
                ["cargo", "fmt"],
                capture_output=True,
                text=True,
                check=False,
                cwd=workspace_root,
            )
            if res.returncode == 0:
                PrettyOutput.auto_print("🔍 [c2rust-transpiler][fmt] Code formatting completed")
            else:
                # fmt failure does not affect the main flow, only log a warning
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][fmt] Code formatting failed (non-fatal): {res.stderr or res.stdout}"
                )
        except Exception as e:
            # fmt failure does not affect the main flow, only log a warning
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][fmt] Code formatting exception (non-fatal): {e}"
            )

    def build_repair_prompt_base(
        self,
        stage: str,
        tags: List[str],
        sym_name: str,
        src_loc: str,
        c_code: str,
        curr: Dict[str, Any],
        symbols_path: str,
        include_output_patch_hint: bool = False,
        agent: Optional[Any] = None,
    ) -> List[str]:
        """
        Build the base part of the fix hint word.

        Return the base line list.
        """
        # check whether it is the root symbol
        is_root = sym_name in (self.root_symbols or [])
        # get C Source file location information (if src_loc contains file path and line number)
        c_file_location = ""
        if src_loc:
            # src_loc format may be "file:start-end" or "file"
            if ":" in src_loc and "-" in src_loc:
                c_file_location = src_loc
            elif src_loc:
                # if there is only the file path, try to get line number info from curr
                if curr.get("file"):
                    file_path = curr.get("file", "")
                    start_line = curr.get("start_line")
                    end_line = curr.get("end_line")
                    if start_line and end_line:
                        c_file_location = f"{file_path}:{start_line}-{end_line}"
                    else:
                        c_file_location = file_path
                else:
                    c_file_location = src_loc

        base_lines = [
            f"Goal: fix the problem with minimal changes so that the `{stage}` command can pass.",
            f"Stage: {stage}",
            f"error classification tags: {tags}",
            *([f"C Source file location: {c_file_location}"] if c_file_location else []),
            f"**Crate root (important)**: {self.crate_dir.resolve()}",
            "  - All Rust source files are under this directory",
            "  - When using read_code tool to read files, Please use path relative to this directory (such as `src/xxx.rs`)or absolute path",
            "  - When using edit_file_* tool to edit files, File path should also be relative to this directory or absolute path",
            "",
            "Allowed fixes: correct entry/module declarations/dependencies; make minor adjustments to the entry file and necessary mod.rs; when missing/unimplemented called functions cause errors, fill in the Rust implementations of these dependencies as well (reasonable new modules/functions may be added); avoid large-scale changes.",
            "- Keep changes minimal, avoid refactoring or formatting unrelated to the error;",
            "- If the build failure stems from missing or unimplemented called functions/dependencies, please read their C source code and fill in equivalent Rust implementations in this pass; if necessary, create new functions in reasonable modules;",
            "- The use of todo!/unimplemented! as placeholders is prohibited;",
            "- You may use the tools read_symbols/read_code to obtain the C source and locations of dependent symbols to assist implementation; import only the exact symbols needed, avoid glob imports;",
            "- **Elimination of compiler warnings**: when fixing, you must also eliminate all compiler warnings. After fixing, run `cargo check --message-format=short` to verify there are no warnings;",
            "- **Elimination of Clippy warnings**: when fixing, you must also eliminate all clippy warnings. After fixing, run `cargo clippy -- -D warnings` to verify there are no warnings;",
            "- **🔍 Debugging assistance: if you encounter problems that are hard to locate, you can use the following methods to assist debugging**:",
            "  * Add temporary debug output: use the `println!()` or `dbg!()` macros to output the values of key variables, function call paths, intermediate states, etc.",
            "  * Check the function call chain: use the `read_code` tool to read the implementations of related functions and confirm whether the call relationships are correct",
            "  * Verify data flow: add debug output at key locations to check whether data is passed correctly between functions",
            "  * Compare with the C implementation: use the `read_symbols` and `read_code` tools to read the C source code and compare the differences between the Rust implementation and the C implementation",
            "  * Check type conversions: confirm whether the correspondence between Rust types and C types is correct, especially pointers, arrays, structs, etc.",
            "  * Verify boundary conditions: check array boundaries, null handling, overflow handling, and other boundary cases",
            "  * Run a single test: if the test suite is large, you can use `cargo test -- --nocapture <test_name>` to run a specific test and speed up debugging",
            "  * View the full error information: make sure to read the complete error output, including stack traces, type information, location information, etc.",
            "  * Note: debug output can be removed after fixing, but it is recommended to keep the debug information at key locations until the problem is fully resolved",
            "- ⚠️ **important: fix scope requirements** - you must not only fix the current problem; if the fixing process causes other test cases to fail, you must fix those as well:",
            "  * After fixing, you must run `cargo test -- --nocapture` to verify that all test cases pass",
            "  * If you find that some test cases that originally passed now fail after fixing, it means the fix introduced a regression problem, and it must be fixed as well",
            "  * You must ensure that after fixing, all test cases (including tests for the target function and tests for other functions) pass",
            "  * If the fix affects other functions or modules, you need to check and fix all affected parts",
            "  * Do not only fix the current problem and ignore the failures of other tests",
            "- **⚠️ important: must verify after fixing** - after fixing is complete, you must use the `execute_script` tool to run the verification command:",
            "  * Run `cargo test -- --nocapture` to verify whether compilation and tests pass",
            "  * The command must succeed (return code 0) to indicate the fix was successful",
            "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
            "  * **cargo test compiles automatically, no need to run cargo check separately**",
            "- Comment convention: all code comments (including doc comments, inline comments, block comments, etc.) must be in Chinese;",
            f"- Dependency management: if the fix introduces a new external crate or requires enabling a feature, please update the [dependencies]/[dev-dependencies]/[features] of Cargo.toml accordingly{('; avoid undeclared dependencies causing build failures; version numbers may use a compatible range (such as ^x.y) or the default value' if stage == 'cargo test' else '')};",
            *(
                [
                    f"- **Disabled library constraint**: the following libraries are prohibited in fixes: {', '.join(self.disabled_libraries)}. If these libraries already exist in Cargo.toml, please remove the related dependencies; if the fix needs the functionality of these libraries, please use the standard library or other allowed libraries instead."
                ]
                if self.disabled_libraries
                else []
            ),
            *(
                [
                    f"- **Root symbol requirement**: This function is a root symbol ({sym_name}), must use `pub` keyword for public exposure, ensure access from outside crate. also, the module containing this function must be exported in src/lib.rs (using `pub mod <module_name>;`). "
                ]
                if is_root
                else []
            ),
            "",
            "[important: dependency checking and implementation requirements]",
            "Before fixing the problem, be sure to check the following:",
            "1. Check whether the current function is fully implemented:",
            f"   - Look for the implementation of function {sym_name} in the target module",
            "   - If an implementation already exists, check whether it is complete and correct",
            "2. Check whether all dependent functions are implemented:",
            "   - Analyze the build errors and identify all missing or unimplemented called functions",
            "   - Traverse all called functions invoked by the current function (including direct and indirect calls)",
            "   - For each called function, check whether it already has a complete implementation in the Rust crate",
            "   - You can use the read_code tool to read the relevant module files for checking",
            "3. For unimplemented dependent functions:",
            "   - Use the read_symbols tool to obtain their C source code and symbol information",
            "   - Use the read_code tool to read their C source implementation",
            "   - Fill in the Rust implementations of these dependent functions in this fix as well",
            "   - Choose an appropriate module location based on the dependency relationships (either in the same module or in a reasonable new module)",
            "   - Ensure all dependent functions have complete implementations; the use of todo!/unimplemented! placeholders is prohibited",
            "4. Implementation order:",
            "   - Implement the lowest-level dependent functions first (functions that do not depend on other unimplemented functions)",
            "   - Then implement the functions that depend on these low-level functions",
            "   - Finally fix the current target function",
            "5. Verification:",
            "   - Ensure the current function and all its dependent functions are fully implemented",
            "   - Ensure there are no leftover todo!/unimplemented! placeholders",
            "   - Ensure all function calls resolve correctly",
        ]
        if include_output_patch_hint:
            base_lines.append("- Please output only the patch, without explanations or extra text.")
        base_lines.extend(
            [
                "",
                "Context of the most recently processed function (for reference; prioritize fixing build errors):",
                f"- function: {sym_name}",
                f"- source location: {src_loc}",
                f"- Target module (progress): {curr.get('module') or ''}",
                f"- Suggested signature (progress): {curr.get('rust_signature') or ''}",
                "",
                "Original C function source snippet (read-only reference): ",
                "<C_SOURCE>",
                c_code,
                "</C_SOURCE>",
            ]
        )
        # Add compile flags (if exists)
        c_file_path = curr.get("file") or ""
        if c_file_path:
            compile_flags = self.extract_compile_flags(c_file_path)
            if compile_flags:
                base_lines.extend(
                    [
                        "",
                        "C file compile flags (from compile_commands.json):",
                        "\n".join(compile_flags),
                    ]
                )
        base_lines.extend(
            [
                "",
                "[Tool usage suggestions]",
                "1. Symbol table search:",
                "   - Tool: read_symbols",
                "   - Purpose: locate or cross-verify the location of C symbols",
                "   - Parameter example (JSON):",
                f'     {{"symbols_file": "{symbols_path}", "symbols": ["{sym_name}"]}}',
                "",
                "2. Code reading:",
                "   - Tool: read_code",
                "   - Purpose: Read C source implementation or Rust module file",
                "   - Debug purpose: when encountering problems, you can read the relevant files to check whether the implementation is correct",
                "   - **Important**: When reading Rust source files, must use absolute path or path relative to crate root",
                f"   - **Crate root**: {self.crate_dir.resolve()}",
                "   - Example:",
                f"     * Read Rust file: `read_code` tool, file path using `{self.crate_dir.resolve()}/src/xxx.rs` or `src/xxx.rs` (relative to crate root)",
                "     * Read C file: `read_code` tool, file path using full path of C source file",
                "",
                "3. Script execution (debugging assistance):",
                "   - Tool: execute_script",
                "   - Debug purpose:",
                "     * Run `cargo test -- --nocapture <test_name>` to run a specific test and speed up debugging",
                "     * Run `cargo test --message-format=short --no-run` to only check compilation without running tests",
                "     * Run `cargo check` to quickly check compilation errors (if tests are too slow)",
                "     * Run `cargo test --lib` to only run library tests and skip integration tests",
                "     * Run `cargo test --test <test_file>` to run a specific test file",
                "",
                "Context:",
                f"- **Crate root path (important)**: {self.crate_dir.resolve()}",
                "  * All Rust source files are under this directory",
                "  * When using the `read_code` tool to read Rust files, the file path should be relative to this directory (such as `src/xxx.rs`) or use an absolute path",
                "  * The current working directory should be switched to this directory, or use an absolute path to access files",
                f"- package name (used for cargo -p): {self.crate_dir.name}",
            ]
        )

        # add git change information as context
        if self.get_git_diff:
            try:
                base_commit = self._current_function_start_commit_getter()
                git_diff = self.get_git_diff(base_commit)
                if git_diff and git_diff.strip():
                    # limit the length of the git diff to avoid excessive context
                    # use a smaller ratio (30%) because the fix hint word itself is already very long
                    # if an agent is provided, use it to get a more accurate remaining token count, otherwise use the fallback approach
                    git_diff = truncate_git_diff_with_context_limit(
                        git_diff, agent=agent, token_ratio=0.3
                    )

                    base_lines.extend(
                        [
                            "",
                            "[Git change information]",
                            "The following are the git changes from when the function started being processed up to now, which can help you understand what modifications have been made:",
                            "<GIT_DIFF>",
                            git_diff,
                            "</GIT_DIFF>",
                            "",
                            "hint: ",
                            "- Please carefully review the above git diff to understand the current state of the code and the modifications made",
                            "- If you see that previous modifications introduced problems, you can handle them together when fixing",
                            "- If you see that some files were accidentally modified, you need to confirm whether these modifications are necessary",
                        ]
                    )
            except Exception:
                # if obtaining the git diff fails, it does not affect the main flow, only log a warning
                pass

        return base_lines

    def build_repair_prompt_stage_section(
        self, stage: str, output: str, command: Optional[str] = None
    ) -> List[str]:
        """
        Build the stage-specific part of the fix hint word (test or check).

        Return the stage-specific line list.
        """
        section_lines: List[str] = []
        if stage == "cargo_test_warning":
            section_lines.extend(
                [
                    "",
                    "[⚠️ important: Cargo Test compiler warnings - must be eliminated]",
                    "The following output comes from the `cargo test -- --nocapture` command, containing details of warnings during compilation and testing:",
                    "- **Current status of Cargo Test warnings: has warnings** - all warnings must be eliminated before continuing",
                    "- These warnings are generated during the `cargo test` compilation phase (such as `unused_mut`, `unused_variables`, `dead_code`, etc.)",
                    "- Cargo Test warnings usually indicate that the code has potential problems or areas that can be improved",
                    "- **Please carefully read the warning messages**, including:",
                    "  * Warning type (such as `unused_mut`, `unused_variables`, `dead_code`, `unused_import`, etc.)",
                    "  * Warning location (file path and line number)",
                    "  * Warning description and suggested fix method",
                    "",
                    "**Key requirements:**",
                    "- You must analyze the root cause of each warning and fix it according to the compiler's suggestions",
                    "- You must actually fix the code causing the warnings, rather than ignoring the warnings",
                    "- After fixing, you must ensure that `cargo test -- --nocapture` can pass (return code 0 and no warning output)",
                    "- Note: `cargo test` automatically compiles the code, and warnings from the compilation phase will be shown in the output",
                    "",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
                section_lines.append(
                    "hint: if you do not trust the execution result of the above command, you can use the execute_script tool to run the command yourself once for verification."
                )
            section_lines.extend(
                [
                    "",
                    "[Cargo Test warning details - must be read carefully and fixed]",
                    "The following is the complete output obtained from the `cargo test -- --nocapture` command, containing specific information about all warnings:",
                    "<CARGO_TEST_WARNINGS>",
                    output,
                    "</CARGO_TEST_WARNINGS>",
                    "",
                    "**Fix requirements:**",
                    "1. Carefully analyze the above warning information and find the root cause of each warning",
                    "2. Locate the specific code positions (file path and line number)",
                    "3. Fix according to the compiler's suggestions:",
                    "   - If the warning suggests removing `mut`, please remove the unnecessary `mut` keyword",
                    "   - If the warning suggests using an underscore prefix, please change the unused variable to `_variable_name`",
                    "   - If the warning is `dead_code` (unused function/variable), please remove the unused code or use the `#[allow(dead_code)]` attribute (only when necessary)",
                    "   - If the warning suggests removing unused imports, please remove them or use the `#[allow(unused_imports)]` attribute (only when necessary)",
                    "   - If the warning suggests using a safer API, please use the suggested API",
                    "   - If the warning suggests improving the code structure, please optimize the code according to the suggestion",
                    "4. Fix all warnings and ensure that `cargo test -- --nocapture` can pass (return code 0 and no warning output)",
                    "5. If some warnings truly cannot be fixed or require special handling, you can use the `#[allow(warning_name)]` attribute, but you must add a comment explaining the reason",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After fixing is complete, **you must use the `execute_script` tool to run the following command to verify the fix effect**:",
                    f"  - Command: `{command or 'cargo test -- --nocapture'}`",
                    "- Verification requirements:",
                    "  * If the command executes successfully (return code 0) and there is no warning output, it indicates the fix was successful",
                    "  * If the command fails (return code non-zero) or there is warning output, it indicates there are still warnings and you need to continue fixing",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, please analyze the reason for the failure and continue fixing until verification passes",
                    "",
                    "After fixing, please run `cargo test -- --nocapture` again for verification.",
                ]
            )
        elif stage == "compiler_warning":
            section_lines.extend(
                [
                    "",
                    "[⚠️ important: compiler warnings - must be eliminated]",
                    "The following output comes from the `cargo check --message-format=short` command, containing compiler warning details:",
                    "- **Current status of compiler warnings: has warnings** - all warnings must be eliminated before continuing",
                    "- Compiler warnings usually indicate that the code has potential problems or areas that can be improved",
                    "- **Please carefully read the warning messages**, including:",
                    "  * Warning type (such as `unused_variable`, `dead_code`, `unused_import`, etc.)",
                    "  * Warning location (file path and line number)",
                    "  * Warning description and suggested fix method",
                    "",
                    "**Key requirements:**",
                    "- You must analyze the root cause of each warning and fix it according to the compiler's suggestions",
                    "- You must actually fix the code causing the warnings, rather than ignoring the warnings",
                    "- After fixing, you must ensure that `cargo check --message-format=short` can pass (return code 0 and no warning output)",
                    "",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
                section_lines.append(
                    "hint: if you do not trust the execution result of the above command, you can use the execute_script tool to run the command yourself once for verification."
                )
            section_lines.extend(
                [
                    "",
                    "[Compiler warning details - must be read carefully and fixed]",
                    "The following is the complete output obtained from the `cargo check --message-format=short` command, containing specific information about all warnings:",
                    "<COMPILER_WARNINGS>",
                    output,
                    "</COMPILER_WARNINGS>",
                    "",
                    "**Fix requirements:**",
                    "1. **Prioritize trying automatic fixes**: first use the `cargo fix` command to automatically fix warnings that can be auto-fixed:",
                    "   - Run `cargo fix --allow-dirty --allow-staged` to try to automatically fix compiler warnings",
                    "   - If the automatic fix succeeds, verify the fix effect: run `cargo check --message-format=short` to check whether there are still warnings",
                    "   - If there are still warnings after the automatic fix, continue to manually fix the remaining warnings",
                    "2. Carefully analyze the above compiler warning information and find the root cause of each warning",
                    "3. Locate the specific code positions (file path and line number)",
                    "4. Fix according to the compiler's suggestions:",
                    "   - If the warning suggests removing unused code, please remove it or use the `#[allow(...)]` attribute (only when necessary)",
                    "   - If the warning suggests using a safer API, please use the suggested API",
                    "   - If the warning suggests improving the code structure, please optimize the code according to the suggestion",
                    "5. Fix all warnings and ensure that `cargo check --message-format=short` can pass (no warning output)",
                    "6. If some warnings truly cannot be fixed or require special handling, you can use the `#[allow(warning_name)]` attribute, but you must add a comment explaining the reason",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After fixing is complete, **you must use the `execute_script` tool to run the following command to verify the fix effect**:",
                    f"  - Command: `{command or 'cargo check --message-format=short'}`",
                    "- Verification requirements:",
                    "  * If the command executes successfully (return code is 0) and has no warning output, it means the fix succeeded",
                    "  * If the command fails (return code is non-zero) or has warning output, it means warnings still exist and the fix needs to continue",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, analyze the cause of failure and continue fixing until verification passes",
                    "",
                    "After fixing, please run `cargo check --message-format=short` again to verify.",
                ]
            )
        elif stage == "clippy":
            section_lines.extend(
                [
                    "",
                    " [⚠️ important: Clippy warnings - must be eliminated]",
                    "The following output comes from the `cargo clippy -- -D warnings` command and contains clippy warning details:",
                    "  - **Clippy current status: has warnings** - must eliminate all warnings before continuing",
                    "  - Clippy is Rust's code quality inspection tool; warnings usually indicate that the code can be improved",
                    "  - **Please read the warning information carefully**, including:",
                    "  * Warning type (such as `unused_variable`, `needless_borrow`, `clippy::unwrap_used`, etc.)",
                    "  * Warning location (file path and line number)",
                    "  * Warning description and suggested fix method",
                    "",
                    "**Key requirements:**",
                    "- Must analyze the root cause of each warning and fix according to clippy's suggestions",
                    "- Must actually fix the code causing the warnings, rather than ignoring the warnings",
                    "- After fixing, must ensure `cargo clippy -- -D warnings` can pass (return code is 0)",
                    "",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
                section_lines.append(
                    "hint: if you don't trust the above command execution result, you can use the execute_script tool to run the command once yourself to verify."
                )
            section_lines.extend(
                [
                    "",
                    " [Clippy warning details - must be read carefully and fixed]",
                    "The following is the complete output obtained from the `cargo clippy -- -D warnings` command, containing specific information for all warnings:",
                    "<CLIPPY_WARNINGS>",
                    output,
                    "</CLIPPY_WARNINGS>",
                    "",
                    "**Fix requirements:**",
                    "1. **Prioritize automatic fixing**: first use the `cargo clippy --fix` command to automatically fix the warnings that can be fixed automatically:",
                    "   - Run `cargo clippy --fix --allow-dirty --allow-staged -- -D warnings` to try to automatically fix clippy warnings",
                    "   - If the automatic fix succeeds, verify the fix result: run `cargo clippy -- -D warnings` to check whether warnings remain",
                    "   - If warnings remain after the automatic fix, continue to manually fix the remaining warnings",
                    "2. Carefully analyze the above clippy warning information and find the root cause of each warning",
                    "3. Locate the specific code location (file path and line number)",
                    "4. Fix according to clippy's suggestions:",
                    "   - If the warning suggests a more concise way of writing, please adopt the suggested approach",
                    "   - If the warning suggests removing unused code, please remove it or use the `#[allow(...)]` attribute (only when necessary)",
                    "   - If the warning suggests using a safer API, please use the suggested API",
                    "   - If the warning suggests improving performance, please optimize the code as suggested",
                    "5. Fix all warnings and ensure `cargo clippy -- -D warnings` can pass",
                    "6. If some warnings truly cannot be fixed or require special handling, you may use the `#[allow(clippy::warning_name)]` attribute, but you must add a comment explaining the reason",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After the fix is complete, **you must use the `execute_script` tool to run the following command to verify the fix result**:",
                    f"  - Command: `{command or 'cargo clippy -- -D warnings'}`",
                    "- Verification requirements:",
                    "  * If the command executes successfully (return code is 0), it means the fix succeeded",
                    "  * If the command fails (return code is non-zero), it means warnings still exist and the fix needs to continue",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, analyze the cause of failure and continue fixing until verification passes",
                    "",
                    "After fixing, please run `cargo clippy -- -D warnings` again to verify.",
                ]
            )
        elif stage == "cargo test":
            section_lines.extend(
                [
                    "",
                    " [⚠️ important: test failure - must fix]",
                    "The following output comes from the `cargo test` command and contains test execution results and failure details:",
                    "- **Test current status: failed** - must fix before continuing",
                    "- If you see a test case name and an assertion failure, it means there is a problem with the test logic or implementation",
                    "- If you see a compilation error, it means the code has a syntax or type error",
                    "- **Please read the failure information carefully**, including:",
                    "  * Test case name (such as `test_bz_read_get_unused`)",
                    "  * Failure location (file path and line number, such as `src/ffi/decompress.rs:76:47`)",
                    "  * Error type (such as `SequenceError`, `Result::unwrap()` failure, etc.)",
                    "  * The difference between expected and actual values",
                    "  * Complete stack trace information",
                    "",
                    "**Key requirements:**",
                    "- Must analyze the root cause of the test failure, rather than assuming the problem is solved",
                    "- Must actually fix the code causing the test failure, rather than only modifying the test case",
                    "- After fixing, must ensure the tests can pass, rather than only fixing compilation errors",
                    "",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
                section_lines.append(
                    "hint: if you don't trust the above command execution result, you can use the execute_script tool to run the command once yourself to verify."
                )
            section_lines.extend(
                [
                    "",
                    " [Test failure details - must be read carefully and fixed]",
                    "The following is the complete output obtained from the `cargo test` command, containing specific information about the test failures:",
                    "<TEST_FAILURE>",
                    output,
                    "</TEST_FAILURE>",
                    "",
                    "**Fix requirements:**",
                    "1. Carefully analyze the above test failure information and find the root cause of the failure",
                    "2. Locate the specific code location (file path and line number)",
                    "3. **If the problem is difficult to locate, add debugging information to help locate it**:",
                    "   - Add `println!()` or `dbg!()` at key positions to output variable values, function call paths, and intermediate states",
                    "   - Check whether function arguments and return values are passed correctly",
                    "   - Verify whether the data structures and type conversions are correct",
                    "   - Compare the differences between the C implementation and the Rust implementation to find points that may cause problems",
                    "   - Use the `read_code` tool to read the implementation of the relevant function and confirm whether the logic is correct",
                    "   - If the test output information is insufficient, you can add more detailed debug output to locate the problem",
                    "4. Fix the code logic that causes the test failure",
                    "5. ⚠️ **important: fix scope requirement** - not only must you fix the currently failing test case, if the fixing process causes other test cases to fail, you must also fix them together:",
                    "   - After fixing, you must run `cargo test -- --nocapture` to verify that all test cases pass",
                    "   - If you find that some test cases that originally passed now fail after the fix, it means the fix introduced a regression problem, and you must fix it as well",
                    "   - Must ensure that after fixing, all test cases (including tests for the target function and tests for other functions) can pass",
                    "   - If the fix affects other functions or modules, you need to check and fix all affected parts",
                    "   - Do not only fix the currently failing tests while ignoring the failures of other tests",
                    "6. Ensure that all tests can pass after fixing (do not only fix compilation errors)",
                    "7. If the test case itself has a problem, you may modify the test case, but you must ensure that the test can correctly verify the function behavior",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After the fix is complete, **you must use the `execute_script` tool to run the following command to verify the fix result**:",
                    f"  - Command: `{command or 'cargo test -- --nocapture'}`",
                    "- Verification requirements:",
                    "  * If the command executes successfully (return code is 0), it means the fix succeeded",
                    "  * If the command fails (return code is non-zero), it means the fix was not successful and the fix needs to continue",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, analyze the cause of failure and continue fixing until verification passes",
                    "",
                    "**⚠️ Concurrency problem hint**:",
                    "- If a test run fails, but no code was modified during the fix, yet re-running the test succeeds, this may be caused by a concurrency problem:",
                    "  * It may be a race condition between tests",
                    "  * It may be a concurrent access problem of shared resources (files, network, database, etc.)",
                    "  * It may be a test execution order dependency problem",
                    "- If you encounter this situation, it is recommended to:",
                    "  * Run the tests multiple times to confirm whether the problem reproduces stably",
                    "  * Check whether there is shared state or resources between tests",
                    "  * Check whether the tests depend on a specific execution order",
                    "  * Consider adding synchronization mechanisms or isolating the test environment",
                    "  * If the problem is unstable, you may need to add a retry mechanism or adjust the test strategy",
                    "",
                    "After fixing, please run `cargo test -q` again to verify.",
                ]
            )
        elif stage == "ffi_export_validation":
            section_lines.extend(
                [
                    "",
                    " [⚠️ important: FFI export verification failed - must fix]",
                    "The following output comes from the FFI export verification and contains information about the missing root symbols:",
                    "- **FFI export verification current status: failed** - the following root symbols were not found in the generated .so file",
                    '- These symbols must be correctly exported using `#[no_mangle]` and `pub extern "C"`',
                    "- **Please read the missing symbol information carefully**, including:",
                    "  * The list of missing root symbol names",
                    "  * The C function names corresponding to these symbols",
                    "",
                    "**Key requirements:**",
                    "- Must ensure that all root symbols (except main) are correctly exported in the FFI interface form",
                    "- The function must use the `#[no_mangle]` attribute to ensure the symbol name is not modified by the Rust compiler",
                    '- The function must be declared with `pub extern "C"`, using the C ABI calling convention',
                    "- The function signature should use C-compatible types (such as `*const c_char`, `c_int`, `c_void`, etc.)",
                    "- The function name should remain consistent with the original C function name (or follow the C naming convention)",
                    "- After fixing, you must rebuild the cdylib and verify whether the symbols are correctly exported",
                    "",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
            section_lines.extend(
                [
                    "",
                    " [FFI export verification details - must be read carefully and fixed]",
                    "The following is the complete information obtained from the FFI export verification, containing specific information about all missing symbols:",
                    "<FFI_EXPORT_VALIDATION>",
                    output,
                    "</FFI_EXPORT_VALIDATION>",
                    "",
                    "**Fix requirements:**",
                    "1. Carefully analyze the above missing symbol information and find the function corresponding to each symbol",
                    "2. Locate the specific code location (file path and function definition)",
                    "3. For each missing root symbol, ensure:",
                    "   - The function uses the `#[no_mangle]` attribute",
                    '   - The function is declared with `pub extern "C"`',
                    "   - The function signature uses C-compatible types",
                    "   - The function name matches the original C function name",
                    "   - The module where the function resides is exported in src/lib.rs",
                    '4. If the function already exists but is not correctly exported, modify the function declaration to add `#[no_mangle]` and `extern "C"`',
                    "5. If the function does not exist, you need to implement the function (using the FFI interface form)",
                    "6. After fixing, you must rebuild the cdylib: run `cargo build --lib`",
                    "7. Verify the fix result: use `nm -D <so_file>` or `objdump -T <so_file>` to check whether the symbols are exported",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After the fix is complete, **you must use the `execute_script` tool to run the following command to verify the fix result**:",
                    "  - Command 1: `cargo build --lib` (rebuild the cdylib)",
                    "  - Command 2: `nm -D target/debug/*.so | grep <symbol_name>` (verify whether the symbol is exported)",
                    "- Verification requirements:",
                    "  * The build command must execute successfully (return code is 0)",
                    "  * The symbol check command must be able to find all missing symbols",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, analyze the cause of failure and continue fixing until verification passes",
                    "",
                    "After fixing, please rebuild the cdylib and verify the symbol export.",
                ]
            )
        else:
            section_lines.extend(
                [
                    "",
                    "Please read the following build error and make the necessary fix:",
                ]
            )
            if command:
                section_lines.append(f"Executed command: {command}")
                section_lines.append(
                    "hint: if you don't trust the above command execution result, you can use the execute_script tool to run the command once yourself to verify."
                )
            section_lines.extend(
                [
                    "",
                    "<BUILD_ERROR>",
                    output,
                    "</BUILD_ERROR>",
                    "",
                    "**Fix requirements:**",
                    "1. Carefully analyze the above build error information and find the root cause of the error",
                    "2. Locate the specific code location (file path and line number)",
                    "3. **If the problem is difficult to locate, add debugging information to help locate it**:",
                    "   - Use the `read_code` tool to read the relevant file and check whether the code implementation is correct",
                    "   - Check whether the type definitions, function signatures, module imports, etc. are correct",
                    "   - Verify whether the dependency relationships are correct and whether all called functions/types are defined",
                    "   - If the error information is not clear enough, you can try compiling a single file or module to narrow down the scope of the problem",
                    "   - Compare the differences between the C implementation and the Rust implementation to confirm whether the type mapping is correct",
                    "4. Fix the code that causes the build error",
                    "5. ⚠️ **important: fix scope requirement** - not only must you fix the current build error, if the fixing process causes other test cases to fail, you must also fix them together:",
                    "   - After fixing, you must run `cargo test -- --nocapture` to verify that all test cases pass",
                    "   - If you find that some test cases that originally passed now fail after the fix, it means the fix introduced a regression problem, and you must fix it as well",
                    "   - Must ensure that after fixing, all test cases (including tests for the target function and tests for other functions) can pass",
                    "   - If the fix affects other functions or modules, you need to check and fix all affected parts",
                    "   - Do not only fix the current build error while ignoring the failures of other tests",
                    "6. Ensure that the code can compile successfully after fixing, and that all test cases can pass",
                    "",
                    "**⚠️ important: must verify after fixing**",
                    "- After the fix is complete, **you must use the `execute_script` tool to run the following command to verify the fix result**:",
                    "  - Command: `cargo test -- --nocapture`",
                    "- Verification requirements:",
                    "  * The command must execute successfully (return code is 0) to indicate that the fix succeeded",
                    "  * If the command fails (return code is non-zero), it means the fix was not successful and the fix needs to continue",
                    "  * **Do not assume the fix succeeded; you must actually run the command to verify**",
                    "- If verification fails, analyze the cause of failure and continue fixing until verification passes",
                    "",
                    "After fixing, please run `cargo test -- --nocapture` to verify.",
                ]
            )
        return section_lines

    def build_repair_prompt(
        self,
        stage: str,
        output: str,
        tags: List[str],
        sym_name: str,
        src_loc: str,
        c_code: str,
        curr: Dict[str, Any],
        symbols_path: str,
        include_output_patch_hint: bool = False,
        command: Optional[str] = None,
        agent: Optional[Any] = None,
    ) -> str:
        """
        Build the fix hint text.

        Args:
            stage: Stage name ("cargo test")
            output: Build error output
            tags: error classification tags
            sym_name: Symbol name
            src_loc: Source file location
            c_code: C source code snippet
            curr: Current progress information
            symbols_path: Symbol table file path
            include_output_patch_hint: Whether to include "output patch only" hint (required during test phase)
            command: Command to execute (optional)
        """
        base_lines = self.build_repair_prompt_base(
            stage,
            tags,
            sym_name,
            src_loc,
            c_code,
            curr,
            symbols_path,
            include_output_patch_hint,
            agent=agent,
        )
        stage_lines = self.build_repair_prompt_stage_section(stage, output, command)
        prompt = "\n".join(base_lines + stage_lines)
        return self.append_additional_notes(prompt)

    def run_cargo_test_and_fix(
        self, workspace_root: str, test_iter: int
    ) -> Tuple[bool, Optional[bool]]:
        """
        Run cargo test and fix on failure.

        Returns:
            (success, whether to rollback and restart; None means rollback is required)
        """
        # When tests fail, detailed output is needed. Remove the -q parameter to get full test failure information (including stack traces, assertion details, etc.)
        try:
            res_test = subprocess.run(
                ["cargo", "test", "--", "--nocapture"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                cwd=workspace_root,
            )
            returncode = res_test.returncode
            stdout = res_test.stdout or ""
            stderr = res_test.stderr or ""
        except subprocess.TimeoutExpired as e:
            # Timeout is treated as test failure and continues to the fix flow
            returncode = -1
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = "Command execution timed out (30 seconds)\n" + (
                e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            )
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][build] Cargo test timed out (30 seconds), treated as failure and continuing fix flow"
            )
        except Exception as e:
            # Other exceptions are also treated as test failures
            returncode = -1
            stdout = ""
            stderr = f"Exception occurred while executing cargo test: {str(e)}"
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][build] Cargo test execution exception: {e}, treated as failure and continuing fix flow"
            )

        # Check if cargo test output contains warnings (even if tests pass, warnings may exist)
        test_output_combined = stdout + "\n" + stderr
        test_has_warnings = "warning:" in test_output_combined.lower()

        warning_type: Optional[str] = None
        output: str = ""
        if returncode == 0:
            # Tests passed; first check warnings in cargo test output, then compilation warnings, then clippy warnings
            if test_has_warnings:
                # Warnings exist in cargo test output, extract and fix them
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][build] Cargo tests passed, but output contains warnings that need to be fixed."
                )
                PrettyOutput.auto_print(test_output_combined)
                # Use cargo test output warnings as fix targets
                warning_type = "cargo_test_warning"
                output = test_output_combined
            else:
                # No warnings in cargo test output, check compilation warnings
                compiler_has_warnings = False
                compiler_output = ""
                try:
                    res_compiler = subprocess.run(
                        ["cargo", "check", "--message-format=short"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                        cwd=workspace_root,
                    )
                    # Check for warning output (warnings may exist even if return code is 0)
                    combined_output = (
                        (res_compiler.stdout or "") + "\n" + (res_compiler.stderr or "")
                    )
                    # Check if output contains warnings (keyword: warning)
                    if (
                        "warning:" in combined_output.lower()
                        or res_compiler.returncode != 0
                    ):
                        compiler_has_warnings = True
                        compiler_output = combined_output
                except subprocess.TimeoutExpired:
                    # Compilation check timed out, treat as having warnings
                    compiler_has_warnings = True
                    compiler_output = "Compilation check timed out (30 seconds)"
                except Exception as e:
                    # Compilation check exception, treat as having warnings
                    compiler_has_warnings = True
                    compiler_output = f"Exception occurred during compilation check: {str(e)}"

                if compiler_has_warnings:
                    PrettyOutput.auto_print(
                        "⚠️ [c2rust-transpiler][build] Cargo tests passed with no cargo test warnings, but compilation warnings exist that need to be fixed."
                    )
                    PrettyOutput.auto_print(compiler_output)
                    # Use compilation warnings as fix targets and continue fix flow
                    warning_type = "compiler"
                    output = compiler_output
                else:
                    # No compilation warnings, check clippy warnings
                    clippy_has_warnings = False
                    clippy_output = ""
                    try:
                        res_clippy = subprocess.run(
                            ["cargo", "clippy", "--", "-D", "warnings"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=False,
                            cwd=workspace_root,
                        )
                        if res_clippy.returncode != 0:
                            clippy_has_warnings = True
                            clippy_output = (
                                (res_clippy.stdout or "")
                                + "\n"
                                + (res_clippy.stderr or "")
                            )
                    except subprocess.TimeoutExpired:
                        # Clippy check timed out, treat as having warnings
                        clippy_has_warnings = True
                        clippy_output = "Clippy check timed out (30 seconds)"
                    except Exception as e:
                        # Clippy execution exception, treat as having warnings
                        clippy_has_warnings = True
                        clippy_output = f"Exception occurred while executing clippy: {str(e)}"

                    if clippy_has_warnings:
                        PrettyOutput.auto_print(
                            "⚠️ [c2rust-transpiler][build] Cargo tests passed with no compilation warnings, but clippy warnings exist that need to be fixed."
                        )
                        PrettyOutput.auto_print(clippy_output)
                        # Use clippy warnings as fix targets and continue fix flow
                        warning_type = "clippy"
                        output = clippy_output
                    else:
                        PrettyOutput.auto_print(
                            "✅ [c2rust-transpiler][build] Cargo tests passed with no cargo test warnings, no compilation warnings, and no clippy warnings."
                        )
                        # Tests passed with no compilation warnings and no clippy warnings; reset consecutive failure count
                        self._consecutive_fix_failures_setter(0)
                        try:
                            cur = self.progress.get("current") or {}
                            metrics = cur.get("metrics") or {}
                            metrics["test_attempts"] = int(test_iter)
                            cur["metrics"] = metrics
                            cur["impl_verified"] = True
                            cur["failed_stage"] = None
                            self.progress["current"] = cur
                            self.save_progress()
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_c2rust.transpiler_build",
                                function="run_cargo_test_and_fix",
                            )
                            pass
                        return (True, False)
        else:
            # Tests failed
            # Check if test failure output also contains warnings (may need to fix together)
            if test_has_warnings:
                # Tests failed and output contains warnings; prioritize fixing warnings (warnings may cause test failures)
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][build] Cargo tests failed, and output contains warnings; will prioritize fixing warnings."
                )
                warning_type = "cargo_test_warning"
                output = test_output_combined
            else:
                # Tests failed but no warnings, handle as test failure
                warning_type = None
                output = test_output_combined
            limit_info = (
                f" (limit: {self.test_max_retries if self.test_max_retries > 0 else 'unlimited'})"
                if test_iter % 10 == 0 or test_iter == 1
                else ""
            )
            PrettyOutput.auto_print(
                f"❌ [c2rust-transpiler][build] Cargo tests failed (attempt {test_iter}{limit_info})."
            )
            PrettyOutput.auto_print(output)
            maxr = self.test_max_retries
            if maxr > 0 and test_iter >= maxr:
                PrettyOutput.auto_print(
                    f"❌ [c2rust-transpiler][build] Maximum retry limit reached ({maxr}); stopping build-fix loop."
                )
                try:
                    cur = self.progress.get("current") or {}
                    metrics = cur.get("metrics") or {}
                    metrics["test_attempts"] = int(test_iter)
                    cur["metrics"] = metrics
                    cur["impl_verified"] = False
                    cur["failed_stage"] = "test"
                    err_summary = (output or "").strip()
                    if len(err_summary) > ERROR_SUMMARY_MAX_LENGTH:
                        err_summary = (
                            err_summary[:ERROR_SUMMARY_MAX_LENGTH] + "...(truncated)"
                        )
                    cur["last_build_error"] = err_summary
                    self.progress["current"] = cur
                    self.save_progress()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_build",
                        function="run_cargo_test_and_fix",
                    )
                    pass
                return (False, False)

        # Build failure (test phase) fix, compilation warning fix, clippy warning fix, or cargo test warning fix
        if warning_type == "cargo_test_warning":
            # Fix for warnings in cargo test output
            tags = ["cargo_test_warning"]
            stage_name = "cargo_test_warning"
            command_str = "cargo test -- --nocapture"
        elif warning_type == "compiler":
            # Fix for compilation warnings
            tags = ["compiler_warning"]
            stage_name = "compiler_warning"
            command_str = "cargo check --message-format=short"
        elif warning_type == "clippy":
            # Fix for clippy warnings
            tags = ["clippy_warning"]
            stage_name = "clippy"
            command_str = "cargo clippy -- -D warnings"
        else:
            # Fix for test failures
            tags = self.classify_rust_error(output)
            stage_name = "cargo test"
            command_str = "cargo test -- --nocapture"

        symbols_path = str((self.data_dir / "symbols.jsonl").resolve())
        curr_info = self.get_current_function_context()
        sym_name = curr_info.get("sym_name", "")
        src_loc = curr_info.get("src_loc", "")
        c_code = curr_info.get("c_code", "")

        # Debug output: verify error information is correctly passed
        if warning_type is None:
            PrettyOutput.auto_print(
                f"🔍 [c2rust-transpiler][debug] Test failure message length: {len(output)} characters"
            )
            if output:
                # Extract key error information for debugging
                error_lines = output.split("\n")
                key_errors = [
                    line
                    for line in error_lines
                    if any(
                        keyword in line.lower()
                        for keyword in [
                            "failed",
                            "error",
                            "panic",
                            "unwrap",
                            "sequence",
                        ]
                    )
                ]
                if key_errors:
                    PrettyOutput.auto_print(
                        "🔍 [c2rust-transpiler][debug] Key error information (first 5 lines):"
                    )
                    for i, line in enumerate(key_errors[:5], 1):
                        PrettyOutput.auto_print(f"🔍   {i}. {line[:100]}")

        # Since transpile() already switched to the crate directory, no need to switch again
        # Record commit before running
        before_commit = self.get_crate_commit_hash()
        # Create fix Agent first (will be reused later)
        # Use fix Agent, create new each time, and pass C code
        agent = self.get_fix_agent()

        repair_prompt = self.build_repair_prompt(
            stage=stage_name,
            output=output,
            tags=tags,
            sym_name=sym_name,
            src_loc=src_loc,
            c_code=c_code,
            curr=curr_info,
            symbols_path=symbols_path,
            include_output_patch_hint=True,
            command=command_str,
            agent=agent,
        )
        agent.run(
            self.compose_prompt_with_context(repair_prompt),
            prefix=f"[c2rust-transpiler][build-fix iter={test_iter}][test]",
            suffix="",
        )

        # Detect and handle test code deletion
        if self.check_and_handle_test_deletion(before_commit, agent):
            # If rolled back, need to rerun agent
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][build-fix] Detected test code deletion issue, rolled back, rerunning agent (iter={test_iter})"
            )
            before_commit = self.get_crate_commit_hash()
            # Recreate fix Agent
            agent = self.get_fix_agent()
            agent.run(
                self.compose_prompt_with_context(repair_prompt),
                prefix=f"[c2rust-transpiler][build-fix iter={test_iter}][test][retry]",
                suffix="",
            )
            # Detect again
            if self.check_and_handle_test_deletion(before_commit, agent):
                PrettyOutput.auto_print(
                    f"❌ [c2rust-transpiler][build-fix] Detected test code deletion issue again, rolled back (iter={test_iter})"
                )

        # Post-fix verification: first check compilation, then actually run tests
        # Step 1: Check if compilation passes
        res_compile = subprocess.run(
            ["cargo", "test", "--message-format=short", "-q", "--no-run"],
            capture_output=True,
            text=True,
            check=False,
            cwd=workspace_root,
        )
        if res_compile.returncode != 0:
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][build] Compilation still has errors after fix; will be handled in next loop iteration"
            )
            # Compilation failed, increment consecutive failure count
            current_failures = self._consecutive_fix_failures_getter()
            self._consecutive_fix_failures_setter(current_failures + 1)
            # Check if rollback is needed
            current_start_commit = self._current_function_start_commit_getter()
            if (
                current_failures >= CONSECUTIVE_FIX_FAILURE_THRESHOLD
                and current_start_commit
            ):
                PrettyOutput.auto_print(
                    f"❌ [c2rust-transpiler][build] Consecutive fix failures: {current_failures}, rolling back to commit at start of function: {current_start_commit}"
                )
                if self.reset_to_commit(current_start_commit):
                    # Return special value indicating need to restart
                    return (False, None)
                # Rollback failed, continue attempting fix
            return (False, False)  # Need to continue loop

        # Step 2: Compilation passed, run actual tests for verification
        try:
            res_test_verify = subprocess.run(
                ["cargo", "test", "--", "--nocapture"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                cwd=workspace_root,
            )
            verify_returncode = res_test_verify.returncode
            verify_stdout = res_test_verify.stdout or ""
            verify_stderr = res_test_verify.stderr or ""
            verify_output_combined = verify_stdout + "\n" + verify_stderr
            verify_has_warnings = "warning:" in verify_output_combined.lower()
        except subprocess.TimeoutExpired:
            # Timeout is treated as test failure
            verify_returncode = -1
            verify_has_warnings = False
            verify_output_combined = ""
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][build] Post-fix verification test timed out (30 seconds), treated as failure"
            )
        except Exception as e:
            # Other exceptions are also treated as test failures
            verify_returncode = -1
            verify_has_warnings = False
            verify_output_combined = ""
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][build] Post-fix verification test exception: {e}, treated as failure"
            )

        if verify_returncode == 0:
            # Tests passed, check if there are warnings
            if verify_has_warnings:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][build] Post-fix tests passed, but output contains warnings; will be handled in next loop iteration"
                )
                PrettyOutput.auto_print(verify_output_combined)
                # Warnings exist, continue loop to fix
                return (False, False)
            # Tests passed, first check compilation warnings, then clippy warnings
            compiler_has_warnings_after_fix = False
            compiler_output_after_fix = ""
            try:
                res_compiler_verify = subprocess.run(
                    ["cargo", "check", "--message-format=short"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                    cwd=workspace_root,
                )
                # Check for warning output
                combined_output = (
                    (res_compiler_verify.stdout or "")
                    + "\n"
                    + (res_compiler_verify.stderr or "")
                )
                if (
                    "warning:" in combined_output.lower()
                    or res_compiler_verify.returncode != 0
                ):
                    compiler_has_warnings_after_fix = True
                    compiler_output_after_fix = combined_output
            except subprocess.TimeoutExpired:
                compiler_has_warnings_after_fix = True
                compiler_output_after_fix = "Compilation check timed out (30 seconds)"
            except Exception as e:
                compiler_has_warnings_after_fix = True
                compiler_output_after_fix = f"Exception occurred during compilation check: {str(e)}"

            if compiler_has_warnings_after_fix:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][build] Post-fix tests passed, but compilation warnings exist; will be handled in next loop iteration"
                )
                PrettyOutput.auto_print(compiler_output_after_fix)
                # Compilation warnings exist, continue loop to fix
                return (False, False)
            else:
                # No compilation warnings, check clippy warnings
                clippy_has_warnings_after_fix = False
                clippy_output_after_fix = ""
                try:
                    res_clippy_verify = subprocess.run(
                        ["cargo", "clippy", "--", "-D", "warnings"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                        cwd=workspace_root,
                    )
                    if res_clippy_verify.returncode != 0:
                        clippy_has_warnings_after_fix = True
                        clippy_output_after_fix = (
                            (res_clippy_verify.stdout or "")
                            + "\n"
                            + (res_clippy_verify.stderr or "")
                        )
                except subprocess.TimeoutExpired:
                    clippy_has_warnings_after_fix = True
                    clippy_output_after_fix = "Clippy check timed out (30 seconds)"
                except Exception as e:
                    clippy_has_warnings_after_fix = True
                    clippy_output_after_fix = f"Exception occurred while executing clippy: {str(e)}"

                if clippy_has_warnings_after_fix:
                    PrettyOutput.auto_print(
                        "⚠️ [c2rust-transpiler][build] Post-fix tests passed with no compilation warnings, but clippy warnings exist; will be handled in next loop iteration"
                    )
                    PrettyOutput.auto_print(clippy_output_after_fix)
                    # Clippy warnings exist, continue loop to fix
                    return (False, False)
                else:
                    PrettyOutput.auto_print(
                        "✅ [c2rust-transpiler][build] Post-fix tests passed with no cargo test warnings, no compilation warnings, and no clippy warnings; continuing build loop"
                    )
                    # Tests truly passed with no compilation warnings and no clippy warnings; reset consecutive failure count
                    self._consecutive_fix_failures_setter(0)
                    return (False, False)  # Need to continue loop (should pass next time)
        else:
            # Compilation passed but tests still failed; fix did not resolve test logic issue
            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][build] Compilation passed after fix, but tests still failed; will be handled in next loop iteration"
            )
            # Tests failed, increment consecutive failure count (even though compilation passed)
            current_failures = self._consecutive_fix_failures_getter()
            self._consecutive_fix_failures_setter(current_failures + 1)
            current_start_commit = self._current_function_start_commit_getter()
            # Check if rollback is needed
            if (
                current_failures >= CONSECUTIVE_FIX_FAILURE_THRESHOLD
                and current_start_commit
            ):
                PrettyOutput.auto_print(
                    f"❌ [c2rust-transpiler][build] Consecutive fix failures: {current_failures} (compilation passed but tests failed); rolling back to commit at start of function: {current_start_commit}"
                )
                if self.reset_to_commit(current_start_commit):
                    # Return special value indicating need to restart
                    return (False, None)
                # Rollback failed, continue attempting fix
            return (False, False)  # Need to continue loop

    def cargo_build_loop(self) -> Optional[bool]:
        """Execute build and tests in crate directory: directly run cargo test (run all tests regardless of project structure). On failure, minimize fixes until passing or reaching limit.

        Returns:
            Optional[bool]:
                - True: Tests passed (possibly after fixes)
                - False: Tests failed (reached retry limit)
                - None: Rollback and restart needed
        """
        workspace_root = str(self.crate_dir)
        test_limit = f"max retries: {self.test_max_retries if self.test_max_retries > 0 else 'unlimited'}"
        PrettyOutput.auto_print(
            f"🔍 [c2rust-transpiler][build] workspace_root={workspace_root}, starting build loop (test, {test_limit})"
        )
        test_iter = 0
        has_fixes = False  # Mark if fixes were made
        while True:
            # Run all tests (regardless of project structure)
            # cargo test compiles and runs all types of tests automatically: lib tests, bin tests, integration tests, doc tests, etc.
            test_iter += 1
            test_success, need_restart = self.run_cargo_test_and_fix(
                workspace_root, test_iter
            )
            if need_restart is None:
                self._build_loop_has_fixes = False  # Reset flag on rollback
                return None  # Rollback and restart needed
            if test_success:
                # If fixes were made (test_iter > 1), mark that re-review is needed
                if test_iter > 1:
                    has_fixes = True
                # Save fix flag to instance variable for caller to check
                self._build_loop_has_fixes = has_fixes

                # If FFI export validation is enabled, detect root symbols in .so file after build verification passes
                if self.enable_ffi_export_validation:
                    ffi_fix_needed = self._validate_ffi_exports()
                    if ffi_fix_needed:
                        # Need to fix FFI exports, continue loop
                        has_fixes = True
                        self._build_loop_has_fixes = True
                        continue

                return True  # Tests passed
            # If tests failed, fixes were attempted
            if test_iter > 1:
                has_fixes = True

    def _validate_ffi_exports(self) -> bool:
        """
        Verify FFI exports: ensure cdylib is produced, and detect root symbols in the .so file after build. If symbols are missing, perform fixes.
        If symbols are missing, perform fixes.

        Returns:
            bool: If fixes are needed, return True; otherwise return False
        """
        try:
            # 1. Ensure Cargo.toml has cdylib configuration
            from haijunbot.haijunbot_c2rust.transpiler_modules import ModuleManager

            module_manager = ModuleManager(self.crate_dir)
            module_manager.ensure_cargo_toml_cdylib()

            # 2. Build cdylib
            PrettyOutput.auto_print(
                "🔍 [c2rust-transpiler][ffi] Building cdylib to verify FFI exports..."
            )
            build_result = subprocess.run(
                ["cargo", "build", "--lib"],
                capture_output=True,
                text=True,
                cwd=str(self.crate_dir),
            )

            if build_result.returncode != 0:
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][ffi] cdylib build failed: {build_result.stderr}"
                )
                # Build failed, need to fix
                return True

            # 3. Find the generated .so file
            # On Linux, .so files are usually in target/debug/
            target_dir = self.crate_dir / "target" / "debug"
            so_files = list(target_dir.glob("*.so"))

            if not so_files:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][ffi] Generated .so file not found"
                )
                return True  # Need to fix

            # Use the first .so file found (usually only one)
            so_file = so_files[0]
            PrettyOutput.auto_print(
                f"📋 [c2rust-transpiler][ffi] Detected .so file: {so_file}"
            )

            # 4. Use nm or objdump to detect symbols in the .so file
            # Get list of root symbols (excluding main)
            root_symbols_not_main = [
                sym for sym in (self.root_symbols or []) if sym != "main"
            ]

            if not root_symbols_not_main:
                PrettyOutput.auto_print(
                    "📋 [c2rust-transpiler][ffi] No root symbols to verify (other than main)"
                )
                return False  # No verification needed

            # Use nm command to get exported symbols
            nm_result = subprocess.run(
                ["nm", "-D", str(so_file)],  # -D means show only dynamic symbols
                capture_output=True,
                text=True,
                cwd=str(self.crate_dir),
            )

            exported_symbols = set()
            if nm_result.returncode == 0:
                # Parse nm output to extract symbol names
                for line in nm_result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        # nm output format: address type symbol_name
                        symbol_name = parts[2]
                        # Only focus on T (text) and D (data) type symbols
                        if parts[1] in ("T", "D", "B"):
                            exported_symbols.add(symbol_name)
            else:
                # nm failed, try objdump
                objdump_result = subprocess.run(
                    ["objdump", "-T", str(so_file)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.crate_dir),
                )
                if objdump_result.returncode == 0:
                    # Parse objdump output
                    for line in objdump_result.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 6 and parts[1] in (".text", ".data", ".bss"):
                            symbol_name = parts[-1]
                            exported_symbols.add(symbol_name)
                else:
                    PrettyOutput.auto_print(
                        "⚠️ [c2rust-transpiler][ffi] Unable to read .so file symbols: both nm and objdump failed"
                    )
                    return True  # Need to fix

            # 5. Check if all root symbols are present in the .so file
            missing_symbols = []
            for sym in root_symbols_not_main:
                # Check symbol names (may have leading underscore depending on platform)
                found = False
                for exported in exported_symbols:
                    # Symbol names may match exactly or have leading underscore
                    if exported == sym or exported == f"_{sym}":
                        found = True
                        break
                if not found:
                    missing_symbols.append(sym)

            if not missing_symbols:
                PrettyOutput.auto_print(
                    "✅ [c2rust-transpiler][ffi] All root symbols (except main) have been correctly exported to the .so file"
                )
                return False  # No fix needed

            # 6. If symbols are missing, perform fix
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][ffi] The following root symbols were not found in the .so file: {', '.join(missing_symbols)}"
            )

            # Build fix hint
            curr, sym_name, src_loc, c_code = self._get_current_function_context_tuple()
            tags = ["ffi_export_missing"]

            prompt = self.build_repair_prompt(
                stage="ffi_export_validation",
                output=f"Missing root symbols: {', '.join(missing_symbols)}",
                tags=tags,
                sym_name=sym_name or "FFI export verification",
                src_loc=src_loc,
                c_code=c_code,
                curr=curr,
                symbols_path=str((self.data_dir / "symbols.jsonl").resolve()),
                include_output_patch_hint=False,
            )

            # Use fix Agent to fix
            before_commit = self.get_crate_commit_hash()
            agent = self.get_fix_agent()
            agent.run(
                self.compose_prompt_with_context(prompt),
                prefix="[c2rust-transpiler][ffi-fix]",
                suffix="",
            )

            # Detect and handle test code deletion
            if self.check_and_handle_test_deletion(before_commit, agent):
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-transpiler][ffi-fix] Detected test code deletion issue, rolled back"
                )

            return True  # Fix performed, need re-verification

        except Exception as e:
            PrettyOutput.auto_print(
                f"❌ [c2rust-transpiler][ffi] FFI export verification failed: {e}"
            )
            return True  # Error occurred, need fix

    def _get_current_function_context_tuple(
        self,
    ) -> Tuple[Dict[str, Any], str, str, str]:
        """Get current function context information, return as tuple"""
        ctx = self.get_current_function_context()
        return (
            ctx.get("curr", {}),
            ctx.get("sym_name", ""),
            ctx.get("src_loc", ""),
            ctx.get("c_code", ""),
        )
