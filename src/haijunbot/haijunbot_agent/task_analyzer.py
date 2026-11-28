# -*- coding: utf-8 -*-
"""
Task analyzer module
Responsible for handling task analysis and methodology generation
"""

from typing import Any, List

from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_TOOL_CALL
from haijunbot.haijunbot_agent.prompts import get_task_analysis_prompt
from haijunbot.haijunbot_agent.utils import join_prompts
from haijunbot.haijunbot_utils.globals import get_interrupt
from haijunbot.haijunbot_utils.globals import set_interrupt
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.exception_utils import save_exception

# Task analysis prompt when native function calling is active: keep the original decision logic, just modernize the language and drop text JSON
_NATIVE_TASK_ANALYSIS_PROMPT = """Do a retrospective on the task that just ended. When an action is needed, **call the tool directly**; do not output JSON text. Judge in the following order:

1. **Rule analysis (rule)**: first check whether existing rules already cover this task's solution—
   - Check whether the current project's global/project rules (.haijunbot/rules/, excluding builtin/rules/ built-in rules) have any gaps.
   - If existing rules already cover it: just state which one to use; no need to create a new one.
   - If there is indeed an obvious gap and it is worth supplementing: briefly describe the suggestion (optional); if not, do not mention it.
2. **Memory consolidation (memory)**: use memory(action=save) to save information worth keeping long-term:
   - project_long_term: project-related (architecture decisions, key conventions, important implementations)
   - global_long_term: general experience, user preferences, methods and techniques
   If there is nothing worth saving, do not save.
3. **Tool generation (meta_agent)**: only when existing rules/tools cannot cover it and the task is truly worth automating:
   - Generate with meta_agent (write the target functionality and expected behavior clearly in function_description; the tool must include parameter definitions and error handling).
   - If existing tools already cover it, just use them directly; do not generate.
4. Finally, summarize the conclusion of this retrospective in one sentence.

Rules: be fact-based, do not fabricate; prefer omission over excess; prioritize rule/memory, use meta_agent only when truly worthwhile, and do not generate for the sake of generating."""


