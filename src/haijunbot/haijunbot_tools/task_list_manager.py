"""Task list management tool.

This tool allows the LLM to manage task lists, including creating task lists, adding tasks, updating task status, etc.
"""

import json
import re


from haijunbot.haijunbot_utils.output import (
    PrettyOutput,
    emit_output,
    OutputEvent,
    OutputType,
)

# -*- coding: utf-8 -*-
from typing import Dict, List, Optional, Any

from haijunbot.haijunbot_agent.task_list import TaskStatus
from haijunbot.haijunbot_utils.config import (
    calculate_token_limit,
    get_max_input_token_count,
    get_llm_group,
    save_exception,
)
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.git_utils import (
    get_latest_commit_hash,
    get_diff_between_commits,
)


class DependencyValidationError(Exception):
    """Base class for dependency validation errors"""

    pass


class DependencyNotFoundError(DependencyValidationError):
    """Dependency task does not exist error"""

    pass


class DependencyNotCompletedError(DependencyValidationError):
    """Dependency task not completed error"""

    pass


class DependencyFailedError(DependencyValidationError):
    """Dependency task failed error"""

    pass


def _calculate_default_max_output_length(agent: Any = None) -> int:
    """Calculate the default maximum output length based on the current model configuration

    Parameters:
        agent: Agent instance, used to obtain the model configuration

    Returns:
        int: Default maximum output length (number of characters)
    """
    try:
        # If there is an agent instance, prefer to use the agent's model configuration
        if agent and hasattr(agent, "model"):
            try:
                # Try to obtain the maximum input token count from the agent's model
                max_input_tokens = (
                    agent.model.get_max_input_token_count()
                    if hasattr(agent.model, "get_max_input_token_count")
                    else get_max_input_token_count()
                )
            except Exception:
                max_input_tokens = get_max_input_token_count()
        else:
            max_input_tokens = get_max_input_token_count()

        # Calculate the token count of the 1/3 limit (a more conservative fallback), then convert to character count
        limit_tokens = int(max_input_tokens * 1 / 3)
        limit_chars = limit_tokens * 4
        # Ensure a reasonable positive number is returned
        return max(1000, limit_chars)  # Minimum 1000 characters, avoid too small a limit
    except Exception:
        # If obtaining fails, return a relatively safe default value
        return 4000  # 4000 characters as the final fallback value


