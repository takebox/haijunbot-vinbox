# -*- coding: utf-8 -*-
"""
LLM-driven Rust Crate module planning Agent

Goal:
- Reuse find_root_function_ids and call graph information from scanner to construct a context "starting from the root function"
- Call the LLM via haijunbot_agent.Agent to generate a Rust crate directory plan (JSON) based on the context

Design points:
- Decoupled from the existing scanner/eli, adding a new module with minimal intrusion
- Uses haijunbot_agent.Agent's platform and system prompt management capabilities, but does not go through the full tool loop, performing a single-shot conversation generation instead
- Strongly constrains the output format: output JSON only, with no explanatory text

Usage:
  from haijunbot.haijunbot_c2rust.llm_module_agent import plan_crate_json_llm
  PrettyOutput.auto_print(plan_crate_json_llm(project_root="."))

CLI integration suggestion:
  You can add an llm-plan subcommand in haijunbot_c2rust/eli.py to call this module's plan_crate_json_llm (already independently encapsulated for later extension)
"""

from __future__ import annotations

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any, List, Optional, Union

from haijunbot.haijunbot_agent import Agent  # Reuse the LLM Agent capabilities
from haijunbot.haijunbot_c2rust.llm_module_agent_apply import (
    apply_project_structure_from_json,
)
from haijunbot.haijunbot_c2rust.llm_module_agent_executor import (
    execute_llm_plan,
)
from haijunbot.haijunbot_c2rust.llm_module_agent_loader import GraphLoader
from haijunbot.haijunbot_c2rust.llm_module_agent_prompts import PromptBuilder
from haijunbot.haijunbot_c2rust.llm_module_agent_types import sanitize_mod_name
from haijunbot.haijunbot_c2rust.llm_module_agent_utils import (
    entries_to_json,
    parse_project_json_entries,
    perform_pre_cleanup_for_planner,
)
from haijunbot.haijunbot_c2rust.llm_module_agent_validator import ProjectValidator
from haijunbot.haijunbot_utils.output import PrettyOutput


