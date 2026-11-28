# -*- coding: utf-8 -*-
"""
Agent management module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
import time
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_c2rust.models import FnRecord
from haijunbot.haijunbot_c2rust.utils import dir_tree

# Use abstract interfaces to decouple from concrete implementations
from haijunbot.haijunbot_c2rust.agent_factory import create_code_agent
from haijunbot.haijunbot_c2rust.agent_protocol import CodeAgentType


class AgentManager:
    """Agent manager"""

    def __init__(
        self,
        crate_dir: Path,
        project_root: Path,
        non_interactive: bool,
        fn_index_by_id: Dict[int, FnRecord],
        get_crate_commit_hash_func: Callable[[], str],
        agent_before_commits: Dict[str, Optional[str]],
        quick_mode: bool = False,
    ) -> None:
        self.crate_dir = crate_dir
        self.project_root = project_root

        self.non_interactive = non_interactive
        self.fn_index_by_id = fn_index_by_id
        self.get_crate_commit_hash = get_crate_commit_hash_func
        self.agent_before_commits = agent_before_commits
        self.quick_mode = quick_mode
        self._current_function_id: Optional[int] = None
        self._current_context_full_header: str = ""
        self._current_context_compact_header: str = ""
        self._current_context_full_sent: bool = False
        # Store the current function's C code for use by the fix Agent
        self._current_c_code: str = ""

    def get_generation_agent(self) -> CodeAgentType:
        """
        Get the code generation Agent (CodeAgent). It is re-created on every call and not reused.
        Used for code generation.
        Note: the Agent must be created in the crate root directory to ensure that tools (such as read_symbols) can correctly obtain the symbol table.
        Tip: code generation follows the TDD (test-driven development) method, using prompts to guide the Agent to write tests before the implementation.
        """
        fid = self._current_function_id
        # Note: the Agent must be created in the crate root directory to ensure that tools (such as read_symbols) can correctly obtain the symbol table
        # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
        # Uniformly enable methodology and analysis features for better code generation
        # Get function information for the Agent name
        fn_name = ""
        if fid is not None:
            rec = self.fn_index_by_id.get(fid)
            if rec:
                fn_name = rec.qname or rec.name or f"fn_{fid}"
        agent_name = "C2Rust-GenerationAgent" + (f"({fn_name})" if fn_name else "")
        agent = create_code_agent(
            name=agent_name,
            need_summary=False,
            non_interactive=self.non_interactive,
            append_tools="read_symbols",
            use_methodology=True,
            use_analysis=True,
            enable_task_list_manager=False,
            disable_review=True,
            quick_mode=self.quick_mode,
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
        return agent

    def get_fix_agent(
        self, c_code: Optional[str] = None, need_summary: bool = False
    ) -> CodeAgentType:
        """
        Get the fix Agent (CodeAgent). It is re-created on every call and not reused.
        Used for fixing build errors and test failures; enables methodology and analysis features for better fixing capability.
        Note: the Agent must be created in the crate root directory to ensure that tools (such as read_symbols) can correctly obtain the symbol table.

        Args:
            c_code: The original C implementation code, which will be added to the Agent's context
            need_summary: Whether to generate a summary; default False (the build-fix stage does not need a summary)
        """
        # Re-created every time, not reused
        # Get function information for the Agent name
        fn_name = ""
        if self._current_function_id is not None:
            rec = self.fn_index_by_id.get(self._current_function_id)
            if rec:
                fn_name = rec.qname or rec.name or f"fn_{self._current_function_id}"

        # Use the current C code (use the argument if provided, otherwise use the cached one)
        current_c_code = c_code if c_code is not None else self._current_c_code

        agent_name = "C2Rust-FixAgent" + (f"({fn_name})" if fn_name else "")

        # Only set summary_prompt when a summary is needed
        summary_prompt = None
        if need_summary:
            summary_prompt = """Please summarize the process and results of this fix. The summary should include the following:
1. **Fix process**:
   - The type of problem encountered (compile errors, test failures, warnings, etc.)
   - The problem localization process (how the root cause was found)
   - The fix steps (what specific changes were made)
   - The tools and methods used
2. **Fix results**:
   - Whether the fix succeeded
   - Which problems were fixed
   - Which files were modified
   - Whether new problems were introduced
   - Verification results (whether compilation and tests passed)
