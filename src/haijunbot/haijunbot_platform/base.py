import json
import os

# -*- coding: utf-8 -*-
import re
import threading
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from types import TracebackType
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union

from typing_extensions import Self

import haijunbot.haijunbot_utils.globals as G
from haijunbot.haijunbot_utils.config import get_cheap_max_input_token_count
from haijunbot.haijunbot_utils.config import get_conversation_turn_threshold
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import is_model_native_supported
from haijunbot.haijunbot_utils.config import mark_model_native_supported
from haijunbot.haijunbot_utils.config import get_max_input_token_count
from haijunbot.haijunbot_utils.config import get_pretty_output
from haijunbot.haijunbot_utils.config import get_smart_max_input_token_count
from haijunbot.haijunbot_utils.config import get_llm_config
from haijunbot.haijunbot_utils.config import get_normal_model_name
from haijunbot.haijunbot_utils.config import get_cheap_model_name
from haijunbot.haijunbot_utils.config import get_eval_max_input_token_count
from haijunbot.haijunbot_utils.config import get_eval_model_name
from haijunbot.haijunbot_utils.config import get_smart_model_name
from haijunbot.haijunbot_utils.config import is_immediate_abort
from haijunbot.haijunbot_utils.config import is_print_prompt
from haijunbot.haijunbot_utils.config import is_save_session_history
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.globals import get_interrupt
from haijunbot.haijunbot_utils.globals import set_interrupt
from haijunbot.haijunbot_utils.globals import set_in_chat
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ct
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.utils import atomic_write_json
from haijunbot.haijunbot_utils.utils import while_success
from haijunbot.haijunbot_utils.utils import while_true
from haijunbot.haijunbot_platform.content_types import ContentBlock