class task_list_manager:
    """Task list management tool, for the LLM to call"""

    name = "task_list_manager"

    def _get_max_output_length(self, agent: Any = None) -> int:
        """Obtain the maximum output length based on the remaining token count (number of characters)

        Parameters:
            agent: Agent instance, used to obtain the model and remaining token count

        Returns:
            int: The maximum allowed number of characters (calculated based on remaining tokens, with a safety margin reserved)
        """
        try:
            # Prefer to use the remaining token count
            if agent and hasattr(agent, "model"):
                try:
                    remaining_tokens = agent.model.get_remaining_token_count()
                    # Use the smaller of 2/3 of the remaining tokens or 64k
                    # Rough estimate: 1 token is approximately equal to 4 characters (Chinese may be fewer, but use a conservative estimate)
                    limit_tokens = calculate_token_limit(remaining_tokens)
                    # Convert to character count (conservative estimate: 1 token = 4 characters)
                    limit_chars = limit_tokens * 4
                    # Ensure at least a reasonable value is returned
                    if limit_chars > 0:
                        return limit_chars
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.task_list_manager",
                        function="_get_max_output_length",
                    )
                    pass

            # Fallback: use 2/3 of the input window
            max_input_tokens = get_max_input_token_count()
            # Calculate the token count of the 2/3 limit, then convert to character count
            limit_tokens = int(max_input_tokens * 2 / 3)
            limit_chars = limit_tokens * 4
            return limit_chars
        except Exception:
            # If obtaining fails, use the dynamically calculated value based on the current model configuration
            return _calculate_default_max_output_length(agent)

    def _get_truncate_lengths(self, max_length: int) -> tuple[int, int]:
        """Calculate the prefix and suffix lengths when truncating based on the maximum length

        Parameters:
            max_length: Maximum length (number of characters)

        Returns:
            tuple[int, int]: (prefix length, suffix length)
        """
        # Prefix accounts for 80%, suffix accounts for 20%
        prefix_length = int(max_length * 0.8)
        suffix_length = int(max_length * 0.2)
        return prefix_length, suffix_length

    def _get_task_list_id(self, agent: Any) -> Optional[str]:
        """Obtain task_list_id from the Agent's user_data

        Parameters:
            agent: Agent instance

        Returns:
            Optional[str]: task_list_id, returns None if it does not exist
        """
        if not agent:
            return None
        try:
            result = agent.get_user_data("__task_list_id__")
            return str(result) if result is not None else None
        except Exception:
            return None

    def _get_running_task_id(self, agent: Any) -> Optional[str]:
        """Obtain the running task_id from the Agent's user_data

        Parameters:
            agent: Agent instance

        Returns:
            Optional[str]: task_id, returns None if it does not exist
        """
        if not agent:
            return None
        try:
            result = agent.get_user_data("__running_task_id__")
            return str(result) if result is not None else None
        except Exception:
            return None

    def _set_running_task_id(self, agent: Any, task_id: Optional[str]) -> None:
        """Save the running task_id to the Agent's user_data

        Parameters:
            agent: Agent instance
            task_id: Task ID, when None it means clear
        """
        if not agent:
            return
        try:
            if task_id is None:
                # Clear running_task_id in user_data
                agent.delete_user_data("__running_task_id__")
            else:
                agent.set_user_data("__running_task_id__", task_id)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.task_list_manager",
                function="_set_running_task_id",
            )
            pass

    def _increment_task_conversation_round(
        self, agent: Any, task_list_manager: Any, task_list_id: str
    ) -> None:
        """Event callback: increment the conversation round of the running task

        Parameters:
            agent: Agent instance
            task_list_manager: TaskListManager instance
            task_list_id: Task list ID
        """
        if not agent or not task_list_manager:
            return

        try:
            # Get the running task ID
            task_id = self._get_running_task_id(agent)
            if not task_id:
                return

            # Get the task list and task
            task_list = task_list_manager.get_task_list(task_list_id)
            if not task_list:
                return

            task = task_list.get_task(task_id)
            if not task:
                return

            # Only the main task in running state increments the model call count
            if task.status.value == "running" and task.agent_type.value == "main":
                task.model_call_count += 1

        except Exception:
            # Exceptions do not affect the main flow
            pass

    def _unsubscribe_model_call_event(self, agent: Any) -> None:
        """Unsubscribe from the model call event

        Parameters:
            agent: Agent instance
        """
        if not agent:
            return
        try:
            # Get the previously saved callback function
            from haijunbot.haijunbot_agent.events import BEFORE_MODEL_CALL

            callback = agent.get_user_data("__model_call_callback__")
            if callback:
                agent.event_bus.unsubscribe(BEFORE_MODEL_CALL, callback)
                # Clear the saved callback reference
                agent.delete_user_data("__model_call_callback__")
        except Exception:
            # Unsubscribe failure does not affect the main flow
            pass

    def _set_task_list_id(self, agent: Any, task_list_id: str) -> None:
        """Save task_list_id to the Agent's user_data

        Parameters:
            agent: Agent instance
            task_list_id: Task list ID
        """
        if not agent:
            return
        try:
            agent.set_user_data("__task_list_id__", task_list_id)
        except Exception as e:
            save_exception(
                e, module="haijunbot_tools.task_list_manager", function="_set_task_list_id"
            )
            pass

    def _determine_agent_type(
        self, agent: Any, task: Any, task_content: str, background: str
    ) -> bool:
        """Determine directly based on the agent instance whether it is a code-related task

        Parameters:
            agent: The currently executing agent instance
            task: Task object
            task_content: Task content
            background: Background information

        Returns:
            bool: True indicates a code-related task, False indicates a general task
        """
        try:
            # Determine directly based on the agent instance type
            from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

            return isinstance(agent, CodeAgent)
        except ImportError:
            # If the import fails, fall back to the general Agent
            return False

    def _create_verification_agent(
        self,
        task: Any,
        parent_agent: Any,
        verification_iteration: int = 1,
        verification_method: str = "",
    ) -> Any:
        """Create a verification Agent, which can only use the read_code and execute_script tools

        Parameters:
            task: Task object
            parent_agent: Parent Agent instance
            verification_iteration: Verification iteration count
            verification_method: Verification method description, describing how to verify whether the task is truly completed

        Returns:
            Agent: Verification Agent instance
        """
        from haijunbot.haijunbot_agent import Agent

        # Build the verification method description section
        verification_method_section = ""
        if verification_method and str(verification_method).strip():
            verification_method_section = f"""\n\n**Verification method description (provided by the task executor):**
{verification_method}

Please verify strictly according to the above verification method; this is the acceptance method specified by the task executor."""

        # Build the system prompt for the verification task
        verification_system_prompt = f"""You are a task verification expert. Your responsibility is to verify whether a task is truly completed, and to only verify the task's expected outputs and artifacts.

**Task information:**
- Task name: {task.task_name}
- Task description: {task.task_desc}
- Expected outputs (please list each item, e.g., 1), 2), 3) or a markdown list): {task.expected_output}{verification_method_section}

**Verification requirements:**
1. Parse the expected outputs into a set of [item-by-item] expected result entries (split by line breaks, numbering 1), 2), 3) or markdown list)
2. Verify each expected result individually: check whether the corresponding code, file, or other artifact actually exists and satisfies that requirement
3. Use the read_code tool to check whether the code or files produced by the task conform to the corresponding entries
4. Only check whether the artifacts explicitly required by the task exist and are correct
5. Do not verify items unrelated to the task's expected outputs (such as overall project compilation, unrelated tests, etc.)
6. Focus on the specific deliverables explicitly mentioned in the task description

**Verification criteria:**
- Whether each expected output has actually generated the corresponding artifact
- Whether the content of each output conforms to the specific requirements in the task description
- Do not verify unrelated compilation status, test coverage, or code style

**Important restrictions (mandatory):**
- Verification can only be performed using the read_code and execute_script tools
- You must base your work on actual verification results; do not speculate or assume
- Only verify the task's expected outputs and directly related artifacts
- If all verifications pass, output only {ot("!!!COMPLETE!!!")}, do not output any other content
- **Actual fixing is prohibited**: Strictly forbidden to perform any code modification, file operation, or configuration change
- **Giving fix suggestions is allowed**: You may analyze the cause of the problem and provide specific fix suggestions and guidance
- **Clearly distinguish suggestions from execution**: You may say "how it should be fixed," but should emphasize that this is only a suggestion
"""

        # Build the summary prompt for the verification task (structured format requirements)
        verification_summary_prompt = f"""Please summarize the task verification results in a structured format, strictly following the template below:

## Task verification results

**Task name**: {task.task_name}

**Verification status**: [PASSED/FAILED]

**Final conclusion**: [VERIFICATION_PASSED or VERIFICATION_FAILED]

**Item-by-item verification results**:
- List each expected output entry and its verification result one by one, format example:
  - Item 1: [PASSED/FAILED] explanation...
  - Item 2: [PASSED/FAILED] explanation...
  - Item 3: [PASSED/FAILED] explanation...

**Explanation**:
- If verification passes: output "All expected output entries have been verified"
- If verification fails: explain in detail the reasons for failure, including:
  * Which expected output entries were not found or are incomplete
  * The specific differences between the actual output and the expectations of each entry
  * The parts that need to be supplemented or corrected

**Important**:
- You must output strictly according to the above format
- The verification status must be PASSED or FAILED
- The final conclusion must be "VERIFICATION_PASSED" or "VERIFICATION_FAILED"
- **Fix suggestions are allowed**: You may analyze the problem in detail and provide specific fix guidance
- **Actual fixing is prohibited**: Strictly forbidden to perform any code modification or file operation
"""

        # Get the parent Agent's model group
        # Prefer to use the parent Agent's llm_group, because the global model group may not have been set correctly yet (timing issue)
        llm_group = None
        try:
            if parent_agent is not None:
                # Prefer to obtain llm_group from the parent Agent
                llm_group = getattr(parent_agent, "llm_group", None)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_tools.task_list_manager",
                function="_create_verification_agent",
            )
            pass

        # Only use the current model group if the parent Agent has no llm_group
        if llm_group is None:
            llm_group = get_llm_group()

        # Determine whether the smart model needs to be used (CodeAgent tasks use the smart model)
        model_type = "normal"
        try:
            from haijunbot.haijunbot_code_agent.code_agent import CodeAgent

            if parent_agent is not None and isinstance(parent_agent, CodeAgent):
                model_type = "smart"
        except ImportError:
            pass

        verification_agent = Agent(
            system_prompt=verification_system_prompt,
            name=f"verification_agent_{task.task_id}_{verification_iteration}",
            description="Task verification agent (read-only verification)",
            summary_prompt=verification_summary_prompt,
            auto_complete=True,
            need_summary=True,
            use_tools=["read_code", "execute_script"],
            non_interactive=True,
            use_methodology=False,
            use_analysis=False,
            model_type=model_type,
        )

        return verification_agent

    def _build_task_content(
        self, task: Any, parent_agent: Any = None, additional_info: str = ""
    ) -> str:
        """Build the task content

        Parameters:
            task: Task object
            parent_agent: Parent Agent instance (used to obtain memory tags)
            additional_info: Additional information

        Returns:
            str: Formatted task content
        """
        task_desc = task.task_desc

        # Get the parent Agent's memory tags and add them to the task description
        memory_tags_info = ""
        if parent_agent:
            try:
                memory_tags = parent_agent.get_memory_tags()
                if memory_tags:
                    memory_tags_info = f"\n\nParent Agent memory tags: {', '.join(memory_tags)}\nTip: These tags can help you recall relevant information through memory."
            except Exception:
                # Failure to obtain memory tags does not affect task execution
                pass

        if additional_info and str(additional_info).strip():
            separator = "\n" + "=" * 50 + "\n"
            task_desc = f"{task.task_desc}{separator}Additional information:\n{additional_info}"

        # Add the memory tag information to the end of the task description
        if memory_tags_info:
            task_desc = f"{task_desc}{memory_tags_info}"

        return f"""Task name: {task.task_name}

Task description:
{task_desc}

Expected output:
{task.expected_output}"""

    def _build_task_background(
        self,
        task_list_manager: Any,
        task_list_id: str,
        task: Any,
        agent_id: str,
        is_main_agent: bool,
        include_completed_summary: bool = True,
    ) -> str:
        """Build task background information

        Parameters:
            task_list_manager: Task list manager
            task_list_id: Task list ID
            task: Task object
            agent_id: Agent ID
            is_main_agent: Whether it is the main Agent
            include_completed_summary: Whether to include summaries of other completed tasks

        Returns:
            str: Formatted background information
        """
        background_parts = []

        # 1. Get the task list's main_goal as global context
        task_list = task_list_manager.get_task_list(task_list_id)
        if task_list:
            background_parts.append(f"Global goal: {task_list.main_goal}")

        # 2. Get the outputs of dependency tasks as background information
        if task.dependencies:
            dep_outputs = []
            for dep_id in task.dependencies:
                dep_task, dep_success, _ = task_list_manager.get_task_detail(
                    task_list_id=task_list_id,
                    task_id=dep_id,
                    agent_id=agent_id,
                    is_main_agent=is_main_agent,
                )
                if dep_success and dep_task:
                    if dep_task.actual_output:
                        dep_outputs.append(
                            f"Dependency task [{dep_task.task_name}] output:\n{dep_task.actual_output}"
                        )
                    elif dep_task.status == TaskStatus.COMPLETED:
                        # Even without output, it indicates the dependency task is completed
                        dep_outputs.append(
                            f"Dependency task [{dep_task.task_name}] completed (status: {dep_task.status.value})"
                        )

            if dep_outputs:
                background_parts.append("Dependency task information:\n" + "\n\n".join(dep_outputs))

        # 3. Get summary information of other completed tasks (optional)
        if include_completed_summary and task_list:
            completed_tasks = [
                t
                for t in task_list.tasks.values()
                if t.status == TaskStatus.COMPLETED
                and t.task_id != task.task_id
                and t.task_id not in (task.dependencies or [])
            ]
            if completed_tasks:
                # Only include brief information for the first 3 completed tasks to avoid overly long context
                completed_summary = []
                for completed_task in completed_tasks[:3]:
                    summary = (
                        f"- [{completed_task.task_name}]: {completed_task.task_desc}"
                    )
                    if completed_task.actual_output:
                        # Only take the first 200 characters of the output as a summary
                        output_preview = completed_task.actual_output[:200]
                        if len(completed_task.actual_output) > 200:
                            output_preview += "..."
                        summary += f"\n  Output summary: {output_preview}"
                    completed_summary.append(summary)

                if completed_summary:
                    background_parts.append(
                        "Other completed tasks (reference information):\n" + "\n".join(completed_summary)
                    )

        return "\n\n".join(background_parts) if background_parts else ""

    def _build_iteration_task_content(
        self, task_content: str, iteration: int, all_verification_results: list
    ) -> str:
        """Second and subsequent iterations: append the previous verification feedback to the task content."""
        if iteration <= 1 or not all_verification_results:
            return task_content
        return f"""{task_content}

**Previous verification feedback (issues that need fixing):**
{all_verification_results[-1]}

Please fix the issues based on the above verification feedback to ensure the task is truly completed.
"""

    def _run_sub_execution(
        self,
        is_code_task: bool,
        parent_agent: Any,
        agent_name: str,
        enhanced_task_content: str,
        background: str,
    ) -> dict:
        """Dispatch to sub_code_agent / sub_agent for execution based on task type."""
        if is_code_task:
            from haijunbot.haijunbot_tools.sub_code_agent import SubCodeAgentTool

            tool = SubCodeAgentTool()
        else:
            from haijunbot.haijunbot_tools.sub_agent import SubAgentTool

            tool = SubAgentTool()

        return tool.execute(
            {
                "task": enhanced_task_content,
                "background": background,
                "name": agent_name,
                "agent": parent_agent,
                "quick_mode": getattr(parent_agent, "quick_mode", False),
            }
        )

    def _verify_task_completion(
        self,
        task: Any,
        task_content: str,
        background: str,
        parent_agent: Any,
        verification_iteration: int = 1,
        verification_method: str = "",
    ) -> tuple[bool, str]:
        """Verify whether the task is truly completed

        Parameters:
            task: Task object
            task_content: Task content
            background: Background information
            parent_agent: Parent Agent instance
            verification_iteration: Verification iteration count
            verification_method: Verification method description, describing how to verify whether the task is truly completed

        Returns:
            tuple[bool, str]: (is completed, verification result or failure reason)
        """
        try:
            # Create verification Agent
            verification_agent = self._create_verification_agent(
                task, parent_agent, verification_iteration, verification_method
            )

            # Build verification task
            verification_task = f"""Please verify whether the following task is truly completed, and verify each item in the expected output separately:

{task_content}

Background information:
{background}

Please use the read_code and execute_script tools to verify, focusing on:
1. Parse the expected output into multiple concrete items (split by line breaks / numbering 1), 2), 3) / markdown lists, etc.)
2. For each expected output item, check whether there is corresponding code, file, or other actual artifact support
3. If an item has no corresponding artifact, the artifact is incomplete, or it does not match the description, mark it individually as FAILED and explain the reason
4. Only when [all] expected output items pass verification can the overall result be judged as PASSED

If there are compilation errors, runtime errors, test failures, or any expected output item does not meet the requirements, you must clearly mark the whole thing as incomplete and detail the reasons.
"""

            PrettyOutput.auto_print(
                f"🔍 Starting verification of task [{task.task_name}] (verification attempt {verification_iteration})..."
            )

            # Execute verification
            verification_result = verification_agent.run(verification_task)

            # Parse verification result (extracted from the structured summary)
            if verification_result:
                verification_result_str = str(verification_result)

                # Attempt to extract the verification status from the structured format
                verification_status = None
                final_conclusion = None

                # Find the verification status
                import re

                status_match = re.search(
                    r"\*\*Verification Status\*\*：\s*\[(PASSED|FAILED)\]", verification_result_str
                )
                if status_match:
                    verification_status = status_match.group(1)

                # Find the final conclusion
                conclusion_match = re.search(
                    r"\*\*Final Conclusion\*\*：\s*\[(VERIFICATION_PASSED|VERIFICATION_FAILED)\]",
                    verification_result_str,
                )
                if conclusion_match:
                    final_conclusion = conclusion_match.group(1)

                # Determine whether verification passed
                is_passed = False
                if (
                    verification_status == "PASSED"
                    or final_conclusion == "VERIFICATION_PASSED"
                ):
                    is_passed = True
                elif (
                    verification_status == "FAILED"
                    or final_conclusion == "VERIFICATION_FAILED"
                ):
                    is_passed = False
                elif "VERIFICATION_PASSED" in verification_result_str.upper():
                    is_passed = True
                elif "VERIFICATION_FAILED" in verification_result_str.upper():
                    is_passed = False
                else:
                    # If it cannot be extracted from the structured format, try to find keywords
                    if (
                        "verification passed" in verification_result_str
                        or "all verifications passed" in verification_result_str
                    ):
                        is_passed = True
                    elif (
                        "verification failed" in verification_result_str
                        or "verification did not pass" in verification_result_str
                    ):
                        is_passed = False
                    else:
                        # Default to considering it not passed
                        is_passed = False

                if is_passed:
                    PrettyOutput.auto_print(f"✅ Task [{task.task_name}] verification passed")
                    # Send to frontend
                    try:
                        emit_output(
                            OutputEvent(
                                text=f"✅ Task [{task.task_name}] verification passed",
                                output_type=OutputType.INFO,
                                timestamp=None,
                                context={
                                    "_gateway_skip": True,
                                    "task_id": task.task_id,
                                    "task_name": task.task_name,
                                    "status": "verified",
                                },
                            )
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.task_list_manager",
                            function="_verify_task_completion",
                        )
                        pass
                    return True, verification_result_str
                else:
                    # Directly use the complete verification result as the failure reason
                    PrettyOutput.auto_print(
                        f"❌ Task [{task.task_name}] verification failed: {verification_result_str[:200]}..."
                    )
                    # Send to frontend
                    try:
                        emit_output(
                            OutputEvent(
                                text=f"❌ Task [{task.task_name}] verification failed",
                                output_type=OutputType.WARNING,
                                timestamp=None,
                                context={
                                    "_gateway_skip": True,
                                    "task_id": task.task_id,
                                    "task_name": task.task_name,
                                    "status": "verification_failed",
                                    "verification_result": verification_result_str[
                                        :500
                                    ],
                                },
                            )
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.task_list_manager",
                            function="_verify_task_completion",
                        )
                        pass
                    return False, verification_result_str
            else:
                PrettyOutput.auto_print(
                    f"⚠️ Task [{task.task_name}] has no verification result, defaulting to considering it incomplete"
                )
                # Send to frontend
                try:
                    emit_output(
                        OutputEvent(
                            text=f"⚠️ Task [{task.task_name}] has no verification result, defaulting to considering it incomplete",
                            output_type=OutputType.WARNING,
                            timestamp=None,
                            context={
                                "_gateway_skip": True,
                                "task_id": task.task_id,
                                "task_name": task.task_name,
                                "status": "verification_no_result",
                            },
                        )
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.task_list_manager",
                        function="_verify_task_completion",
                    )
                    pass
                return False, "No verification result"

        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ Exception occurred while verifying task [{task.task_name}]: {str(e)}"
            )
            # Send to frontend
            try:
                emit_output(
                    OutputEvent(
                        text=f"⚠️ Exception occurred while verifying task [{task.task_name}]: {str(e)}",
                        output_type=OutputType.WARNING,
                        timestamp=None,
                        context={
                            "_gateway_skip": True,
                            "task_id": task.task_id,
                            "task_name": task.task_name,
                            "status": "verification_error",
                        },
                    )
                )
            except Exception as inner_e:
                save_exception(
                    inner_e,
                    module="haijunbot_tools.task_list_manager",
                    function="_verify_task_completion",
                )
                pass
            return False, f"Verification exception: {str(e)}"

    def _extract_task_number(self, task_id: str) -> int:
        """Extract the numeric part from task_id for sorting

        Parameters:
            task_id: Task ID in the format task-{number}

        Returns:
            Task number; returns 999999 if extraction fails (sorted last)
        """
        try:
            match = re.search(r"\d+", task_id)
            if match:
                return int(match.group())
            return 999999
        except (ValueError, AttributeError):
            return 999999

    def _print_task_list_status(
        self, task_list_manager: Any, task_list_id: Optional[str] = None
    ) -> None:
        """Print task list status

        Parameters:
            task_list_manager: Task list manager instance
            task_list_id: Task list ID (if None, nothing is printed)
        """
        try:
            # Determine the task list to print
            task_lists_to_print = {}
            if task_list_id:
                task_list = task_list_manager.get_task_list(task_list_id)
                if task_list:
                    task_lists_to_print[task_list_id] = task_list

            if not task_lists_to_print:
                return

            for tlist_id, task_list in task_lists_to_print.items():
                tasks = list(task_list.tasks.values())
                if not tasks:
                    continue

                # Sort ascending by the numeric part of task_id
                def extract_task_number(task_id: str) -> int:
                    """Extract the numeric part from task_id"""
                    try:
                        return int(task_id.split("-")[1])
                    except (IndexError, ValueError):
                        return 999999

                sorted_tasks = sorted(
                    tasks, key=lambda t: extract_task_number(t.task_id)
                )

                # Build Markdown table
                md_lines = [f"## Task list status: {tlist_id}", ""]
                md_lines.append("| Task ID | Task Name | Status | Agent Type | Dependency |")
                md_lines.append("|-------|---------|------|----------|-----|")

                for task in sorted_tasks:
                    status_text = task.status.value
                    task_name = (
                        task.task_name[:28] + "..."
                        if len(task.task_name) > 30
                        else task.task_name
                    )
                    deps_text = ", ".join(task.dependencies[:3])
                    if len(task.dependencies) > 3:
                        deps_text += f" (+{len(task.dependencies) - 3})"
                    if not task.dependencies:
                        deps_text = "-"
                    md_lines.append(
                        f"| {task.task_id} | {task_name} | {status_text} | {task.agent_type.value} | {deps_text} |"
                    )

                # Print to console
                md_table = "\n".join(md_lines)
                PrettyOutput.print_markdown(md_table)

                # Print statistics
                summary = task_list_manager.get_task_list_summary(tlist_id)
                if summary:
                    stats_text = (
                        f"📊 Total: {summary['total_tasks']} | "
                        f"⏳ Pending: {summary['pending']} | "
                        f"🔄 Running: {summary['running']} | "
                        f"✅ Completed: {summary['completed']} | "
                        f"❌ Failed: {summary['failed']} | "
                        f"🚫 Abandoned: {summary['abandoned']}"
                    )
                    PrettyOutput.auto_print(f"[dim]{stats_text}[/dim]")
                    PrettyOutput.auto_print("")

                    # Send to frontend
                    try:
                        # Build the Markdown table for the task list
                        table_md_lines = [f"## Task list status: {tlist_id}\n"]
                        table_md_lines.append(
                            "| Task ID | Task Name | Status | Agent Type | Dependency |"
                        )
                        table_md_lines.append(
                            "|-------|---------|------|----------|-----|"
                        )

                        for task in sorted_tasks:
                            status_text = task.status.value
                            task_name = (
                                task.task_name[:28] + "..."
                                if len(task.task_name) > 30
                                else task.task_name
                            )
                            deps_text = ", ".join(task.dependencies[:3])
                            if len(task.dependencies) > 3:
                                deps_text += f" (+{len(task.dependencies) - 3})"
                            if not task.dependencies:
                                deps_text = "-"

                            table_md_lines.append(
                                f"| {task.task_id} | {task_name} | {status_text} | {task.agent_type.value} | {deps_text} |"
                            )

                        table_md_lines.append(f"\n**Statistics:** {stats_text}")
                        table_md = "\n".join(table_md_lines)

                        emit_output(
                            OutputEvent(
                                text=table_md,
                                output_type=OutputType.INFO,
                                timestamp=None,
                                lang="markdown",  # Mark as Markdown format; the frontend will render the table
                                context={
                                    "_gateway_skip": True,  # Do not print Gateway-specific data in the terminal
                                    "task_list_id": tlist_id,
                                    "summary": summary,
                                },
                            )
                        )
                    except Exception:
                        # Ignore output errors; does not affect console display
                        pass

        except Exception as e:
            # Print detailed error information to help with debugging
            import traceback

            PrettyOutput.auto_print(f"⚠️ Failed to print task status: {e}")
            PrettyOutput.auto_print(f"   Error details: {traceback.format_exc()}")

    @property
    def description(self) -> str:
        """Generate tool description

        Returns:
            str: Tool description
        """
        return self._get_description()

    def _get_description(self) -> str:
        """Generate tool description

        Returns:
            str: Tool description
        """
        description = """Task list management tool: break complex tasks into subtasks, advance item by item, and track status.

Core operations: add_tasks adds tasks in bulk (add them all at once during the planning phase); get_task_list_summary views task status; execute_task executes a task; update_task updates task status and results; clear_tasks clears the task list.

Task type agent_type:
- main: simple tasks (1-3 steps, single file), executed directly by the main Agent
- sub: complex tasks (multi-step, multi-file), automatically handed to a sub Agent for execution

⚠️ Use sub with caution: if a task is not independent enough, do not use sub; once sub is used, complete context must be provided in task_desc and additional_info (involving file and directory structure, dependencies and interfaces, required environment/tech stack, execution prerequisites and limitations).

Mandatory requirements: execute_task must carry a non-empty additional_info; do not split simple tasks too finely; each Agent can maintain only one task list at a time.

Typical workflow: first use add_tasks to build the task list, then advance them one by one with execute_task, updating status and results with update_task in between.
"""

        return description

    @property
    def parameters(self) -> dict:
        """Generate tool parameters

        Returns:
            dict: Tool parameter definitions
        """
        return self._get_parameters()

    def _get_parameters(self) -> dict:
        """Generate tool parameters

        Returns:
            dict: Tool parameter definitions
        """
        action_enum = [
            "add_tasks",
            "get_task_detail",
            "get_task_list_summary",
            "execute_task",
            "update_task",
            "clear_tasks",
        ]

        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": action_enum,
                    "description": "The operation to perform; see the enum field for values (e.g., add_tasks to add tasks, execute_task to execute a task, update_task to update a task)",
                },
                "main_goal": {
                    "type": "string",
                    "description": "The core goal of the task list (required, only used when creating the task list for the first time). This parameter must be provided when creating a new task list.",
                },
                "background": {
                    "type": "string",
                    "description": "Common background information for all subtasks, automatically added to each subtask description. It should include: 1) global constraints; 2) mandatory requirements; 3) prohibited items; 4) verification criteria. Used to provide unified context and standards.",
                },
                "tasks_info": {
                    "type": "array",
                    "description": "Task information list (required by add_tasks; if the task list does not exist, it will be created automatically)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_name": {"type": "string", "description": "Task name"},
                            "task_desc": {
                                "type": "string",
                                "description": "Task description, which should be clear, specific, and executable. It should include: 1) constraints; 2) mandatory requirements; 3) prohibited items; 4) verification criteria.",
                            },
                            "expected_output": {
                                "type": "string",
                                "description": "Expected output, which must use an itemized structured format (e.g., 1)xxx; 2)yyy or a markdown list); the subsequent verification Agent will verify each item separately.",
                            },
                            "agent_type": {
                                "type": "string",
                                "enum": ["main", "sub"],
                                "description": "Agent type: **simple tasks must use `main`** (executed directly by the main Agent, do not split into subtasks); **complex tasks use `sub`** (the system intelligently handles complex tasks)",
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of dependency task names or task IDs (optional; can reference task names in the current batch)",
                            },
                        },
                        "required": [
                            "task_name",
                            "task_desc",
                            "expected_output",
                            "agent_type",
                        ],
                    },
                },
                "task_id": {
                    "type": "string",
                    "description": "Task ID (required by execute_task/update_task/get_task_detail)",
                },
                "additional_info": {
                    "type": "string",
                    "description": "Additional information (**required only for execute_task**). Detailed context information for the task must be provided, including task background, key information, constraints, expected results, etc. It must not be an empty string or None.",
                },
                "task_update_info": {
                    "type": "object",
                    "description": "Task update information (required by update_task)",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Updated task name (optional)",
                        },
                        "task_desc": {
                            "type": "string",
                            "description": "Updated task description (optional). It should include: 1) constraints; 2) mandatory requirements; 3) prohibited items; 4) verification criteria.",
                        },
                        "expected_output": {
                            "type": "string",
                            "description": "Updated expected output (optional)",
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Updated list of dependency task IDs (optional)",
                        },
                        "status": {
                            "type": "string",
                            "enum": [
                                "pending",
                                "running",
                                "completed",
                                "failed",
                                "abandoned",
                            ],
                            "description": "Updated task status (optional; usually does not need to be called manually)",
                        },
                        "actual_output": {
                            "type": "string",
                            "description": "Updated actual output (optional; usually does not need to be called manually)",
                        },
                        "verification_method": {
                            "type": "string",
                            "description": "Verification method description (required when status is updated to completed), passed to the verification Agent as guidance. It should include: 1) files/code locations to check (paths, function names, line numbers); 2) specific verification steps (commands/tools/check content); 3) expected verification results (what should be seen for pass/fail respectively); 4) judgment criteria (clear pass/fail conditions). The description should be detailed and specific.",
                        },
                    },
                },
            },
            "required": ["action"],
        }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task list management operations"""

        try:
            agent = args.get("agent")
            if not agent:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Unable to obtain Agent instance",
                }

            # Get the task list manager
            task_list_manager = getattr(agent, "task_list_manager", None)
            if not task_list_manager:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Task list manager not initialized",
                }

            # Get the Agent ID (using the Agent name as the ID)
            agent_id = getattr(agent, "name", "main_agent")
            is_main_agent = True  # CodeAgent is the main Agent by default

            action = args.get("action")
            if not action:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing action parameter",
                }

            # Execute the corresponding operation based on action
            result = None
            task_list_id_for_status = None

            if action == "add_tasks":
                result = self._handle_add_tasks(
                    args, task_list_manager, agent_id, is_main_agent, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            elif action == "get_task_detail":
                result = self._handle_get_task_detail(
                    args, task_list_manager, agent_id, is_main_agent, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            elif action == "get_task_list_summary":
                result = self._handle_get_task_list_summary(
                    args, task_list_manager, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            elif action == "execute_task":
                result = self._handle_execute_task(
                    args, task_list_manager, agent_id, is_main_agent, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            elif action == "update_task":
                result = self._handle_update_task(
                    args, task_list_manager, agent_id, is_main_agent, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            elif action == "clear_tasks":
                result = self._handle_clear_tasks(
                    args, task_list_manager, agent_id, is_main_agent, agent
                )
                task_list_id_for_status = self._get_task_list_id(agent)

            else:
                result = {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Unknown operation: {action}",
                }

            # Print task status (if the operation succeeded)
            if result and result.get("success"):
                # If there is a task_list_id, print only that task list; otherwise print all task lists
                self._print_task_list_status(task_list_manager, task_list_id_for_status)

            return result

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to execute task list operation: {str(e)}",
            }

    def _handle_add_tasks(
        self,
        args: Dict[str, Any],
        task_list_manager: Any,
        agent_id: str,
        is_main_agent: bool,
        agent: Any,
    ) -> Dict[str, Any]:
        """Handle batch task addition (supports matching dependencies by task name)"""
        # Prohibit sub_agent from creating sub-type tasks to avoid nested sub Agents
        if agent and agent.get_user_data("__is_sub_agent__"):
            tasks_info = args.get("tasks_info")
            if tasks_info and isinstance(tasks_info, list):
                for task_info in tasks_info:
                    if (
                        isinstance(task_info, dict)
                        and task_info.get("agent_type") == "sub"
                    ):
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": "Refusing to create a sub-type task: the current Agent is already a sub Agent (sub_agent), and is not allowed to create sub-type tasks or nest sub Agents. Please use a main-type task and have the current Agent execute it directly.",
                        }
        task_list_id = self._get_task_list_id(agent)
        tasks_info = args.get("tasks_info")

        # Automatically clear the historical task list when creating a new task list (creating a new list usually means the previous tasks are already completed)
        if task_list_id:
            existing_task_list = task_list_manager.get_task_list(task_list_id)
            if existing_task_list:
                # Only the main Agent has the right to delete the task list; sub Agents are not allowed to auto-clear
                if not is_main_agent:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Agent already has a task list (ID: {task_list_id}); as a sub Agent it has no right to auto-clear the historical task list. Please have the main Agent clear the old task list before creating a new one.",
                    }
                del_success, del_msg = task_list_manager.delete_task_list(
                    task_list_id, is_main_agent
                )
                if not del_success:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Failed to auto-clear the historical task list: {del_msg}",
                    }
                # Clear the residual task-list-related state on the Agent
                self._set_task_list_id(agent, "")
                self._set_running_task_id(agent, None)
                self._unsubscribe_model_call_event(agent)
                PrettyOutput.auto_print(
                    f"🧹 Historical task list detected (ID: {task_list_id}), auto-cleared, starting to create a new task list"
                )
                task_list_id = None

        if not task_list_id:
            # Validation: if there is no task_list, there is only one task, and the agent is not main, then reject
            if tasks_info and isinstance(tasks_info, list) and len(tasks_info) == 1:
                # Get the agent_type of the first task
                first_task = tasks_info[0]
                agent_type = first_task.get("agent_type")
                if agent_type != "main":
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Refusing to add a single non-main-type task: for simple tasks, agent_type should be main and the main Agent executes it directly. To create a complex task, please add multiple tasks or change agent_type to main.",
                    }

            # Automatically create a task list
            if not tasks_info:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing tasks_info parameter",
                }

            # Validate whether main_goal is a required parameter
            main_goal = args.get("main_goal")
            if not main_goal:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing main_goal parameter: main_goal must be provided when creating a task list",
                }

            # Create task list
            task_list_id, success, error_msg = task_list_manager.create_task_list(
                main_goal=main_goal, agent_id=agent_id
            )

            if not success:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Failed to auto-create task list: {error_msg}",
                }

            # Save task_list_id to the Agent's user_data
            self._set_task_list_id(agent, task_list_id)

        tasks_info = args.get("tasks_info")
        if not tasks_info:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing tasks_info parameter",
            }

        if not isinstance(tasks_info, list):
            return {
                "success": False,
                "stdout": "",
                "stderr": "tasks_info must be an array",
            }

        # Get and process the background parameter
        background = args.get("background", "")
        if background and str(background).strip():
            # Append the background information to each subtask's description
            processed_tasks_info = []
            for task_info in tasks_info:
                if isinstance(task_info, dict) and "task_desc" in task_info:
                    # Create a new task_info dictionary to avoid modifying the original data
                    new_task_info = task_info.copy()

                    # Build a new task description containing the background information
                    original_desc = task_info["task_desc"]
                    separator = "\n" + "=" * 50 + "\n"
                    new_task_info["task_desc"] = (
                        f"{original_desc}{separator}Shared background information:\n{background}"
                    )
                    processed_tasks_info.append(new_task_info)
                else:
                    processed_tasks_info.append(task_info)
            tasks_info = processed_tasks_info

        # The add_tasks method already supports matching dependencies by task name
        task_ids, success, error_msg = task_list_manager.add_tasks(
            task_list_id=task_list_id, tasks_info=tasks_info, agent_id=agent_id
        )

        if success:
            result = {
                "task_ids": task_ids,
                "task_count": len(task_ids),
                "task_list_id": task_list_id,
                "message": f"Successfully batch-added {len(task_ids)} tasks",
            }

            # Send to the frontend
            try:
                emit_output(
                    OutputEvent(
                        text=f"✅ Successfully batch-added {len(task_ids)} tasks to task list: {task_list_id}",
                        output_type=OutputType.INFO,
                        timestamp=None,
                        context={
                            "_gateway_skip": True,
                            "task_list_id": task_list_id,
                            "task_ids": task_ids,
                            "task_count": len(task_ids),
                        },
                    )
                )
            except Exception:
                # Ignore output errors; they do not affect the returned result
                pass

            return {
                "success": True,
                "stdout": json.dumps(result, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to batch-add tasks: {error_msg}",
            }

    def _handle_get_task_detail(
        self,
        args: Dict[str, Any],
        task_list_manager: Any,
        agent_id: str,
        is_main_agent: bool,
        agent: Any,
    ) -> Dict[str, Any]:
        """Handle getting task details"""
        task_list_id = self._get_task_list_id(agent)
        if not task_list_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Agent has no task list yet; please use add_tasks to add tasks first (a task list will be created automatically)",
            }
        task_id = args.get("task_id")

        if not task_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing task_id parameter",
            }

        task, success, error_msg = task_list_manager.get_task_detail(
            task_list_id=task_list_id,
            task_id=task_id,
            agent_id=agent_id,
            is_main_agent=is_main_agent,
        )

        if success and task:
            result = {
                "task": task.to_dict(),
                "message": "Task details retrieved successfully",
            }
            return {
                "success": True,
                "stdout": json.dumps(result, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg or "Failed to get task details",
            }

    def _handle_get_task_list_summary(
        self, args: Dict[str, Any], task_list_manager: Any, agent: Any
    ) -> Dict[str, Any]:
        """Handle getting task list summary"""
        task_list_id = self._get_task_list_id(agent)
        if not task_list_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Agent has no task list yet; please use add_tasks to add tasks first (a task list will be created automatically)",
            }

        summary = task_list_manager.get_task_list_summary(task_list_id=task_list_id)

        if summary:
            return {
                "success": True,
                "stdout": json.dumps(summary, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        else:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Task list does not exist",
            }

    def _validate_dependencies_status(
        self,
        task_list_manager: Any,
        task_list_id: str,
        task: Any,
        agent_id: str,
        is_main_agent: bool,
    ) -> None:
        """Verify whether all dependencies of a task are completed

        Args:
            task_list_manager: Task list manager
            task_list_id: Task list ID
            task: The task object to verify
            agent_id: Agent ID
            is_main_agent: Whether it is the main Agent

        Raises:
            DependencyNotFoundError: Dependency task does not exist
            DependencyNotCompletedError: Dependency task not completed
            DependencyFailedError: Dependency task failed
        """
        if not task.dependencies:
            return  # No dependencies, return directly

        for dep_id in task.dependencies:
            dep_task, success, error_msg = task_list_manager.get_task_detail(
                task_list_id=task_list_id,
                task_id=dep_id,
                agent_id=agent_id,
                is_main_agent=is_main_agent,
            )

            if not success:
                raise DependencyNotFoundError(f"Dependency task '{dep_id}' does not exist")

            if dep_task.status == TaskStatus.FAILED:
                raise DependencyFailedError(
                    f"Dependency task '{dep_id}' failed; cannot execute the current task"
                )

            if dep_task.status == TaskStatus.ABANDONED:
                raise DependencyFailedError(
                    f"Dependency task '{dep_id}' has been abandoned; cannot execute the current task"
                )

            if dep_task.status == TaskStatus.PENDING:
                raise DependencyNotCompletedError(
                    f"Dependency task '{dep_id}' has not started yet; cannot execute the current task"
                )

            if dep_task.status == TaskStatus.RUNNING:
                raise DependencyNotCompletedError(
                    f"Dependency task '{dep_id}' is currently executing; cannot execute the current task"
                )

            if dep_task.status != TaskStatus.COMPLETED:
                raise DependencyNotCompletedError(
                    f"Dependency task '{dep_id}' has status '{dep_task.status.value}', which does not satisfy the execution conditions"
                )

    def _handle_execute_task(
        self,
        args: Dict[str, Any],
        task_list_manager: Any,
        agent_id: str,
        is_main_agent: bool,
        parent_agent: Any,
    ) -> Dict[str, Any]:
        """Handle executing a task (automatically create a sub Agent for execution)

        Important reminder: before executing a task, the system automatically verifies whether all its dependency tasks are completed (completed status).
        If any dependency task is incomplete or failed, task execution will be rejected and a corresponding error message will be returned."""
        task_list_id = self._get_task_list_id(parent_agent)
        if not task_list_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Agent has no task list yet; please use add_tasks to add tasks first (a task list will be created automatically)",
            }
        task_id = args.get("task_id")
        additional_info = args.get("additional_info")

        if not task_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing task_id parameter",
            }

        if additional_info is None:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing additional_info parameter",
            }

        if not additional_info or not str(additional_info).strip():
            return {
                "success": False,
                "stdout": "",
                "stderr": "additional_info parameter cannot be empty",
            }

        # Get task details
        task, success, error_msg = task_list_manager.get_task_detail(
            task_list_id=task_list_id,
            task_id=task_id,
            agent_id=agent_id,
            is_main_agent=is_main_agent,
        )

        if not success or not task:
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg or "Failed to get task details",
            }

        # Verify dependency status
        try:
            self._validate_dependencies_status(
                task_list_manager=task_list_manager,
                task_list_id=task_list_id,
                task=task,
                agent_id=agent_id,
                is_main_agent=is_main_agent,
            )
        except DependencyValidationError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
            }

        # Check task status
        if task.status.value != "pending":
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Task status is {task.status.value}; cannot execute (only tasks in pending status can be executed)",
            }

        # Check whether there are running tasks
        try:
            running_tasks = []
            # Get the task list instance
            task_list = task_list_manager.get_task_list(task_list_id)
            if task_list:
                # Scan all tasks to find running tasks
                for task_obj in task_list.tasks.values():
                    if task_obj.status.value == "running":
                        running_tasks.append(
                            {
                                "task_id": task_obj.task_id,
                                "task_name": task_obj.task_name,
                            }
                        )

            if running_tasks:
                running_task_details = []
                for rt in running_tasks:
                    running_task_details.append(
                        f"Task ID: {rt['task_id']}, Task name: {rt['task_name']}"
                    )

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Detected {len(running_tasks)} tasks currently running; please finish these tasks before executing new ones:\n"
                    + "\n".join(running_task_details),
                }

        except Exception:
            # If detection fails, log it but do not block task execution, to avoid affecting system stability
            pass

        # Update task status to running
        update_success, update_msg = task_list_manager.update_task_status(
            task_list_id=task_list_id,
            task_id=task_id,
            status="running",
            agent_id=agent_id,
            is_main_agent=is_main_agent,
        )

        if not update_success:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to update task status: {update_msg}",
            }

        # Send to the frontend: task starts executing
        try:
            emit_output(
                OutputEvent(
                    text=f"🚀 Starting task execution: [{task.task_name}] ({task_id})",
                    output_type=OutputType.INFO,
                    timestamp=None,
                    context={
                        "_gateway_skip": True,
                        "task_list_id": task_list_id,
                        "task_id": task_id,
                        "task_name": task.task_name,
                        "agent_type": task.agent_type.value,
                        "status": "running",
                    },
                )
            )
        except Exception:
            # Ignore output errors; they do not affect task execution
            pass

        # For main-type tasks, initialize the model call count and subscribe to events
        if task.agent_type.value == "main":
            try:
                # Unsubscribe previous event subscriptions first (to avoid accumulation)
                self._unsubscribe_model_call_event(parent_agent)

                # Initialize the model call count to 0
                task_list = task_list_manager.get_task_list(task_list_id)
                if task_list:
                    current_task = task_list.get_task(task_id)
                    if current_task:
                        current_task.model_call_count = 0

                # Save the ID of the running task
                self._set_running_task_id(parent_agent, task_id)

                # Subscribe to the BEFORE_MODEL_CALL event to record the model call count
                from haijunbot.haijunbot_agent.events import BEFORE_MODEL_CALL

                # Use a named function instead of a lambda so it can be unsubscribed later
                def model_call_callback(agent: Any, message: Any) -> None:
                    self._increment_task_conversation_round(
                        parent_agent, task_list_manager, task_list_id
                    )

                parent_agent.event_bus.subscribe(
                    BEFORE_MODEL_CALL,
                    model_call_callback,
                    priority=50,  # High priority, to ensure earlier execution during event handling
                )

                # Save the callback function reference so it can be unsubscribed later
                parent_agent.set_user_data(
                    "__model_call_callback__", model_call_callback
                )

            except Exception:
                # Subscription failure does not affect task execution
                pass

        # Pre-initialize to ensure accessibility outside try-except (ty cross-branch inference limitation)
        final_verification_passed = False
        iteration = 0
        all_verification_results: List[str] = []

        try:
            # Record the commit before execution
            start_commit = get_latest_commit_hash()

            # Merge the task description and additional info (actually update the task's desc field so it is visible when printed)
            if additional_info and str(additional_info).strip():
                separator = "\n" + "=" * 50 + "\n"
                task.task_desc = (
                    f"{task.task_desc}{separator}Additional information:\n{additional_info}"
                )

            # Use a common method to build the task execution content
            task_content = self._build_task_content(task, parent_agent)

            # Build background information
            background_parts = []

            # Get extra background information (if provided)
            additional_background = args.get("additional_background")
            if additional_background:
                background_parts.append(f"Extra background information: {additional_background}")

            # Use a common method to build standard background information
            standard_background = self._build_task_background(
                task_list_manager=task_list_manager,
                task_list_id=task_list_id,
                task=task,
                agent_id=agent_id,
                is_main_agent=is_main_agent,
                include_completed_summary=True,
            )

            if standard_background:
                background_parts.append(standard_background)

            background = "\n\n".join(background_parts) if background_parts else ""

            # Create the corresponding sub Agent to execute the task based on agent_type
            execution_result = None
            if task.agent_type.value == "main":
                # Main Agent execution: execute directly in the current Agent (do not create a sub Agent)
                # Note: main-Agent-type tasks must be executed by the main Agent itself; after execution completes, update_task_status must be called manually to update the status
                result = {
                    "task_id": task_id,
                    "task_name": task.task_name,
                    "task_desc": task.task_desc,
                    "expected_output": task.expected_output,
                    "background": background,
                    "message": "Task has been marked as running; please have the main Agent execute it itself",
                    "note": "Main-Agent-type tasks should be executed directly by the current Agent; after execution completes, call update_task to update the task status to completed or failed",
                    "warning": "Be sure to update the task status after execution completes, otherwise the task will remain in running status",
                }
                return {
                    "success": True,
                    "stdout": json.dumps(result, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            elif task.agent_type.value == "sub":
                # Forbid sub_agent from executing sub-type tasks, to avoid nesting sub Agents
                if parent_agent and parent_agent.get_user_data("__is_sub_agent__"):
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Refusing to execute a sub-type task: the current Agent is already a sub Agent (sub_agent), and is not allowed to execute sub-type tasks or nest sub Agents. Please use a main-type task and have the current Agent execute it directly.",
                    }
                # Sub Agent execution: automatically identify and use the appropriate sub Agent tool
                # After execution, verify whether the task is truly complete; if not, continue iterative execution
                # Initialize variables to ensure accessibility outside try-except
                final_verification_passed = False
                execution_result = None
                iteration = 0

                try:
                    # Determine the task type directly from the agent instance type
                    is_code_task = self._determine_agent_type(
                        parent_agent, task, task_content, background
                    )

                    # Iteratively execute and verify until the task is truly complete (unlimited iterations until verification passes)
                    iteration = 0
                    verification_passed = False
                    all_execution_results = []  # Record all execution results
                    all_verification_results: List[str] = []  # Record all verification results
                    # Record whether the user chose to skip verification (only asked on the first iteration)
                    user_skipped_verification = False

                    while not verification_passed:
                        iteration += 1

                        PrettyOutput.auto_print(
                            f"🔄 Executing task [{task.task_name}] (iteration {iteration})..."
                        )
                        # Send to the frontend
                        try:
                            emit_output(
                                OutputEvent(
                                    text=f"🔄 Executing task [{task.task_name}] (iteration {iteration})...",
                                    output_type=OutputType.INFO,
                                    timestamp=None,
                                    context={
                                        "_gateway_skip": True,
                                        "task_id": task_id,
                                        "task_name": task.task_name,
                                        "iteration": iteration,
                                    },
                                )
                            )
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_tools.task_list_manager",
                                function="model_call_callback",
                            )
                            pass

                        # Code vs general tasks are uniformly dispatched to sub-agents; from the second time onward, verification feedback is automatically attached
                        agent_name = f"{task.task_name} (task_{task_id})"
                        enhanced_task_content = self._build_iteration_task_content(
                            task_content, iteration, all_verification_results
                        )
                        tool_result = self._run_sub_execution(
                            is_code_task=is_code_task,
                            parent_agent=parent_agent,
                            agent_name=agent_name,
                            enhanced_task_content=enhanced_task_content,
                            background=background,
                        )

                        execution_result = tool_result.get("stdout", "")
                        execution_success = tool_result.get("success", False)

                        if not execution_success:
                            # Execution failed; update task status to failed
                            task_list_manager.update_task_status(
                                task_list_id=task_list_id,
                                task_id=task_id,
                                status="failed",
                                agent_id=agent_id,
                                is_main_agent=is_main_agent,
                                actual_output=f"Execution failed: {tool_result.get('stderr', 'Unknown error')}",
                            )
                            return {
                                "success": False,
                                "stdout": "",
                                "stderr": f"Sub Agent execution failed: {tool_result.get('stderr', 'Unknown error')}",
                            }

                        # Record execution result
                        all_execution_results.append(execution_result)

                        # Get the commit after execution and compute the diff
                        end_commit = get_latest_commit_hash()
                        diff = ""
                        if start_commit and end_commit and start_commit != end_commit:
                            diff = get_diff_between_commits(start_commit, end_commit)

                            # Limit the diff size to fit the context window
                            max_diff_length = _calculate_default_max_output_length(
                                parent_agent
                            )  # Dynamically compute the maximum length based on the agent context
                            if len(diff) > max_diff_length:
                                # Truncate the diff and add a hint message at the end
                                diff = (
                                    diff[: max_diff_length - 100]
                                    + f"\n\n... (diff truncated, omitted {len(diff) - max_diff_length + 100} characters) ..."
                                )

                        # Build background information containing the diff for verification
                        verification_background = background
                        if diff:  # If there is a diff, add it to the verification background
                            verification_background = (
                                f"{background}\n\nCode change diff:\n{diff}"
                            )

                        # Check whether verification is needed (in interactive mode, only ask the user on the first iteration)
                        should_verify = True
                        if iteration == 1:
                            # On the first iteration, ask the user in interactive mode
                            is_interactive = not getattr(
                                parent_agent, "non_interactive", True
                            )
                            if is_interactive:
                                from haijunbot.haijunbot_utils.input import user_confirm

                                should_verify = user_confirm(
                                    f"Verify the completion status of task [{task.task_name}]?",
                                    default=False,
                                )
                                if not should_verify:
                                    user_skipped_verification = True
                        else:
                            # Subsequent iterations: if the user previously chose to skip verification, do not verify again; otherwise continue verifying
                            should_verify = not user_skipped_verification

                        # Verify whether the task is truly complete
                        if should_verify:
                            verification_passed, verification_result = (
                                self._verify_task_completion(
                                    task,
                                    task_content,
                                    verification_background,
                                    parent_agent,
                                    verification_iteration=iteration,
                                )
                            )
                        else:
                            # User chose not to verify; mark as passed directly
                            verification_passed = True
                            verification_result = "User chose to skip verification"
                            PrettyOutput.auto_print(
                                f"⏭️ User chose to skip verification; task [{task.task_name}] marked as completed directly"
                            )
                            # Send to the frontend
                            try:
                                emit_output(
                                    OutputEvent(
                                        text=f"⏭️ User chose to skip verification; task [{task.task_name}] marked as completed directly",
                                        output_type=OutputType.INFO,
                                        timestamp=None,
                                        context={
                                            "_gateway_skip": True,
                                            "task_id": task_id,
                                            "task_name": task.task_name,
                                            "status": "verification_skipped",
                                        },
                                    )
                                )
                            except Exception as e:
                                save_exception(
                                    e,
                                    module="haijunbot_tools.task_list_manager",
                                    function="model_call_callback",
                                )
                                pass

                        # Record verification result
                        all_verification_results.append(verification_result)

                        if not verification_passed:
                            PrettyOutput.auto_print(
                                f"⚠️ Task [{task.task_name}] verification did not pass; will continue iterating to fix (iteration {iteration})"
                            )
                        else:
                            PrettyOutput.auto_print(
                                f"✅ Task [{task.task_name}] verification passed; task is truly complete ({iteration} iterations total)"
                            )
                            final_verification_passed = True

                    # Save the final verification status (verification_passed should be True when the loop exits)
                    final_verification_passed = verification_passed

                    # Use the last execution result
                    execution_result = (
                        all_execution_results[-1]
                        if all_execution_results
                        else "Task execution completed"
                    )
                except Exception as e:
                    # Execution exception; update task status to failed
                    task_list_manager.update_task_status(
                        task_list_id=task_list_id,
                        task_id=task_id,
                        status="failed",
                        agent_id=agent_id,
                        is_main_agent=is_main_agent,
                        actual_output=f"Execution exception: {str(e)}",
                    )
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Failed to create sub Agent to execute task: {str(e)}",
                    }

                # Ensure execution_result has a value
                if execution_result is None:
                    execution_result = "Task execution completed"

            # Process the execution result: if it is too long, truncate it and add a hint
            processed_result = execution_result or "Task execution completed"

            # Dynamically compute the maximum output length based on remaining tokens
            max_output_length = self._get_max_output_length(parent_agent)

            if len(processed_result) > max_output_length:
                # Compute the prefix and suffix lengths for truncation based on the maximum length
                prefix_length, suffix_length = self._get_truncate_lengths(
                    max_output_length
                )

                # Keep the prefix and suffix, connecting the middle with an ellipsis
                truncated_result = (
                    processed_result[:prefix_length]
                    + "\n\n... [Output too long; middle portion truncated] ...\n\n"
                    + processed_result[-suffix_length:]
                )
                processed_result = truncated_result
                execution_result_len = (
                    len(execution_result) if execution_result is not None else 0
                )
                PrettyOutput.auto_print(
                    f"⚠️ The execution result of task {task_id} is too long ({execution_result_len} characters), "
                    f"truncated to {len(truncated_result)} characters (based on remaining token limit: {max_output_length} characters)"
                )

            # For sub agent-type tasks, only update to completed after verification passes
            # If verification did not pass but the maximum number of iterations is reached, mark as failed
            if task.agent_type.value == "sub":
                # Check the final verification status
                if final_verification_passed:
                    # Verification passed, updating task status to completed
                    task_list_manager.update_task_status(
                        task_list_id=task_list_id,
                        task_id=task_id,
                        status="completed",
                        agent_id=agent_id,
                        is_main_agent=is_main_agent,
                        actual_output=processed_result,
                    )
                    # Send to frontend
                    try:
                        emit_output(
                            OutputEvent(
                                text=f"✅ Task [{task.task_name}] execution completed",
                                output_type=OutputType.INFO,
                                timestamp=None,
                                context={
                                    "_gateway_skip": True,
                                    "task_id": task_id,
                                    "task_name": task.task_name,
                                    "status": "completed",
                                    "iteration": iteration,
                                },
                            )
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.task_list_manager",
                            function="model_call_callback",
                        )
                        pass
                else:
                    # Verification failed, marking as failed, and returning detailed verification results
                    task_list_manager.update_task_status(
                        task_list_id=task_list_id,
                        task_id=task_id,
                        status="failed",
                        agent_id=agent_id,
                        is_main_agent=is_main_agent,
                        actual_output=processed_result,
                    )

                    # Send to frontend
                    try:
                        emit_output(
                            OutputEvent(
                                text=f"❌ Task [{task.task_name}] execution failed",
                                output_type=OutputType.ERROR,
                                timestamp=None,
                                context={
                                    "_gateway_skip": True,
                                    "task_id": task_id,
                                    "task_name": task.task_name,
                                    "status": "failed",
                                    "iteration": iteration,
                                },
                            )
                        )
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_tools.task_list_manager",
                            function="model_call_callback",
                        )
                        pass

                    # Get the last verification result
                    last_verification = (
                        all_verification_results[-1]
                        if all_verification_results
                        else "Verification failed"
                    )

                    # Build detailed failure report
                    failure_report = f"""
