# -*- coding: utf-8 -*-
"""
AgentRunLoop: hosts the Agent's main run-loop logic.

Phase one goal (minimal changes):
- Copy the existing _main_loop logic into a standalone class, using the passed-in agent instance for delegated calls
- Do not change the external calling entry point for now; later delegate to this class in Agent._main_loop
- Keep exception handling, tool calls, and user interaction exactly consistent with the existing implementation
"""

import datetime
import os
import re
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import List
from typing import Optional
from typing import Union


from haijunbot.haijunbot_agent.events import AFTER_SUMMARY
from haijunbot.haijunbot_agent.events import AFTER_TOOL_CALL
from haijunbot.haijunbot_agent.events import BEFORE_SUMMARY
from haijunbot.haijunbot_agent.utils import is_auto_complete
from haijunbot.haijunbot_agent.utils import join_prompts
from haijunbot.haijunbot_agent.utils import normalize_next_action
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.config import get_conversation_turn_threshold
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.config import get_max_input_token_count
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.utils import get_context_token_count


def ensure_str(content: Union[str, List[ContentBlock]]) -> str:
    """Ensure the content is a string; if it is a multimodal list, extract the text part"""
    if isinstance(content, str):
        return content
    # Extract the text part
    text_parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return "\n".join(text_parts)


if TYPE_CHECKING:
    # For type annotation only, to avoid runtime circular dependencies
    from . import Agent


