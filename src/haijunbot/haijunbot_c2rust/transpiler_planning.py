# -*- coding: utf-8 -*-
"""
Module and signature planning module
"""

import json
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.utils import dir_tree
from haijunbot.haijunbot_c2rust.utils import extract_json_from_summary


class PlanningManager:
    """Module and signature planning manager"""

    def __init__(
        self,
        project_root: Path,
        crate_dir: Path,
        data_dir: Path,
        plan_max_retries: int,
        non_interactive: bool,
        disabled_libraries: List[str],
        root_symbols: List[str],
        extract_compile_flags_func: Callable[[str], Dict[str, Any]],
        collect_callees_context_func: Callable[[Any], List[Dict[str, Any]]],
        append_additional_notes_func: Callable[[str], str],
        is_root_symbol_func: Callable[[Any], bool],
        get_crate_commit_hash_func: Callable[[], str],
        on_before_tool_call_func: Callable[[Any, Optional[Any]], None],
        on_after_tool_call_func: Callable[
            [Any, Optional[Any], Optional[bool], Optional[str]], None
        ],
        agent_before_commits: Dict[str, Optional[str]],
        enable_ffi_export_validation: bool = False,
    ) -> None:
        self.project_root = project_root
        self.crate_dir = crate_dir
        self.data_dir = data_dir

        self.plan_max_retries = plan_max_retries
        self.non_interactive = non_interactive
        self.disabled_libraries = disabled_libraries
        self.root_symbols = root_symbols
        self.extract_compile_flags = extract_compile_flags_func
        self.collect_callees_context = collect_callees_context_func
        self.append_additional_notes = append_additional_notes_func
        self.is_root_symbol = is_root_symbol_func
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.on_before_tool_call = on_before_tool_call_func
        self.on_after_tool_call = on_after_tool_call_func
        self.agent_before_commits = agent_before_commits
        self.enable_ffi_export_validation = enable_ffi_export_validation

    def build_module_selection_prompts(
        self,
        rec: FnRecord,
        c_code: str,
        callees_ctx: List[Dict[str, Any]],
        crate_tree: str,
    ) -> Tuple[str, str, str]:
        """
        Returns (system_prompt, user_prompt, summary_prompt).
        summary is required to output JSON:
        {
          "module": "src/<path>.rs or module path (e.g., src/foo/mod.rs or src/foo/bar.rs)",
          "rust_signature": "pub fn ...",
          "notes": "optional"
        }
        """
        is_root = self.is_root_symbol(rec)
        is_main = rec.name == "main" or rec.qname == "main"
        is_root_not_main = is_root and not is_main
        system_prompt = (
            "You are a senior Rust engineer, skilled at choosing the appropriate Rust module location for C/C++ functions and producing the corresponding Rust function signatures.\n"
            "Goal: Based on the provided C source, caller context, and crate directory structure, choose an appropriate Rust module file for the function and give its Rust function signature (without implementing it).\n"
            "Principles:\n"
            "- Choose modules by functional cohesion and dependency direction; avoid circular dependencies;\n"
            "- The module path must fall under the crate's src/; prefer placing it in an existing module; when necessary, you may suggest creating a new submodule file;\n"
            "- Function interface design should follow Rust best practices and does not need to be compatible with C data types; prefer Rust native types (such as i32/u32/usize, &[T]/&mut [T], String, Result<T, E>, etc.) rather than C-style types (such as core::ffi::c_*, libc::c_*);\n"
            '- Do not use extern "C"; functions should use the standard Rust calling convention and do not need the C ABI;\n'
            "- The number and order of parameters may stay consistent with C, but the type design should prioritize Rust idioms and safety;\n"
            + (
                "- **Root symbol requirement**: This function is a root symbol; it must use the `pub` keyword for public exposure to ensure access from outside the crate. Also, the module containing this function must be exported in src/lib.rs (using `pub mod <module_name>;`).\n"
                if is_root
                else ""
            )
            + (
                "\n- **FFI export requirement**: This function is a root symbol (other than main), and FFI export validation is enabled. The function must be named and exported as an FFI interface:\n"
                "  * The function must use the `#[no_mangle]` attribute to ensure the symbol name is not mangled by the Rust compiler\n"
                '  * The function must be declared with `pub extern "C"`, using the C ABI calling convention\n'
                "  * The function signature should use C-compatible types (such as `*const c_char`, `c_int`, `c_void`, etc.) so it can be called from C code\n"
                "  * The function name should remain consistent with the original C function name so it exports correctly in the generated cdylib\n"
                '  * Note: Although `extern "C"` is used, the function implementation should still follow Rust safety practices; internally it may use Rust native types and safe APIs\n'
                if (is_root_not_main and self.enable_ffi_export_validation)
                else ""
            )
            + "- **Assess whether implementation is needed**: During the planning stage, assess whether this function really needs to be implemented. In the following cases implementation may be skipped (set skip_implementation to true), but **functional consistency must be ensured**:\n"
            + "  * **Already-implemented function**: If the function is already implemented in the target module, you may use the read_code tool to check the target file and confirm the function exists and **is functionally consistent with the C implementation**, then there is no need to implement it again. **Important**: If the already-implemented function is not functionally consistent (such as different parameter handling, different return values, different behavior, etc.), it cannot be skipped; it needs to be re-implemented or corrected\n"
            + "  * **Resource-release functions**: such as file close fclose, memory free free, handle release, lock release, etc.; in Rust these are usually managed automatically via RAII (the Drop trait) and do not need explicit implementation\n"
            + "  * **Replaced by a library**: If the function has been replaced by the standard library or a third-party crate (the lib_replacement field is set), and **the library's functionality is fully consistent with the C implementation**, no compatibility layer is needed and implementation may be skipped. **Important**: If the library's functionality is not consistent with the C implementation (such as different API behavior, different parameter requirements, different return values, etc.), a compatibility layer or re-implementation is required and cannot be skipped\n"
            + "  * **Empty or meaningless function**: If the C function itself is an empty implementation, simply returns a constant, or exists only as a compatibility placeholder, it may not need to be implemented in Rust\n"
            + "  * **Inline functions or macros**: If the function is an inline function or macro in C, it may not need a separate implementation in Rust\n"
            + "  * **Other cases where implementation is not needed**: Judge on a case-by-case basis; if the function truly does not need to be implemented in the Rust transpilation, it may be skipped\n"
            + "  * **Functional consistency checking principle**: When deciding whether to skip implementation, you must carefully compare the functional consistency of the C implementation and the Rust implementation (or library replacement), including but not limited to: input parameter handling, return values, side effects, error handling, boundary condition handling, etc. If any inconsistency exists, implementation cannot be skipped\n"
            + "  * If skip_implementation is set to true, explain the reason in detail in the notes field and confirm that a functional consistency check has been performed\n"
            + "- Output only the necessary information; avoid redundant explanations."
        )
        # Extract compile flags
        compile_flags = self.extract_compile_flags(rec.file)
        compile_flags_section = ""
        if compile_flags:
            compile_flags_section = "\n".join(
                [
                    "",
                    "C file compile flags (from compile_commands.json):",
                    str(compile_flags),
                ]
            )

        user_prompt = "\n".join(
            [
                "Please read the following context and prepare a summary:",
                f"- Function identifier: id={rec.id}, name={rec.name}, qualified={rec.qname}",
                f"- Source file location: {rec.file}:{rec.start_line}-{rec.end_line}",
                f"- crate root directory path: {self.crate_dir.resolve()}",
                "",
                "C function source snippet:",
                "<C_SOURCE>",
                c_code,
                "</C_SOURCE>",
                "",
                "Symbol table signature and parameters (read-only reference):",
                json.dumps(
                    {
                        "signature": getattr(rec, "signature", ""),
                        "params": getattr(rec, "params", None),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "",
                "Referenced symbol context (includes Rust module info if already transpiled):",
                json.dumps(callees_ctx, ensure_ascii=False, indent=2),
                "",
                "Library replacement context (if exists):",
                json.dumps(
                    getattr(rec, "lib_replacement", None), ensure_ascii=False, indent=2
                ),
                compile_flags_section,
                "",
                *(
                    [
                        f"Disabled library list (prohibited from using these libraries in implementation): {', '.join(self.disabled_libraries)}"
                    ]
                    if self.disabled_libraries
                    else []
                ),
                *([""] if self.disabled_libraries else []),
                "Current crate directory structure (partial):",
                "<CRATE_TREE>",
                crate_tree,
                "</CRATE_TREE>",
                "",
                "To avoid fully reading a large symbol table, you may also use the read_symbols tool to fetch specific symbol records on demand:",
                "- Tool: read_symbols",
                "- Parameter example (JSON):",
                f'  {{"symbols_file": "{(self.data_dir / "symbols.jsonl").resolve()}", "symbols": ["symbol1", "symbol2"]}}',
                "",
                "**Important: check whether the function is already implemented and functional consistency**",
                "After determining the target module, use the read_code tool to check the module file and confirm whether the function is already implemented:",
                "- Tool: read_code",
                "- Parameter example (JSON):",
                '  {"file_path": "<target module path>"}',
                '- If the function is already implemented in the target module, **you must carefully compare the functional consistency of the C implementation and the Rust implementation** (including parameter handling, return values, side effects, error handling, boundary conditions, etc.); only when the functionality is fully consistent may you set skip_implementation to true and explain in notes that "the function is already implemented in the target module and is functionally consistent with the C implementation". If the functionality is not consistent, it cannot be skipped; it needs to be re-implemented or corrected',
                "",
                "If you have understood everything, proceed to the summary stage.",
            ]
        )
        summary_prompt = (
            "Output only a single <SUMMARY> block; the block must contain exactly one JSON object and nothing else.\n"
            "Allowed fields (JSON object):\n"
            '- "module": "<absolute path>/src/xxx.rs or <absolute path>/src/xxx/mod.rs; or relative path src/xxx.rs / src/xxx/mod.rs"\n'
            '- "rust_signature": "pub fn xxx(...)->..."\n'
            '- "skip_implementation": bool  // optional; if true, indicates this function does not need implementation and can be marked as implemented directly\n'
            '- "notes": "optional explanation (list any missing context or risk points here; if skip_implementation is true, the reason must be explained here)"\n'
            "Note:\n"
            "- module must be under the crate's src/ directory; absolute paths or relative paths beginning with src/ are accepted; prefer existing files; if a new file is needed, give a reasonable path;\n"
            "- rust_signature should follow Rust best practices and does not need to be compatible with C data types; prefer Rust native types and idioms rather than C-style types.\n"
            "- **Assess whether implementation is needed**: Carefully assess whether this function really needs to be implemented. In the following cases skip_implementation may be set to true, but **functional consistency must be ensured**:\n"
            + "  * **Already-implemented function**: If the function is already implemented in the target module, you may use the read_code tool to check the target file and confirm the function exists and **is functionally consistent with the C implementation**, then there is no need to implement it again. **Important**: If the already-implemented function is not functionally consistent (such as different parameter handling, different return values, different behavior, etc.), it cannot be skipped; it needs to be re-implemented or corrected\n"
            + "  * **Resource-release functions**: such as file close fclose, memory free free, handle release, lock release, etc.; in Rust these are usually managed automatically via RAII (the Drop trait) and do not need explicit implementation\n"
            + "  * **Replaced by a library**: If the function has been replaced by the standard library or a third-party crate (the lib_replacement field is set), and **the library's functionality is fully consistent with the C implementation**, no compatibility layer is needed and implementation may be skipped. **Important**: If the library's functionality is not consistent with the C implementation (such as different API behavior, different parameter requirements, different return values, etc.), a compatibility layer or re-implementation is required and cannot be skipped\n"
            + "  * **Empty or meaningless function**: If the C function itself is an empty implementation, simply returns a constant, or exists only as a compatibility placeholder, it may not need to be implemented in Rust\n"
            + "  * **Inline functions or macros**: If the function is an inline function or macro in C, it may not need a separate implementation in Rust\n"
            + "  * **Other cases where implementation is not needed**: Judge on a case-by-case basis; if the function truly does not need to be implemented in the Rust transpilation, it may be skipped\n"
            + "  * **Functional consistency checking principle**: When deciding whether to skip implementation, you must carefully compare the functional consistency of the C implementation and the Rust implementation (or library replacement), including but not limited to: input parameter handling, return values, side effects, error handling, boundary condition handling, etc. If any inconsistency exists, implementation cannot be skipped\n"
            + "  * **Important**: If skip_implementation is set to true, you must explain the reason in detail in the notes field and confirm that a functional consistency check has been performed, for example:\n"
            + '    - "the function is already implemented in the target module and is functionally consistent with the C implementation"\n'
            + '    - "managed automatically via RAII; no explicit implementation needed"\n'
            + '    - "replaced by the standard library std::xxx, fully consistent, no implementation needed"\n'
            + '    - "empty function; not needed in Rust"\n'
            + '    - "inline function; already expanded at the call site, no separate implementation needed"\n'
            + "- If the function really needs to be implemented, or the functionality is inconsistent and needs correction, do not set skip_implementation or set it to false\n"
            + "- Type design principles:\n"
            + "  * Primitive types: prefer Rust native types such as i32/u32/i64/u64/isize/usize/f32/f64 rather than core::ffi::c_* or libc::c_*;\n"
            + "  * Pointers/references: prefer references &T/&mut T or slices &[T]/&mut [T] over raw pointers *const T/*mut T; use raw pointers only when necessary;\n"
            + "  * Strings: prefer String, &str over *const c_char/*mut c_char;\n"
            + "  * Error handling: consider using Result<T, E> rather than C-style error codes;\n"
            + "  * The number and order of parameters may stay consistent with C, but types should prioritize Rust idioms, safety, and readability;\n"
            + (
                "- **Root symbol requirement**: This function is a root symbol; rust_signature must include the `pub` keyword to ensure access from outside the crate. Also, the module containing this function must be exported in src/lib.rs (using `pub mod <module_name>;`).\n"
                if is_root
                else ""
            )
            + "- The function signature should include a visibility modifier (pub) and the function name; types should be chosen per Rust best practices rather than a simple mapping of C types.\n"
            + '- Do not use extern "C"; functions should use the standard Rust calling convention and do not need the C ABI.\n'
            + "Output strictly in the following format (JSON format, supporting jsonnet syntax such as trailing commas, comments, etc.):\n"
            + "Example1 (normal function):\n"
            + '<SUMMARY>\n{\n  "module": "...",\n  "rust_signature": "...",\n  "notes": "..."\n}\n</SUMMARY>\n'
            + "Example2 (already-implemented function, functionally consistent, may skip implementation):\n"
            + '<SUMMARY>\n{\n  "module": "...",\n  "rust_signature": "...",\n  "skip_implementation": true,\n  "notes": "the function is already implemented in the target module and is functionally consistent with the C implementation (parameter handling, return values, side effects all consistent)"\n}\n</SUMMARY>\n'
            + "Example3 (function that does not need implementation, may skip implementation):\n"
            + '<SUMMARY>\n{\n  "module": "...",\n  "rust_signature": "...",\n  "skip_implementation": true,\n  "notes": "managed automatically via RAII; no explicit implementation needed"\n}\n</SUMMARY>\n'
            + "Example4 (replaced by a library, functionally consistent, may skip implementation):\n"
            + '<SUMMARY>\n{\n  "module": "...",\n  "rust_signature": "...",\n  "skip_implementation": true,\n  "notes": "replaced by the standard library std::xxx and fully consistent with the C implementation (API behavior, parameter requirements, return values all consistent); no implementation needed"\n}\n</SUMMARY>\n'
            + "Example5 (empty function, may skip implementation):\n"
            + '<SUMMARY>\n{\n  "module": "...",\n  "rust_signature": "...",\n  "skip_implementation": true,\n  "notes": "C function is an empty implementation; not needed in Rust"\n}\n</SUMMARY>'
        )
        # Append additional notes to user_prompt and summary_prompt (system_prompt usually does not need it)
        user_prompt = self.append_additional_notes(user_prompt)
        summary_prompt = self.append_additional_notes(summary_prompt)
        return system_prompt, user_prompt, summary_prompt

    def plan_module_and_signature(
        self, rec: FnRecord, c_code: str
    ) -> Tuple[str, str, bool]:
        """Call the Agent to choose the module and signature, returning (module_path, rust_signature, skip_implementation); if the format does not satisfy the requirements it will automatically retry until it does"""
        crate_tree = dir_tree(self.crate_dir)
        callees_ctx = self.collect_callees_context(rec)
        sys_p, usr_p, base_sum_p = self.build_module_selection_prompts(
            rec, c_code, callees_ctx, crate_tree
        )

        def _validate(meta: Any) -> Tuple[bool, str]:
            """Basic format check; only verifies field existence, without hard-coded rule validation"""
            if not isinstance(meta, dict) or not meta:
                return False, "No valid JSON object parsed from <SUMMARY>"
            module = meta.get("module")
            rust_sig = meta.get("rust_signature")
            if not isinstance(module, str) or not module.strip():
                return False, "Missing required field module"
            if not isinstance(rust_sig, str) or not rust_sig.strip():
                return False, "Missing required field rust_signature"
            # Path normalization: tolerate relative/short paths; finally normalize to an absolute path under crate_dir (no hard-coded validation)
            try:
                raw = str(module).strip().replace("\\", "/")
                crate_root = self.crate_dir.resolve()
                mp: Path
                p = Path(raw)
                if p.is_absolute():
                    mp = p.resolve()
                else:
                    # Normalize relative path: if it does not start with src/, automatically complete it as src/<raw>
                    if raw.startswith("./"):
                        raw = raw[2:]
                    if not raw.startswith("src/"):
                        raw = f"src/{raw}"
                    mp = (crate_root / raw).resolve()
                # Write the normalized absolute path back to meta to avoid ambiguity when parsing again in later steps
                meta["module"] = str(mp)
            except Exception:
                # Path normalization failure is non-fatal; keep the original value
                pass
            return True, ""

        def _retry_sum_prompt(reason: str) -> str:
            return (
                base_sum_p
                + "\n\n[Format check failed; you must retry]\n"
                + f"- Failure reason: {reason}\n"
                + "- Output only a single <SUMMARY> block; the block directly contains the JSON object (no extra tags needed);\n"
                + "- The JSON object must contain the fields: module, rust_signature.\n"
            )

        attempt = 0
        last_reason = "unknown error"
        plan_max_retries_val = self.plan_max_retries
        # If plan_max_retries is 0, it means infinite retries
        use_direct_model = False  # Flag whether to use a direct model call
        agent = None  # Declared outside the loop so it can be reused on retries

        # Note: The Agent must be created in the crate root directory to ensure tools (such as read_symbols) can correctly fetch the symbol table
        # Since transpile() switches to the crate directory at the start, no further switching is needed here
        while plan_max_retries_val == 0 or attempt < plan_max_retries_val:
            attempt += 1
            sum_p = base_sum_p if attempt == 1 else _retry_sum_prompt(last_reason)

            # Create the Agent the first time and reuse it on later retries (if using direct model calls)
            # Note: The Agent must be created in the crate root directory to ensure tools (such as read_symbols) can correctly fetch the symbol table
            if agent is None or not use_direct_model:
                # Get function info for the Agent name
                fn_name = rec.qname or rec.name or f"fn_{rec.id}"
                agent_name = f"C2Rust-Function-Planner({fn_name})"
                agent = Agent(
                    system_prompt=sys_p,
                    name=agent_name,
                    summary_prompt=sum_p,
                    need_summary=True,
                    auto_complete=True,
                    use_tools=["execute_script", "read_code", "read_symbols"],
                    non_interactive=self.non_interactive,
                    use_methodology=False,
                    use_analysis=False,
                    enable_auto_rule_select=False,
                    model_type="smart",
                    quick_mode=True,
                )
                # Subscribe to BEFORE_TOOL_CALL and AFTER_TOOL_CALL events for fine-grained detection of test code deletion
                agent.event_bus.subscribe(BEFORE_TOOL_CALL, self.on_before_tool_call)
                agent.event_bus.subscribe(AFTER_TOOL_CALL, self.on_after_tool_call)
                # Record the commit id at Agent creation time (as the initial value)
                agent_id = id(agent)
                agent_key = f"agent_{agent_id}"
                initial_commit = self.get_crate_commit_hash()
                if initial_commit:
                    self.agent_before_commits[agent_key] = initial_commit

            if use_direct_model:
                # After format validation fails, call the model interface directly
                # Build the complete prompt containing the summary prompt and the specific error information
                error_guidance = ""
                if last_reason and last_reason != "unknown error":
                    if "JSON parse failed" in last_reason:
                        error_guidance = f"\n\n**Format error details (fix the output format based on the following errors):**\n- {last_reason}\n\nEnsure the output JSON format is correct, including correct quotes, commas, braces, etc. The JSON object must contain the fields: module (string), rust_signature (string). jsonnet syntax is supported (such as trailing commas, comments, etc.)."
                    else:
                        error_guidance = f"\n\n**Format error details (fix the output format based on the following errors):**\n- {last_reason}\n\nEnsure the output format is correct: output only a single <SUMMARY> block, the block directly containing the JSON object (no extra tags needed); the JSON object must contain the fields: module (string), rust_signature (string). jsonnet syntax is supported (such as trailing commas, comments, etc.)."

                full_prompt = f"{usr_p}{error_guidance}\n\n{sum_p}"
                try:
                    response = agent.model.chat_until_success(full_prompt)
                    summary = response
                except Exception as e:
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-transpiler][plan] Direct model call failed: {e}; falling back to run()"
                    )
                    summary = agent.run(usr_p)
            else:
                # The first time, use run() to let the Agent run fully (it may use tools)
                summary = agent.run(usr_p)

            meta, parse_error = extract_json_from_summary(str(summary or ""))
            if parse_error:
                # JSON parse failed; feed the error information back to the model
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][plan] JSON parse failed: {parse_error}"
                )
                last_reason = f"JSON parse failed: {parse_error}"
                use_direct_model = True
                # Parse failed; continue retrying
                continue
            else:
                ok, reason = _validate(meta)
            if ok:
                module = str(meta.get("module") or "").strip()
                rust_sig = str(meta.get("rust_signature") or "").strip()
                skip_impl = bool(meta.get("skip_implementation") is True)
                if skip_impl:
                    notes = str(meta.get("notes") or "")
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][plan] Attempt {attempt} succeeded: module={module}, signature={rust_sig}, skip_implementation={skip_impl}"
                    )
                    if notes:
                        PrettyOutput.auto_print(
                            f"ℹ️ [c2rust-transpiler][plan] Reason for skipping implementation: {notes}"
                        )
                else:
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][plan] Attempt {attempt} succeeded: module={module}, signature={rust_sig}"
                    )
                return module, rust_sig, skip_impl
            else:
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-transpiler][plan] Attempt {attempt} failed: {reason}"
                )
                last_reason = reason
                # Format validation failed; later retries use direct model calls
                use_direct_model = True

        # Planning exceeded the retry limit: fall back to the default (default module src/ffi.rs + simple placeholder signature)
        # Note: If plan_max_retries_val == 0 (infinite retries), this should not be reached in theory
        try:
            crate_root = self.crate_dir.resolve()
            fallback_module = str((crate_root / "src" / "ffi.rs").resolve())
        except Exception:
            fallback_module = "src/ffi.rs"
        fallback_sig = f"pub fn {rec.name or ('fn_' + str(rec.id))}()"
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-transpiler][plan] Exceeded the planning retry limit ({plan_max_retries_val if plan_max_retries_val > 0 else 'infinite'}); falling back to default: module={fallback_module}, signature={fallback_sig}"
        )
        return fallback_module, fallback_sig, False