❌ **Task Execution Failure Report**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **Task Information**
   Task ID: {task_id}
   Task Name: {task.task_name}
   Task Type: sub
   Final Status: failed

⚠️ **Execution Details**
   Iterations: {iteration}
   Verification Result: ❌ Verification failed

📋 **Last Verification Report**
{last_verification}

📊 **Execution Output**
{processed_result[:1000]}{"..." if len(processed_result) > 1000 else ""}

💡 **Follow-up Suggestions**
   • The task has been marked as failed
   • Please read the verification report carefully to understand the specific failure reasons
   • You can modify the task description or expected output and re-execute
   • Or adjust the task goal according to the actual situation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task [{task.task_name}] execution failed, marked as failed.
"""
                    return {
                        "success": False,
                        "stdout": failure_report.strip(),
                        "stderr": "Subtask execution verification failed, marked as failed",
                    }
            else:
                # For main agent type tasks, directly update to completed (the main Agent manages the status itself)
                # Status is not updated here; the main Agent calls update_task itself to update
                pass

            # Build a formatted task completion notification
            import datetime

            # Get the current time as the completion time
            completion_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Preview length: 50% of the maximum output length
            preview_length = int(max_output_length * 0.5)

            # Create a formatted completion notification
            formatted_notification = f"""
✅ **Task Completion Notification**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **Task Information**
   Task ID: {task_id}
   Task Name: {task.task_name}
   Completion Time: {completion_time}

