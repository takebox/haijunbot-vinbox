# -*- coding: utf-8 -*-
"""History summary/compression responsibility module

The "history summary/compression" responsibility cluster extracted from the Agent class.

Design notes:
- Follows the existing split paradigm of the haijunbot_agent package (e.g. MemoryManager(self), AgentRunLoop(agent)):
  this module holds a reference to agent and accesses the Agent's other capabilities through self.agent.xxx inside method bodies.
- The Agent side keeps thin delegation methods of the same name, ensuring the external interface (including reverse calls from run_loop / code_agent) remains completely unchanged.
- Circular dependencies are handled through TYPE_CHECKING.
"""

from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_agent.events import AFTER_HISTORY_CLEAR
from haijunbot.haijunbot_agent.events import BEFORE_HISTORY_CLEAR
from haijunbot.haijunbot_agent.prompts import DEFAULT_SUMMARY_PROMPT
from haijunbot.haijunbot_agent.prompts import SUMMARY_REQUEST_PROMPT
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput

if TYPE_CHECKING:
    from haijunbot.haijunbot_agent import Agent


class HistoryCompressor:
    """History summary/compression responsibility implementation

    All methods are equivalent to the same-named methods on the original Agent class, only changing self.xxx to self.agent.xxx.
    """

    def __init__(self, agent: "Agent") -> None:
        self.agent = agent
        # Summary trigger reason: originally an Agent instance attribute, migrated here with this cluster
        # (this object is one-to-one with Agent, so behavior is equivalent)
        self._summary_trigger_reason = "Token limit triggered"

    def validate_summary(self, summary: str) -> tuple[bool, list[str]]:
        """Check whether the summary is acceptable.

        Only basic length checks are done; no fixed keywords are forced anymore, avoiding needless rewrite loops and extra inference cost.

        Returns:
            tuple[bool, list[str]]: (whether it passed, list of problems). Failure is determined only when the content is too short or empty.
        """
        if not summary:
            return False, ["Summary content is empty"]
        if len(summary.strip()) < 20:
            return False, ["Summary content is too short"]
        return True, []

    def generate_summary(self, for_token_limit: bool = False) -> str:
        """Generate a conversation history summary

        Args:
            for_token_limit: if True, indicates a summary triggered by the token limit, using SUMMARY_REQUEST_PROMPT
                             if False, indicates a summary at task completion, using the user-supplied summary_prompt

        Returns:
            str: a string containing the conversation summary

        Note:
            Only generates the summary; does not modify the conversation state
        """

        try:
            if not self.agent.model:
                raise RuntimeError("Model not initialized")

            if for_token_limit:
                PrettyOutput.auto_print(
                    "🔍 Starting to generate conversation history summary... (reason: token limit triggered)"
                )
            else:
                PrettyOutput.auto_print(
                    "🔍 Starting to generate conversation history summary... (reason: task completion triggered)"
                )

            if for_token_limit:
                # summary triggered by the token limit: use SUMMARY_REQUEST_PROMPT for context compression
                # For multimodal content, only extract the text part for summarization
                if isinstance(self.agent.session.prompt, list):
                    text_parts = [
                        b.get("text", "")
                        for b in self.agent.session.prompt
                        if b.get("type") == "text"
                    ]
                    prompt_text = "\n".join(text_parts)
                else:
                    prompt_text = self.agent.session.prompt
                prompt_to_use = prompt_text + "\n" + SUMMARY_REQUEST_PROMPT
            else:
                # summary at task completion: use the user-supplied summary_prompt or DEFAULT_SUMMARY_PROMPT
                safe_summary_prompt = self.agent.summary_prompt or ""
                if (
                    isinstance(safe_summary_prompt, str)
                    and safe_summary_prompt.strip() != ""
                ):
                    prompt_to_use = safe_summary_prompt
                else:
                    prompt_to_use = DEFAULT_SUMMARY_PROMPT

            # If it is a CodeAgent and has start_commit, append a hint to the prompt to only summarize the goals after that commit
            if hasattr(self.agent, "start_commit") and self.agent.start_commit:
                start_commit_hint = (
                    f"\n\n<start_commit_context>\n"
                    f"The initial Git Commit for this task is: `{self.agent.start_commit}`\n"
                    f"Please summarize only the task goals, changes, and progress after that commit,"
                    f"no need to summarize the historical content before that commit.\n"
                    f"</start_commit_context>"
                )
                prompt_to_use += start_commit_hint

            # Generate the summary, retrying at most 2 times
            max_retries = 2
            retry_count = 0
            summary = ""

            while retry_count <= max_retries:
                summary = self.agent.model.chat_until_success(prompt_to_use)
                # Defensive: it may return an empty response (None or empty string); normalize to empty string and warn
                if not summary:
                    try:
                        PrettyOutput.auto_print("⚠️  The model returned an empty response")
                    except Exception as e:
                        save_exception(
                            e,
                            module="haijunbot_agent.__init__",
                            function="generate_summary",
                        )
                        pass
                    summary = ""
                    break  # Do not retry on empty response

                # Do a basic length check only for summaries triggered by the token limit
                if for_token_limit and retry_count < max_retries:
                    if not self.validate_summary(summary)[0]:
                        retry_count += 1
                        PrettyOutput.auto_print(
                            f"⚠️  The summary is empty or too short, retry {retry_count}"
                        )
                        continue  # Regenerate

                # Validation passed or max retries reached; exit the loop
                break

            if summary:
                # Print the summary content using a Rich Panel
                try:
                    import haijunbot.haijunbot_utils.globals as G

                    title = f"[bold cyan]{(G.get_current_agent_name() + ' · ') if G.get_current_agent_name() else ''}{self.agent.model.model_name or 'LLM'} Conversation Summary[/bold cyan]"
                    PrettyOutput.print_markdown(
                        summary, title=title, border_style="cyan"
                    )
                except Exception:
                    # If Rich Panel printing fails, use the normal method to print the summary
                    try:
                        PrettyOutput.auto_print(f"📋 Conversation Summary:\n{summary}")
                    except Exception:
                        # If normal printing also fails, at least print a hint
                        PrettyOutput.auto_print("⚠️  Failed to print the summary content")
                        PrettyOutput.auto_print(
                            f"📋 Summary content (first 500 characters): {summary[:500]}..."
                        )
            return summary
        except KeyboardInterrupt:
            raise  # Propagate the interrupt signal directly upward
        except Exception:
            # Check whether this is an exception caused by an interrupt
            from haijunbot.haijunbot_utils.utils import get_interrupt

            if get_interrupt() > 0:
                raise KeyboardInterrupt("User interrupted")
            PrettyOutput.auto_print("❌ Failed to summarize the conversation history")
            return ""

    def print_compression_summary(self, summary: str, compression_type: str) -> None:
        """Print the compression summary using a Panel

        Args:
            summary: the compressed summary content
            compression_type: the compression type (such as "sliding window compression", "importance-score compression", etc.)
        """
        try:
            import haijunbot.haijunbot_utils.globals as G

            title = f"[bold cyan]{(G.get_current_agent_name() + ' · ') if G.get_current_agent_name() else ''}{self.agent.model.model_name or 'LLM'} {compression_type} Summary[/bold cyan]"
            PrettyOutput.print_markdown(summary, title=title, border_style="cyan")
        except Exception:
            # If formatted output fails, fall back to simple printing
            PrettyOutput.auto_print(f"📋 {compression_type} Summary:\n{summary}")

    def sliding_window_compression(self, window_size: Optional[int] = None) -> bool:
        """Sliding window compression: keep the most recent 2 user/tool messages and 3 assistant messages, and compress earlier conversation

        Args:
            window_size: sliding window size (total number of messages to keep, default 5: 2 user/tool + 3 assistant); if None, use the configured value

        Returns:
            bool: True if compression executed successfully, otherwise False

        Note:
            - Only compresses user and assistant messages; system messages are always kept
            - Keeps the most recent 2 user/tool messages and 3 assistant messages (5 in total; odd to avoid consecutive same-role messages)
            - If the number of messages is insufficient, no compression is performed
            - The compressed history summary is inserted into the history as a user message
        """
        from haijunbot.haijunbot_utils.config import get_sliding_window_size

        if window_size is None:
            window_size = get_sliding_window_size()

        # Keep an odd number of user/tool messages and assistant messages (to avoid consecutive same-role messages)
        # Keep 2 user/tool messages and 3 assistant messages, 5 in total (odd)
        # Note: the actual number kept is controlled by the window_size parameter

        try:
            # Get the conversation history
            history = self.agent.model.get_messages()
            if not history:
                return False

            # Find the end position of the system messages (system messages are usually at the beginning and need to be kept)
            system_end_idx = 0
            for i, msg in enumerate(history):
                if msg.get("role", "").lower() != "system":
                    system_end_idx = i
                    break
            else:
                # If all messages are system messages, compression is impossible
                return False

            # System messages (need to be kept)
            system_messages = history[:system_end_idx]
            # Non-system messages (the part to be compressed)
            non_system_messages = history[system_end_idx:]

            # Only compress non-system messages with the window
            if len(non_system_messages) < window_size:
                return False

            # Take the last window_size non-system messages
            recent_messages = non_system_messages[-window_size:]

            # If the number of non-system messages is less than twice the window size, no compression is needed
            # (At least twice is needed, because the window still needs to be kept after compression)
            if len(non_system_messages) <= window_size * 2:
                return False

            # Separate the earlier non-system messages (messages not in the keep list)
            # Take one extra, because s u a u a u a u a u a u a
            old_messages = non_system_messages[: -window_size + 1]

            if not old_messages:
                return False

            # Compress the earlier messages
            try:
                # Create a temporary model using the same model as the current session
                # (Do not pass the system prompt, because it will be set via set_messages)
                temp_model = self.agent._create_temp_model()

                # Use set_messages to set the conversation history, including the system messages and the old messages to compress
                messages_to_set = system_messages + old_messages
                temp_model.set_messages(messages_to_set)

                # Use SUMMARY_REQUEST_PROMPT for compression (to avoid polluting the current conversation)
                # Do limited retries only when the summary is empty/too short; give up this compression if the limit is exceeded
                MAX_COMPRESS_RETRIES = 3
                compressed_summary = ""
                for retry_count in range(MAX_COMPRESS_RETRIES):
                    if retry_count == 0:
                        compressed_summary = temp_model.chat_until_success(
                            SUMMARY_REQUEST_PROMPT
                        )
                    else:
                        compressed_summary = temp_model.chat_until_success(
                            "The previous summary is empty or too short; please regenerate a complete, executable summary based on the above conversation history."
                        )

                    if not compressed_summary or not compressed_summary.strip():
                        PrettyOutput.auto_print("⚠Sliding window compression: failed to generate summary, skipping compression")
                        return False

                    # Do only a basic length check: pass and exit
                    if self.validate_summary(compressed_summary.strip())[0]:
                        break
                else:
                    PrettyOutput.auto_print(
                        f"⚠Sliding window compression: the summary is too short and has reached the maximum number of retries ({MAX_COMPRESS_RETRIES}), giving up this compression"
                    )
                    return False

                # Print the compression summary
                self.print_compression_summary(
                    compressed_summary.strip(), "Sliding window compression"
                )

                # Format the compressed summary, adding extra information such as Pin, memories, Git diff, etc.
                formatted_summary = self.format_compressed_summary(
                    compressed_summary.strip()
                )

                # Build the compressed message (inserted as a user message)
                compressed_msg = {
                    "role": "user",
                    "content": formatted_summary,
                }

                # Rebuild the message list: system messages + compressed summary + recent non-system messages
                new_history = system_messages + [compressed_msg] + recent_messages

                # Update the model's message history; use the set_messages method to ensure conversation_turn is updated correctly
                if hasattr(self.agent.model, "set_messages"):
                    self.agent.model.set_messages(new_history)
                    # Clean up the pre-compression state (to prevent leftover stale state from affecting subsequent compression)
                    self.agent._pre_compressed_summary = None
                    self.agent._pre_compress_snapshot_count = 0
                    self.agent._pre_compressing = False
                    # Count the types of messages kept
                    user_tool_count_kept = sum(
                        1
                        for msg in recent_messages
                        if msg.get("role", "").lower() in ["user", "tool"]
                    )
                    assistant_count_kept = sum(
                        1
                        for msg in recent_messages
                        if msg.get("role", "").lower() == "assistant"
                    )
                    PrettyOutput.auto_print(
                        f"✅ Sliding window compression complete: compressed {len(old_messages)} messages, "
                        f"kept the most recent {user_tool_count_kept} user/tool messages and {assistant_count_kept} assistant messages ({len(recent_messages)} in total)"
                    )
                    return True
                else:
                    # The model does not support the set_messages method, compression failed
                    return False

            except Exception as e:
                PrettyOutput.auto_print(
                    f"⚠️ Sliding window compression failed: {str(e)}, falling back to full summary compression"
                )
                return False

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Sliding window compression error: {str(e)}")
            return False

    def start_background_pre_compression(self) -> None:
        """Start background pre-compression: generate the summary in advance at the 75% threshold, and use it directly when the 90% trigger actually occurs.

        This method snapshots the current messages, creates a temporary model (silent mode), and generates the summary in a background thread.
        When done, it stores the formatted summary in _pre_compressed_summary for use during the actual compression.
        """
        import threading

        # If already compressing or a pre-compression result already exists, do not start again
        if self.agent._pre_compressing or self.agent._pre_compressed_summary:
            return

        try:
            # Get the conversation history
            history = self.agent.model.get_messages()
            if not history:
                return

            # Find the end position of the system messages
            system_end_idx = 0
            for i, msg in enumerate(history):
                if msg.get("role", "").lower() != "system":
                    system_end_idx = i
                    break
            else:
                return  # All messages are system messages, compression is impossible

            # Snapshot the messages
            system_messages = history[:system_end_idx]
            non_system_messages = history[system_end_idx:]

            # Use the same window size as _sliding_window_compression
            from haijunbot.haijunbot_utils.config import get_sliding_window_size

            window_size = get_sliding_window_size()

            # If the number of non-system messages is insufficient, no pre-compression is needed
            if len(non_system_messages) < window_size * 2:
                return
            # Separate the part to be compressed (messages before the window size)
            old_messages = non_system_messages[: -window_size + 1]

            if not old_messages:
                return

            # Record the number of snapshot messages
            self.agent._pre_compress_snapshot_count = len(history)
            self.agent._pre_compressing = True

            def _background_compress() -> None:
                """Background thread executing compression summary generation"""
                try:
                    # Create a temporary model, silent mode
                    temp_model = self.agent._create_temp_model()
                    temp_model.set_suppress_output(True)

                    # Use set_messages to set the conversation history
                    messages_to_set = system_messages + old_messages
                    temp_model.set_messages(messages_to_set)

                    # Use SUMMARY_REQUEST_PROMPT to generate the summary
                    compressed_summary = temp_model.chat_until_success(
                        SUMMARY_REQUEST_PROMPT
                    )

                    if not compressed_summary or not compressed_summary.strip():
                        self.agent._pre_compressing = False
                        return

                    # Limited retries only when the summary is empty/too short (no old-keyword supplement mode)
                    for retry_count in range(3):
                        if retry_count > 0:
                            compressed_summary = temp_model.chat_until_success(
                                "The previous summary is empty or too short; please regenerate a complete, executable summary based on the above conversation history."
                            )
                        if not compressed_summary or not compressed_summary.strip():
                            break
                        if self.validate_summary(compressed_summary.strip())[0]:
                            break

                    if not compressed_summary or not compressed_summary.strip():
                        self.agent._pre_compressing = False
                        return

                    # Format the compressed summary (silent, no printing)
                    formatted_summary = self.format_compressed_summary(
                        compressed_summary.strip()
                    )

                    # Before storing the pre-compression result, check whether it has been canceled externally (e.g. the foreground already compressed by itself)
                    if self.agent._pre_compressing:
                        self.agent._pre_compressed_summary = formatted_summary
                except Exception:
                    pass
                finally:
                    self.agent._pre_compressing = False

            # Start the background thread
            thread = threading.Thread(
                target=_background_compress,
                name="background-pre-compression",
                daemon=True,
            )
            thread.start()

        except Exception:
            # Pre-compression failure does not affect the main flow
            self.agent._pre_compressing = False

    def check_and_use_pre_compressed_summary(self) -> bool:
        """Check and use the pre-compressed summary to rebuild the session.

        Called when the 90% trigger actually fires. If pre-compression is complete, use the pre-generated summary to rebuild the message history directly;
        if it is still compressing, wait for it to finish before using it.

        Returns:
            bool: True if the session was successfully rebuilt using the pre-compressed summary, otherwise False
        """
        try:
            # If pre-compressing, wait for completion (at most 60 seconds)
            if self.agent._pre_compressing:
                import time

                wait_count = 0
                while self.agent._pre_compressing and wait_count < 120:  # Wait at most 60 seconds
                    time.sleep(0.5)
                    wait_count += 1

            # Check whether there is a pre-compression result
            if not self.agent._pre_compressed_summary:
                # Clean up the pre-compression state (may have timed out or the background compression failed)
                self.agent._pre_compressed_summary = None
                self.agent._pre_compress_snapshot_count = 0
                self.agent._pre_compressing = False
                return False

            # Get the current messages
            history = self.agent.model.get_messages()
            if not history:
                # Clean up the pre-compression state
                self.agent._pre_compressed_summary = None
                self.agent._pre_compress_snapshot_count = 0
                self.agent._pre_compressing = False
                return False

            # Find the end position of the system messages
            system_end_idx = 0
            for i, msg in enumerate(history):
                if msg.get("role", "").lower() != "system":
                    system_end_idx = i
                    break
            else:
                # Clean up the pre-compression state
                self.agent._pre_compressed_summary = None
                self.agent._pre_compress_snapshot_count = 0
                self.agent._pre_compressing = False
                return False

            system_messages = history[:system_end_idx]
            non_system_messages = history[system_end_idx:]

            # Use the same window size as _sliding_window_compression
            from haijunbot.haijunbot_utils.config import get_sliding_window_size

            window_size = get_sliding_window_size()

            # Divide messages based on the snapshot point:
            # Non-system messages before the message count recorded at snapshot time are the "already compressed part" (covered by the pre-compression summary),
            # and messages added after the snapshot should be kept as recent_messages
            if self.agent._pre_compress_snapshot_count > 0:
                # Snapshot point = number of system messages + number of non-system messages at snapshot time
                snapshot_non_system_count = max(
                    0, self.agent._pre_compress_snapshot_count - system_end_idx
                )
                # Non-system messages added after the snapshot point
                recent_messages = non_system_messages[snapshot_non_system_count:]
                # If no messages were added after the snapshot, keep the last window_size as context continuity
                if not recent_messages:
                    recent_messages = non_system_messages[-window_size:]
            else:
                # When there is no snapshot record, fall back to the sliding window logic
                recent_messages = non_system_messages[-window_size:]

            # Build the compressed message
            compressed_msg = {
                "role": "user",
                "content": self.agent._pre_compressed_summary,
            }

            # Rebuild the message list: system messages + compressed summary + messages added after the snapshot
            new_history = system_messages + [compressed_msg] + recent_messages

            # Update the model's message history
            if hasattr(self.agent.model, "set_messages"):
                self.agent.model.set_messages(new_history)
                # Clean up the pre-compression state
                self.agent._pre_compressed_summary = None
                self.agent._pre_compress_snapshot_count = 0
                self.agent._pre_compressing = False
                return True

            # The model does not support set_messages; clean up the pre-compression state
            self.agent._pre_compressed_summary = None
            self.agent._pre_compress_snapshot_count = 0
            self.agent._pre_compressing = False
            return False

        except Exception:
            # On exception, clean up the pre-compression state to avoid leftover stale state
            self.agent._pre_compressed_summary = None
            self.agent._pre_compress_snapshot_count = 0
            self.agent._pre_compressing = False
            return False

    def format_compressed_summary(self, compressed_summary: str) -> str:
        """Format the compressed summary, adding extra information such as Pin, memories, Git diff, etc.

        Args:
            compressed_summary: the compressed summary content

        Returns:
            str: the formatted complete summary content
        """
        formatted_summary = f"[History Summary] {compressed_summary}"

        # Add the important content fixed by the user
        user_fixed_content = []

        # Add important content fixed by the user via the <Pin> marker
        if self.agent.pin_content.strip():
            user_fixed_content.append(
                f"**User-fixed content**:\n{self.agent.pin_content.strip()}"
            )

        # Add the most recent memories
        if hasattr(self.agent, "recent_memories") and self.agent.recent_memories:
            user_fixed_content.append(
                f"**Recent memories**:\n{chr(10).join(self.agent.recent_memories)}"
            )

        # If there is any fixed content, add it to the summary (placed at the very front to ensure priority)
        if user_fixed_content:
            pin_section = f"\n\n## 🎯 The user's original needs and requirements (must always be kept in mind)\n{chr(10).join(user_fixed_content)}"
            formatted_summary = pin_section + "\n\n" + formatted_summary

        # Get the git diff statistics
        git_diff_stat = ""
        git_view_command = ""
        try:
            from haijunbot.haijunbot_agent.run_loop import AgentRunLoop

            if hasattr(self.agent, "_agent_run_loop") and isinstance(
                self.agent._agent_run_loop, AgentRunLoop
            ):
                agent_run_loop = self.agent._agent_run_loop
                # Get the diff statistics
                git_diff_stat = agent_run_loop.get_git_diff_stat()

                # Generate the view command
                if hasattr(self.agent, "start_commit") and self.agent.start_commit:
                    git_view_command = f"git diff {self.agent.start_commit}..HEAD"
            # If _agent_run_loop does not exist (e.g. in a background thread), skip the git diff statistics
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        # Add the git diff statistics to the summary - only show valid code change statistics
        is_valid_git_stat = (
            git_diff_stat
            and git_diff_stat.strip()
            and not git_diff_stat.startswith("Failed to get git diff stats")
            and "No code changes detected" not in git_diff_stat
        )

        if is_valid_git_stat:
            diff_section = f"\n\n## Code Change Statistics\n```\n{git_diff_stat}\n```"
            if git_view_command:
                diff_section += f"\n\nView the full diff: ```bash\n{git_view_command}\n```"
            formatted_summary += diff_section

        # Get the task list information
        task_list_info = ""
        try:
            # Get the summary information of all task lists
            task_lists_summary: List[Dict[str, Any]] = []
            for (
                task_list_id,
                task_list,
            ) in self.agent.task_list_manager.task_lists.items():
                summary_dict = self.agent.task_list_manager.get_task_list_summary(
                    task_list_id
                )
                if summary_dict and isinstance(summary_dict, dict):
                    task_lists_summary.append(summary_dict)

            if task_lists_summary:
                task_list_info = "\n\n## Task List Status\n"
                for summary_dict in task_lists_summary:
                    task_list_info += (
                        f"\n- Goal: {summary_dict.get('main_goal', 'unknown')}"
                    )
                    task_list_info += (
                        f"\n- Total tasks: {summary_dict.get('total_tasks', 0)}"
                    )
                    task_list_info += f"\n- Pending: {summary_dict.get('pending', 0)}"
                    task_list_info += f"\n- Running: {summary_dict.get('running', 0)}"
                    task_list_info += f"\n- Completed: {summary_dict.get('completed', 0)}"
                    task_list_info += f"\n- Failed: {summary_dict.get('failed', 0)}"
                    task_list_info += (
                        f"\n- Abandoned: {summary_dict.get('abandoned', 0)}\n"
                    )
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        # Add the task list information to the summary
        if task_list_info:
            formatted_summary += task_list_info

        # Get the initial commit information (only for CodeAgent)
        initial_commit_info = ""
        try:
            if hasattr(self.agent, "start_commit") and self.agent.start_commit:
                initial_commit_info = f"\n\n**🔖 Initial Git Commit (safe rollback point)**:\nThe initial commit at the start of this task is: `{self.agent.start_commit}`\n\n**⚠️ Important note**: If a file is damaged so severely that it cannot be recovered, you can use the following command to reset to this initial commit:\n```bash\ngit reset --hard {self.agent.start_commit}\n```\nThis will discard all uncommitted changes and restore the working tree to the state at the start of the task. Please use this command with caution and make sure this is really what you want."
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        if initial_commit_info:
            formatted_summary += initial_commit_info

        return formatted_summary

    def adaptive_compression(self) -> bool:
        """Adaptive compression: use the sliding window compression strategy

        Returns:
            bool: True if compression executed successfully, otherwise False
        """
        try:
            # First try to use the pre-compressed summary (background pre-compression was already started at 75%)
            if self.agent._check_and_use_pre_compressed_summary():
                PrettyOutput.auto_print("✅ Context compression completed using the background pre-compressed summary")
                return True

            # Pre-compression unavailable (wait timed out or background compression failed); clean up the pre-compression state and fall back to sliding window compression
            self.agent._pre_compressed_summary = None
            self.agent._pre_compress_snapshot_count = 0
            self.agent._pre_compressing = False
            return self.agent._sliding_window_compression()
        except Exception:
            # On exception, clean up the pre-compression state to avoid leftover stale state
            self.agent._pre_compressed_summary = None
            self.agent._pre_compress_snapshot_count = 0
            self.agent._pre_compressing = False
            PrettyOutput.auto_print("⚠ Adaptive compression failed, falling back to sliding window compression")
            return False

    def summarize_and_clear_history(self, trigger_reason: str = "Token limit triggered") -> str:
        """Summarize the current conversation and clear the history

        This method will:
        1. Prompt the user to save important memories
        2. Call generate_summary to generate the summary
        3. Clear the conversation history
        4. Keep the system messages
        5. Add the summary as new context
        6. Reset the conversation length counter

        Args:
            trigger_reason: the reason that triggered the summary

        Returns:
            str: a string containing the conversation summary

        Note:
            Used when the context length exceeds the maximum value
        """
        # Save the trigger reason to an instance variable for use by subsequent methods
        self._summary_trigger_reason = trigger_reason

        # File upload is no longer supported; handle the history directly with the summary approach
        return self.handle_history_with_summary()

    def handle_history_with_summary(self) -> str:
        """Handle the history using the summary approach"""
        # Use the saved trigger reason
        trigger_reason = self._summary_trigger_reason
        # Decide whether it was triggered by the token limit based on the trigger reason
        is_for_token_limit = trigger_reason in [
            "Token limit triggered",
            "Conversation round limit triggered",
            "Other limit triggered",
        ]
        summary = self.generate_summary(for_token_limit=is_for_token_limit)

        # Get the git diff statistics
        git_diff_stat = ""
        git_view_command = ""
        try:
            from haijunbot.haijunbot_agent.run_loop import AgentRunLoop

            if hasattr(self.agent, "_agent_run_loop") and isinstance(
                self.agent._agent_run_loop, AgentRunLoop
            ):
                agent_run_loop = self.agent._agent_run_loop
            else:
                # Create a temporary AgentRunLoop instance to get the git diff
                agent_run_loop = AgentRunLoop(self.agent)

            # Get the diff statistics
            git_diff_stat = agent_run_loop.get_git_diff_stat()

            # Generate the view command
            if hasattr(self.agent, "start_commit") and self.agent.start_commit:
                git_view_command = f"git diff {self.agent.start_commit}..HEAD"
        except Exception as e:
            git_diff_stat = f"Failed to get git diff stats: {str(e)}"

        # First get the formatted summary message
        formatted_summary = ""
        if summary:
            formatted_summary = self.format_summary_message(summary)

        # Add the git diff statistics to the summary - only show valid code change statistics
        is_valid_git_stat = (
            git_diff_stat
            and git_diff_stat.strip()
            and
            # Filter error messages (get failed, etc.)
            not git_diff_stat.startswith("Failed to get git diff stats")
            and
            # Filter no-change hints
            "No code changes detected" not in git_diff_stat
        )

        if is_valid_git_stat:
            diff_section = f"\n\n## Code Change Statistics\n```\n{git_diff_stat}\n```"
            if git_view_command:
                diff_section += f"\n\nView the full diff: ```bash\n{git_view_command}\n```"
            formatted_summary += diff_section

        # Critical flow: call memory_manager directly to ensure the memory prompt
        try:
            self.agent.memory_manager._ensure_memory_prompt(agent=self.agent)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.__init__",
                function="_handle_history_with_summary",
            )
            pass

            # Non-critical flow: broadcast the before-history-clear event (for logging, monitoring, etc.)
            try:
                self.agent.event_bus.emit(BEFORE_HISTORY_CLEAR, agent=self.agent)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.__init__",
                    function="_handle_history_with_summary",
                )
                pass

        # Clear the history (but do not clear the prompt, because the prompt is set in builtin_input_handler)
        if self.agent.model:
            self.agent.model.reset()
            # After reset, re-set the system prompt to ensure system constraints still take effect
            self.agent._setup_system_prompt()
        # Clean up the pre-compression state (the foreground summary already cleared the history, so the pre-compressed summary based on the old snapshot has expired)
        self.agent._pre_compressed_summary = None
        self.agent._pre_compress_snapshot_count = 0
        self.agent._pre_compressing = False
        # Reset the session
        self.agent.session.clear_history()
        # Reset the addon_prompt skip-rounds counter
        self.agent._addon_prompt_skip_rounds = 0
        # Reset the counter for no tool calls
        self.agent._no_tool_call_count = 0
        # Turn on the input handler switch so the next round can process special markers in pin_content
        self.agent.run_input_handlers_next_turn = True

        # Get the task list information (for the history record)
        task_list_info = ""
        try:
            # Get the summary information of all task lists
            task_lists_summary: List[Dict[str, Any]] = []
            for (
                task_list_id,
                task_list,
            ) in self.agent.task_list_manager.task_lists.items():
                summary_dict = self.agent.task_list_manager.get_task_list_summary(
                    task_list_id
                )
                if summary_dict and isinstance(summary_dict, dict):
                    task_lists_summary.append(summary_dict)

            if task_lists_summary:
                task_list_info = "\\n\\n## Task List Status\\n"
                for summary_dict in task_lists_summary:
                    task_list_info += (
                        f"\\n- Goal: {summary_dict.get('main_goal', 'unknown')}"
                    )
                    task_list_info += (
                        f"\\n- Total tasks: {summary_dict.get('total_tasks', 0)}"
                    )
                    task_list_info += f"\\n- Pending: {summary_dict.get('pending', 0)}"
                    task_list_info += f"\\n- Running: {summary_dict.get('running', 0)}"
                    task_list_info += f"\\n- Completed: {summary_dict.get('completed', 0)}"
                    task_list_info += f"\\n- Failed: {summary_dict.get('failed', 0)}"
                    task_list_info += (
                        f"\\n- Abandoned: {summary_dict.get('abandoned', 0)}\\n"
                    )
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        # Non-critical flow: broadcast the after-history-clear event (for logging, monitoring, etc.)
        try:
            self.agent.event_bus.emit(AFTER_HISTORY_CLEAR, agent=self.agent)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.__init__",
                function="_handle_history_with_summary",
            )
            pass

        # Add the task list information to the summary
        if task_list_info:
            formatted_summary += task_list_info

        # Add the important content fixed by the user
        user_fixed_content = []

        # Add other important content fixed by the user via the <Pin> marker
        # pin_content may contain content appended by the user via the <Pin> marker; these serve as supplements
        if self.agent.pin_content.strip():
            pin_content_stripped = self.agent.pin_content.strip()
            user_fixed_content.append(f"**User-fixed content**:\n{pin_content_stripped}")

        # Add the most recent memories
        if hasattr(self.agent, "recent_memories") and self.agent.recent_memories:
            user_fixed_content.append(
                f"**Recent memories**:\n{chr(10).join(self.agent.recent_memories)}"
            )

        # If there is any fixed content, add it to the summary (placed at the very front to ensure priority)
        if user_fixed_content:
            pin_section = f"\n\n## 🎯 The user's original needs and requirements (must always be kept in mind)\n{chr(10).join(user_fixed_content)}"
            # Place the fixed content at the very front to ensure the highest priority
            formatted_summary = pin_section + formatted_summary

        return formatted_summary

    def format_summary_message(self, summary: str) -> str:
        """Format the summary message"""
        # Get the task list information
        task_list_info = self.agent._get_task_list_info()

        # Get the loaded rule information (file path and description)
        rules_section = ""
        loaded_rule_infos = []
        for rule_name in sorted(self.agent.rules_manager.loaded_rules):
            rule_path = self.agent.rules_manager.get_rule_file_path(rule_name)
            description = self.agent.rules_manager._extract_rule_description(rule_path)
            if description:
                loaded_rule_infos.append(
                    f"- {rule_name}: {description} (path: {rule_path})"
                )
            else:
                loaded_rule_infos.append(f"- {rule_name} (path: {rule_path})")

        if loaded_rule_infos:
            rules_info = "\n".join(loaded_rule_infos)
            rules_section = f"\n\n\n**📋 Currently loaded rules:**\n\n{rules_info}\n\nHint: to view the detailed content of a rule, use the `load_rule` tool to load the corresponding rule file.\n\n"

        # Get the session file path information
        session_file_info = ""
        try:
            from haijunbot.haijunbot_utils.dialogue_recorder import get_global_recorder
            from pathlib import Path

            recorder = get_global_recorder()
            session_file_path = recorder.get_session_file_path()
            if Path(session_file_path).exists():
                session_file_info = f"\n\n**📁 Full conversation history file**:\nThe full conversation history has been saved in the file below; when you need to check more detailed context you can read it directly:\n`{session_file_path}`\n\nThis file contains the complete record of all previous conversations (JSONL format), one message per line, including timestamp, role, and content."
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        # Get the initial commit information (only for CodeAgent)
        initial_commit_info = ""
        try:
            if hasattr(self.agent, "start_commit") and self.agent.start_commit:
                initial_commit_info = f"\n\n**🔖 Initial Git Commit (safe rollback point)**:\nThe initial commit at the start of this task is: `{self.agent.start_commit}`\n\n**⚠️ Important note**: If a file is damaged so severely that it cannot be recovered, you can use the following command to reset to this initial commit:\n```bash\ngit reset --hard {self.agent.start_commit}\n```\nThis will discard all uncommitted changes and restore the working tree to the state at the start of the task. Please use this command with caution and make sure this is really what you want."
        except Exception:
            # Non-critical flow; failure does not affect the main functionality
            pass

        formatted_message = f"""
    The following is a summary of key points extracted from the previous conversation:

    <content>
    {summary}
    </content>{rules_section}

    **Important constraints**:
    - All operations are based on the actual results returned by tools; speculation, assumptions, or fabrication are prohibited; every conclusion must have verification evidence.
    - Tool calls: you may call one or more **mutually independent** tools at a time; when dependencies exist, execute the depended-upon tool first, and continue after the result arrives.
    - Code changes that require compile/build/test verification must pass verification before being considered complete; do not declare the task complete just because "the code is written".

    **🎯 Core task goal reminder**:
    Always keep in mind the user's latest task goal (see the "user's original needs and requirements" section above). All operations revolve around that goal; if the current progress deviates from the latest goal, adjust the direction promptly. Note: the user's goal may change during the conversation; take the latest statement as authoritative.

    Please continue advancing the task based on the above information. Note: this is a summary of the previous conversation; the context has been reset due to exceeding the limit. Please continue directly without repeating completed steps; if you need more information, you may ask the user.{session_file_info}{initial_commit_info}
        """

        # If there is task list information, add it after the message
        if task_list_info:
            formatted_message += f"\n\n{task_list_info}"

        return formatted_message