3. **Notes**:
   - If difficulties were encountered during the fix, explain the reason
   - If the fix is incomplete, describe the remaining issues
   - If the fix may affect other code, describe the scope of impact

Please use a clear structure and concise language to ensure the summary is complete and easy to understand."""

        agent = create_code_agent(
            name=agent_name,
            need_summary=need_summary,
            summary_prompt=summary_prompt,
            non_interactive=self.non_interactive,
            append_tools="read_symbols",
            use_methodology=True,
            use_analysis=True,
            disable_review=True,
            quick_mode=self.quick_mode,
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

        # Add context containing the original C code for the fix Agent
        if current_c_code:
            # Add the C code context to the Agent's session
            if hasattr(agent, "session") and hasattr(agent.session, "prompt"):
                c_code_context = (
                    "\n\n[Original C Implementation Code (fix reference)]\n"
                    "Below is the original C implementation code for the current function; please refer to it when fixing:\n"
                    "<C_SOURCE>\n"
                    f"{current_c_code}\n"
                    "</C_SOURCE>\n"
                )
                agent.session.prompt = c_code_context + agent.session.prompt

        return agent

    def get_code_agent(self) -> CodeAgentType:
        """
        Get the code generation/fix Agent (CodeAgent). It is re-created on every call and not reused.
        Used uniformly for code generation and fixes; enables methodology and analysis features for better code quality.
        Note: the Agent must be created in the crate root directory to ensure that tools (such as read_symbols) can correctly obtain the symbol table.
        Tip: code generation follows the TDD (test-driven development) method, using prompts to guide the Agent to write tests before the implementation.
        """
        fid = self._current_function_id
        # Note: the Agent must be created in the crate root directory to ensure that tools (such as read_symbols) can correctly obtain the symbol table
        # Since transpile() already switches to the crate directory at the start, there is no need to switch again here
        # Uniformly enable methodology and analysis features for better code generation and fixing capability
        # Get function information for the Agent name
        fn_name = ""
        if fid is not None:
            rec = self.fn_index_by_id.get(fid)
            if rec:
                fn_name = rec.qname or rec.name or f"fn_{fid}"
        agent_name = "C2Rust-CodeAgent" + (f"({fn_name})" if fn_name else "")
        agent = create_code_agent(
            name=agent_name,
            need_summary=False,
            non_interactive=self.non_interactive,
            append_tools="read_symbols",
            use_methodology=True,
            use_analysis=True,
            enable_task_list_manager=False,
            disable_review=True,
            quick_mode=self.quick_mode,
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
        return agent

    def compose_prompt_with_context(self, prompt: str, for_fix: bool = False) -> str:
        """
        When reusing an Agent, prepend the previously built function context header to the current prompt to ensure continuity.
        Strategy:
        - Within each function's lifecycle, the first call prepends the "full header";
        - subsequent calls prepend only the "compact header";
        - if the header is missing, return the original prompt directly.

        Args:
            for_fix: If True, this indicates the prompt is for the fix Agent, and the original C code will be added to the context
        """
        # If this is the fix Agent, add the original C code context
        if for_fix and self._current_c_code:
            c_code_header = (
                "\n[Original C Implementation Code (fix reference)]\n"
                "Below is the original C implementation code for the current function; please refer to it when fixing:\n"
                "<C_SOURCE>\n"
                f"{self._current_c_code}\n"
                "</C_SOURCE>\n"
            )
            # Send the full context the first time
            if (
                not self._current_context_full_sent
            ) and self._current_context_full_header:
                self._current_context_full_sent = True
                return (
                    self._current_context_full_header + c_code_header + "\n\n" + prompt
                )
            # Append the compact context afterward
            if self._current_context_compact_header:
                return (
                    self._current_context_compact_header
                    + c_code_header
                    + "\n\n"
                    + prompt
                )
            return c_code_header + "\n\n" + prompt

        # Send the full context the first time
        if (not self._current_context_full_sent) and self._current_context_full_header:
            self._current_context_full_sent = True
            return self._current_context_full_header + "\n\n" + prompt
        # Append the compact context afterward
        if self._current_context_compact_header:
            return self._current_context_compact_header + "\n\n" + prompt
        return prompt

    def reset_function_context(
        self,
        rec: FnRecord,
        module: str,
        rust_sig: str,
        c_code: str,
        collect_callees_context_func: Callable[[Any], str],
        extract_compile_flags_func: Callable[[str], Dict[str, Any]],
    ) -> None:
        """
        Initialize the context for the current function.
        Called once at the start of implementing a single function.
        Note: all Agents are re-created on every call and not reused.
        """
        self._current_function_id = rec.id
        # Store the current function's C code for use by the fix Agent
        self._current_c_code = c_code or ""

        # Assemble the context header for later reuse concatenation
        callees_ctx = collect_callees_context_func(rec)
        crate_tree = dir_tree(self.crate_dir)
        librep_ctx = (
            rec.lib_replacement if isinstance(rec.lib_replacement, dict) else None
        )
        # Extract compile flags
        compile_flags = extract_compile_flags_func(rec.file)

        header_lines = [
            "[Current Function Context (for Agent reuse)]",
            f"- Function: {rec.qname or rec.name} (id={rec.id})",
            f"- Source location: {rec.file}:{rec.start_line}-{rec.end_line}",
            f"- Original C project directory: {self.project_root.resolve()}",
            f"- Target module: {module}",
            f"- Suggested/current signature: {rust_sig}",
            f"- crate root directory: {self.crate_dir.resolve()}",
            "",
            "Original C function source snippet (read-only reference):",
            "<C_SOURCE>",
            c_code or "",
            "</C_SOURCE>",
            "",
            "Referenced symbol context:",
            json.dumps(callees_ctx, ensure_ascii=False, indent=2),
            "",
            "Library replacement context (if any):",
            json.dumps(librep_ctx, ensure_ascii=False, indent=2),
        ]
        # Add compile flags (if present)
        if compile_flags:
            header_lines.extend(
                [
                    "",
                    "C file compile flags (from compile_commands.json):",
                    str(compile_flags),
                ]
            )
        header_lines.extend(
            [
                "",
                "crate directory structure (partial):",
                "<CRATE_TREE>",
                crate_tree,
                "</CRATE_TREE>",
            ]
        )
        # Compact header (for later reuse)
        compact_lines = [
            "[Function Context Summary (for reuse)]",
            f"- Function: {rec.qname or rec.name} (id={rec.id})",
            f"- Original C project directory: {self.project_root.resolve()}",
            f"- Module: {module}",
            f"- Signature: {rust_sig}",
            f"- crate: {self.crate_dir.resolve()}",
        ]
        self._current_context_full_header = "\n".join(header_lines)
        self._current_context_compact_header = "\n".join(compact_lines)
        self._current_context_full_sent = False

    def refresh_compact_context(
        self, rec: FnRecord, module: str, rust_sig: str
    ) -> None:
        """
        Refresh the compact context header (called after sig-fix/ensure-impl to keep subsequent prompts consistent).
        Only updates the compact header; does not affect the full header already sent.
        """
        try:
            compact_lines = [
                "[Function Context Summary (for reuse)]",
                f"- Function: {rec.qname or rec.name} (id={rec.id})",
                f"- Module: {module}",
                f"- Signature: {rust_sig}",
                f"- crate: {self.crate_dir.resolve()}",
            ]
            self._current_context_compact_header = "\n".join(compact_lines)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_agents",
                function="refresh_compact_context",
            )
            pass

    def on_before_tool_call(
        self, agent: Any, current_response: Optional[Any] = None, **kwargs: Any
    ) -> None:
        """
        Event handler before a tool call, used to record the commit id before the tool call.

        Records the current commit before each tool call so that it can be rolled back if a problem is detected after the tool call.
        """
        try:
            # Only focus on tools that may modify code
            # Note: at BEFORE_TOOL_CALL, the tool has not executed yet, so the tool name cannot be obtained
            # But we can check the tool name at AFTER_TOOL_CALL; here we just record the commit
            agent_id = id(agent)
            agent_key = f"agent_{agent_id}"
            current_commit = self.get_crate_commit_hash()
            if current_commit:
                # Record the commit before the tool call (if not recorded before, or the commit has changed)
                if (
                    agent_key not in self.agent_before_commits
                    or self.agent_before_commits[agent_key] != current_commit
                ):
                    self.agent_before_commits[agent_key] = current_commit
        except Exception as e:
            # Event handler exceptions should not affect the main flow
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][test-detection] BEFORE_TOOL_CALL event handler exception: {e}"
            )

    def on_after_tool_call(
        self,
        agent: Any,
        current_response: Optional[Any] = None,
        need_return: Optional[bool] = None,
        tool_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Event handler after a tool call, used for fine-grained detection of test code deletion.

        Detects immediately after each tool call; if test code is found to have been incorrectly deleted, rolls back immediately.
        """
        try:
            # Only detect tool calls that edit files
            last_tool = (
                agent.get_user_data("__last_executed_tool__")
                if hasattr(agent, "get_user_data")
                else None
            )
            if not last_tool:
                return

            # Only focus on tools that may modify code
            edit_tools = {
                "edit_file",
                "edit_file_by_line",
                "write_file",
                "apply_patch",
            }
            if last_tool not in edit_tools:
                return

            # Get the commit id before the tool call for this Agent
            agent_id = id(agent)
            agent_key = f"agent_{agent_id}"
            before_commit = self.agent_before_commits.get(agent_key)

            # If there is no commit information, detection is not possible
            if not before_commit:
                return

            # Detect test code deletion
            from haijunbot.haijunbot_c2rust.utils import ask_llm_about_test_deletion
            from haijunbot.haijunbot_c2rust.utils import detect_test_deletion

            detection_result = detect_test_deletion("[c2rust-transpiler]")
            if not detection_result:
                # No deletion detected; update the commit record
                current_commit = self.get_crate_commit_hash()
                if current_commit and current_commit != before_commit:
                    self.agent_before_commits[agent_key] = current_commit
                return

            PrettyOutput.auto_print(
                "⚠️ [c2rust-transpiler][test-detection] Detected a possibly erroneous deletion of test code markers (detected after the tool call)"
            )

            # Ask the LLM whether it is reasonable
            need_reset = ask_llm_about_test_deletion(
                detection_result, agent, "[c2rust-transpiler]"
            )

            if need_reset:
                PrettyOutput.auto_print(
                    f"❌ [c2rust-transpiler][test-detection] The LLM confirmed the deletion is unreasonable; rolling back to commit: {before_commit}"
                )
                # The reset_to_commit function needs to be called, but it must be passed via a callback here
                # Record it for now; the caller will handle it
                if hasattr(self, "_reset_to_commit_func"):
                    if self._reset_to_commit_func(before_commit):
                        PrettyOutput.auto_print(
                            "✅ [c2rust-transpiler][test-detection] Rolled back to the previous commit (detected after the tool call)"
                        )
                        # After rolling back, keep the previous commit record
                        self.agent_before_commits[agent_key] = before_commit
                        # Add a hint to the agent's session informing it that the changes were reverted
                        if hasattr(agent, "session") and hasattr(
                            agent.session, "prompt"
                        ):
                            agent.session.prompt += "\n\n⚠️ Changes reverted: test code was detected as incorrectly deleted, rolled back to the previous version.\n"
                    else:
                        PrettyOutput.auto_print(
                            "❌ [c2rust-transpiler][test-detection] Rollback failed"
                        )
            else:
                # The LLM considers the deletion reasonable; update the commit record
                current_commit = self.get_crate_commit_hash()
                if current_commit and current_commit != before_commit:
                    self.agent_before_commits[agent_key] = current_commit
        except Exception as e:
            # Event handler exceptions should not affect the main flow
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][test-detection] AFTER_TOOL_CALL event handler exception: {e}"
            )

    def set_reset_to_commit_func(self, reset_func: Callable[[str], bool]) -> None:
        """Set the function that resets to a commit"""
        self._reset_to_commit_func = reset_func

    def update_progress_current(
        self,
        rec: FnRecord,
        module: str,
        rust_sig: str,
        progress: Dict[str, Any],
        save_progress_func: Callable[[], None],
    ) -> None:
        """Update the current progress"""
        progress["current"] = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "id": rec.id,
            "name": rec.name,
            "qualified_name": rec.qname,
            "file": rec.file,
            "start_line": rec.start_line,
            "end_line": rec.end_line,
            "module": module,
            "rust_signature": rust_sig,
        }
        save_progress_func()