class BasePlatform(ABC):
    """Base class for large language models"""

    # Conversation message history (initialized by subclasses in __init__)
    messages: List[Dict[str, Any]]

    def __init__(
        self,
        platform_type: str = "normal",
        agent: Optional[Any] = None,
    ):
        """Initialize the model

        Args:
            platform_type: The platform type; one of 'normal', 'cheap', 'smart', or 'eval'
            agent: An Agent instance, used for callbacks such as triggering summarization
        """
        self.suppress_output = False  # Add an output control flag
        self._saved = False
        self._panel_lock = threading.RLock()  # Thread lock protecting panel updates

        self._session_history_file: Optional[str] = None
        self.platform_type: str = platform_type  # Platform type: normal/cheap/smart
        self.agent = agent  # Keep an Agent reference for callbacks

        # Get the matching model_name based on platform_type
        if platform_type == "cheap":
            self.model_name = get_cheap_model_name()
        elif platform_type == "smart":
            self.model_name = get_smart_model_name()
        elif platform_type == "eval":
            self.model_name = get_eval_model_name()
        else:
            self.model_name = get_normal_model_name()

        # Native function calling sets this flag once it fails because the endpoint does not support it; this instance then falls back to the plain-text protocol.
        # However, if the model was previously confirmed to support native tool calls (returned a native response), it will not downgrade.
        self._native_disabled = False
        self._native_confirmed = is_model_native_supported(self.model_name)

        # Read llm_config for subclasses to use
        self._llm_config = get_llm_config(platform_type)

        # Check whether multimodal is supported
        self._supports_multimodal = self._llm_config.get("supports_multimodal", False)

    def _get_proxy_extra_headers(self) -> Dict[str, str]:
        """Get the dynamic request headers in proxy mode.

        Reads HAIJUNBOT_AUTH_TOKEN from the environment on every call,
        avoiding 401s after the master gateway restarts when the Token updates but the client still uses the old one.

        Returns:
            A dict containing X-HaijunBot-Token, or an empty dict outside proxy mode or without a Token.
        """
        import haijunbot.haijunbot_utils.globals as jglobals

        if not (jglobals.proxy_node and jglobals.master_url):
            return {}
        haijunbot_token = os.getenv("HAIJUNBOT_AUTH_TOKEN")
        if haijunbot_token:
            return {"X-HaijunBot-Token": haijunbot_token}
        return {}

    def supports_multimodal(self) -> bool:
        """Check whether multimodal input is supported"""
        return self._supports_multimodal

    def supports_native_tool_calls(self) -> bool:
        """Whether the current platform supports native function calling.

        Default False; OpenAI-compatible and Juglow platforms override it to True.
        """
        return False

    def mark_native_supported(self) -> None:
        """Mark the current model as confirmed to support native function calling and persist it.

        Call after a native request returns successfully (whether content or tool_calls):
        the endpoint indeed supports tools, so later temporary errors no longer downgrade to the plain-text protocol.
        """
        self._native_confirmed = True
        mark_model_native_supported(self.model_name)

    def append_native_tool_result(
        self, tool_call_id: str, name: str, content: str
    ) -> None:
        """Append one native tool execution result to the history as a role=tool message."""
        from haijunbot.haijunbot_platform.native_tools import make_tool_result_msg

        self.messages.append(make_tool_result_msg(tool_call_id, name, content))

    def get_conversation_turn(self) -> int:
        """Get the current conversation turn count"""
        return len(self.get_messages()) // 2

    def __enter__(self) -> Self:
        """Enter the context manager"""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager"""
        if not self._saved:
            self.delete_chat()

    @abstractmethod
    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Set the conversation history"""
        raise NotImplementedError("set_messages is not implemented")

    @abstractmethod
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the conversation history"""
        raise NotImplementedError("get_messages is not implemented")

    @abstractmethod
    def set_model_name(self, model_name: str):
        """Set the model name"""
        raise NotImplementedError("set_model_name is not implemented")

    def reset(self) -> None:
        """Reset the model"""
        self.delete_chat()
        self._session_history_file = None

    @abstractmethod
    def chat(
        self, message: Union[str, List[ContentBlock]]
    ) -> Generator[Tuple[str, str], None, None]:
        """Run a conversation

        Args:
            message: The user input content; supports plain text (str) or multimodal content (List[ContentBlock])

        Returns:
            Generator[Tuple[str, str], None, None]: A generator yielding (type, content) tuples chunk by chunk
            type: "reason" means the reasoning process, "content" means the main body content
        """
        raise NotImplementedError("chat is not implemented")

    def complete(self, prompt: Union[str, List[ContentBlock]], **kwargs: Any) -> str:
        """Stateless completion method

        Automatically resets the conversation state before each call, ensuring no context accumulates between calls.
        Suitable for one-shot inference tasks: sentiment analysis, ambiguity detection, code analysis, etc.

        Args:
            prompt: The prompt; supports plain text (str) or multimodal content (List[ContentBlock])
            **kwargs: Extra parameters (reserved)

        Returns:
            str: The full response content

        Note:
            - This method calls delete_chat() to reset the state
            - Does not affect the messages history of the main conversation
            - Each call is independent and stateless
        """
        # Reset the conversation state first to ensure statelessness
        self.delete_chat()

        # Call chat and collect all responses (content type only)
        response = ""
        for chunk_type, chunk_content in self.chat(prompt):
            if chunk_type == "content":
                response += chunk_content

        return response

    def _format_progress_bar(self, percent: float, width: int = 20) -> str:
        """Format a progress bar string

        Args:
            percent: The percentage (0-100)
            width: The progress bar width (in characters)

        Returns:
            str: The formatted progress bar string
        """
        # Clamp the percentage range
        percent = max(0, min(100, percent))

        # Compute the number of filled characters
        filled = int(width * percent / 100)
        empty = width - filled

        # Build the progress bar: █ marks filled, ░ marks unfilled
        bar = "█" * filled + "░" * empty

        return bar

    def _get_token_usage_info(
        self, current_response: str = ""
    ) -> Tuple[float, str, str]:
        """Get the token usage information

        Args:
            current_response: The current response content (used for computing tokens during streaming output)

        Returns:
            Tuple[float, str, str]: (usage_percent, percent_color, progress_bar)
        """
        try:
            history_tokens = self.get_used_token_count()
            current_response_tokens = get_context_token_count(current_response)
            total_tokens = history_tokens + current_response_tokens
            max_tokens = self._get_platform_max_input_token_count()

            if max_tokens > 0:
                usage_percent = (total_tokens / max_tokens) * 100
                if usage_percent >= 90:
                    percent_color = "red"
                elif usage_percent >= 80:
                    percent_color = "yellow"
                else:
                    percent_color = "green"
                progress_bar = self._format_progress_bar(usage_percent, width=15)
                return usage_percent, percent_color, progress_bar
            return 0.0, "green", ""
        except Exception:
            return 0.0, "green", ""

    def _print_response_stats(
        self,
        response: str,
        reasoning_content: str,
        first_token_time: float,
        start_time: float,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Print model response statistics (aligned with _chat, for reuse on the native tool path).

        tool_calls: The native tool-call list; the tokens of its serialized form also count toward the output tokens and speed,
        so stats do not report 0 speed/tokens when the model returns only tool calls (no text content).
        """
        import time

        end_time = time.time()
        duration = end_time - start_time

        # Serialized tool-call text (for token accounting)
        tool_calls_text = ""
        if tool_calls:
            try:
                tool_calls_text = json.dumps(tool_calls, ensure_ascii=False)
            except Exception:
                tool_calls_text = str(tool_calls)

        # Compute performance metrics (tool-call portion included)
        response_tokens = (
            get_context_token_count(response)
            + get_context_token_count(reasoning_content)
            + get_context_token_count(tool_calls_text)
        )
        generation_time = max(
            0.0,
            duration - first_token_time if duration > first_token_time else duration,
        )
        tokens_per_second = (
            response_tokens / generation_time if generation_time > 0 else 0.0
        )

        # Get token usage info
        try:
            usage_percent, percent_color, progress_bar = self._get_token_usage_info(
                response + tool_calls_text
            )
            threshold = get_conversation_turn_threshold()
            # Compute the currently used tokens and total tokens (tool-call portion included)
            used_tokens = (
                self.get_used_token_count()
                + get_context_token_count(response)
                + get_context_token_count(reasoning_content)
                + get_context_token_count(tool_calls_text)
            )
            max_tokens = self._get_platform_max_input_token_count()
            PrettyOutput.auto_print(
                f"✅ {self.name()} model response completed: {duration:.2f}s | turn: {self.get_conversation_turn()}/{threshold} | "
                f"first token: {first_token_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s | "
                f"Token: {used_tokens}/{max_tokens} ({usage_percent:.1f}%)"
            )
        except Exception:
            threshold = get_conversation_turn_threshold()
            PrettyOutput.auto_print(
                f"✅ {self.name()} model response completed: {duration:.2f}s | turn: {self.get_conversation_turn()}/{threshold} | "
                f"first token: {first_token_time:.2f}s | speed: {tokens_per_second:.1f} tokens/s"
            )
            pass

    def _chat_with_pretty_output(
        self,
        message: Union[str, List[ContentBlock]],
        start_time: float,
        max_output: int = 0,
        chat_iterator: Optional[Generator[Tuple[str, str], None, None]] = None,
        raise_on_error: bool = False,
    ) -> Tuple[str, str, float]:
        """Chat in pretty output mode (wrapped in PrettyOutput)

        Args:
            chat_iterator: Optional custom response iterator; when None, uses self.chat(message).
                Lets custom-generator scenarios such as native tool calls reuse the same rendering pipeline.
            raise_on_error: Whether streaming exceptions propagate upward (used by the native tool path when native support is confirmed)
        """
        # For multimodal messages, pass only the prompt string to PrettyOutput
        display_message = message if isinstance(message, str) else "[multimodal message]"
        if chat_iterator is None:
            chat_iterator = self.chat(message)
        return PrettyOutput.stream_chat_with_panel(
            chat_iterator=chat_iterator,
            title=self.name(),
            status_message=f"🤔 {(G.get_current_agent_name() + ' · ') if G.get_current_agent_name() else ''}{self.name()} is thinking...",
            get_used_token_count=self.get_used_token_count,
            get_conversation_turn=self.get_conversation_turn,
            get_platform_max_input_token_count=self._get_platform_max_input_token_count,
            get_context_token_count=get_context_token_count,
            append_session_history=self._append_session_history,
            start_time=start_time,
            message=display_message,
            max_output=max_output,
            check_interrupt=lambda: bool(get_interrupt()),
            panel_lock=self._panel_lock,
            raise_on_error=raise_on_error,
        )

    def _chat_with_simple_output(
        self,
        message: Union[str, List[ContentBlock]],
        start_time: float,
        max_output: int = 0,
        chat_iterator: Optional[Generator[Tuple[str, str], None, None]] = None,
        raise_on_error: bool = False,
    ) -> Tuple[str, str, float]:
        """Chat in simple output mode (wrapped in PrettyOutput)

        Args:
            chat_iterator: Optional custom response iterator; when None, uses self.chat(message).
            raise_on_error: Whether streaming exceptions propagate upward (used by the native tool path when native support is confirmed)
        """
        # For multimodal messages, pass only the prompt string to PrettyOutput
        display_message = message if isinstance(message, str) else "[multimodal message]"
        if chat_iterator is None:
            chat_iterator = self.chat(message)
        response, reasoning_content, first_token_time = PrettyOutput.stream_chat_simple(
            chat_iterator=chat_iterator,
            prefix=f"🤖 Model output - {(G.get_current_agent_name() + ' · ') if G.get_current_agent_name() else ''}{self.name()}  (press Ctrl+C to interrupt)",
            start_time=start_time,
            message=display_message,
            max_output=max_output,
            check_interrupt=lambda: bool(is_immediate_abort() and get_interrupt()),
            append_session_history=self._append_session_history,
            get_context_token_count=get_context_token_count,
            get_used_token_count=self.get_used_token_count,
            get_platform_max_input_token_count=self._get_platform_max_input_token_count,
            raise_on_error=raise_on_error,
        )
        return response, reasoning_content, first_token_time

    def _chat_with_suppressed_output(
        self,
        message: Union[str, List[ContentBlock]],
        max_output: int = 0,
        chat_iterator: Optional[Generator[Tuple[str, str], None, None]] = None,
        raise_on_error: bool = False,
    ) -> Tuple[str, str]:
        """Chat in unattended (suppressed) mode

        Args:
            message: The user message
            max_output: The max output length; 0 means unlimited
            chat_iterator: Optional custom response iterator; when None, uses self.chat(message).
            raise_on_error: Whether streaming exceptions propagate upward (used by the native tool path when native support is confirmed)

        Returns:
            Tuple[str, str]: (model response, reasoning content)
        """
        response = ""
        reasoning_content = ""
        if chat_iterator is None:
            chat_iterator = self.chat(message)
        try:
            for chunk_type, chunk_content in chat_iterator:
                # Concatenate content type
                if chunk_type == "content":
                    response += chunk_content
                # Concatenate reason type
                elif chunk_type == "reason":
                    reasoning_content += chunk_content
                # Check whether the max output length was reached
                if max_output > 0 and len(response) >= max_output:
                    self._append_session_history(message, response)
                    return response, reasoning_content
                if is_immediate_abort() and get_interrupt():
                    self._append_session_history(message, response)
                    return response, reasoning_content
        except Exception as e:
            # On exception, print the error and return the content collected so far
            PrettyOutput.auto_print(f"⚠️ Streaming output exception: {e}")
            if raise_on_error:
                raise
            self._append_session_history(message, response)
            return response, reasoning_content
        return response, reasoning_content

    def _process_response(self, response: str) -> str:
        """Process the response, removing think tags

        Args:
            response: The raw response

        Returns:
            str: The processed response
        """
        response = re.sub(
            ot("think") + r".*?" + ct("think"), "", response, flags=re.DOTALL
        )
        response = re.sub(
            ot("thinking") + r".*?" + ct("thinking"), "", response, flags=re.DOTALL
        )
        return response

    def _chat(self, message: Union[str, List[ContentBlock]], max_output: int = 0):
        import time

        start_time = time.time()

        # When the input is a blank string, print a warning and return an empty string
        if isinstance(message, str) and message.strip() == "":
            PrettyOutput.auto_print("⚠️ Input message is a blank string; ignored")
            return ""

        # Check and truncate the message to avoid exceeding the remaining token limit
        # Note: multimodal messages are not truncated yet; only plain text is handled
        if isinstance(message, str):
            message = self._truncate_message_if_needed(message)

        # Choose different handling based on the output mode
        first_token_time = 0.0
        reasoning_content = ""
        if not self.suppress_output:
            if get_pretty_output():
                response, reasoning_content, first_token_time = (
                    self._chat_with_pretty_output(message, start_time, max_output)
                )
            else:
                response, reasoning_content, first_token_time = (
                    self._chat_with_simple_output(message, start_time, max_output)
                )

            # Compute response time and print a summary (shares _print_response_stats with the native tool path)
            self._print_response_stats(
                response, reasoning_content, first_token_time, start_time
            )
        else:
            response, reasoning_content = self._chat_with_suppressed_output(
                message, max_output
            )

        # Process the response and save the session history
        response = self._process_response(response)

        # If interrupted and the response is empty, set a notice message
        if not response and get_interrupt():
            response = "<output interrupted by user>"
        # If content is empty but reasoning_content is not and the user did not interrupt, return reasoning_content
        elif not response and reasoning_content and not get_interrupt():
            response = reasoning_content

        self._append_session_history(message, response)

        # Ensure the message is correctly added to messages (especially on interrupt)
        # If interrupted, chat() may not complete, so the assistant message may not be added to messages
        if response:  # Only check when there is a response
            try:
                messages = self.get_messages()
                # Check whether the last message is an assistant message
                if messages:
                    last_message = messages[-1]
                    if last_message.get("role") != "assistant":
                        # The last message is not an assistant message; add one manually
                        # Check whether the last message is a user message (with matching content)
                        if (
                            last_message.get("role") == "user"
                            and last_message.get("content") == message
                        ):
                            # The last message is a user message; only add the assistant response
                            messages.append({"role": "assistant", "content": response})
                        else:
                            # The last message is not a user message; add both the user message and the assistant response
                            # Convert the multimodal message to a string representation
                            user_content = (
                                message if isinstance(message, str) else "[multimodal message]"
                            )
                            messages.append({"role": "user", "content": user_content})
                            messages.append({"role": "assistant", "content": response})
                        # Update the message list
                        self.set_messages(messages)
                else:
                    # messages is empty; add the user message and the assistant response directly
                    # Convert the multimodal message to a string representation
                    user_content = (
                        message if isinstance(message, str) else "[multimodal message]"
                    )
                    messages = [
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": response},
                    ]
                    self.set_messages(messages)
            except Exception as e:
                # If updating messages fails, do not affect the chat flow; only print a warning
                PrettyOutput.auto_print(f"⚠️ Warning: failed to update the message list: {e}")

        return response

    def chat_until_success(
        self, message: Union[str, List[ContentBlock]], max_output: int = 0
    ) -> str:
        """Chat with the model until a successful response.

        Args:
            message: The user message; supports plain text (str) or multimodal content (List[ContentBlock])
            max_output: The max output length; 0 means unlimited

        Returns:
            str: The model response
        """
        try:
            # Clear the interrupt flag so every new conversation starts from a clean state
            # This prevents a previous interrupt (e.g. Ctrl+C) from affecting the first call of a new conversation
            # Fixes: rerunning a task after a user interrupt failed to load the methodology (returned empty)
            set_interrupt(False)
            set_in_chat(True)
            if not self.suppress_output and is_print_prompt():
                # Only print plain-text messages; print a notice for multimodal messages
                if isinstance(message, str):
                    PrettyOutput.auto_print(f"👤 {message}")  # Kept for syntax highlighting
                else:
                    PrettyOutput.auto_print("👤 [multimodal message]")

            # Record the user input (model input)
            from haijunbot.haijunbot_utils.dialogue_recorder import record_user_message

            # Only record plain-text messages; record a notice for multimodal ones
            if isinstance(message, str):
                record_user_message(message)
            else:
                record_user_message("[multimodal message]")

            result: str = ""
            result = while_true(
                lambda: while_success(lambda: self._chat(message, max_output))
            )

            # When the model fails repeatedly, try switching to the fallback model group once in non-interactive mode
            if result is False or result == "":
                if self._try_switch_to_fallback_group():
                    result = while_true(
                        lambda: while_success(lambda: self._chat(message, max_output))
                    )

            # Check if result is empty or False (retry exhausted)
            # Convert False to empty string for type safety
            if result is False or result == "":
                raise ValueError("Returned result is empty")

            # Record the model output
            from haijunbot.haijunbot_utils.dialogue_recorder import record_assistant_message

            record_assistant_message(result)

            from haijunbot.haijunbot_utils.globals import set_last_message

            set_last_message(result)
            return result
        finally:
            set_in_chat(False)

    def _try_switch_to_fallback_group(self) -> bool:
        """Try switching to the fallback model group when the model fails repeatedly

        Only takes effect in non-interactive mode; returns False when no fallback group is configured, the fallback group is invalid, or switching fails.

        Returns:
            bool: Whether the switch to the fallback model group succeeded
        """
        from haijunbot.haijunbot_utils.config import is_non_interactive
        from haijunbot.haijunbot_utils.config import switch_to_fallback_group

        try:
            if not is_non_interactive():
                return False
            if not switch_to_fallback_group():
                return False

            if self.agent is None:
                # With no Agent instance, only switch the global config; the caller rebuilds the model
                PrettyOutput.auto_print("🔄 Switched to the fallback model group")
                return True

            # Rebuild the model instance so the new model group config takes effect
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            old_messages = self.get_messages()
            platform_registry = PlatformRegistry()
            if self.platform_type == "smart":
                new_model = platform_registry.get_smart_platform()
            elif self.platform_type == "cheap":
                new_model = platform_registry.get_cheap_platform()
            elif self.platform_type == "eval":
                new_model = platform_registry.get_eval_platform()
            else:
                new_model = platform_registry.get_normal_platform()
            if new_model is None:
                return False
            new_model.set_suppress_output(self.suppress_output)
            new_model.agent = self.agent
            if old_messages:
                new_model.set_messages(old_messages)
            self.agent.model = new_model
            if getattr(self.agent, "session", None) is not None:
                self.agent.session.model = new_model
            PrettyOutput.auto_print("🔄 Switched to the fallback model group; retrying")
            return True
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to switch to the fallback model group: {e}")
            return False

    @abstractmethod
    def name(self) -> str:
        """The model name"""
        raise NotImplementedError("name is not implemented")

    @classmethod
    @abstractmethod
    def platform_name(cls) -> str:
        """The platform name"""
        raise NotImplementedError("platform_name is not implemented")

    @abstractmethod
    def delete_chat(self) -> bool:
        """Delete the conversation"""
        raise NotImplementedError("delete_chat is not implemented")

    def save(self, file_path: str) -> bool:
        """Save the conversation session to a file.

        Note:
            The implementation should set `self._saved` to True after a successful save,
            to prevent the session from being deleted when the object is destroyed.

        Args:
            file_path: The path of the file to save the session to.

        Returns:
            True if the save succeeded, otherwise False.
        """
        state = {
            "messages": self.get_messages(),
        }
        try:
            atomic_write_json(file_path, state, indent=4, ensure_ascii=False)
            self._saved = True
            from haijunbot.haijunbot_utils.output import PrettyOutput

            PrettyOutput.auto_print(f"✅ Session saved successfully to {file_path}")
            return True
        except Exception as e:
            from haijunbot.haijunbot_utils.output import PrettyOutput

            PrettyOutput.auto_print(f"❌ Failed to save the session: {str(e)}")
            return False

    def restore(self, file_path: str) -> bool:
        """Restore the conversation session from a file.

        Args:
            file_path: The path of the session file to restore.

        Returns:
            True if the restore succeeded, otherwise False.
        """
        import json
        from haijunbot.haijunbot_utils.output import PrettyOutput

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            messages = state.get("messages", [])
            self.set_messages(messages)
            self._saved = True
            return True
        except FileNotFoundError:
            PrettyOutput.auto_print(f"❌ Session file not found: {file_path}")
            return False
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to restore the session: {str(e)}")
            return False

    @abstractmethod
    def set_system_prompt(self, message: str):
        """Set the system message"""
        raise NotImplementedError("set_system_prompt is not implemented")

    @abstractmethod
    def get_model_list(self) -> List[Tuple[str, str]]:
        """Get the list of models"""
        raise NotImplementedError("get_model_list is not implemented")

    @classmethod
    @abstractmethod
    def get_required_env_keys(cls) -> List[str]:
        """Get the required environment variable keys"""
        raise NotImplementedError("get_required_env_keys is not implemented")

    @classmethod
    def get_env_defaults(cls) -> Dict[str, str]:
        """Get the environment variable defaults"""
        return {}

    @classmethod
    def get_env_config_guide(cls) -> Dict[str, str]:
        """Get the environment variable configuration guide

        Returns:
            Dict[str, str]: A dict mapping environment variable key names to their configuration descriptions
        """
        return {}

    def set_suppress_output(self, suppress: bool):
        """Set whether to suppress output"""
        self.suppress_output = suppress

    def set_platform_type(self, platform_type: str):
        """Set the platform type

        Args:
            platform_type: The platform type; one of 'normal', 'cheap', or 'smart'
        """
        self.platform_type = platform_type

    def _get_platform_max_input_token_count(self) -> int:
        """Get the matching max input token count based on the platform type

        Returns:
            int: The maximum input token count the model can handle
        """
        if self.platform_type == "cheap":
            return get_cheap_max_input_token_count()
        elif self.platform_type == "smart":
            return get_smart_max_input_token_count()
        elif self.platform_type == "eval":
            return get_eval_max_input_token_count()
        else:
            return get_max_input_token_count()

    def _append_session_history(
        self, user_input: Union[str, List[ContentBlock]], model_output: str
    ) -> None:
        """
        Append the user input and model output to a session history file if enabled.
        The file name is generated on first save and reused until reset.
        """
        try:
            if not is_save_session_history():
                return

            if self._session_history_file is None:
                # Ensure session history directory exists under data directory
                data_dir = get_data_dir()
                session_dir = os.path.join(data_dir, "session_history")
                os.makedirs(session_dir, exist_ok=True)

                # Build a safe filename including platform, model and timestamp
                try:
                    platform_name = type(self).platform_name()
                except Exception:
                    platform_name = "unknown_platform"

                try:
                    model_name = self.name()
                except Exception:
                    model_name = "unknown_model"

                safe_platform = re.sub(r"[^\w\-\.]+", "_", str(platform_name))
                safe_model = re.sub(r"[^\w\-\.]+", "_", str(model_name))
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")

                self._session_history_file = os.path.join(
                    session_dir,
                    f"session_history_{safe_platform}_{safe_model}_{ts}.log",
                )

            # Append record
            with open(
                self._session_history_file, "a", encoding="utf-8", errors="ignore"
            ) as f:
                ts_line = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"===== {ts_line} =====\n")
                f.write("USER:\n")
                # Convert the multimodal message to a string representation
                user_content = (
                    user_input if isinstance(user_input, str) else "[multimodal message]"
                )
                f.write(f"{user_content}\n")
                f.write("\nASSISTANT:\n")
                f.write(f"{model_output}\n\n")
        except Exception:
            # Do not break chat flow if writing history fails
            pass

    def get_used_token_count(self) -> int:
        """Compute the token count used by the current conversation history

        Returns:
            int: The token count used by the current conversation history
        """
        from haijunbot.haijunbot_utils.embedding import get_multimodal_token_count

        history = self.get_messages()
        if not history:
            return 0

        total_tokens = 0
        for message in history:
            content = message.get("content", "")
            if content:
                total_tokens += get_multimodal_token_count(content)
            # Native tool calls: the assistant message's tool-call arguments live in the tool_calls field
            # (not in content), so they must be counted into the context length to avoid underestimating used tokens.
            tool_calls = message.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    args = tc.get("arguments")
                    if isinstance(args, dict):
                        total_tokens += get_multimodal_token_count(
                            json.dumps(args, ensure_ascii=False)
                        )
                    elif args:
                        total_tokens += get_multimodal_token_count(str(args))

        return total_tokens

    def get_remaining_token_count(self) -> int:
        """Get the remaining available token count

        Returns:
            int: The remaining available token count (input window limit - currently used token count)
        """
        max_tokens = self._get_platform_max_input_token_count()
        used_tokens = self.get_used_token_count()
        remaining = max_tokens - used_tokens
        return max(0, remaining)  # Ensure the return value is not negative

    def _truncate_message_if_needed(self, message: str) -> str:
        """Truncate the message if it exceeds the remaining token limit

        Args:
            message: The original message

        Returns:
            str: The truncated message (or the original if no truncation is needed)
        """
        try:
            # Get the remaining token count
            remaining_tokens = self.get_remaining_token_count()

            # If the remaining tokens are 0 or negative, try trimming the history to free space
            if remaining_tokens <= 0:
                PrettyOutput.auto_print("⚠️ Warning: remaining tokens are 0; trying to trim the history...")
                if self.trim_messages():
                    # Trim succeeded; recompute the remaining tokens
                    remaining_tokens = self.get_remaining_token_count()
                    PrettyOutput.auto_print(
                        f"✅ Trim succeeded; remaining tokens: {remaining_tokens}"
                    )
                    if remaining_tokens > 0:
                        # Still has space after trimming; continue processing the message
                        pass
                    else:
                        PrettyOutput.auto_print(
                            "⚠️ Warning: still no remaining tokens after trimming; cannot send the message"
                        )
                        return ""
                else:
                    # trim_messages failed (fewer than 10 messages); try truncating the current message directly
                    PrettyOutput.auto_print(
                        "⚠️ Warning: trim failed (fewer than 10 messages); trying to truncate the current message..."
                    )
                    # Compute the message's token count
                    message_tokens = get_context_token_count(message)
                    # Even when remaining_tokens is 0, try to keep part of the message (using a fixed ratio)
                    # Use 5% of the model's max input tokens as the target
                    max_tokens = self._get_platform_max_input_token_count()
                    target_tokens = int(max_tokens * 0.05)  # 5% of max tokens
                    if target_tokens <= 100:
                        target_tokens = 100  # Keep at least 100 tokens

                    # Estimate the character count (1 token ≈ 4 chars)
                    target_chars = target_tokens * 4

                    # If the message is shorter than the target chars, return it as is (token estimation may be inaccurate)
                    if len(message) <= target_chars:
                        PrettyOutput.auto_print(
                            f"✅ Message length is acceptable; sending directly (about {message_tokens} tokens)"
                        )
                        return message

                    # Truncate the message: keep the leading content and append a truncation notice
                    truncated_message = message[:target_chars]
                    # Try to break at the last complete sentence
                    last_period = truncated_message.rfind(".")
                    last_newline = truncated_message.rfind("\n")
                    last_break = max(last_period, last_newline)

                    if last_break > target_chars * 0.5:  # If the break point found is not too far back
                        truncated_message = truncated_message[: last_break + 1]

                    truncated_message += (
                        "\n\n... (message too long; truncated to avoid exceeding the context limit)"
                    )
                    PrettyOutput.auto_print(
                        f"✅ Message truncated to about {target_tokens} tokens (originally about {message_tokens} tokens)"
                    )

                    return truncated_message

            # Compute the message's token count
            message_tokens = get_context_token_count(message)

            # If the message tokens do not exceed the remaining tokens, no truncation is needed
            if message_tokens <= remaining_tokens:
                return message

            # Truncation needed: keep 80% of the remaining tokens for the message, 20% as a safety margin
            target_tokens = int(remaining_tokens * 0.8)
            if target_tokens <= 0:
                PrettyOutput.auto_print("⚠️ Warning: not enough remaining tokens; cannot send the message")
                return ""

            # Estimate the character count (1 token ≈ 4 chars)
            target_chars = target_tokens * 4

            # If the message is shorter than the target chars, no truncation is needed (token estimation may be inaccurate)
            if len(message) <= target_chars:
                return message

            # Truncate the message: keep the leading content and append a truncation notice
            truncated_message = message[:target_chars]
            # Try to break at the last complete sentence
            last_period = truncated_message.rfind(".")
            last_newline = truncated_message.rfind("\n")
            last_break = max(last_period, last_newline)

            if last_break > target_chars * 0.5:  # If the break point found is not too far back
                truncated_message = truncated_message[: last_break + 1]

            truncated_message += "\n\n... (message too long; truncated to avoid exceeding the context limit)"
            PrettyOutput.auto_print(
                f"⚠️ Warning: message too long ({message_tokens} tokens); truncated to about {target_tokens} tokens"
            )

            return truncated_message
        except Exception as e:
            # If an error occurs during truncation, return the original message (avoid blocking the conversation)
            PrettyOutput.auto_print(f"⚠️ Warning: error while checking the message length: {e}; using the original message")
            return message

    @abstractmethod
    def trim_messages(self) -> bool:
        """Trim the message history to free up token space

        When the remaining tokens are insufficient, free up space by trimming the history.
        The default implementation should keep system messages and drop the first 10 non-system messages.

        Returns:
            bool: True if space was successfully freed, otherwise False
        """
        raise NotImplementedError("trim_messages is not implemented")