📊 **Execution Result**
   Status: ✅ Completed
   Output Length: {len(processed_result)} characters
   
📝 **Execution Summary**
{processed_result[:preview_length]}{"..." if len(processed_result) > preview_length else ""}

📋 **Follow-up Actions**
   • The full result has been saved to the task's actual_output field
   • Full details can be obtained via get_task_detail
   • Other tasks that depend on this task can now start executing
   • ⚠️ Before starting subsequent tasks, please evaluate the necessity of task execution - if the previous tasks have already done more, subsequent tasks can be abandoned

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task [{task.task_name}] completed successfully!
"""

            # Directly return the formatted task completion notification
            return {
                "success": True,
                "stdout": formatted_notification.strip(),
                "stderr": "",
            }

        except Exception as e:
            # An exception occurred, updating task status to failed
            try:
                task_list_manager.update_task_status(
                    task_list_id=task_list_id,
                    task_id=task_id,
                    status="failed",
                    agent_id=agent_id,
                    is_main_agent=is_main_agent,
                    actual_output=f"Execution exception: {str(e)}",
                )
            except Exception as inner_e:
                save_exception(
                    inner_e,
                    module="haijunbot_tools.task_list_manager",
                    function="model_call_callback",
                )
                pass

            return {
                "success": False,
                "stdout": "",
                "stderr": f"Task execution failed: {str(e)}",
            }

    def _handle_update_task(
        self,
        args: Dict[str, Any],
        task_list_manager: Any,
        agent_id: str,
        is_main_agent: bool,
        agent: Any,
    ) -> Dict[str, Any]:
        """Handle updating task attributes"""
        task_list_id = self._get_task_list_id(agent)
        if not task_list_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Agent does not have a task list yet, please use add_tasks to add tasks first (a task list will be created automatically)",
            }
        task_id = args.get("task_id")
        task_update_info = args.get("task_update_info", {})

        if not task_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing task_id parameter",
            }

        if not task_update_info:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Missing task_update_info parameter",
            }

        try:
            # Permission check
            if not task_list_manager._check_agent_permission(
                agent_id, task_id, is_main_agent
            ):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Insufficient permissions: cannot access this task",
                }

            # Get the task list
            task_list = task_list_manager.get_task_list(task_list_id)
            if not task_list:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Task list does not exist",
                }

            # Get the task
            task = task_list.get_task(task_id)
            if not task:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Task does not exist",
                }

            # Validate and update task attributes
            update_kwargs = {}

            if "task_name" in task_update_info:
                new_name = task_update_info["task_name"]
                update_kwargs["task_name"] = new_name

            if "task_desc" in task_update_info:
                new_desc = task_update_info["task_desc"]
                update_kwargs["task_desc"] = new_desc

            if "expected_output" in task_update_info:
                update_kwargs["expected_output"] = task_update_info["expected_output"]

            if "dependencies" in task_update_info:
                # Validate dependency relationships
                new_deps = task_update_info["dependencies"]
                for dep_id in new_deps:
                    if dep_id not in task_list.tasks:
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": f"Dependency task {dep_id} does not exist",
                        }
                update_kwargs["dependencies"] = new_deps

            # Handle status update (if provided)
            status = task_update_info.get("status")
            actual_output = task_update_info.get("actual_output")
            verification_method = task_update_info.get("verification_method")

            # Whether the task list was automatically cleared because all tasks ended
            auto_cleared = False

            if status is not None:
                # When the status is updated to completed, verification_method must be present
                if status == "completed" and task.status.value != "completed":
                    if not verification_method or not str(verification_method).strip():
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": "Missing verification_method parameter: when the task status is updated to completed, the verification_method parameter must be provided, describing how to verify whether the task is truly completed.",
                        }

                # For main type tasks, perform verification when updating to completed status
                # But if the task is already in completed status, re-verification is not needed
                if (
                    status == "completed"
                    and task.agent_type.value == "main"
                    and task.status.value != "completed"
                ):
                    # Check the model call count; if ≤15, skip verification (15 calls usually correspond to 2-3 rounds of dialogue)
                    if task.model_call_count <= 15:
                        from haijunbot.haijunbot_utils.output import PrettyOutput

                        PrettyOutput.auto_print(
                            f"⚡ Task [{task.task_name}] model call count ≤15 (actual {task.model_call_count} times), skipping verification and completing directly"
                        )
                        verification_passed = True
                        verification_result = "Model call count ≤15, skipping verification"
                    else:
                        # Check whether verification is needed (ask the user in interactive mode)
                        should_verify = True
                        is_interactive = not getattr(agent, "non_interactive", True)
                        if is_interactive:
                            from haijunbot.haijunbot_utils.input import user_confirm
                            from haijunbot.haijunbot_utils.output import PrettyOutput

                            PrettyOutput.auto_print(
                                f"🔍 Preparing to verify completion of main type task [{task.task_name}]..."
                            )
                            should_verify = user_confirm(
                                f"Verify the completion of task [{task.task_name}]?",
                                default=False,
                            )

                        if should_verify:
                            # Use a common method to build task content
                            task_content = self._build_task_content(task, agent)

                            # Use a common method to build background information
                            background = self._build_task_background(
                                task_list_manager=task_list_manager,
                                task_list_id=task_list_id,
                                task=task,
                                agent_id=agent_id,
                                is_main_agent=is_main_agent,
                                include_completed_summary=False,  # Summaries of other completed tasks are not needed when verifying main tasks
                            )

                            # Execute verification
                            from haijunbot.haijunbot_utils.output import PrettyOutput

                            PrettyOutput.auto_print(
                                f"🔍 Starting to verify completion of main type task [{task.task_name}]..."
                            )

                            verification_passed, verification_result = (
                                self._verify_task_completion(
                                    task,
                                    task_content,
                                    background,
                                    agent,
                                    verification_iteration=1,
                                    verification_method=verification_method,
                                )
                            )
                        else:
                            # User chose not to verify, directly mark as passed
                            from haijunbot.haijunbot_utils.output import PrettyOutput

                            verification_passed = True
                            verification_result = "User chose to skip verification"
                            PrettyOutput.auto_print(
                                f"⏭️ User chose to skip verification, task [{task.task_name}] marked as completed directly"
                            )

                    if not verification_passed:
                        # Verification failed, do not update status, return the failure reason to the agent
                        PrettyOutput.auto_print(
                            f"❌ Task [{task.task_name}] verification failed, status not updated"
                        )

                        # Build a detailed failure report, return it to the agent
                        failure_report = f"""
