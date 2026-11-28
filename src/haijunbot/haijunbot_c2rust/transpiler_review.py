# -*- coding: utf-8 -*-
"""
Code review module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import re
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.agent_factory import create_agent
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.utils import dir_tree
from haijunbot.haijunbot_c2rust.utils import extract_json_from_summary
from haijunbot.haijunbot_c2rust.utils import truncate_git_diff_with_context_limit


class ReviewManager:
    """Code review manager"""

    def __init__(
        self,
        crate_dir: Path,
        data_dir: Path,
        non_interactive: bool,
        review_max_iterations: int,
        disabled_libraries: List[str],
        progress: Dict[str, Any],
        save_progress_func: Callable[[], None],
        read_source_span_func: Callable[[FnRecord], str],
        collect_callees_context_func: Callable[[FnRecord], List[Dict[str, Any]]],
        extract_compile_flags_func: Callable[[str], Optional[str]],
        is_root_symbol_func: Callable[[FnRecord], bool],
        get_crate_commit_hash_func: Callable[[], Optional[str]],
        current_function_start_commit_getter: Callable[[], Optional[str]],
        compose_prompt_with_context_func: Callable[[str, bool], str],
        get_fix_agent_func: Callable[[Optional[str]], Any],
        check_and_handle_test_deletion_func: Callable[[Optional[str], Any], bool],
        append_additional_notes_func: Callable[[str], str],
        cargo_build_loop_func: Callable[[], Optional[bool]],
        get_build_loop_has_fixes_func: Callable[[], bool],
        on_before_tool_call_func: Callable[[Any, Any], None],
        on_after_tool_call_func: Callable[[Any, Any, Any, Any], None],
        agent_before_commits: Dict[str, Optional[str]],
        get_git_diff: Optional[Callable[[str], str]] = None,
        get_git_diff_func: Optional[Callable[[Optional[str]], str]] = None,
    ) -> None:
        self.crate_dir = crate_dir
        self.data_dir = data_dir

        self.non_interactive = non_interactive
        self.review_max_iterations = review_max_iterations
        self.disabled_libraries = disabled_libraries
        self.progress = progress
        self.save_progress = save_progress_func
        self.read_source_span = read_source_span_func
        self.collect_callees_context = collect_callees_context_func
        self.extract_compile_flags = extract_compile_flags_func
        self.is_root_symbol = is_root_symbol_func
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.current_function_start_commit_getter = current_function_start_commit_getter
        self.compose_prompt_with_context: Callable[[str, bool], str] = (
            compose_prompt_with_context_func
        )
        self.get_fix_agent = get_fix_agent_func
        self.check_and_handle_test_deletion = check_and_handle_test_deletion_func
        self.append_additional_notes = append_additional_notes_func
        self.cargo_build_loop = cargo_build_loop_func
        self.get_build_loop_has_fixes = get_build_loop_has_fixes_func
        self.on_before_tool_call = on_before_tool_call_func
        self.on_after_tool_call = on_after_tool_call_func
        self.agent_before_commits = agent_before_commits
        self.get_git_diff = get_git_diff_func

    def review_and_optimize(self, rec: FnRecord, module: str, rust_sig: str) -> None:
        """
        Review the generated implementation; if the summary reports issues, call CodeAgent to optimize, until there are no issues or the max iterations are reached.
        Combines functional consistency review and type/boundary critical issue review to avoid duplicate reviews.
        Review only focuses on the current function and minimal related context, avoiding global refactoring.
        """

        def build_review_prompts() -> Tuple[str, str, str]:
            sys_p = (
                "You are a Rust code review expert. Acceptance criteria: the Rust implementation should be functionally consistent with the original C implementation, and should not contain serious issues that may cause functional errors.\n"
                "**Review priority**: test breaking change check > test case completeness > critical issues > breaking changes > functional consistency > file structure. Prioritize checking whether tests are broken (missing/duplicate #[test] markers, incorrect code insertion positions, etc.), then check whether test cases are complete, then handle issues that may cause crashes or compilation failures.\n"
                "**Review scope**: mainly review the current function implementation, with related dependency functions as auxiliary reference.\n"
                "Review criteria (combining functional consistency and critical issues checks):\n"
                "1. Functional consistency check:\n"
                "   - **Core functionality definition**: core input/output, whether the main functional logic is consistent with the C implementation. Core functionality refers to the main purpose and expected behavior of the function (such as 'calculate hash value', 'parse string', 'compress data', etc.) and does not include implementation details;\n"
                "   - **Security improvements allow behavioral inconsistency**: Allow the Rust implementation to fix security vulnerabilities in the C code (such as buffer overflow, null pointer dereference, uninitialized memory usage, integer overflow, format string vulnerability, etc.); these security improvements may cause behavior inconsistent with the C implementation, but this is allowed and should not be considered functional inconsistency;\n"
                "   - **Ignore behavioral inconsistency caused by language differences**: Due to essential differences between the Rust and C languages, the following behavioral differences are unavoidable and should be ignored:\n"
                "     * Integer overflow handling: Rust panics in debug mode and wraps in release mode, while C has undefined behavior;\n"
                "     * Undefined behavior: Rust avoids or explicitly handles it, while C may produce undefined behavior;\n"
                "     * Null pointer/null reference: Rust uses Option<T> or Result<T, E>, while C may directly dereference causing a crash;\n"
                "     * Memory safety: Rust's borrow checker prevents certain unsafe operations allowed in C;\n"
                "     * Error handling: Rust uses Result<T, E> or Option<T>, while C may use error codes or the global errno;\n"
                "   - Allow the Rust implementation to use a different type design, error handling approach, resource management approach, etc., as long as the functionality is consistent;\n"
                "2. Critical issues check (may cause functional errors or program crashes):\n"
                "   - obvious null pointer dereference or serious errors causing a panic;\n"
                "   - obvious out-of-bounds access or issues causing a program crash;\n"
                "   - logic errors causing the program to be unable to run normally;\n"
                "3. Breaking change detection (impact on existing code):\n"
                "   - **allow signature inconsistency**: Allow the function signature, parameter count, parameter type, return type, etc. to be inconsistent with the C implementation, as long as the functionality is implemented. This is normal for Rust transpilation, because Rust's type system and design philosophy differ from C;\n"
                "   - **only check actual breaking impact**: Only report as a breaking change when a function signature change actually causes caller code to fail compilation or at runtime. If the caller code has adapted to the new signature, or can be resolved through simple adaptation, it should not be considered a breaking change;\n"
                "   - **⚠️⚠️ focus: test breaking change check**: Must focus on checking whether code changes break current tests; this is the highest priority check item. Specifically includes:\n"
                "     * **check for missing #[test] marks**: must check whether code changes incorrectly deleted test case marks (#[test] or #[cfg(test)]). If deleted test case marks are found, must report as a breaking change, unless:\n"
                "       - test cases moved to other locations (corresponding additions visible in diff);\n"
                "       - test cases are duplicate or outdated and indeed need deletion;\n"
                "       - test cases refactored to other test forms (such as integration tests, doc tests, etc.);\n"
                "     * **Check for duplicate #[test] marks**: Must check whether code changes incorrectly added duplicate #[test] marks, causing test functions to be defined multiple times. If duplicate test marks are found, must report as a breaking change;\n"
                "     * **check for incorrect code insertion positions**: must check whether the code insertion position causes #[test] mark loss or test function structure damage. For example:\n"
                "       - code inserted between #[test] mark and test function, causing the test mark to be invalid;\n"
                "       - code inserted at the wrong position inside a test function, causing test function structure damage;\n"
                "       - test-related code inserted outside #[cfg(test)] mod tests { ... } block, causing tests unable to run;\n"
                "     * **Check for test function structure damage**: Must check test function integrity, ensure test functions are not accidentally truncated, merged, or structure damaged;\n"
                "     * **Verify tests can still run**: If possible, check that test code syntax and structure are correct, ensuring tests can still be recognized and run by cargo test;\n"
                "   - check whether module export changes affect other module imports (such as missing pub keyword, module path changes);\n"
                "   - check whether type definition changes cause dependent code to fail (such as struct field changes, enum variant changes);\n"
                "   - check whether constant or static variable changes affect referencing code;\n"
                "   - **prioritize using diff information**: if the diff already contains caller code information, prioritize judging based on the diff; only when diff information is insufficient, then use the read_code tool to read caller code for verification;\n"
                "4. file structure reasonableness check:\n"
                "   - check whether module file location matches Rust project conventions (such as src/ directory structure, module hierarchy);\n"
                "   - check whether file naming matches Rust naming conventions (such as snake_case, module file naming);\n"
                "   - check whether module organization is reasonable (such as whether related functionality is in the same module, whether module splitting is excessive or insufficient);\n"
                "   - check whether module exports are reasonable (such as whether the pub mod declaration in lib.rs is correct, whether necessary exports are missing);\n"
                "   - check for circular dependencies or excessive coupling;\n"
                "5. test case completeness check:\n"
                "   - **check whether test cases exist**: must check whether the target function has corresponding test cases. If there are no test cases at all, must report as a functional consistency issue, because it cannot verify whether the Rust implementation is consistent with the C implementation;\n"
                "   - **Check whether test cases cover main functionality**: Test cases should cover main functionality paths and expected behavior. If test cases only cover partial functionality, or lack tests for key functionality, should report as a functional consistency issue;\n"
                "   - **check whether test cases cover edge cases**: test cases should cover edge cases, such as:\n"
                "     * Empty input (empty string, empty array, null pointer, etc.);\n"
                "     * Extreme value input (maximum value, minimum value, zero value, etc.);\n"
                "     * Boundary values (array boundaries, string length boundaries, etc.);\n"
                "     * Special values (negative numbers, NaN, infinity, etc., if applicable);\n"
                "   - **Check whether test cases cover error cases**: If the C implementation has error handling (such as returning error codes, setting errno, etc.), test cases should cover these error cases. If the Rust implementation uses Result<T, E> or Option<T> for error handling, test cases should verify error cases;\n"
                "   - **Check whether test case behavior matches the C implementation**: Test case expected results should match the C implementation behavior. If the test case expected results are inconsistent with the C implementation, should report as a functional consistency issue;\n"
                "   - **check test case quality**: Test cases should:\n"
                "     * Have clear test names that explain the test purpose;\n"
                "     * Have appropriate assertions that verify function output and behavior;\n"
                "     * Have correct test logic that can truly verify function functionality;\n"
                "   - **Note**: If the function is a resource-release type (such as fclose, free, etc.), in Rust it is managed automatically through RAII, so test cases can be very simple (such as only verifying the function can be called without crashing); this is acceptable;\n"
                "Do not check type matching, pointer mutability, boundary check details, resource release details, memory semantics and other technical details (unless they cause functional errors).\n"
                "**Important requirement: in the summary phase, for each issue found, you must provide:**\n"
                "1. Detailed issue description: clearly indicate the issue location (file, function, line number, etc.), the specific manifestation of the issue, and why this is an issue\n"
                "2. Specific fix suggestion: provide a detailed fix plan, including the code location to modify, the modification method, the expected effect, etc.\n"
                "3. **Fix code example (if applicable)**: For issues that can be clearly fixed, provide a specific fix code example, including before/after code comparison, to help the fix phase quickly locate and fix the issue\n"
                "4. Issue classification: use [function] to mark functional consistency issues (including test case completeness issues), use [critical] to mark critical issues, use [breaking] to mark breaking changes, and use [structure] to mark file structure issues\n"
                "Please detail the issues, fix suggestions and fix code examples in the summary phase, but do not attempt to fix or modify any code, and do not output patches."
            )
            # Attach original C function source snippet, for review as read-only reference
            c_code = self.read_source_span(rec) or ""
            # Attach referenced symbol context and library replacement context, and crate directory structure, to provide more complete review context
            callees_ctx = self.collect_callees_context(rec)
            librep_ctx = (
                rec.lib_replacement if isinstance(rec.lib_replacement, dict) else None
            )
            crate_tree = dir_tree(self.crate_dir)
            # Extract compile flags
            compile_flags = self.extract_compile_flags(rec.file)

            # Get changes from the initial commit to the current working area as context (must get for each review)
            # Use the unified get_git_diff method, which can get current working area changes (including uncommitted modifications)
            commit_diff = ""
            diff_status = ""  # Used to record diff fetch status
            if self.get_git_diff:
                base_commit = self.current_function_start_commit_getter()
                try:
                    commit_diff = self.get_git_diff(base_commit)
                    if commit_diff and commit_diff.strip():
                        # Successfully got diff; limit length to avoid context overflow
                        # Use a 50% ratio, because the review phase needs more context information
                        commit_diff = truncate_git_diff_with_context_limit(
                            commit_diff,
                            token_ratio=0.5,
                            base_commit=base_commit,
                            crate_dir=self.crate_dir,
                        )
                        diff_status = "success"
                    else:
                        # No changes or fetch failed
                        if base_commit:
                            current_commit = self.get_crate_commit_hash()
                            if current_commit == base_commit:
                                commit_diff = "(No changes: current commit matches function start commit, and working area has no modifications)"
                                diff_status = "no_change"
                            else:
                                commit_diff = "(Cannot get git diff)"
                                diff_status = "error"
                        else:
                            commit_diff = "(Function start commit id not recorded)"
                            diff_status = "no_start_commit"
                except Exception as e:
                    commit_diff = f"Exception occurred while getting git diff: {str(e)}"
                    diff_status = "error"
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-transpiler][review] Failed to get git diff: {e}",
                    )
            else:
                # get_git_diff function not provided
                commit_diff = "(Git diff fetch function not provided)"
                diff_status = "no_git_diff_func"

            # Get build fix phase summary information
            build_fixes_summary = ""
            try:
                cur = self.progress.get("current") or {}
                build_fixes = cur.get("build_fixes", [])
                if build_fixes:
                    build_fixes_summary = "\n\n[Build fix phase summary]\n"
                    build_fixes_summary += (
                        "Below is the fix process and results summary from the build fix phase, for review reference:\n\n"
                    )
                    for i, fix_info in enumerate(build_fixes, 1):
                        fix_iter = fix_info.get("iteration", "?")
                        fix_stage = fix_info.get("stage", "unknown")
                        fix_tags = fix_info.get("tags", [])
                        fix_summary = fix_info.get("summary", "")
                        is_retry = fix_info.get("retry", False)
                        retry_marker = "(retry)" if is_retry else ""
                        build_fixes_summary += f"fix #{i} (iteration {fix_iter}, stage: {fix_stage}){retry_marker}:\n"
                        if fix_tags:
                            build_fixes_summary += (
                                f"  error classification: {', '.join(fix_tags)}\n"
                            )
                        if fix_summary:
                            build_fixes_summary += f"  fix summary:\n{fix_summary}\n"
                        build_fixes_summary += "\n"
                    build_fixes_summary += "Hint: please refer to the above fix summary to understand the issues encountered and the fix process during the build fix phase; this helps review the code more accurately."
            except Exception as e:
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][review] Failed to get build fix summary: {e}",
                )

            usr_p_lines = [
                f"Function to review: {rec.qname or rec.name}",
                f"Suggested signature: {rust_sig}",
                f"Target module: {module}",
                f"**Crate root (important)**: {self.crate_dir.resolve()}",
                "  - All Rust source files are under this directory",
                "  - When using the read_code tool to read files, please use a path relative to this directory (such as `src/xxx.rs`) or an absolute path",
                "  - When using the edit_file_* tool to edit files, the file path should also be relative to this directory or an absolute path",
                f"Source file location: {rec.file}:{rec.start_line}-{rec.end_line}",
                "",
                "Original C function source snippet (read-only reference, do not modify C code):",
                "<C_SOURCE>",
                c_code,
                "</C_SOURCE>",
                "",
            ]
            # If build fix summary exists, add to prompt
            if build_fixes_summary:
                usr_p_lines.append(build_fixes_summary)
                usr_p_lines.append("")

            usr_p_lines.extend(
                [
                    "Review instructions (combined review):",
                    "**Review priority**: test breaking change check > critical issues > breaking changes > functional consistency > file structure. Prioritize checking whether tests are broken (missing/duplicate #[test] markers, incorrect code insertion positions, etc.), then handle issues that may cause crashes or compilation failures.",
                    "",
                    "1. Functional consistency:",
                    "   - **Core functionality definition**: core input/output, whether the main functional logic is consistent with the C implementation. Core functionality refers to the main purpose and expected behavior of the function (such as 'calculate hash value', 'parse string', 'compress data', etc.) and does not include implementation details;",
                    "   - **Security improvements allow behavioral inconsistency**: Allow the Rust implementation to fix security vulnerabilities in the C code (such as buffer overflow, null pointer dereference, uninitialized memory usage, integer overflow, format string vulnerability, etc.); these security improvements may cause behavior inconsistent with the C implementation, but this is allowed and should not be considered functional inconsistency;",
                    "   - **Ignore behavioral inconsistency caused by language differences**: Due to essential differences between the Rust and C languages, the following behavioral differences are unavoidable and should be ignored:",
                    "     * Integer overflow handling: Rust panics in debug mode and wraps in release mode, while C has undefined behavior;",
                    "     * Undefined behavior: Rust avoids or explicitly handles it, while C may produce undefined behavior;",
                    "     * Null pointer/null reference: Rust uses Option<T> or Result<T, E>, while C may directly dereference causing a crash;",
                    "     * Memory safety: Rust's borrow checker prevents certain unsafe operations allowed in C;",
                    "     * Error handling: Rust uses Result<T, E> or Option<T>, while C may use error codes or the global errno;",
                    "   - Allow the Rust implementation to use a different type design, error handling approach, resource management approach, etc., as long as the functionality is consistent;",
                    "2. Critical issues (may cause functional errors):",
                    "   - obvious null pointer dereference or serious errors causing a panic;",
                    "   - obvious out-of-bounds access or issues causing a program crash;",
                    "3. Breaking change detection (impact on existing code):",
                    "   - **allow signature inconsistency**: Allow the function signature, parameter count, parameter type, return type, etc. to be inconsistent with the C implementation, as long as the functionality is implemented. This is normal for Rust transpilation, because Rust's type system and design philosophy differ from C;",
                    "   - **only check actual breaking impact**: Only report as a breaking change when a function signature change actually causes caller code to fail compilation or at runtime. If the caller code has adapted to the new signature, or can be resolved through simple adaptation, it should not be considered a breaking change;",
                    "   - **⚠️⚠️ focus: test breaking change check**: Must focus on checking whether code changes break current tests; this is the highest priority check item. Specifically includes:",
                    "     * **check for missing #[test] marks**: must check whether code changes incorrectly deleted test case marks (#[test] or #[cfg(test)]). If deleted test case marks are found, must report as a breaking change, unless:",
                    "       - test cases moved to other locations (corresponding additions visible in diff);",
                    "       - test cases are duplicate or outdated and indeed need deletion;",
                    "       - test cases refactored to other test forms (such as integration tests, doc tests, etc.);",
                    "     * **Check for duplicate #[test] marks**: Must check whether code changes incorrectly added duplicate #[test] marks, causing test functions to be defined multiple times. If duplicate test marks are found, must report as a breaking change;",
                    "     * **check for incorrect code insertion positions**: must check whether the code insertion position causes #[test] mark loss or test function structure damage. For example:",
                    "       - code inserted between #[test] mark and test function, causing the test mark to be invalid;",
                    "       - code inserted at the wrong position inside a test function, causing test function structure damage;",
                    "       - test-related code inserted outside #[cfg(test)] mod tests { ... } block, causing tests unable to run;",
                    "     * **Check for test function structure damage**: Must check test function integrity, ensure test functions are not accidentally truncated, merged, or structure damaged;",
                    "     * **Verify tests can still run**: If possible, check that test code syntax and structure are correct, ensuring tests can still be recognized and run by cargo test;",
                    "   - check whether module export changes affect other module imports (such as missing pub keyword, module path changes);",
                    "   - check whether type definition changes cause dependent code to fail (such as struct field changes, enum variant changes);",
                    "   - check whether constant or static variable changes affect referencing code;",
                    "   - **prioritize using diff information**: if the diff already contains caller code information, prioritize judging based on the diff; only when diff information is insufficient, then use the read_code tool to read caller code for verification;",
                    "   - if the function is a root symbol or is called by other transpiled functions, check whether the caller code can still compile and work normally; if the caller has adapted to the new signature, then it should not be considered a breaking change;",
                    "4. file structure reasonableness check:",
                    "   - check whether module file location matches Rust project conventions (such as src/ directory structure, module hierarchy);",
                    "   - check whether file naming matches Rust naming conventions (such as snake_case, module file naming);",
                    "   - check whether module organization is reasonable (such as whether related functionality is in the same module, whether module splitting is excessive or insufficient);",
                    "   - check whether module exports are reasonable (such as whether the pub mod declaration in lib.rs is correct, whether necessary exports are missing);",
                    "   - check for circular dependencies or excessive coupling;",
                    "   - check whether file size is reasonable (such as whether a single file is too large and needs splitting, or whether over-splitting causes too many files);",
                    "5. test case completeness check:",
                    "   - **check whether test cases exist**: must check whether the target function has corresponding test cases. If there are no test cases at all, must report as a functional consistency issue, because it cannot verify whether the Rust implementation is consistent with the C implementation;",
                    "   - **Check whether test cases cover main functionality**: Test cases should cover main functionality paths and expected behavior. If test cases only cover partial functionality, or lack tests for key functionality, should report as a functional consistency issue;",
                    "   - **Check whether test cases cover edge cases**: Test cases should cover edge cases, such as empty input (empty string, empty array, null pointer, etc.), extreme value input (max, min, zero, etc.), boundary values (array boundaries, string length boundaries, etc.), special values (negative numbers, NaN, infinity, etc., if applicable);",
                    "   - **Check whether test cases cover error cases**: If the C implementation has error handling (such as returning error codes, setting errno, etc.), test cases should cover these error cases. If the Rust implementation uses Result<T, E> or Option<T> for error handling, test cases should verify error cases;",
                    "   - **Check whether test case behavior matches the C implementation**: Test case expected results should match the C implementation behavior. If the test case expected results are inconsistent with the C implementation, should report as a functional consistency issue;",
                    "   - **Check test case quality**: Test cases should have clear test names, appropriate assertions, and correct test logic, able to truly verify function functionality;",
                    "   - **Note**: If the function is a resource-release type (such as fclose, free, etc.), in Rust it is managed automatically through RAII, so test cases can be very simple (such as only verifying the function can be called without crashing); this is acceptable;",
                    "do not check type matching, pointer mutability, boundary check details and other technical details (unless they cause functional errors).",
                    "",
                    "**Important: Issue reporting requirements**",
                    "For each issue found, must provide in summary:",
                    "1. Detailed issue description: clearly indicate issue location (file, function, line number etc), specific manifestation of issue, why this is an issue",
                    "2. Specific fix suggestion: provide detailed fix plan, including code location to modify, modification method, expected effect etc",
                    "3. **Fix code example (if applicable)**: For issues that can be clearly fixed, must provide specific fix code example, including before/after code comparison. Format requirements:",
                    "   - Before: show problematic code snippet (including sufficient context, such as function signature, surrounding lines)",
                    "   - After: show fixed code snippet",
                    "   - use code block format (```rust ... ```) to display code",
                    "   - if issue involves multiple locations, provide fix code examples for all related locations",
                    "4. Issue classification: use [function] for functional consistency issues, [critical] for critical issues, [breaking] for breaking changes, [structure] for file structure issues",
                    "Example (must include fix code example):",
                    '  "[function] Return value handling missing: at line 42 of function foo, when the input parameter is negative, the function does not return an error code, but the C implementation returns -1. Fix suggestion: add parameter validation at the function start, return Result::Err(Error::InvalidInput) when the parameter is negative. Fix code example:\n'
                    "    Before:\n"
                    "    ```rust\n"
                    "    pub fn foo(x: i32) -> i32 {\n"
                    "        // missing parameter validation\n"
                    "        x * 2\n"
                    "    }\n"
                    "    ```\n"
                    "    After:\n"
                    "    ```rust\n"
                    "    pub fn foo(x: i32) -> Result<i32, Error> {\n"
                    "        if x < 0 {\n"
                    "            return Err(Error::InvalidInput);\n"
                    "        }\n"
                    "        Ok(x * 2)\n"
                    "    }\n"
                    '    ```"',
                    '  "[critical] Null pointer dereference risk: at line 58 of function bar, directly dereferences pointer ptr without checking if null, may cause panic. Fix suggestion: use if let Some(value) = ptr.as_ref() for null check, or use Option<&T> type. Fix code example:\n'
                    "    Before:\n"
                    "    ```rust\n"
                    "    pub fn bar(ptr: *const i32) -> i32 {\n"
                    "        unsafe { *ptr }\n"
                    "    }\n"
                    "    ```\n"
                    "    After:\n"
                    "    ```rust\n"
                    "    pub fn bar(ptr: Option<&i32>) -> Option<i32> {\n"
                    "        ptr.map(|p| *p)\n"
                    "    }\n"
                    '    ```"',
                    '  "[breaking] Test function duplicate definition: at line 111-112 in src/common/buffer.rs, new test function test_write_buf_1_byte was marked with #[test] twice, causing duplicate definition. Fix suggestion: delete one of the #[test] marks, ensure each test function has only one #[test] attribute. Fix code example:\n'
                    "    Before:\n"
                    "    ```rust\n"
                    "    #[test]\n"
                    "    #[test]  // duplicate mark\n"
                    "    fn test_write_buf_1_byte() {\n"
                    "        // ...\n"
                    "    }\n"
                    "    ```\n"
                    "    After:\n"
                    "    ```rust\n"
                    "    #[test]\n"
                    "    fn test_write_buf_1_byte() {\n"
                    "        // ...\n"
                    "    }\n"
                    '    ```"',
                    '  "[function] Test case missing: function foo has no corresponding test case, cannot verify if Rust implementation is consistent with C implementation. Fix suggestion: add test cases in target module\'s #[cfg(test)] mod tests { ... } block, covering main functionality, edge cases and error cases. Fix code example:\n'
                    "    Before (src/foo.rs):\n"
                    "    ```rust\n"
                    "    pub fn foo(x: i32) -> i32 {\n"
                    "        x * 2\n"
                    "    }\n"
                    "    // missing test case\n"
                    "    ```\n"
                    "    After (src/foo.rs):\n"
                    "    ```rust\n"
                    "    pub fn foo(x: i32) -> i32 {\n"
                    "        x * 2\n"
                    "    }\n"
                    "    \n"
                    "    #[cfg(test)]\n"
                    "    mod tests {\n"
                    "        use super::*;\n"
                    "        \n"
                    "        #[test]\n"
                    "        fn test_foo_normal() {\n"
                    "            assert_eq!(foo(5), 10);\n"
                    "        }\n"
                    "        \n"
                    "        #[test]\n"
                    "        fn test_foo_zero() {\n"
                    "            assert_eq!(foo(0), 0);\n"
                    "        }\n"
                    "    }\n"
                    '    ```"',
                    '  "[structure] Module export missing: module utils containing function qux is not exported in src/lib.rs, causing inability to access from outside crate. Fix suggestion: add `pub mod utils;` declaration in src/lib.rs. Fix code example:\n'
                    "    Before (src/lib.rs):\n"
                    "    ```rust\n"
                    "    // missing pub mod utils;\n"
                    "    ```\n"
                    "    After (src/lib.rs):\n"
                    "    ```rust\n"
                    "    pub mod utils;\n"
                    '    ```"',
                    "",
                    "Referenced symbol context (includes Rust module info if already transpiled):",
                    json.dumps(callees_ctx, ensure_ascii=False, indent=2),
                    "",
                    "Library replacement context (if exists):",
                    json.dumps(librep_ctx, ensure_ascii=False, indent=2),
                    "",
                ]
            )
            # Add disabled library list (if exists)
            if self.disabled_libraries:
                usr_p_lines.append(
                    f"Disabled library list (prohibited from using these libraries in implementation): {', '.join(self.disabled_libraries)}"
                )
            # Add root symbol requirement (if root symbol)
            if self.is_root_symbol(rec):
                usr_p_lines.append(
                    f"Root symbol requirement: this function is a root symbol ({rec.qname or rec.name}); it must use the `pub` keyword for public exposure to ensure access from outside the crate. Also, the module containing this function must be exported in src/lib.rs (using `pub mod <module_name>;`)."
                )
            # Add compile flags (if exists)
            if compile_flags:
                usr_p_lines.extend(
                    [
                        "",
                        "C file compile flags (from compile_commands.json):",
                        compile_flags,
                    ]
                )
            usr_p_lines.extend(
                [
                    "",
                    "Current crate directory structure (partial):",
                    "<CRATE_TREE>",
                    crate_tree,
                    "</CRATE_TREE>",
                ]
            )

            # Add git change context (must include for each review)
            usr_p_lines.extend(
                [
                    "",
                    "Git changes from function start to current (for understanding code change history and context, including uncommitted modifications):",
                    "<GIT_DIFF>",
                    commit_diff,
                    "</GIT_DIFF>",
                    "",
                ]
            )

            # Add different notes based on diff status
            if diff_status == "success":
                usr_p_lines.extend(
                    [
                        "**Important: Git change context notes**",
                        "- Above diff shows all changes from function start commit to current working area (including committed and uncommitted modifications)",
                        "- These changes may include: current function implementation, dependency function implementation, module structure adjustments etc",
                        "- **Prioritize using diff information for review judgment**: If diff already contains sufficient information (such as function implementation, signature changes, module structure etc), can directly review based on diff without reading original files",
                        "- Only when diff information is insufficient or need to view complete context, use read_code tool to read original files",
                        "- When reviewing breaking changes, please pay special attention to impact on existing code",
                        "- If issues found in changes (such as breaking changes, unreasonable file structure etc), please point out in review report",
                    ]
                )
            elif diff_status == "no_change":
                usr_p_lines.extend(
                    [
                        "**Note**: Current commit matches function start commit, and working area has no modifications, indicating no code changes. Please use read_code tool to read latest content of target module file for review.",
                    ]
                )
            else:
                # diff_status is "error", "no_current_commit", "no_start_commit", or "no_git_diff_func"
                usr_p_lines.extend(
                    [
                        "**Note**: Since cannot get git diff information, please use read_code tool to read latest content of target module file for review.",
                    ]
                )

            usr_p_lines.extend(
                [
                    "",
                    "To locate or cross-validate C symbol positions, please use symbol table search tool:",
                    "- Tool: read_symbols",
                    "- Parameter example (JSON):",
                    f'  {{"symbols_file": "{(self.data_dir / "symbols.jsonl").resolve()}", "symbols": ["{rec.qname or rec.name}"]}}',
                    "",
                    "**Code reading tool usage instructions**:",
                    "- Tool: read_code",
                    "- Purpose: Read C source implementation or Rust module file",
                    "- **Important**: When reading Rust source files, must use absolute path or path relative to crate root",
                    f"- **Crate root**: {self.crate_dir.resolve()}",
                    "  - Example:",
                    f"    * Read Rust file: `read_code` tool, file path using `{self.crate_dir.resolve()}/src/xxx.rs` or `src/xxx.rs` (relative to crate root)",
                    "    * Read C file: `read_code` tool, file path using full path of C source file",
                    "",
                    "**Important: Review requirements**",
                    "- **Prioritize using diff information**: If git diff provided (GIT_DIFF), prioritize reviewing based on diff information, only use read_code tool to read original files when diff information is insufficient",
                    "- Must review based on latest code, if using read_code tool, please read latest content of target module file",
                    f"- **When using read_code tool, file path should be relative to crate root ({self.crate_dir.resolve()}) or use an absolute path**",
                    "- Prohibited from relying on any historical memory, previous review conclusions or conversation history for judgment",
                    "- Each review must be based on latest code state (obtained via diff or read_code), ensuring review results reflect true state of current code",
                    "- Combine git change context (if provided), comprehensively evaluate impact and reasonableness of code changes",
                    "",
                    "Please review based on provided diff information (if available) or read current implementation of function in crate, and prepare summary.",
                ]
            )
            usr_p = "\n".join(usr_p_lines)
            sum_p = (
                "Please output only one <SUMMARY> block, block directly contains JSON object (no extra tags needed), fields:\n"
                '"ok": bool  // true if functionally consistent with no critical issues, no breaking changes, reasonable file structure\n'
                '"function_issues": [string, ...]  // functional consistency issues, each starting with [function], must include detailed issue description and fix suggestion\n'
                '"critical_issues": [string, ...]  // critical issues (may cause functional errors), each starting with [critical], must include detailed issue description and fix suggestion\n'
                '"breaking_issues": [string, ...]  // breaking change issues (impact on existing code), each starting with [breaking], must include detailed issue description and fix suggestion\n'
                '"structure_issues": [string, ...]  // file structure issues, each starting with [structure], must include detailed issue description and fix suggestion\n'
                "Note: \n"
                "- Precondition: Must find function implementation in crate (matching function name or signature). If not found, ok must be false, function_issues should include [function] function not found: detail issue location and how to find function implementation\n"
                "- **Security improvements allow behavioral inconsistency**: If Rust implementation fixes security vulnerabilities in C code (such as buffer overflow, null pointer dereference, uninitialized memory usage etc), even if causing behavior inconsistent with C implementation, this is allowed and should not be considered functional inconsistency;\n"
                "- **Ignore behavioral inconsistency caused by language differences**: Due to essential differences between Rust and C languages (such as memory safety, type system, error handling, undefined behavior handling etc), certain behavioral differences are unavoidable, these differences should be ignored and not considered functional inconsistency;\n"
                "- **allow signature inconsistency**: Allow function signature, parameter count, parameter type, return type etc to be inconsistent with C implementation, as long as functionality is implemented. This is normal for Rust transpilation and should not be considered breaking change;\n"
                "- **Breaking change criteria**: Only report as breaking change when function signature change actually causes caller code to fail compilation or runtime. If caller code has adapted to new signature, or can be resolved through simple adaptation, should not be considered breaking change;\n"
                "- **⚠️⚠️ focus: test breaking change check**: Must focus on checking if code changes break current tests, this is the highest priority check item. Specifically includes:\n"
                "  1. **Check for missing #[test] marks**: Must check if code changes incorrectly deleted test case marks (#[test] or #[cfg(test)]). If deleted test case marks found without reasonable justification (such as moved to other locations, duplicate tests etc), must report as breaking change;\n"
                "  2. **Check for duplicate #[test] marks**: Must check if code changes incorrectly added duplicate #[test] marks, causing test functions to be defined multiple times. If duplicate test marks found, must report as breaking change;\n"
                "  3. **Check for incorrect code insertion positions**: Must check if code insertion position causes #[test] mark loss or test function structure damage. For example: code inserted between #[test] mark and test function, code inserted at wrong position inside test function, test-related code inserted outside #[cfg(test)] mod tests { ... } block etc;\n"
                "  4. **Check for test function structure damage**: Must check test function integrity, ensure test functions are not accidentally truncated, merged or structure damaged;\n"
                "  5. **Verify tests can still run**: If possible, check test code syntax and structure are correct, ensure tests can still be recognized and run by cargo test;\n"
                "- **⚠️⚠️ focus: test case completeness check**: Must check if test cases are complete, this is the second priority check item. Specifically includes:\n"
                "  1. **Check if test cases exist**: Must check if target function has corresponding test cases. If no test cases at all, must report as functional consistency issue ([function]), because cannot verify if Rust implementation is consistent with C implementation;\n"
                "  2. **Check if test cases cover main functionality**: Test cases should cover main functionality paths and expected behavior. If test cases only cover partial functionality, or lack tests for key functionality, should report as functional consistency issue;\n"
                "  3. **Check if test cases cover edge cases**: Test cases should cover edge cases, such as empty input (empty string, empty array, null pointer etc), extreme value input (max, min, zero etc), boundary values (array boundaries, string length boundaries etc), special values (negative numbers, NaN, infinity etc, if applicable);\n"
                "  4. **Check if test cases cover error cases**: If C implementation has error handling (such as returning error codes, setting errno etc), test cases should cover these error cases. If Rust implementation uses Result<T, E> or Option<T> for error handling, test cases should verify error cases;\n"
                "  5. **Check if test cases behavior matches C implementation**: Test case expected results should match C implementation behavior. If test case expected results inconsistent with C implementation, should report as functional consistency issue;\n"
                "  6. **Check test case quality**: Test cases should have clear test names, appropriate assertions, correct test logic, able to truly verify function functionality;\n"
                "  7. **Note**: If function is resource release type (Such as fclose, free etc), In Rust managed automatically through RAII, Test cases can be very simple (Such as only verifying function can be called without crashing), This is acceptable; \n"
                "- If Rust implementation uses different implementation approach but maintains functional consistency, with no critical issues, no breaking changes, reasonable file structure, ok should be true\n"
                "- Only report functional inconsistency, critical issues, breaking changes and file structure issues, do not report type matching, pointer mutability, boundary check details and other technical details (unless they cause functional errors)\n"
                "- **Important: Each issue description must include:**\n"
                "  1. Detailed issue description: clearly indicate issue location (file, function, line number etc), specific manifestation of issue, why this is an issue\n"
                "  2. Fix suggestion: provide specific fix plan, including code location to modify, modification method, expected effect etc\n"
                "  3. **Fix code example (If applicable)**: For issues that can be clearly fixed, provide specific fix code example, including before/after code comparison. Format:\n"
                "     - Before: show problematic code snippet (including sufficient context, such as function signature, surrounding lines)\n"
                "     - After: show fixed code snippet\n"
                "     - if issue involves multiple locations, provide fix code examples for all related locations\n"
                "  4. Issue format: starting with [function], [critical], [breaking] or [structure], followed by detailed issue description, fix suggestion and fix code example\n"
                "  Example format:\n"
                '    "[function] Return value handling missing: At line 42 of function foo, when input parameter is negative, function does not return error code, but C implementation returns -1. Fix suggestion: add parameter validation at function start, return Result::Err(Error::InvalidInput) when parameter is negative. Fix code example: \n'
                "    Before:\n"
                "    ```rust\n"
                "    pub fn foo(x: i32) -> i32 {\n"
                "        // missing parameter validation\n"
                "        x * 2\n"
                "    }\n"
                "    ```\n"
                "    After:\n"
                "    ```rust\n"
                "    pub fn foo(x: i32) -> Result<i32, Error> {\n"
                "        if x < 0 {\n"
                "            return Err(Error::InvalidInput);\n"
                "        }\n"
                "        Ok(x * 2)\n"
                "    }\n"
                '    ```"\n'
                '    "[critical] Null pointer dereference risk: at line 58 of function bar, directly dereferences pointer ptr without checking if null, may cause panic. Fix suggestion: use if let Some(value) = ptr.as_ref() for null check, or use Option<&T> type. Fix code example:\n'
                "    Before:\n"
                "    ```rust\n"
                "    pub fn bar(ptr: *const i32) -> i32 {\n"
                "        unsafe { *ptr }\n"
                "    }\n"
                "    ```\n"
                "    After:\n"
                "    ```rust\n"
                "    pub fn bar(ptr: Option<&i32>) -> Option<i32> {\n"
                "        ptr.map(|p| *p)\n"
                "    }\n"
                '    ```"\n'
                '    "[breaking] Test function duplicate definition: at line 111-112 in src/common/buffer.rs, new test function test_write_buf_1_byte was marked with #[test] twice, causing duplicate definition. Fix suggestion: delete one of the #[test] marks, ensure each test function has only one #[test] attribute. Fix code example:\n'
                "    Before:\n"
                "    ```rust\n"
                "    #[test]\n"
                "    #[test]  // duplicate mark\n"
                "    fn test_write_buf_1_byte() {\n"
                "        // ...\n"
                "    }\n"
                "    ```\n"
                "    After:\n"
                "    ```rust\n"
                "    #[test]\n"
                "    fn test_write_buf_1_byte() {\n"
                "        // ...\n"
                "    }\n"
                '    ```"\n'
                '    "[structure] Module export missing: module utils containing function qux is not exported in src/lib.rs, causing inability to access from outside crate. Fix suggestion: add `pub mod utils;` declaration in src/lib.rs. Fix code example:\n'
                "    Before (src/lib.rs):\n"
                "    ```rust\n"
                "    // missing pub mod utils;\n"
                "    ```\n"
                "    After (src/lib.rs):\n"
                "    ```rust\n"
                "    pub mod utils;\n"
                '    ```"\n'
                "Please strictly output in the following format (JSON format; jsonnet syntax such as trailing commas and comments is supported): \n"
                "**Example1: Review passed (no issues)**\n"
                '<SUMMARY>\n{\n  "ok": true,\n  "function_issues": [],\n  "critical_issues": [],\n  "breaking_issues": [],\n  "structure_issues": []\n}\n</SUMMARY>\n'
                "**Example2: Issues found (must report issues)**\n"
                '<SUMMARY>\n{\n  "ok": false,\n  "function_issues": [],\n  "critical_issues": [],\n  "breaking_issues": [\n    "[breaking] Test function duplicate definition: At line 111-112 in src/common/buffer.rs, new test function test_write_buf_1_byte was marked with #[test] twice, causing duplicate definition. Fix suggestion: delete one of the #[test] marks, ensure each test function has only one #[test] attribute. "\n  ],\n  "structure_issues": []\n}\n</SUMMARY>\n'
                "**important**: If issues are found, ok must be false, and the issues must be reported in the corresponding issue arrays. Do not set ok to true just because the issues are minor. "
            )
            # Append additional notes to usr_p and sum_p (usually not needed for sys_p)
            usr_p = self.append_additional_notes(usr_p)
            sum_p = self.append_additional_notes(sum_p)
            return sys_p, usr_p, sum_p

        i = 0
        max_iterations = self.review_max_iterations
        # Note: the Agent must be created in the crate root directory to ensure tools (such as read_symbols) can correctly obtain the symbol table
        # Since transpile() has already switched to the crate directory at the start, no need to switch again here

        # Get function info for the Agent name
        fn_name = rec.qname or rec.name or f"fn_{rec.id}"
        agent_name = f"C2Rust-Review-Agent({fn_name})"

        # 0 means unlimited retries, otherwise limit the number of iterations
        use_direct_model_review = False  # Whether to use direct model invocation
        parse_failed = False  # Whether the previous parse failed
        parse_error_msg: Optional[str] = None  # Stores the previous YAML parse error message
        previous_issues: Dict[
            str, List[str]
        ] = {}  # Stores the issues found in the previous review, used to verify whether they have been fixed
        while max_iterations == 0 or i < max_iterations:
            # Create a new Agent for each iteration to avoid interference from historical memory
            # But include previous_issues in the hint
            sys_p_init, _, sum_p_init = build_review_prompts()
            review_agent = create_agent(
                system_prompt=sys_p_init,
                name=agent_name,
                summary_prompt=sum_p_init,
                need_summary=True,
                auto_complete=True,
                use_tools=["execute_script", "read_code", "read_symbols"],
                non_interactive=self.non_interactive,
                use_methodology=False,
                use_analysis=False,
                model_type="smart",
                quick_mode=True,
            )
            # Subscribe to BEFORE_TOOL_CALL and AFTER_TOOL_CALL events for fine-grained detection of test code deletion
            review_agent.event_bus.subscribe(BEFORE_TOOL_CALL, self.on_before_tool_call)
            review_agent.event_bus.subscribe(AFTER_TOOL_CALL, self.on_after_tool_call)
            # Record the commit id when the Agent was created (as the initial value)
            agent_id = id(review_agent)
            agent_key = f"agent_{agent_id}"
            initial_commit = self.get_crate_commit_hash()
            if initial_commit:
                self.agent_before_commits[agent_key] = initial_commit

            agent = review_agent
            # Since transpile() has already switched to the crate directory at the start, no need to switch again here

            # Re-fetch the latest diff for each iteration (from the saved commit to the current HEAD)
            # Rebuild the user prompt to include the latest diff
            _, usr_p_current, _ = build_review_prompts()  # Rebuild to obtain the latest diff

            if i > 0:
                # Review after fix: add the hint that the code has been updated and the verification requirement for previous issues
                previous_issues_text = ""
                if previous_issues:
                    previous_issues_lines = []
                    if previous_issues.get("function_issues"):
                        previous_issues_lines.append("Functional consistency issues: ")
                        previous_issues_lines.extend(
                            [
                                f"  - {issue}"
                                for issue in previous_issues["function_issues"]
                            ]
                        )
                    if previous_issues.get("critical_issues"):
                        previous_issues_lines.append("Critical issues: ")
                        previous_issues_lines.extend(
                            [
                                f"  - {issue}"
                                for issue in previous_issues["critical_issues"]
                            ]
                        )
                    if previous_issues.get("breaking_issues"):
                        previous_issues_lines.append("Breaking changes issues: ")
                        previous_issues_lines.extend(
                            [
                                f"  - {issue}"
                                for issue in previous_issues["breaking_issues"]
                            ]
                        )
                    if previous_issues.get("structure_issues"):
                        previous_issues_lines.append("File structure issues: ")
                        previous_issues_lines.extend(
                            [
                                f"  - {issue}"
                                for issue in previous_issues["structure_issues"]
                            ]
                        )
                    if previous_issues_lines:
                        previous_issues_text = "\n".join(
                            [
                                "",
                                " [important: verify whether the previously found issues have been fixed]",
                                f"In the {i}-th review, the following issues were found: ",
                                "<PREVIOUS_ISSUES>",
                                "\n".join(previous_issues_lines),
                                "</PREVIOUS_ISSUES>",
                                "",
                                "**Must verify:**",
                                "- Carefully check whether each of the above issues has already been resolved in the code fix",
                                "- If an issue still exists, it must be reported again as an issue of the corresponding type",
                                "- If an issue has already been fixed, it should not be reported again",
                                "- **You must use the read_code tool or git diff to verify whether an issue has been fixed; do not rely on assumptions alone**",
                                "",
                            ]
                        )

                code_changed_notice = "\n".join(
                    [
                        "",
                        " [important: the code has been updated]",
                        f"Before this review (iteration {i}), the code has been fixed and optimized according to the review comments. ",
                        "The implementation of the target function has changed, including but not limited to: ",
                        "- Modifications to the function implementation logic",
                        "- Adjustments to types and signatures",
                        "- Updates to dependencies",
                        "- Improvements to error handling",
                        "",
                        "**Review requirements:**",
                        "- **prioritize using diff information**: If the latest git diff is provided (GIT_DIFF), prioritize reviewing based on the diff; only use the read_code tool to read the original file when the diff information is insufficient",
                        "- If you must use the read_code tool, please read the latest content of the target module file",
                        "- **Do not make judgments based on previous review results, conversation history, or any cached information**",
                        "- You must review and evaluate based on the latest code state (obtained via diff or read_code)",
                        "",
                        "If the diff information is sufficient, you can review directly based on the diff; if the diff information is insufficient, please use the read_code tool to read the latest code. ",
                        "",
                    ]
                )
                usr_p_with_notice = (
                    usr_p_current + previous_issues_text + code_changed_notice
                )
                composed_prompt = self.compose_prompt_with_context(
                    usr_p_with_notice, False
                )
                # After a fix, Agent.run() must be used; direct model invocation is not allowed (because tool calls are needed)
                use_direct_model_review = False
            else:
                composed_prompt = self.compose_prompt_with_context(usr_p_current, False)

            if use_direct_model_review:
                # After a format parse failure, invoke the model interface directly
                # Build the full hint including the summary hint and the specific error message
                error_guidance = ""
                # Check the previous parse result
                if parse_error_msg:
                    # If there is a JSON parse error, report it first
                    error_guidance = (
                        f"\n\n**Format error details (please fix the output format based on the following errors): **\n"
                        f"- JSON parse failed: {parse_error_msg}\n\n"
                        f"Please ensure the output JSON format is correct, including correct quotes, commas, braces, etc. The JSON object must contain the fields: ok (boolean), function_issues (array of strings), critical_issues (array of strings), breaking_issues (array of strings), structure_issues (array of strings). jsonnet syntax is supported (such as trailing commas and comments). "
                    )
                elif parse_failed:
                    error_guidance = (
                        "\n\n**Format error details (please fix the output format based on the following errors): **\n"
                        "- Unable to parse a valid JSON object from the summary\n\n"
                        "Please ensure the output format is correct: output only one <SUMMARY> block, and the block directly contains the JSON object (no extra tags are needed). Fields: ok (boolean), function_issues (array of strings), critical_issues (array of strings), breaking_issues (array of strings), structure_issues (array of strings). jsonnet syntax is supported (such as trailing commas and comments). "
                    )

                full_prompt = f"{composed_prompt}{error_guidance}\n\n{sum_p_init}"
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][review] Invoking the model interface directly to fix the format error (retry {i + 1})",
                )
                try:
                    # Try to use the model attribute directly (if it exists) to improve efficiency
                    if hasattr(agent, "model"):
                        response = agent.model.chat_until_success(full_prompt)  # ty: ignore[unresolved-attribute]
                        summary = str(response or "")
                    else:
                        # Fall back to the run() method
                        summary = str(agent.run(full_prompt) or "")
                except Exception as e:
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-transpiler][review] Direct model invocation failed: {e}, falling back to run()",
                    )
                    summary = str(agent.run(composed_prompt) or "")
            else:
                # First use run() to let the Agent run fully (may use tools)
                summary = str(agent.run(composed_prompt) or "")

            # Parse the JSON-format review result
            verdict, parse_error_review = extract_json_from_summary(summary)
            parse_failed = False
            parse_error_msg = None
            if parse_error_review:
                # JSON parse failed
                parse_failed = True
                parse_error_msg = parse_error_review
                PrettyOutput.auto_print(
                    f"[c2rust-transpiler][review] JSON parse failed: {parse_error_review}",
                )
                # Backward compatibility with the old format: try to parse plain text OK
                m = re.search(
                    r"<SUMMARY>([\s\S]*?)</SUMMARY>", summary, flags=re.IGNORECASE
                )
                content = (m.group(1).strip() if m else summary.strip()).upper()
                if content == "OK":
                    verdict = {
                        "ok": True,
                        "function_issues": [],
                        "critical_issues": [],
                        "breaking_issues": [],
                        "structure_issues": [],
                    }
                    parse_failed = False  # Compatibility format succeeded, not counted as a parse failure
                    parse_error_msg = None
                else:
                    # Unable to parse, retry immediately: set the flag and continue the loop
                    use_direct_model_review = True
                    parse_error_msg = f"Unable to parse a valid JSON object from the summary; the obtained content type is: {type(verdict).__name__}"
                    # Continue the loop and retry immediately
                    continue

            ok = bool(verdict.get("ok") is True)
            raw_function_issues = verdict.get("function_issues")
            function_issues: list[str] = (
                [str(item) for item in raw_function_issues]
                if isinstance(raw_function_issues, list)
                else []
            )
            raw_critical_issues = verdict.get("critical_issues")
            critical_issues: list[str] = (
                [str(item) for item in raw_critical_issues]
                if isinstance(raw_critical_issues, list)
                else []
            )
            raw_breaking_issues = verdict.get("breaking_issues")
            breaking_issues: list[str] = (
                [str(item) for item in raw_breaking_issues]
                if isinstance(raw_breaking_issues, list)
                else []
            )
            raw_structure_issues = verdict.get("structure_issues")
            structure_issues: list[str] = (
                [str(item) for item in raw_structure_issues]
                if isinstance(raw_structure_issues, list)
                else []
            )

            PrettyOutput.auto_print(
                f"📊 [c2rust-transpiler][review][iter={i + 1}] verdict ok={ok}, function_issues={len(function_issues)}, critical_issues={len(critical_issues)}, breaking_issues={len(breaking_issues)}, structure_issues={len(structure_issues)}",
            )

            # Save the issues found in this review for verification in the next review (only save when issues are found)
            if (
                not ok
                or function_issues
                or critical_issues
                or breaking_issues
                or structure_issues
            ):
                previous_issues = {
                    "function_issues": list(function_issues),
                    "critical_issues": list(critical_issues),
                    "breaking_issues": list(breaking_issues),
                    "structure_issues": list(structure_issues),
                }

            # If ok is true, the review passed (functionally consistent with no critical issues, no breaking changes, reasonable file structure); return directly without triggering a fix
            if ok:
                limit_info = (
                    f" (limit: {max_iterations if max_iterations > 0 else 'unlimited'})"
                )
                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][review] Code review passed{limit_info} ({i + 1} iterations in total). ",
                )
                # Clean up the current agent's event subscriptions and records
                try:
                    review_agent.event_bus.unsubscribe(
                        BEFORE_TOOL_CALL, self.on_before_tool_call
                    )
                    review_agent.event_bus.unsubscribe(
                        AFTER_TOOL_CALL, self.on_after_tool_call
                    )
                    # Clean up records in agent_before_commits
                    if agent_key in self.agent_before_commits:
                        del self.agent_before_commits[agent_key]
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_review",
                        function="build_review_prompts",
                    )
                    pass
                # Record the review result to progress
                try:
                    cur = self.progress.get("current") or {}
                    cur["review"] = {
                        "ok": True,
                        "function_issues": list(function_issues),
                        "critical_issues": list(critical_issues),
                        "breaking_issues": list(breaking_issues),
                        "structure_issues": list(structure_issues),
                        "iterations": i + 1,
                    }
                    metrics = cur.get("metrics") or {}
                    metrics["review_iterations"] = i + 1
                    metrics["function_issues"] = len(function_issues)
                    metrics["type_issues"] = len(critical_issues)
                    metrics["breaking_issues"] = len(breaking_issues)
                    metrics["structure_issues"] = len(structure_issues)
                    cur["metrics"] = metrics
                    self.progress["current"] = cur
                    self.save_progress()
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_c2rust.transpiler_review",
                        function="build_review_prompts",
                    )
                    pass
                return

            # Needs optimization: provide detailed context and clarify that the review comments apply only to the Rust crate, not the C source
            crate_tree = dir_tree(self.crate_dir)
            issues_text = "\n".join(
                [
                    "Functional consistency issues: " if function_issues else "",
                    *[f"  - {issue}" for issue in function_issues],
                    "Critical issues (may cause functional errors): " if critical_issues else "",
                    *[f"  - {issue}" for issue in critical_issues],
                    "Breaking changes issues (impact on existing code): " if breaking_issues else "",
                    *[f"  - {issue}" for issue in breaking_issues],
                    "File structure issues: " if structure_issues else "",
                    *[f"  - {issue}" for issue in structure_issues],
                ]
            )
            # Get C source file location info
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

            fix_prompt = "\n".join(
                [
                    "Please perform minimal optimization on the target function based on the following review conclusions (preserve structure and intent; do not perform large-scale refactoring): ",
                    "<REVIEW>",
                    issues_text
                    if issues_text.strip()
                    else "The review found issues, but no specific issue description was provided",
                    "</REVIEW>",
                    "",
                    "Context background information: ",
                    f"- **Crate root (important)**: {self.crate_dir.resolve()}",
                    "  * All Rust source files are under this directory",
                    "  * When using the `read_code` tool to read a Rust file, the file path should be relative to this directory (such as `src/xxx.rs`) or use an absolute path",
                    "  * When using edit_file_* tool to edit files, File path should also be relative to this directory or absolute path",
                    "  * The current working directory should be switched to this directory, or use an absolute path to access files",
                    f"- Target module file: {module}",
                    f"- Suggested/current Rust signature: {rust_sig}",
                    *(
                        [f"- C Source file location: {c_file_location}"]
                        if c_file_location
                        else []
                    ),
                    "crate directory structure (partial): ",
                    crate_tree,
                    "",
                    "Constraints and scope: ",
                    "- The review comments in this round apply only to the code and configuration of the Rust crate; do not modify any C/C++ source files (*.c, *.h, etc). ",
                    "- Only minimal necessary modifications are allowed under crate_dir (Cargo.toml, src/**/*.rs); do not modify other directories. ",
                    "- Keep changes minimal; avoid refactoring or formatting unrelated to the issues. ",
                    "- Prioritize fixing critical issues (may cause functional errors), then fix functional consistency issues; ",
                    "- ⚠️ **important: fix scope requirement** - Not only must the issues found in the current review be fixed, but if the fix causes other test cases to fail, they must also be fixed: ",
                    "  * After fixing, you must run `cargo test -- --nocapture` to verify that all test cases pass",
                    "  * If you find that some previously passing test cases now fail after the fix, it means the fix introduced a regression, and it must be fixed as well",
                    "  * You must ensure that after the fix all test cases pass (including the tests of the target function and those of other functions)",
                    "  * If the fix affects other functions or modules, you need to check and fix all affected parts",
                    "- If the review issue involves a missing/unimplemented callee function or dependency, please read its C source and supply the equivalent Rust implementation in this round as well; if necessary, add functions in reasonable modules or introduce precise use statements; ",
                    "- Do not use todo!/unimplemented! as placeholders; ",
                    "- You may use the read_symbols/read_code tools to obtain the C source and location of dependency symbols to assist implementation; import only the exact symbols required (wildcards are forbidden); ",
                    "- **Path notes when using tools**: ",
                    f"  * `read_code` tool: When reading a Rust file, use a path relative to the crate root ({self.crate_dir.resolve()}) (such as `src/xxx.rs`) or an absolute path",
                    "  * `edit_file_*` tool: When editing a file, the file path should also be relative to the crate root or use an absolute path",
                    "- Comment convention: all code comments (including doc comments, inline comments, block comments, etc) must be in Chinese; ",
                    *(
                        [
                            f"- **Disabled library constraint**: The following libraries are prohibited in the optimization: {', '.join(self.disabled_libraries)}. If these libraries already exist in Cargo.toml, please remove the related dependencies; if the optimization needs the functionality of these libraries, use the standard library or other allowed libraries instead. "
                        ]
                        if self.disabled_libraries
                        else []
                    ),
                    *(
                        [
                            f"- **Root symbol requirement**: This function is a root symbol ({rec.qname or rec.name}), must use `pub` keyword for public exposure, ensure access from outside crate. also, the module containing this function must be exported in src/lib.rs (using `pub mod <module_name>;`). "
                        ]
                        if self.is_root_symbol(rec)
                        else []
                    ),
                    "",
                    " [important: dependency check and implementation requirements]",
                    "Before optimizing the function, be sure to check the following: ",
                    "1. Check whether the current function is fully implemented: ",
                    f"   - Look for the implementation of function {rec.qname or rec.name} in the target module {module}",
                    "   - If an implementation already exists, check whether it is complete and correct",
                    "2. Check whether all dependency functions are implemented: ",
                    "   - Traverse all callee functions called by the current function (including direct and indirect calls)",
                    "   - For each callee function, check whether it already has a complete implementation in the Rust crate",
                    "   - You may use the read_code tool to read the relevant module files for checking",
                    "3. For unimplemented dependency functions: ",
                    "   - Use the read_symbols tool to obtain their C source and symbol information",
                    "   - Use the read_code tool to read their C source implementation",
                    "   - Supply the Rust implementation of these dependency functions in this optimization as well",
                    "   - Choose appropriate module positions based on the dependency relationships (either in the same module or in a reasonable new module)",
                    "   - Ensure all dependency functions have complete implementations; do not use todo!/unimplemented! as placeholders",
                    "4. Implementation order: ",
                    "   - Implement the lowest-level dependency functions first (functions that do not depend on other unimplemented functions)",
                    "   - Then implement the functions that depend on these lower-level functions",
                    "   - Finally, optimize the current target function",
                    "5. Verification: ",
                    "   - Ensure the current function and all its dependency functions are fully implemented",
                    "   - Ensure there are no leftover todo!/unimplemented! placeholders",
                    "   - Ensure all function calls can be resolved correctly",
                    "",
                ]
            )

            # Get the C code for the fix Agent
            c_code = self.read_source_span(rec)

            # Create the fix Agent first (it will be reused later)
            # Since transpile() has already switched to the crate directory at the start, no need to switch again here
            # Record the commit before running
            before_commit = self.get_crate_commit_hash()
            # Use the fix Agent; recreate it each time and pass in the C code
            ca = self.get_fix_agent(c_code)

            # Add git change info as context
            if self.get_git_diff:
                try:
                    base_commit = self.current_function_start_commit_getter()
                    git_diff = self.get_git_diff(base_commit)
                    if git_diff and git_diff.strip():
                        # Limit the git diff length to avoid an oversized context
                        # Use a smaller ratio (30%) because the fix hint itself is already very long
                        # Use the already-created fix Agent to get a more accurate remaining token count
                        git_diff = truncate_git_diff_with_context_limit(
                            git_diff,
                            agent=ca,
                            token_ratio=0.3,
                            base_commit=base_commit,
                            crate_dir=self.crate_dir,
                        )

                        fix_prompt += "\n\n"
                        fix_prompt += " [Git change info]\n"
                        fix_prompt += "The following are the git changes from when the function processing began up to now; this can help you understand what modifications have already been made: \n"
                        fix_prompt += "<GIT_DIFF>\n"
                        fix_prompt += git_diff
                        fix_prompt += "\n</GIT_DIFF>\n"
                        fix_prompt += "\n"
                        fix_prompt += "hint: \n"
                        fix_prompt += "- Please carefully review the above git diff to understand the current code state and the modifications already made\n"
                        fix_prompt += (
                            "- If you see that previous modifications introduced problems, you can handle them together during the fix\n"
                        )
                        fix_prompt += (
                            "- If you see that some files were modified unexpectedly, confirm whether these modifications are necessary\n"
                        )
                        fix_prompt += "- Fix the code in a targeted manner based on the review issues\n"
                except Exception:
                    # If obtaining the git diff fails, it does not affect the main flow
                    pass

            fix_prompt += "\nPlease output the modifications only in the form of a patch, and avoid redundant explanations. "
            limit_info = f"/{max_iterations}" if max_iterations > 0 else "/∞"
            fix_prompt_with_notes = self.append_additional_notes(fix_prompt)
            ca.run(
                self.compose_prompt_with_context(fix_prompt_with_notes, True),
                prefix=f"⚠️ [c2rust-transpiler][review-fix iter={i + 1}{limit_info}]",
                suffix="",
            )

            # Detect and handle test code deletion
            if self.check_and_handle_test_deletion(before_commit, ca):
                # If rolled back, the agent needs to be run again
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][review-fix] Test code deletion detected, rolled back, re-running agent (iter={i + 1})",
                )
                before_commit = self.get_crate_commit_hash()
                # Recreate the fix Agent
                ca = self.get_fix_agent(c_code)
                ca.run(
                    self.compose_prompt_with_context(fix_prompt_with_notes, True),
                    prefix=f"⚠️ [c2rust-transpiler][review-fix iter={i + 1}{limit_info}][retry]",
                    suffix="",
                )
                # Detect again
                if self.check_and_handle_test_deletion(before_commit, ca):
                    PrettyOutput.auto_print(
                        f"❌ [c2rust-transpiler][review-fix] Test code deletion detected again, rolled back (iter={i + 1})",
                    )

            # Perform a build verification after optimization; if it does not pass, enter the build-fix loop until it passes
            self.cargo_build_loop()

            # Check whether a fix was performed during the build-fix process
            build_has_fixes = (
                self.get_build_loop_has_fixes()
                if hasattr(self, "get_build_loop_has_fixes")
                else False
            )
            if build_has_fixes:
                PrettyOutput.auto_print(
                    "[c2rust-transpiler][review-fix] A fix was performed during the build-fix process; it will be re-checked in the next review round",
                )

            # Record the result of this review
            try:
                cur = self.progress.get("current") or {}
                cur["review"] = {
                    "ok": False,
                    "function_issues": list(function_issues),
                    "critical_issues": list(critical_issues),
                    "breaking_issues": list(breaking_issues),
                    "structure_issues": list(structure_issues),
                    "iterations": i + 1,
                }
                metrics = cur.get("metrics") or {}
                metrics["function_issues"] = len(function_issues)
                metrics["type_issues"] = len(critical_issues)
                metrics["breaking_issues"] = len(breaking_issues)
                metrics["structure_issues"] = len(structure_issues)
                cur["metrics"] = metrics
                self.progress["current"] = cur
                self.save_progress()
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_review",
                    function="build_review_prompts",
                )
                pass

            # Clean up the agent event subscriptions and records of the current iteration (to prepare for the next iteration)
            # Unsubscribe to avoid the event bus holding a reference to the agent, which would prevent the agent from being garbage collected
            try:
                review_agent.event_bus.unsubscribe(
                    BEFORE_TOOL_CALL, self.on_before_tool_call
                )
                review_agent.event_bus.unsubscribe(
                    AFTER_TOOL_CALL, self.on_after_tool_call
                )
                # Clean up records in agent_before_commits
                if agent_key in self.agent_before_commits:
                    del self.agent_before_commits[agent_key]
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_review",
                    function="build_review_prompts",
                )
                pass

            i += 1

            # Reached the iteration limit (only when a limit is set)
            # Note: the agent of the last iteration has already been cleaned up inside the loop, so no extra cleanup is needed here
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][review] Reached the maximum iteration limit ({max_iterations}), stopping review optimization. ",
            )
            try:
                cur = self.progress.get("current") or {}
                cur["review_max_iterations_reached"] = True
                cur["review_iterations"] = i
                self.progress["current"] = cur
                self.save_progress()
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_review",
                    function="build_review_prompts",
                )
                pass