class LLMRustCratePlannerAgent:
    """
    Uses haijunbot_agent.Agent to call the LLM to generate a Rust crate plan (JSON).
    """

    def __init__(
        self,
        project_root: Union[Path, str] = ".",
        db_path: Optional[Union[Path, str]] = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.db_path = (
            Path(db_path).resolve()
            if db_path is not None
            else (self.project_root / ".haijunbot" / "c2rust" / "symbols.jsonl")
        )
        self.loader = GraphLoader(self.db_path, self.project_root)
        # Read additional notes
        self.additional_notes = self._load_additional_notes()

        # Initialize the prompt builder and validator
        self.prompt_builder = PromptBuilder(
            self.project_root,
            self.loader,
            self._crate_name,
            self._has_original_main,
            self._append_additional_notes,
        )
        self.validator = ProjectValidator(
            self._crate_name,
            self._has_original_main,
        )

    def _load_additional_notes(self) -> str:
        """Load additional notes from the config file"""
        try:
            from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON

            config_path = self.project_root / ".haijunbot" / "c2rust" / CONFIG_JSON
            if config_path.exists():
                with config_path.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                    if isinstance(config, dict):
                        return str(config.get("additional_notes", "") or "").strip()
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.llm_module_agent",
                function="_load_additional_notes",
            )
            pass
        return ""

    def _append_additional_notes(self, prompt: str) -> str:
        """
        Append additional notes to the end of the prompt (if present).

        Args:
            prompt: Original prompt

        Returns:
            The prompt with the additional notes appended
        """
        if self.additional_notes and self.additional_notes.strip():
            return (
                prompt
                + "\n\n"
                + "[Additional Notes (User-Defined)]\n"
                + self.additional_notes.strip()
            )
        return prompt

    def _crate_name(self) -> str:
        """
        Compute the crate name:
        - When project_root is the current directory, return "<current directory name>_rs"
        - Otherwise return the directory name of project_root
        - The output is used for naming/prompts, keeping the underscore style (does not affect the Cargo package name)
        """
        try:
            cwd = Path(".").resolve()
            if self.project_root.resolve() == cwd:
                base = f"{cwd.name}_rs"
            else:
                base = self.project_root.name or "c2rust_crate"
        except Exception:
            base = "c2rust_crate"
        return sanitize_mod_name(base)

    def _has_original_main(self) -> bool:
        """
        Determine whether the original project contains a main function:
        - If a function named 'main' exists in the symbols graph or a qualified name ends with '::main', consider it present
        """
        try:
            for m in self.loader.fn_by_id.values():
                n = (m.name or "").strip()
                q = (m.qname or "").strip()
                if n == "main" or q.endswith("::main"):
                    return True
        except Exception:
            # If an exception occurs during traversal, treat it as main not existing
            pass
        return False

    def _get_project_json_text(self, max_retries: int = 10) -> str:
        """
        Run the main flow and return the raw <PROJECT> JSON text without parsing.
        If format validation fails, retry automatically until it is satisfied or the maximum number of retries is reached.

        Args:
            max_retries: Maximum number of retries, default 10

        Raises:
            RuntimeError: The maximum number of retries was reached without producing valid output
        """
        # Generate context from translation_order.jsonl; no longer based on call graph traversal of symbols.jsonl
        roots_ctx = self.prompt_builder.build_roots_context_from_order()

        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(roots_ctx)
        base_summary_prompt = self.prompt_builder.build_summary_prompt(roots_ctx)

        last_error = "Unknown error"
        attempt = 0
        use_direct_model = False  # Flag whether to use direct model calls
        agent = None  # Declared outside the loop so it can be reused on retries

        while attempt < max_retries:
            attempt += 1
            # Use the base summary_prompt the first time; append feedback after a failure
            summary_prompt = (
                base_summary_prompt
                if attempt == 1
                else self.prompt_builder.build_retry_summary_prompt(
                    base_summary_prompt, last_error
                )
            )

            # Create the Agent the first time and reuse it on subsequent retries (if using direct model calls)
            if agent is None or not use_direct_model:
                agent = Agent(
                    system_prompt=system_prompt,
                    name="C2Rust-LLM-Module-Planner",
                    summary_prompt=summary_prompt,
                    need_summary=True,
                    auto_complete=True,
                    use_tools=["execute_script", "read_code"],
                    non_interactive=True,  # Non-interactive
                    use_methodology=False,
                    use_analysis=False,
                    enable_auto_rule_select=False,
                    quick_mode=True,
                )

            # Enter the main loop: the first round outputs only {ot('!!!COMPLETE!!!')} to trigger auto-completion; then the summary outputs the <PROJECT> block (JSON only)
            if use_direct_model:
                # After format validation fails, call the model interface directly
                # Construct a full prompt containing the summary prompt and the specific error information
                error_guidance = ""
                if last_error and last_error != "Unknown error":
                    if "JSON parsing failed" in last_error:
                        error_guidance = f"\n\n**Format error details (fix the output format based on the following error):**\n- {last_error}\n\nPlease ensure that the output JSON format is correct, including correct quotes, commas, braces, etc. Output only one <PROJECT> block, and the block should contain only the project structure definition in JSON format. jsonnet syntax is supported (such as trailing commas, comments, etc.)."
                    else:
                        error_guidance = f"\n\n**Format error details (fix the output format based on the following error):**\n- {last_error}\n\nPlease ensure that the output format is correct: output only one <PROJECT> block, and the block should contain only the project structure definition in JSON format. jsonnet syntax is supported (such as trailing commas, comments, etc.)."

                full_prompt = f"{user_prompt}{error_guidance}\n\n{summary_prompt}"
                try:
                    response = agent.model.chat_until_success(full_prompt)
                    summary_output = response
                except Exception as e:
                    PrettyOutput.auto_print(
                        f"[c2rust-llm-planner] Direct model call failed: {e}, falling back to run()"
                    )
                    summary_output = agent.run(user_prompt)
            else:
                # Use run() the first time to let the Agent run fully (it may use tools)
                summary_output = agent.run(user_prompt)

            project_text = str(summary_output) if summary_output is not None else ""
            json_text = self.validator.extract_json_from_project(project_text)

            # Try to parse and validate
            entries, parse_error_json = parse_project_json_entries(json_text)
            if parse_error_json:
                # JSON parsing failed; record the error and retry
                last_error = parse_error_json
                use_direct_model = True  # Format validation failed; use direct model calls for subsequent retries
                PrettyOutput.auto_print(
                    f"[c2rust-llm-planner] JSON parsing failed: {parse_error_json}"
                )
                continue

            ok, reason = self.validator.validate_project_entries(entries)
            if ok:
                return json_text
            else:
                last_error = reason
                use_direct_model = True  # Format validation failed; use direct model calls for subsequent retries

        # Maximum number of retries reached
        raise RuntimeError(
            f"Reached the maximum number of retries ({max_retries}) without producing a valid project structure."
            f"Last error: {last_error}"
        )

    def plan_crate_json_with_project(self) -> List[Any]:
        """
        Run the main flow and return the parsed JSON object (a list):
        - List items:
          * String: a file, e.g. "lib.rs"
          * Dict: a directory and its children, e.g. {"src/": [ ... ]}
        """
        json_text = self._get_project_json_text()
        json_entries, parse_error = parse_project_json_entries(json_text)
        if parse_error:
            raise RuntimeError(f"JSON parsing failed: {parse_error}")
        return json_entries

    def plan_crate_json_text(self) -> str:
        """
        Run the main flow but return the raw <PROJECT> JSON text without parsing.
        This makes it convenient to apply the directory structure as-is later and avoids information loss caused by early parse failures.
        """
        return self._get_project_json_text()