❌ **Task Verification Failure Report**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 **Task Information**
   Task ID: {task_id}
   Task Name: {task.task_name}
   Task Type: main
   Current Status: {task.status.value}

⚠️ **Verification Result**
   Status: ❌ Verification failed
   Reason: The task failed to meet the expected output requirements

📋 **Detailed Verification Report**
{verification_result}

💡 **Follow-up Suggestions**
   • Please read the above verification report carefully to understand which expected output items were not completed
   • Fix the related issues based on the verification feedback
   • After fixing, call update_task again to update the status to completed
   • The task status will remain as {task.status.value} and will not be updated to completed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task [{task.task_name}] verification failed; please fix the issues based on the above feedback before updating the status again.
"""
                        return {
                            "success": False,
                            "stdout": failure_report.strip(),
                            "stderr": "Task verification failed, status not updated",
                        }
                    else:
                        PrettyOutput.auto_print(
                            f"✅ Task [{task.task_name}] verification passed, updating status to completed"
                        )

                # Use the update_task_status method to update the status
                status_success, status_msg = task_list_manager.update_task_status(
                    task_list_id=task_list_id,
                    task_id=task_id,
                    status=status,
                    agent_id=agent_id,
                    is_main_agent=is_main_agent,
                    actual_output=actual_output,
                )
                if not status_success:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Failed to update task status: {status_msg}",
                    }

                # Send to frontend: task status update
                try:
                    status_emoji = {
                        "pending": "⏳",
                        "running": "🔄",
                        "completed": "✅",
                        "failed": "❌",
                        "abandoned": "🚫",
                    }.get(status, "📋")

                    emit_output(
                        OutputEvent(
                            text=f"{status_emoji} Task [{task.task_name}] status updated to: {status}",
                            output_type=OutputType.INFO,
                            timestamp=None,
                            context={
                                "_gateway_skip": True,
                                "task_id": task_id,
                                "task_name": task.task_name,
                                "status": status,
                            },
                        )
                    )
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.task_list_manager",
                        function="_handle_update_task",
                    )
                    pass

                # After the task status is successfully updated, clean up the event subscription (for main type tasks)
                if task.agent_type.value == "main":
                    try:
                        # Clear running_task_id in user_data
                        self._set_running_task_id(agent, None)

                        # Cancel the event subscription
                        self._unsubscribe_model_call_event(agent)
                    except Exception:
                        # Cleanup failure does not affect the main flow
                        pass

            # Perform other attribute updates (if any)
            if update_kwargs:
                if not task_list.update_task(task_id, **update_kwargs):
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Failed to update task attributes",
                    }

            # After the task completes, if all tasks have entered a terminal state, automatically clear the task list
            if status == "completed" and self._try_auto_clear_task_list(
                task_list_manager, task_list_id, agent, is_main_agent
            ):
                auto_cleared = True

            # Get the updated task information
            updated_task = task_list.get_task(task_id)
            result = {
                "task_id": task_id,
                "task": updated_task.to_dict() if updated_task else None,
                "message": "Task updated successfully",
            }

            # If the task list was automatically cleared because all tasks ended, state this explicitly in the returned content
            if auto_cleared:
                result["message"] = (
                    f"Task [{task.task_name}] has been updated to completed; "
                    "All tasks in the current task list have ended (no pending/running tasks), "
                    "the task list has been automatically cleared, no need to call clear_tasks again."
                    "If you need to continue executing tasks later, please call add_tasks again to create a new task list."
                )
                result["task_list_auto_cleared"] = True
                result["auto_clear_reason"] = (
                    "All tasks have entered a terminal state (completed/failed/abandoned), "
                    "to avoid task list accumulation, the system automatically cleared this task list"
                )

            return {
                "success": True,
                "stdout": json.dumps(result, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to update task: {str(e)}",
            }

    def _try_auto_clear_task_list(
        self,
        task_list_manager: Any,
        task_list_id: str,
        agent: Any,
        is_main_agent: bool,
    ) -> bool:
        """Automatically clear the task list after all tasks enter a terminal state, to prevent the task list from piling up.

        Only clear when the task list is non-empty and no active tasks (pending/running) exist.
        Silently ignore cleanup failures without affecting the main flow.

        Parameters:
            task_list_manager: TaskListManager instance
            task_list_id: Task list ID
            agent: Agent instance
            is_main_agent: Whether it is the main Agent

        Returns:
            bool: Whether automatic clearing was performed
        """
        # Only the main Agent has permission to delete the task list
        if not is_main_agent:
            return False

        try:
            task_list = task_list_manager.get_task_list(task_list_id)
            if not task_list or not task_list.tasks:
                return False

            # Do not clear when active tasks (pending/running) exist
            if task_list.active_task_ids:
                return False

            success, error_msg = task_list_manager.delete_task_list(
                task_list_id, is_main_agent
            )
            if not success:
                return False

            # Clear residual task list related state on the Agent
            self._set_task_list_id(agent, "")
            self._set_running_task_id(agent, None)
            self._unsubscribe_model_call_event(agent)

            PrettyOutput.auto_print(
                "🧹 All tasks have ended, the task list has been automatically cleared to avoid task accumulation"
            )
            return True
        except Exception as e:
            # Automatic clearing is an optimization behavior; failures do not affect the main flow
            save_exception(
                e,
                module="haijunbot_tools.task_list_manager",
                function="_try_auto_clear_task_list",
            )
            return False

    def _handle_clear_tasks(
        self,
        args: Dict[str, Any],
        task_list_manager: Any,
        agent_id: str,
        is_main_agent: bool,
        agent: Any,
    ) -> Dict[str, Any]:
        """Handle clearing all tasks"""
        task_list_id = self._get_task_list_id(agent)
        if not task_list_id:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Agent does not have a task list yet",
            }

        try:
            success, error_msg = task_list_manager.delete_task_list(
                task_list_id, is_main_agent
            )
            if not success:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": error_msg or "Failed to delete task list",
                }

            # Clear the Agent's task_list_id
            self._set_task_list_id(agent, "")
            # Clear running_task_id
            self._set_running_task_id(agent, None)
            # Cancel the event subscription
            self._unsubscribe_model_call_event(agent)

            return {
                "success": True,
                "stdout": "Task list cleared",
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to clear task list: {str(e)}",
            }