class TaskAnalyzer:
    """Task analyzer, responsible for task analysis and satisfaction feedback handling"""

    def __init__(self, agent: Any) -> None:
        """
        Initialize the task analyzer

        Args:
            agent: Agent instance
        """
        self.agent: Any = agent
        self._analysis_done: bool = False
        # Collect information during task execution, used for methodology extraction
        self._execution_steps: List[str] = []
        self._tool_calls: List[str] = []

    def analysis_task(self, satisfaction_feedback: str = "") -> None:
        """Analyze the task and generate methodology"""

        try:
            # Prepare the analysis prompt
            self.agent.session.prompt = self._prepare_analysis_prompt(
                satisfaction_feedback
            )

            if not self.agent.model:
                raise RuntimeError("Model not initialized")

            # Loop through tool calls until there are no more
            self._process_analysis_loop()

        except Exception:
            PrettyOutput.auto_print("❌ Analysis failed")
        finally:
            # Mark that an analysis has completed, to avoid repeated execution by event callbacks
            self._analysis_done = True
            try:
                self.agent.set_user_data("__task_analysis_done__", True)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.task_analyzer", function="analysis_task"
                )
                pass

    def _prepare_analysis_prompt(self, satisfaction_feedback: str) -> str:
        """Prepare the analysis prompt"""
        # Check whether the memory tool is available (tool availability)
        has_memory_tool = False
        # Check whether the meta_agent tool is available (formerly generate_new_tool, a self-bootstrapping tool generator)
        has_generate_new_tool = False
        try:
            tool_registry = self.agent.get_tool_registry()
            if tool_registry:
                # Check the memory tool
                memory_tool = tool_registry.get_tool("memory")
                has_memory_tool = memory_tool is not None

                # Check the meta_agent tool
                generate_tool = tool_registry.get_tool("meta_agent")
                has_generate_new_tool = generate_tool is not None
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.task_analyzer",
                function="_prepare_analysis_prompt",
            )
            pass

        # When native function calling is active, use a concise modern prompt (tools called directly, no text JSON)
        if self.agent._native_active():
            analysis_prompt = _NATIVE_TASK_ANALYSIS_PROMPT
        else:
            # Text protocol path: use the historical prompt with the JSON call format description
            analysis_prompt = get_task_analysis_prompt(
                has_memory_tool=has_memory_tool,
                has_generate_new_tool=has_generate_new_tool,
            )

        # All inputs are str; join_prompts necessarily returns str
        return join_prompts([analysis_prompt, satisfaction_feedback])  # ty: ignore[invalid-return-type]

    def _process_analysis_loop(self) -> None:
        """Process the analysis loop"""
        while True:
            # When native function calling is active, use Agent._invoke_model's native channel:
            # tools (memory/meta_agent, etc.) are executed by the internal native loop and trigger AFTER_TOOL_CALL,
            # no longer parsed via text JSON.
            if (
                self.agent._native_active()
                and isinstance(self.agent.session.prompt, str)
                and self.agent.session.prompt.strip()
            ):
                try:
                    self.agent._run_native_until_content(self.agent.session.prompt)
                finally:
                    self.agent.session.prompt = ""
                return

            response = self.agent.model.chat_until_success(self.agent.session.prompt)
            self.agent.session.prompt = ""

            # Handle user interruption
            if get_interrupt():
                if not self._handle_analysis_interrupt(response):
                    break

            # Execute tool calls (supplementary events: before_tool_call/after_tool_call)
            try:
                self.agent.event_bus.emit(
                    BEFORE_TOOL_CALL,
                    agent=self.agent,
                    current_response=response,
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.task_analyzer",
                    function="_process_analysis_loop",
                )
                pass
            need_return, tool_prompt = self.agent._call_tools(response)
            self.agent.session.prompt = tool_prompt
            try:
                self.agent.event_bus.emit(
                    AFTER_TOOL_CALL,
                    agent=self.agent,
                    current_response=response,
                    need_return=need_return,
                    tool_prompt=tool_prompt,
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.task_analyzer",
                    function="_process_analysis_loop",
                )
                pass

            # If there are no tool calls or no new prompt, exit the loop
            if not self.agent.session.prompt:
                break

    def _handle_analysis_interrupt(self, response: str) -> bool:
        """Handle a user interruption during analysis

        Returns:
            bool: True to continue analysis, False to exit analysis
        """
        set_interrupt(False)
        user_input = self.agent._multiline_input(
            "Interrupted during analysis; please enter intervention information", False
        )

        if not user_input:
            # The user input is empty; exit the analysis
            return False

        if self._has_tool_calls(response):
            self.agent.session.prompt = self._handle_interrupt_with_tool_calls(
                user_input
            )
        else:
            self.agent.session.prompt = f"The task was interrupted by the user; the user's supplementary information is: {user_input}"

        return True

    def _has_tool_calls(self, response: str) -> bool:
        """Check whether the response contains tool calls"""
        return any(
            handler.can_handle(response) for handler in self.agent.output_handler
        )

    def _handle_interrupt_with_tool_calls(self, user_input: str) -> str:
        """Handle an interruption when there are tool calls"""
        if self.agent.confirm_callback("Tool calls detected; continue execution?", False):
            # All inputs are str; join_prompts necessarily returns str
            return join_prompts(  # ty: ignore[invalid-return-type]
                [
                    f"The task was interrupted by the user; the user's supplementary information is: {user_input}",
                    "The user allows continuing the tool calls.",
                ]
            )
        else:
            # All inputs are str; join_prompts necessarily returns str
            return join_prompts(  # ty: ignore[invalid-return-type]
                [
                    f"The task was interrupted by the user; the user's supplementary information is: {user_input}",
                    "Tool calls were detected but rejected by the user. Please reconsider the next step based on the user's supplementary information.",
                ]
            )

    def collect_satisfaction_feedback(self, auto_completed: bool) -> str:
        """Collect satisfaction feedback"""
        satisfaction_feedback: str = ""

        # If the current agent is a CodeAgent, skip satisfaction collection
        if self.agent.agent_type() == "code_agent":
            return ""

        if not auto_completed and self.agent.use_analysis:
            if self.agent.confirm_callback("The task is complete; are you satisfied?", True):
                satisfaction_feedback = "The user is satisfied with the completion of this task."
            else:
                feedback = self.agent._multiline_input(
                    "Please provide improvement feedback (press Enter to skip)", False
                )
                if feedback:
                    satisfaction_feedback = (
                        f"The user is not satisfied with the completion of this task; feedback is as follows:\n{feedback}"
                    )
                else:
                    satisfaction_feedback = (
                        "The user is not satisfied with the completion of this task but did not provide specific feedback."
                    )
        elif auto_completed and self.agent.use_analysis:
            # In auto-complete mode, still perform the analysis but do not collect user feedback
            satisfaction_feedback = "The task completed automatically; no user feedback needed."

        return satisfaction_feedback

    def trigger_task_analysis(self, auto_completed: bool = False) -> None:
        """Trigger task analysis and satisfaction collection

        This method replaces the original event-driven mechanism and is called directly by the Agent

        Args:
            auto_completed: Whether this is auto-complete mode
        """
        if self._analysis_done:
            return
        # Avoid repeated execution
        try:
            if bool(self.agent.get_user_data("__task_analysis_done__")):
                self._analysis_done = True
                return
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.task_analyzer", function="trigger_task_analysis"
            )
            pass

        # After task completion, task analysis is enabled by default (default True); no longer distinguished by scenario
        if not self.agent.confirm_callback(
            "The task is complete. Perform task analysis (save memory, generate methodology, etc.)?",
            True,
        ):
            self._analysis_done = True
            return

        # Perform task analysis in non-interactive mode or after user confirmation
        try:
            feedback = self.collect_satisfaction_feedback(auto_completed)
            self.analysis_task(feedback)
        except Exception:
            # Ignore exceptions to keep the main flow
            self._analysis_done = True

    def _collect_execution_steps(self) -> List[str]:
        """Collect execution steps from the conversation history"""
        steps: List[str] = []
        try:
            # Try to extract from the model's conversation history
            if hasattr(self.agent, "model") and self.agent.model:
                history = getattr(self.agent.model, "_history", [])
                for msg in history:
                    if isinstance(msg, dict):
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "assistant" and content:
                            # Extract key steps (simplified handling)
                            lines = content.split("\n")
                            for line in lines:
                                line = line.strip()
                                # Recognize step markers
                                if line and (
                                    line.startswith(("1.", "2.", "3.", "4.", "5."))
                                    or line.startswith(("-", "*", "•"))
                                    or "step" in line.lower()
                                    or "execute" in line.lower()
                                ):
                                    if len(line) > 10 and len(line) < 200:
                                        steps.append(line)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.task_analyzer",
                function="_collect_execution_steps",
            )
            pass
        return steps[:20]  # Limit the number of steps