def plan_crate_json_text(
    project_root: Union[Path, str] = ".",
    db_path: Optional[Union[Path, str]] = None,
    skip_cleanup: bool = False,
) -> str:
    """
    Return the raw directory structure JSON text generated by the LLM (from the <PROJECT> block).
    Before planning, perform pre-cleanup and ask for user confirmation: delete the crate directory to be generated, the Cargo.toml workspace file in the current directory, and progress.json and symbol_map.jsonl under .haijunbot/c2rust.
    If the user does not agree, exit the program.
    When skip_cleanup=True, skip cleanup and confirmation (for cases already handled by the outer layer).
    """
    # If the outer layer has already handled cleanup confirmation, skip this function's cleanup and confirmation (to avoid asking twice)
    if skip_cleanup:
        agent = LLMRustCratePlannerAgent(project_root=project_root, db_path=db_path)
        return agent.plan_crate_json_text()

    perform_pre_cleanup_for_planner(project_root)

    agent = LLMRustCratePlannerAgent(project_root=project_root, db_path=db_path)
    return agent.plan_crate_json_text()


def plan_crate_json_llm(
    project_root: Union[Path, str] = ".",
    db_path: Optional[Union[Path, str]] = None,
    skip_cleanup: bool = False,
) -> List[Any]:
    """
    Convenience function: use the LLM to generate a Rust crate module plan (a parsed object).
    Before planning, perform pre-cleanup and ask for user confirmation: delete the crate directory to be generated, the Cargo.toml workspace file in the current directory, and progress.json and symbol_map.jsonl under .haijunbot/c2rust.
    If the user does not agree, exit the program.
    When skip_cleanup=True, skip cleanup and confirmation (for cases already handled by the outer layer).
    """
    # If the outer layer has already handled cleanup confirmation, skip this function's cleanup and confirmation (to avoid asking twice)
    if skip_cleanup:
        agent = LLMRustCratePlannerAgent(project_root=project_root, db_path=db_path)
        return agent.plan_crate_json_with_project()

    perform_pre_cleanup_for_planner(project_root)

    agent = LLMRustCratePlannerAgent(project_root=project_root, db_path=db_path)
    return agent.plan_crate_json_with_project()


__all__ = [
    "LLMRustCratePlannerAgent",
    "plan_crate_json_text",
    "plan_crate_json_llm",
    "execute_llm_plan",  # Backward compatible
    "entries_to_json",  # Backward compatible
    "apply_project_structure_from_json",  # Backward compatible
]