class AgentRunLoop:
    def __init__(self, agent: "Agent") -> None:
        self.agent = agent
        self.tool_reminder_rounds = int(os.environ.get("tool_reminder_rounds", 20))
        self.conversation_turn_threshold = get_conversation_turn_threshold()

        # Git diff related attributes
        self._git_diff: Optional[str] = None  # Cache the git diff content

    def _preprocess_user_input(self, user_input: str) -> str:
        """Preprocess user input (returns it directly)

        Args:
            user_input: the original user input

        Returns:
            the original user input
        """
        return user_input

    def _postprocess_response(self, response: str) -> str:
        """Post-process the response: extract and remove the stage marker, and update it to an agent attribute

        Args:
            response: the original response

        Returns:
            the processed response (with the stage marker removed)
        """
        # Extract the stage marker [MODE: xxx]
        import re

        # Match [MODE: xxx] and the consecutive blank lines after it
        mode_pattern = r"^\[MODE:\s*([A-Z_]+)\]\s*\n(\s*\n)*"
        match = re.match(mode_pattern, response, re.MULTILINE)

        if match:
            # Remove the stage marker and the surrounding consecutive blank lines from the response
            response = re.sub(mode_pattern, "", response, count=1)

        return response

    def _filter_tool_calls_from_response(self, response: str) -> str:
        """Filter tool-call content out of the response

        Args:
            response: the original response content

        Returns:
            str: the filtered response content (excluding the tool-call part)
        """
        from haijunbot.haijunbot_utils.utils import extract_json_from_text
        from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads

        # First remove the <tool_call>toolname argsJSON format
        tool_call_pattern = r"<tool_call>\s*\w+\s+"
        matches = list(re.finditer(tool_call_pattern, response))

        # Delete from back to front to avoid index changes
        for match in reversed(matches):
            json_start = match.end()
            # Skip whitespace characters to find the position of {
            while json_start < len(response) and response[json_start].isspace():
                json_start += 1

            if json_start < len(response) and response[json_start] == "{":
                # Use extract_json_from_text to extract the complete JSON object
                json_str, end_pos = extract_json_from_text(response, json_start)
                if json_str:
                    # Delete the entire segment from <tool_call> to the end of the JSON
                    response = response[: match.start()] + response[end_pos:]

        # Pure JSON protocol: scan and remove all JSON objects containing name and arguments fields
        # Also clean up the surrounding ```json or ``` markers
        filtered = ""
        last_end = 0
        i = 0
        while i < len(response):
            if response[i] == "{":
                json_str, end_pos = extract_json_from_text(response, i)
                if json_str:
                    try:
                        parsed = json_loads(json_str)
                        if (
                            isinstance(parsed, dict)
                            and "name" in parsed
                            and "arguments" in parsed
                        ):
                            # Skip this tool-call JSON
                            filtered += response[last_end:i]
                            last_end = end_pos
                            i = end_pos
                            continue
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_agent.run_loop",
                            function="_filter_tool_calls_from_response",
                        )
                        pass
                i += 1
            elif response[i : i + 3] == "```":
                # Detect the ``` or ```json marker; if it is a marker before/after the tool-call JSON, skip it
                fence_end = i + 3
                # Skip the optional "json" keyword
                if (
                    fence_end < len(response)
                    and response[fence_end : fence_end + 4].lower() == "json"
                ):
                    fence_end += 4
                # Skip the whitespace and newlines after ```
                while fence_end < len(response) and response[fence_end] in (
                    " ",
                    "\t",
                    "\n",
                    "\r",
                ):
                    fence_end += 1
                # Check whether a tool-call JSON immediately follows the ```
                if fence_end < len(response) and response[fence_end] == "{":
                    json_str, json_end = extract_json_from_text(response, fence_end)
                    if json_str:
                        try:
                            parsed = json_loads(json_str)
                            if (
                                isinstance(parsed, dict)
                                and "name" in parsed
                                and "arguments" in parsed
                            ):
                                # Skip the whole ```json
                                # {...}
                                # ``` block
                                filtered += response[last_end:i]
                                last_end = json_end
                                i = json_end
                                # Check whether there is a ``` marker at the end
                                while i < len(response) and response[i] in (
                                    " ",
                                    "\t",
                                    "\n",
                                    "\r",
                                ):
                                    i += 1
                                if i < len(response) and response[i : i + 3] == "```":
                                    i += 3
                                last_end = i
                                continue
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_agent.run_loop",
                                function="_filter_tool_calls_from_response",
                            )
                            pass
                i += 1
            else:
                i += 1
        filtered += response[last_end:]

        # Clean up any leftover extra blank lines (replace more than 2 consecutive newlines with 2)
        filtered = re.sub(r"\n{3,}", "\n\n", filtered)
        return filtered.strip()

    def _handle_interrupt_with_input(self) -> Optional[str]:
        """Handle the interrupt and get extra information from the user

        Returns:
            Optional[str]: if the user entered extra information, return a formatted string; otherwise return None
        """
        from haijunbot.haijunbot_utils.input import get_multiline_input
        from haijunbot.haijunbot_utils.input import get_single_line_input

        try:
            user_input = get_multiline_input(
                "⚠ Interrupt detected; please enter extra information (Ctrl+J/Ctrl+] to confirm, press Enter to skip)",
                print_on_empty=False,
            )
            if user_input and user_input.strip():
                return f"[User interrupt] Extra information: {user_input.strip()}"
        except (KeyboardInterrupt, EOFError):
            # The user interrupted again; ask whether to fully exit
            PrettyOutput.auto_print("🔄 Interrupt detected again; please choose an action:")
            PrettyOutput.auto_print("  1. Skip the extra information and continue execution")
            PrettyOutput.auto_print("  2. Fully exit the program")
            try:
                choice = get_single_line_input("Please enter an option (1/2, press Enter to skip by default):")
                if choice and choice.strip() == "2":
                    raise  # Re-raise KeyboardInterrupt so the outer layer handles the exit
            except (KeyboardInterrupt, EOFError):
                raise  # The user interrupted again; exit directly
        return None

    def _recover_interrupt_addon(self, ag) -> None:
        """KeyboardInterrupt recovery.

        Text protocol: merge the user's extra information into addon, and set the input handler to run next round.
        Native function calling: the extra information is **passed directly as the next round's user input** to the model—
        it cannot go into addon, because when _call_model runs run_input_handlers, if message is empty it does
        `if not message: return ""`, causing the message to never be sent and returning to the input prompt;
        at the same time, clean up the pending tool state (_pending_native_tool_calls / _native_continue).
        """
        addon_info = self._handle_interrupt_with_input()

        if ag._native_active():
            ag._pending_native_tool_calls = None
            ag._native_continue = False
            ag.session.prompt = ensure_str(addon_info or "")
            ag.run_input_handlers_next_turn = False
            return

        if addon_info:
            ag.session.addon_prompt = ensure_str(
                join_prompts([ag.session.addon_prompt, addon_info])
            )
        ag.run_input_handlers_next_turn = True

    def _augment_round_prompt(self, prompt) -> Any:
        """Assemble this round's model input: append the global input buffer, and prepend the current time when non-empty.

        Unified injection logic for both str / multimodal List[ContentBlock] forms.
        """
        from haijunbot.haijunbot_utils.globals import get_input_buffer

        buffered_messages = get_input_buffer()
        if buffered_messages:
            supplement = "\n\n[User supplement]\n" + "\n".join(buffered_messages)
            if isinstance(prompt, str):
                prompt = prompt + supplement
            else:
                prompt = list(prompt) + [{"type": "text", "text": supplement}]

        has_prompt_content = (
            bool(prompt.strip()) if isinstance(prompt, str) else len(prompt) > 0
        )
        if has_prompt_content:
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_prompt = f"[Current time: {current_time_str}]\n\n"
            if isinstance(prompt, str):
                prompt = time_prompt + prompt
            else:
                prompt = [{"type": "text", "text": time_prompt}] + prompt
        return prompt

    def check_and_compress_context(
        self,
        model_instance,
        current_message_tokens: int = 0,
    ) -> None:
        """Check and compress the conversation context

        Automatic compression trigger check: checked before calling the model (based on the remaining token count or conversation turn)

        Args:
            model_instance: the platform model instance (a BasePlatform subclass instance)
            current_message_tokens: the token count of the current message
        """
        conversation_turn = model_instance.get_conversation_turn()
        try:
            # Get the remaining token count
            remaining_tokens = model_instance.get_remaining_token_count()
            max_input_tokens = model_instance._get_platform_max_input_token_count()

            # Subtract the current message's token count from the remaining tokens
            remaining_tokens -= current_message_tokens

            # Check whether the compression trigger conditions are met
            # Condition 1: remaining tokens below 10% (i.e. more than 90% used)
            token_limit_triggered = max_input_tokens > 0 and remaining_tokens <= int(
                max_input_tokens * 0.10
            )

            # Condition 2: conversation turn exceeds the threshold (check current turn+1, because this call adds one turn)
            conversation_turn_threshold = get_conversation_turn_threshold()
            turn_limit_triggered = (conversation_turn + 1) > conversation_turn_threshold

            # Pre-compression trigger condition: remaining tokens below 25% (i.e. more than 75% used)
            # Start background pre-compression, generating the summary in advance, to be used directly when the 90% trigger fires
            pre_compress_triggered = (
                max_input_tokens > 0
                and remaining_tokens <= int(max_input_tokens * 0.25)
                and not token_limit_triggered
            )
            if pre_compress_triggered:
                # Start background pre-compression (executed silently, not blocking the main flow)
                self.agent._start_background_pre_compression()

            should_compress = token_limit_triggered or turn_limit_triggered

            # Background pre-compression complete: apply the summary to compress the context immediately, without waiting for the 90% threshold
            # (it is also applied inside _adaptive_compression when the 90% trigger fires; here it handles the case of not yet reaching 90%)
            if (
                not should_compress
                and self.agent._pre_compressed_summary
                and not self.agent._pre_compressing
            ):
                if self.agent._check_and_use_pre_compressed_summary():
                    PrettyOutput.auto_print(
                        "✅ Background pre-compression is complete; applying the summary to compress the context immediately"
                    )
                    return

            if should_compress:
                # Check whether it was caused by the current message being too long
                current_prompt = self.agent.session.prompt
                if current_prompt and current_message_tokens > 0:
                    # Compute the ratio of the current message to the total tokens
                    total_tokens = (
                        max_input_tokens - remaining_tokens + current_message_tokens
                    )
                    message_ratio = (
                        current_message_tokens / total_tokens if total_tokens > 0 else 0
                    )

                    # If the current message exceeds 30% of the total tokens, perform truncation
                    if message_ratio > 0.3:
                        PrettyOutput.auto_print(
                            f"⚠️ Current message is too long (accounting for {message_ratio * 100:.1f}%), performing truncation"
                        )

                        # Truncation strategy: keep the first and last 20%
                        # Note: current_prompt may be a string or a multimodal list
                        if isinstance(current_prompt, str):
                            content_length = len(current_prompt)
                            keep_start = int(content_length * 0.2)
                            keep_end = max(1, int(content_length * 0.2))

                            truncated_prompt = (
                                current_prompt[:keep_start]
                                + "\n...[middle part omitted]...\n"
                                + current_prompt[-keep_end:]
                            )
                        else:
                            # For multimodal content, skip truncation for now
                            truncated_prompt = current_prompt

                        # Update the prompt and recompute the tokens
                        self.agent.session.prompt = truncated_prompt
                        # Note: truncated_prompt may be a string or a multimodal list
                        if isinstance(truncated_prompt, str):
                            current_message_tokens = get_context_token_count(
                                truncated_prompt
                            )
                        else:
                            # For multimodal content, set to 0 for now
                            # TODO: implement more precise multimodal token counting
                            current_message_tokens = 0

                        # Recompute the remaining tokens and determine whether compression is still needed
                        remaining_tokens = model_instance.get_remaining_token_count()
                        remaining_tokens -= current_message_tokens
                        token_limit_triggered = (
                            max_input_tokens > 0
                            and remaining_tokens <= int(max_input_tokens * 0.10)
                        )
                        should_compress = token_limit_triggered or turn_limit_triggered

                        if not should_compress:
                            PrettyOutput.auto_print("✅ No compression needed after truncation")
                            return  # Return directly without performing compression

                # Determine the trigger reason
                if token_limit_triggered and turn_limit_triggered:
                    trigger_reason = "Token and round dual limit triggered"
                elif token_limit_triggered:
                    trigger_reason = "Token limit triggered"
                else:
                    trigger_reason = "Conversation round limit triggered"

                # Print the trigger information
                if token_limit_triggered:
                    PrettyOutput.auto_print(
                        f"🔍 {trigger_reason}, current remaining tokens: {remaining_tokens}/{max_input_tokens} (remaining {remaining_tokens / max_input_tokens * 100:.1f}%)"
                    )
                else:
                    PrettyOutput.auto_print(
                        f"🔍 {trigger_reason}, current conversation turn: {conversation_turn + 1}/{conversation_turn_threshold}"
                    )

                try:
                    # Use adaptive compression: dynamically select the compression strategy based on the task type
                    compression_success = self.agent._adaptive_compression()

                    if compression_success:
                        # Adaptive compression succeeded; the summary has been inserted into the history as a message
                        PrettyOutput.auto_print("✅ Adaptive compression complete; the conversation context has been updated")
                    else:
                        # Adaptive compression failed; fall back to full summary compression
                        PrettyOutput.auto_print("⚠️ Adaptive compression failed, falling back to full summary compression")
                        summary_text = self.agent._summarize_and_clear_history(
                            trigger_reason=trigger_reason
                        )

                        if summary_text:
                            # Add the summary to addon_prompt to maintain context continuity
                            self.agent.session.addon_prompt = ensure_str(
                                join_prompts(
                                    [self.agent.session.addon_prompt, summary_text]
                                )
                            )
                            # Full compression cleared session.prompt; set the force-continue flag,
                            # so that subsequent rounds do not fall into _get_next_user_action and return to the user even without tool calls
                            self.agent._force_continue_after_compress = True

                        PrettyOutput.auto_print("✅ Full summary compression complete; the conversation context has been updated")
                except Exception as e:
                    # Compression failure does not affect the conversation flow
                    PrettyOutput.auto_print(f"⚠️ Automatic compression failed: {str(e)}")
        except Exception as e:
            # Compression check failure does not affect the conversation flow
            PrettyOutput.auto_print(f"⚠️ Compression check failed: {str(e)}")

    def _handle_summary(self, ag, current_response: str) -> tuple[bool, str]:
        """Handle the SUMMARY marker

        Args:
            ag: the agent instance
            current_response: the current response content

        Returns:
            tuple[bool, str]: (whether to continue to the next round, the processed response content)
        """

        if ot("!!!SUMMARY!!!") not in current_response:
            return False, current_response

        PrettyOutput.auto_print(f"ℹ️ {ot('!!!SUMMARY!!!')}")
        # Remove the marker to prevent it from appearing in subsequent processing
        current_response = current_response.replace(ot("!!!SUMMARY!!!"), "").strip()
        # Get the git diff before summarizing (only for the CodeAgent type)
        try:
            if hasattr(ag, "start_commit") and ag.start_commit:
                self._git_diff = self.get_git_diff()
            else:
                self._git_diff = None
        except KeyboardInterrupt:
            raise
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to get git diff: {str(e)}")
            self._git_diff = f"Failed to get git diff: {str(e)}"
        # Broadcast the before-summary event (manually triggered summary scenario; does not affect the main flow)
        # Note: this scenario is a summary actively requested by the user, auto_completed=False
        # Complementary to the automatic summary scenario in _complete_task (auto_completed=True)
        try:
            ag.event_bus.emit(
                BEFORE_SUMMARY,
                agent=ag,
                prompt=current_response,
                auto_completed=False,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.run_loop", function="_handle_summary"
            )
            pass
        # Use full summarization directly
        summary_text = ag._summarize_and_clear_history(trigger_reason="Manual trigger")
        # Broadcast the after-summary event (manually triggered summary scenario; does not affect the main flow)
        try:
            ag.event_bus.emit(
                AFTER_SUMMARY,
                agent=ag,
                summary=summary_text,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.run_loop", function="_handle_summary"
            )
            pass
        if summary_text:
            # Add the summary as the next round's additional hint, thereby maintaining context continuity
            ag.session.addon_prompt = ensure_str(
                join_prompts([ag.session.addon_prompt, summary_text])
            )
        # If there is other content in the response, continue processing; otherwise continue to the next round
        if not current_response:
            return True, current_response
        return False, current_response

    def _handle_tool_calls(self, ag, current_response: str) -> tuple[bool, Any, str]:
        """Handle tool calls

        Args:
            ag: the agent instance
            current_response: the current response content

        Returns:
            tuple[bool, Any, str]: (whether a result needs to be returned, the returned result or None, safe_tool_prompt)
                - If the tool requires returning a result immediately, return (True, tool_prompt, safe_tool_prompt)
                - If the next round needs to continue, return (True, None, safe_tool_prompt)
                - Otherwise return (False, None, safe_tool_prompt) and continue executing the subsequent logic
        """
        try:
            need_return, tool_prompt = ag._call_tools(current_response)
        except KeyboardInterrupt:
            # Get the user's extra information and continue execution
            self._recover_interrupt_addon(ag)
            need_return = False
            tool_prompt = ""

        # If the tool requires returning a result immediately (e.g. SEND_MESSAGE needs to return a dict to the upper layer), return that result directly
        if need_return:
            ag._no_tool_call_count = 0
            safe_tool_prompt = tool_prompt if isinstance(tool_prompt, str) else ""
            return True, tool_prompt, safe_tool_prompt

        # Safely concatenate the previous prompt and the tool prompt (only when the tool result is a string)
        safe_tool_prompt = tool_prompt if isinstance(tool_prompt, str) else ""

        ag.session.prompt = join_prompts([ag.session.prompt, safe_tool_prompt])

        # Broadcast the after-tool-call event: emit calls all subscribed callbacks in priority order
        # (previously _listeners was traversed manually and then emit was called, causing the same batch of callbacks to be dispatched twice)
        try:
            ag.event_bus.emit(
                AFTER_TOOL_CALL,
                agent=ag,
                current_response=current_response,
                need_return=need_return,
                tool_prompt=tool_prompt,
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.run_loop", function="_handle_tool_calls"
            )
            pass

        # Check whether continuation is needed
        if ag.session.prompt or ag.session.addon_prompt:
            ag._no_tool_call_count = 0
            return True, None, safe_tool_prompt

        return False, None, safe_tool_prompt

    def _collect_auto_complete_context(self, ag) -> str:
        """Collect the context information needed for auto-completion

        Args:
            ag: the agent instance

        Returns:
            str: the formatted context information string
        """
        context_parts = []

        # 1. Check the code modification status
        try:
            if hasattr(ag, "start_commit") and ag.start_commit:
                from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

                current_commit = get_latest_commit_hash()
                if current_commit and ag.start_commit != current_commit:
                    context_parts.append("✅ Code modifications detected.")
                else:
                    context_parts.append("⚠ No code modifications detected.")
        except Exception:
            context_parts.append("❓ Unable to detect the code modification status.")

        # 2. Check the unfinished task status
        all_unfinished_tasks = []
        try:
            if hasattr(ag, "task_list_manager") and ag.task_list_manager.task_lists:
                for task_list_id, task_list in ag.task_list_manager.task_lists.items():
                    summary = ag.task_list_manager.get_task_list_summary(task_list_id)
                    if summary:
                        for task in summary.get("tasks", []):
                            if task.get("status") in ["pending", "running"]:
                                all_unfinished_tasks.append(
                                    {
                                        "task_id": task.get("task_id"),
                                        "task_name": task.get("task_name"),
                                        "task_desc": task.get("task_desc", "")[:100]
                                        + "..."
                                        if len(task.get("task_desc", "")) > 100
                                        else task.get("task_desc", ""),
                                        "status": task.get("status"),
                                        "task_list_id": task_list_id,
                                        "main_goal": summary.get("main_goal", ""),
                                    }
                                )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.run_loop",
                function="_collect_auto_complete_context",
            )
            pass

        if all_unfinished_tasks:
            context_parts.append(
                f"📋 Detected {len(all_unfinished_tasks)} unfinished tasks:"
            )
            for task in all_unfinished_tasks[:5]:  # Show at most 5
                context_parts.append(
                    f"  - {task.get('task_name', 'Unknown')}: {task.get('status', 'Unknown')}"
                )
        else:
            context_parts.append("✅ No unfinished tasks.")

        return "\n".join(context_parts)

    def _execute_auto_complete(self, ag, current_response: str) -> tuple[bool, Any]:
        """Execute the auto-completion operation

        Args:
            ag: the agent instance
            current_response: the current response content

        Returns:
            tuple[bool, Any]: (whether to continue to the next round, the returned result or None)
                - If the next round needs to continue, return (True, None)
                - If a result needs to be returned, return (False, result)
        """
        # On auto-completion, execute the commit flow (refer to the commit command implementation in builtin_input_handler)
        if (
            hasattr(ag, "git_manager")
            and hasattr(ag, "start_commit")
            and ag.start_commit
        ):
            try:
                from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

                PrettyOutput.auto_print("📝 AutoComplete: committing code...")
                end_commit = get_latest_commit_hash()
                commits = ag.git_manager.show_commit_between(
                    ag.start_commit, end_commit
                )
                ag.git_manager.handle_commit_confirmation(
                    commits,
                    ag.start_commit,
                    prefix=getattr(ag, "prefix", ""),
                    suffix=getattr(ag, "suffix", ""),
                    agent=ag,
                    post_process_func=getattr(
                        getattr(ag, "post_process_manager", None),
                        "post_process_modified_files",
                        None,
                    ),
                    skip_confirm=True,
                )
                # Mark auto-completion as committed, to avoid CodeAgent.run committing again
                try:
                    ag._auto_commit_done = True
                except Exception:
                    pass
            except Exception as e:
                save_exception(
                    e, module="haijunbot_agent.run_loop", function="_execute_auto_complete"
                )
                PrettyOutput.auto_print(f"⚠ AutoComplete: failed to commit code: {str(e)}")

        if ag.return_control_on_auto_complete:
            ag.return_control_on_auto_complete = False
            if ag.non_interactive:
                ag.set_non_interactive(False)
            ag.run_input_handlers_next_turn = True
            PrettyOutput.auto_print(
                "🤝 AutoComplete has completed the current automatic execution phase; now restored to interactive mode and returned control to the user."
            )
            return True, None
        else:
            # First run _complete_task to trigger side effects such as memory consolidation/events, then decide the return value
            result = ag._complete_task(auto_completed=True)
            # If a summary is not needed, use the last LLM output as the return value
            if not getattr(ag, "need_summary", True):
                return False, current_response
            return False, result

    def _track_no_tool_call(
        self, ag, safe_tool_prompt: str, current_response: str
    ) -> tuple[bool, Any]:
        """Track the no-tool-call situation and attempt to fix it when necessary

        Core logic:
        - First-round detection: if it is the first round and there is no tool call, trigger a cheap LLM to judge whether a tool should be called
        - Subsequent rounds: follow the original logic (fix when there are 2 consecutive rounds with no tool call)

        Args:
            ag: the agent instance
            safe_tool_prompt: the safe tool prompt content
            current_response: the current response content

        Returns:
            tuple[bool, Any]: (whether to continue to the next round, the returned result or None)
                - If the next round needs to continue, return (True, None)
                - If a result needs to be returned, return (False, result)
                - Otherwise return (False, None) and continue executing the subsequent logic
        """
        # Check whether there is a tool call: if tool_prompt is not empty, it means a tool was called
        has_tool_call = bool(safe_tool_prompt and safe_tool_prompt.strip())
        # Save the current response content for the user to manually fix the tool call
        ag._last_response_content = current_response

        # [New] First-round detection: if it is the first round and there is no tool call, trigger a cheap LLM judgment
        # Note: regardless of whether there is a tool call in the first round, the flag must be reset to avoid false triggering in subsequent rounds
        is_first_run = getattr(ag, "_first_run_occurred", False)
        ag._first_run_occurred = False
        if is_first_run and not has_tool_call:
            try:
                from haijunbot.haijunbot_platform.registry import PlatformRegistry
                from haijunbot.haijunbot_agent.utils import build_fix_prompt

                # Create a temporary cheap LLM to avoid extra cost
                platform_registry = PlatformRegistry()
                cheap_model = platform_registry.get_cheap_platform()

                # Build the inquiry prompt: includes the user's original input, the LLM response, and a tool list summary
                tool_list_summary = ag.get_tool_usage_prompt()
                # Truncate the tool list summary to avoid it being too long
                if len(tool_list_summary) > 2000:
                    tool_list_summary = (
                        tool_list_summary[:2000] + "\n...(tool list too long, truncated)"
                    )

                ask_prompt = (
                    "The following is the Agent's first-round output; please judge whether a tool needs to be called.\n\n"
                    f"User input: {ag.original_user_input}\n\n"
                    f"Agent response: {current_response[:1000]}\n\n"
                    f"Available tool summary: {tool_list_summary}\n\n"
                    "Please judge: should the Agent call a tool to complete this task?\n"
                    "If a tool should be called, reply <!!!YES!!!>\n"
                    "If no tool needs to be called (e.g. pure conversation, greetings, etc.), reply <!!!NO!!!>"
                )

                # Call the cheap LLM to get the judgment result
                judgment = cheap_model.chat_until_success(ask_prompt)

                if "<!!!YES!!!>" in judgment:
                    # A tool should be called; inject the FixToolCall prompt
                    PrettyOutput.auto_print(
                        "🔍 No tool call in the first round; the cheap LLM judged that a tool should be called; injecting the fix prompt"
                    )
                    fix_prompt = build_fix_prompt(
                        content=current_response,
                        error_msg="No tool was called in the first round; please correct the output according to the tool instructions",
                        tool_usage=ag.get_tool_usage_prompt(),
                    )
                    ag.set_addon_prompt(fix_prompt)
                    ag._no_tool_call_count = 0
                    # Continue to the next round immediately after injecting the fix prompt, interacting with the LLM
                    return True, None
                else:
                    # No tool should be called or the judgment is unclear; skip silently
                    ag._no_tool_call_count = 0
                    return False, None

            except Exception:
                # On exception, skip silently without affecting the main flow
                ag._no_tool_call_count = 0
                return False, None

        # [Original logic] For non-first rounds or when there is already a tool call, follow the original logic
        # In non-interactive mode, track the number of consecutive rounds without a tool call
        if ag.non_interactive:
            if has_tool_call:
                # There is a tool call; reset the counter
                ag._no_tool_call_count = 0
            else:
                # No tool call; increment the counter
                ag._no_tool_call_count += 1
                # If there are 2 consecutive rounds with no tool call, attempt to fix with an LLM
                if ag._no_tool_call_count >= 2:
                    from haijunbot.haijunbot_agent.utils import fix_tool_call_with_llm

                    error_msg = "There have been 2 consecutive conversations with no tool call; please use a tool to complete the current task"
                    PrettyOutput.auto_print(f"⚠ {error_msg}")

                    # Attempt to fix with an LLM
                    fixed_content = fix_tool_call_with_llm(
                        current_response, ag, error_msg
                    )

                    if fixed_content:
                        # Fix succeeded; re-parse and execute the tool call directly
                        need_return, tool_prompt = ag._call_tools(fixed_content)

                        # If the tool requires returning a result immediately, return that result directly
                        if need_return:
                            ag._no_tool_call_count = 0
                            return False, tool_prompt

                        # Safely concatenate the previous prompt and the tool prompt
                        safe_tool_prompt = (
                            tool_prompt if isinstance(tool_prompt, str) else ""
                        )

                        ag.session.prompt = join_prompts(
                            [ag.session.prompt, safe_tool_prompt]
                        )
                    else:
                        # Fix failed; send the tool usage hint
                        tool_usage_prompt = ag.get_tool_usage_prompt()
                        ag.set_addon_prompt(tool_usage_prompt)

                    # Reset the counter to avoid repeated additions
                    ag._no_tool_call_count = 0

        # By default do not continue; go through the subsequent logic of the main loop
        return False, None

    def _check_auto_complete(self, ag, current_response: str) -> tuple[bool, Any]:
        """Check and handle auto-completion

        Args:
            ag: the agent instance
            current_response: the current response content

        Returns:
            tuple[bool, Any]: (whether to continue to the next round, the returned result or None)
                - If the next round needs to continue, return (True, None)
                - If a result needs to be returned, return (False, result)
                - Otherwise return (False, None) and continue executing the subsequent logic
        """
        if not (ag.auto_complete and is_auto_complete(current_response)):
            return False, None

        ag._no_tool_call_count = 0

        if ag.non_interactive:
            # Non-interactive mode: must go through LLM secondary confirmation
            # Collect context information
            context = self._collect_auto_complete_context(ag)

            # Build the confirmation prompt
            confirm_prompt_parts = ["Auto-completion marker detected; please confirm whether the current task is complete.\n"]
            confirm_prompt_parts.append(context)
            confirm_prompt_parts.append(
                "\n⚠️ Important: before confirming completion, you must verify that all acceptance criteria have passed:"
            )
            confirm_prompt_parts.append("1. Check whether the task goal is fully achieved")
            confirm_prompt_parts.append("2. Verify whether all deliverables meet the requirements")
            confirm_prompt_parts.append("3. Confirm there is no omitted or unfinished work item")
            confirm_prompt_parts.append("4. Ensure the result quality meets the expected standard")
            confirm_prompt_parts.append(
                "\nIf all acceptance criteria have passed, reply <!!!YES!!!>"
            )
            confirm_prompt_parts.append(
                "If there is still any unfinished or unverified item, reply <!!!NO!!!> and continue executing the task"
            )

            confirm_prompt = "\n".join(confirm_prompt_parts)

            # Inject the current time/date into the confirmation prompt (inject only when the prompt is non-empty)
            if confirm_prompt.strip():
                current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                confirm_prompt = f"[Current time: {current_time_str}]\n\n" + confirm_prompt

            # Ask the LLM
            try:
                llm_response = ag._call_model(confirm_prompt, False, False)
            except KeyboardInterrupt:
                self._recover_interrupt_addon(ag)
                return True, None

            # Parse the response
            if "<!!!NO!!!>" in llm_response:
                ag.set_addon_prompt("The LLM chose to continue executing the task.")
                PrettyOutput.auto_print("📝 The LLM confirmed to continue executing the task.")
                return True, None
            elif "<!!!YES!!!>" in llm_response:
                PrettyOutput.auto_print("✅ The LLM confirmed the current task is complete.")
            else:
                ag.set_addon_prompt("Please continue the task.")
                PrettyOutput.auto_print("⚠ The LLM response is unclear; continuing to execute the task by default.")
                return True, None

        # Execute auto-completion (directly in interactive mode; after LLM confirmation in non-interactive mode)
        return self._execute_auto_complete(ag, current_response)

    def run(self) -> Any:
        """Main run loop (delegates to the methods and attributes of the passed-in agent instance)"""
        # Check whether the input handler has already been run externally (e.g. CodeAgent.run or haijunbot.py)
        # If it has, do not run input_handler again on the first _call_model call
        run_input_handlers = not getattr(
            self.agent, "_input_handlers_already_run", False
        )

        # Import the status manager
        from haijunbot.haijunbot_agent.haijunbot import get_agent_status_manager

        status_manager = get_agent_status_manager()

        while True:
            # Task begins; set to running status
            status_manager.set_running()
            ag = self.agent
            try:
                current_round = self.agent.model.get_conversation_turn()
                # When native function calling is active, do not inject the text tool list/reminder (tools are provided by the API tools)
                if (
                    current_round <= 1 or current_round % self.tool_reminder_rounds == 0
                ) and not self.agent._native_active():
                    self.agent.session.addon_prompt = ensure_str(
                        join_prompts(
                            [
                                self.agent.session.addon_prompt,
                                self.agent.get_tool_usage_prompt(),
                                "Please use tools to advance the current task.",
                            ]
                        )
                    )

                ag = self.agent

                # Update the input handler flag
                if ag.run_input_handlers_next_turn:
                    run_input_handlers = True
                    ag.run_input_handlers_next_turn = False

                # Check and perform compression before calling the model
                # Compute the current message's token count
                # Note: ag.session.prompt may be a string or a multimodal list
                if isinstance(ag.session.prompt, str):
                    current_message_tokens = (
                        get_context_token_count(ag.session.prompt)
                        if ag.session.prompt
                        else 0
                    )
                else:
                    # For multimodal content, estimate simply or set to 0 for now
                    # TODO: implement more precise multimodal token counting
                    current_message_tokens = 0
                self.check_and_compress_context(
                    model_instance=ag.model,
                    current_message_tokens=current_message_tokens,
                )

                # Assemble this round's input: append the global input buffer + prepend the current time (unified handling for str/multimodal)
                ag.session.prompt = self._augment_round_prompt(ag.session.prompt)

                # Call the model to get the response
                try:
                    current_response = ag._call_model(
                        ag.session.prompt, True, run_input_handlers
                    )
                except KeyboardInterrupt:
                    # Get the user's extra information and continue to the next round
                    self._recover_interrupt_addon(ag)
                    continue

                ag.session.prompt = ""
                run_input_handlers = False

                # Repeated response detection: a repeated response is determined when 3 consecutive responses are identical
                if current_response and current_response.strip():
                    filtered_for_detect = self._filter_tool_calls_from_response(
                        current_response
                    ).strip()
                    if filtered_for_detect:
                        if (
                            ag._last_responses
                            and ag._last_responses[-1] == filtered_for_detect
                        ):
                            ag._repeat_count += 1
                        else:
                            ag._repeat_count = 1
                        ag._last_responses.append(filtered_for_detect)
                        # Keep only the most recent 10 responses to avoid unbounded growth
                        if len(ag._last_responses) > 10:
                            ag._last_responses = ag._last_responses[-10:]

                        # 3 consecutive identical responses; determined as repeated; handle progressively by escalation level
                        if ag._repeat_count >= 3 and not ag._repeat_detected:
                            ag._repeat_detected = True
                            ag._repeat_count = 0
                            level = ag._repeat_escalation_level
                            if level == 0:
                                # Level 1: add a prompt + truncate the most recent repeated rounds
                                ag.session.prompt = join_prompts(
                                    [
                                        ag.session.prompt,
                                        "You just repeated the same answer; please stop restating and give a new answer.",
                                    ]
                                )
                                # Truncate the most recent repeated assistant message to cut off the model's self-feedback
                                try:
                                    history = ag.model.get_messages()
                                    if history:
                                        # Remove consecutive duplicate assistant messages from the end backwards
                                        new_history = list(history)
                                        removed = 0
                                        while new_history and removed < 3:
                                            last_msg = new_history[-1]
                                            if (
                                                last_msg.get("role", "").lower()
                                                == "assistant"
                                            ):
                                                new_history.pop()
                                                removed += 1
                                            else:
                                                break
                                        if removed > 0 and hasattr(
                                            ag.model, "set_messages"
                                        ):
                                            ag.model.set_messages(new_history)
                                except Exception:
                                    pass
                                PrettyOutput.auto_print(
                                    f"⚠ LLM detected with {3} consecutive repeated responses (level 1); truncated the repeated rounds and added a no-repeat hint"
                                )
                            elif level == 1:
                                # Level 2: sliding-window compression + stronger instruction
                                try:
                                    ag._sliding_window_compression()
                                except Exception:
                                    pass
                                ag.session.prompt = join_prompts(
                                    [
                                        ag.session.prompt,
                                        "You have repeated the same answer multiple times. I have compressed the context to help you break out of the loop. Please carefully review the current task and give a completely new answer; do not restate the previous output.",
                                    ]
                                )
                                PrettyOutput.auto_print(
                                    f"⚠ LLM detected with {3} consecutive repeated responses (level 2); compressed the context and strengthened the instruction"
                                )
                            else:
                                # Level 3: terminate the loop and request user intervention
                                PrettyOutput.auto_print(
                                    f"⚠ LLM detected with {3} consecutive repeated responses (level 3); terminating the loop and requesting user intervention"
                                )
                                ag.session.prompt = join_prompts(
                                    [
                                        ag.session.prompt,
                                        "You have repeated many times and cannot escape on your own. Please stop the current output and wait for user instructions.",
                                    ]
                                )
                            ag._repeat_escalation_level += 1

                # Print the LLM output (filter out tool-call content, before the intelligent enhancement processing)
                if current_response and current_response.strip():
                    # First remove the stage marker [MODE: xxx]
                    current_response = self._postprocess_response(current_response)
                    # Filter out the <TOOL_CALL>...</TOOL_CALL> tags and their content
                    filtered_response = self._filter_tool_calls_from_response(
                        current_response
                    )
                    # Print only when there is still content after filtering
                    if filtered_response:
                        # Do not show a title; print the content directly
                        PrettyOutput.print_markdown(
                            filtered_response, border_style="bright_blue"
                        )

                # Handle the SUMMARY marker
                should_continue, current_response = self._handle_summary(
                    ag, current_response
                )
                if should_continue:
                    continue

                # Handle interrupts
                interrupt_result = ag._handle_run_interrupt(current_response)
                if (
                    isinstance(interrupt_result, Enum)
                    and getattr(interrupt_result, "value", None) == "skip_turn"
                ):
                    # The interrupt handler requests skipping the rest of this round and starting the next loop directly
                    continue
                elif interrupt_result is not None and not isinstance(
                    interrupt_result, Enum
                ):
                    # The interrupt handler returned a final result; the task ends
                    return interrupt_result

                # Handle tool calls
                if ag._native_active():
                    # Native mode: the model-call layer makes only one call; tool_calls are stored in _pending_native_tool_calls.
                    # If there are pending tools, execute them and fill back role=tool, then continue to the top of the main loop,
                    # so that the next round goes through context compression / input_buffer injection / turn checks (consistent with the text protocol).
                    if getattr(ag, "_pending_native_tool_calls", None):
                        ag._execute_pending_native_calls()
                        should_return, result, safe_tool_prompt = True, None, ""
                    else:
                        should_return, result, safe_tool_prompt = False, None, ""
                else:
                    should_return, result, safe_tool_prompt = self._handle_tool_calls(
                        ag, current_response
                    )
                if should_return:
                    # The first-round detection flag has been consumed (regardless of whether there is a tool call), to avoid false triggering in subsequent rounds
                    ag._first_run_occurred = False
                    if result is not None:
                        # The tool requires returning the result immediately
                        return result
                    else:
                        # Need to continue to the next round
                        continue

                # Check auto-completion
                should_continue, result = self._check_auto_complete(
                    ag, current_response
                )
                if should_continue:
                    continue
                if result is not None:
                    return result

                # Track the no-tool-call situation (native mode has no text JSON anymore, so the heuristic no longer applies)
                if not ag._native_active():
                    should_continue, track_result = self._track_no_tool_call(
                        ag, safe_tool_prompt, current_response
                    )
                    if should_continue:
                        continue
                    if track_result is not None:
                        return track_result

                # Force continue after full compression: compression cleared session.prompt (the summary has been put into addon_prompt),
                # if the model did not call a tool this round, skip _get_next_user_action to avoid returning control to the user and interrupting the task.
                # The flag is cleared immediately after being consumed, taking effect only for the next round after compression, without affecting normal interactive mode behavior.
                if ag._force_continue_after_compress:
                    ag._force_continue_after_compress = False
                    continue

                # Get the next user input
                try:
                    next_action = ag._get_next_user_action()
                except KeyboardInterrupt:
                    # Get the user's extra information and continue to the next round
                    self._recover_interrupt_addon(ag)
                    continue
                action = normalize_next_action(next_action)
                if action == "continue":
                    run_input_handlers = True
                    continue
                elif action == "complete":
                    return ag._complete_task(auto_completed=False)

            except KeyboardInterrupt:
                # Get the user's extra information and continue execution
                self._recover_interrupt_addon(ag)
                continue
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Task failed: {str(e)}")
                from haijunbot.haijunbot_utils.input import get_multiline_input
                from haijunbot.haijunbot_agent.builtin_input_handler import (
                    builtin_input_handler,
                )

                while True:
                    try:
                        user_input = get_multiline_input(
                            "⚠ API call failed; please enter an action (press Enter to retry, you may enter '<SwitchModelGroup>'/'<SwitchModel>' to switch models, Ctrl+C to exit)",
                            print_on_empty=False,
                        )
                        if not user_input or not user_input.strip():
                            # Pressing Enter directly = retry with the original prompt (ag.session.prompt is still retained)
                            ag.run_input_handlers_next_turn = True
                            break
                        # Handle the user input (may contain special tags)
                        processed_input, need_return = builtin_input_handler(
                            user_input, ag
                        )
                        if need_return:
                            # A special tag has been handled (e.g. switch model); continue letting the user enter more actions or retry
                            continue
                        if processed_input and processed_input.strip():
                            # Content that is not a special tag; treat it as extra information
                            ag.session.addon_prompt = ensure_str(
                                join_prompts(
                                    [
                                        ag.session.addon_prompt,
                                        f"[API error recovery] {processed_input.strip()}",
                                    ]
                                )
                            )
                            ag.run_input_handlers_next_turn = True
                            break
                    except (KeyboardInterrupt, EOFError):
                        return f"Task failed: {str(e)}"
                continue

    def get_git_diff_stat(self) -> str:
        """Get the git diff statistics from the starting commit to the current commit

        Returns:
            str: git diff statistics, or an error message if it cannot be obtained
        """
        try:
            from haijunbot.haijunbot_utils.git_utils import get_diff_stat_between_commits
            from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

            # Get the agent instance
            agent = self.agent

            # Check whether the agent has the start_commit attribute
            if not hasattr(agent, "start_commit") or not agent.start_commit:
                return "Unable to get the initial commit hash"

            start_commit = agent.start_commit
            current_commit = get_latest_commit_hash()

            if not current_commit:
                return "Unable to get the current commit hash"

            if start_commit == current_commit:
                return "No code changes detected"

            # Get the diff statistics
            stat_content = get_diff_stat_between_commits(start_commit, current_commit)
            return stat_content

        except Exception as e:
            return f"Failed to get git diff stats: {str(e)}"

    def get_git_diff(self) -> str:
        """Get the git diff from the starting commit to the current commit

        Returns:
            str: the git diff content, or an error message if it cannot be obtained
        """
        try:
            from haijunbot.haijunbot_utils.git_utils import get_diff_between_commits
            from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash

            # Get the agent instance
            agent = self.agent

            # Check whether the agent has the start_commit attribute
            if not hasattr(agent, "start_commit") or not agent.start_commit:
                return "Unable to get the initial commit hash"

            start_commit = agent.start_commit
            current_commit = get_latest_commit_hash()

            if not current_commit:
                return "Unable to get the current commit hash"

            if start_commit == current_commit:
                return (
                    "# No code changes detected\n\nThe starting commit and the current commit are the same; there are no code changes."
                )

            # Get the diff
            diff_content = get_diff_between_commits(start_commit, current_commit)

            return self._check_diff_token_limit(diff_content)

        except Exception as e:
            return f"Failed to get git diff: {str(e)}"

    def get_cached_git_diff(self) -> Optional[str]:
        """Get the cached git diff information

        Returns:
            Optional[str]: the cached git diff content, or None if not yet obtained
        """
        return self._git_diff

    def has_git_diff(self) -> bool:
        """Check whether there is available git diff information

        Returns:
            bool: True if there is available git diff information, otherwise False
        """
        return self._git_diff is not None and bool(self._git_diff.strip())

    def _check_diff_token_limit(self, diff_content: str) -> str:
        """Check the token limit of the diff content and return the appropriate diff content

        Args:
            diff_content: the original diff content

        Returns:
            str: the processed diff content (may be the original content or truncated content)
        """
        from haijunbot.haijunbot_utils.embedding import get_context_token_count

        # Check the token count limit
        max_input_tokens = get_max_input_token_count()
        # Reserve part of the tokens for other content; use 10% as the diff limit
        max_diff_tokens = int(max_input_tokens * 0.1)

        diff_token_count = get_context_token_count(diff_content)

        if diff_token_count <= max_diff_tokens:
            return diff_content

        # If the diff content is too large, truncate it
        lines = diff_content.split("\n")
        truncated_lines = []
        current_tokens = 0

        for line in lines:
            line_tokens = get_context_token_count(line)
            if current_tokens + line_tokens > max_diff_tokens:
                # Add a truncation hint
                truncated_lines.append("")
                truncated_lines.append("# ⚠️ diff content too large, truncated for display")
                truncated_lines.append(
                    f"# The original diff has {len(lines)} lines, {diff_token_count} tokens"
                )
                truncated_lines.append(
                    f"# Showing the first {len(truncated_lines)} lines, about {current_tokens} tokens"
                )
                break

            truncated_lines.append(line)
            current_tokens += line_tokens

        return "\n".join(truncated_lines)
