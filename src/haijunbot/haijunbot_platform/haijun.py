# -*- coding: utf-8 -*-
import os
from typing import Any
from typing import Dict
from typing import Optional
from typing import Generator
from typing import List
from typing import Tuple
from typing import Union

from juglow import Juglow
from juglow import APIConnectionError
from juglow import APITimeoutError
from juglow import InternalServerError
from juglow.types import MessageParam

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_platform.native_tools import sanitize_message, to_juglow_messages
from haijunbot.haijunbot_utils.output import PrettyOutput
import haijunbot.haijunbot_utils.globals as jglobals


def _is_rate_limit_error(e: Exception) -> bool:
    """Check whether the exception is a rate-limit/overload error (HTTP 429 or 529).

    Compatible with the juglow SDK's RateLimitError and any exception carrying a status_code.
    """
    try:
        from juglow import RateLimitError as _JuglowRateLimitError

        _rate_limit_cls: Any = _JuglowRateLimitError
    except Exception:
        _rate_limit_cls = None
    if _rate_limit_cls is not None and isinstance(e, _rate_limit_cls):
        return True
    status = getattr(e, "status_code", None)
    if status in (429, 529):
        return True
    body = getattr(e, "response", None)
    if body is not None and hasattr(body, "status_code"):
        return getattr(body, "status_code", None) in (429, 529)
    return False


def _is_retryable_error(e: Exception) -> bool:
    """Check whether the exception is a retryable, temporary error.

    Retryable: rate-limit/overload (429/529), server errors (5xx), network connection/timeout.
    Not retryable: deterministic errors such as auth/permission/parameter (4xx), and ordinary business exceptions (e.g. tools unsupported).
    """
    # Network-layer/timeout errors: retryable
    if isinstance(e, (APIConnectionError, APITimeoutError)):
        return True
    # Rate-limit/overload: retryable
    if _is_rate_limit_error(e):
        return True
    # Server errors (5xx): retryable
    if isinstance(e, InternalServerError):
        return True
    # Other exceptions with status_code: 5xx retryable, 4xx not
    status = getattr(e, "status_code", None)
    if isinstance(status, int):
        return status >= 500
    body = getattr(e, "response", None)
    if body is not None and hasattr(body, "status_code"):
        body_status = getattr(body, "status_code", None)
        return isinstance(body_status, int) and body_status >= 500
    # Ordinary exceptions without a status code (e.g. RuntimeError "tools unsupported"): not retryable by default
    return False


class HaijunModel(BasePlatform):
    def __init__(
        self,
        platform_type: str = "normal",
        agent: Optional[Any] = None,
    ):
        """
        Initialize Haijun model

        Args:
            platform_type: The platform type; one of 'normal', 'cheap', or 'smart'
        """
        super().__init__(platform_type=platform_type, agent=agent)
        self.system_message = ""
        llm_config = self._llm_config or {}

        # If llm_config was passed in (non-empty dict), read from it first to avoid environment variable pollution
        # Only read from environment variables when the corresponding key is missing from llm_config (backward compatible)
        # Note: if a key exists in llm_config but its value is None or an empty string, that value is used; never falls to env vars
        if llm_config:
            # llm_config was passed in; prefer its values
            # Use get(); if the key is absent, returns None, then fall back to environment variables
            # However, if llm_config is an empty dict {}, it's an explicitly passed empty config; read from env vars
            # If a key exists in llm_config but its value is None, that None is used; reading from env vars is skipped
            if "juglow_api_key" in llm_config:
                # The key exists; use the value from llm_config (even if None or an empty string)
                self.api_key = llm_config.get("juglow_api_key")
            else:
                # The key is absent; read from environment variables (backward compatible)
                self.api_key = os.getenv("JUGLOW_API_KEY")

            if "juglow_base_url" in llm_config:
                # The key exists; use the value from llm_config (even if None or an empty string)
                self.base_url = llm_config.get("juglow_base_url")
            else:
                # The key is absent; read from environment variables (backward compatible)
                self.base_url = os.getenv("JUGLOW_BASE_URL")
        else:
            # No llm_config passed; read from environment variables (backward compatible)
            self.api_key = os.getenv("JUGLOW_API_KEY")
            self.base_url = os.getenv("JUGLOW_BASE_URL")

        # Normalize api_key to api_keys list for round-robin support
        # Support: single string, comma-separated string, or list
        if isinstance(self.api_key, list):
            self.api_keys = self.api_key
        elif isinstance(self.api_key, str) and self.api_key:
            # Support comma-separated keys in string format
            self.api_keys = [k.strip() for k in self.api_key.split(",") if k.strip()]
        else:
            self.api_keys = [self.api_key] if self.api_key else []
        # Set current api_key to the first one for backward compatibility
        if self.api_keys:
            self.api_key = self.api_keys[0]
        self._api_key_index = 0

        # If a proxy node is set, convert base_url into a Gateway proxy URL
        if jglobals.proxy_node and jglobals.master_url and self.base_url:
            # Use the original base_url as the target URL and concatenate it into the proxy format
            # Note: the /api/node/{node_id}/ prefix is required to match the FastAPI route
            self.base_url = f"{jglobals.master_url}/api/node/{jglobals.proxy_node}/http_proxy/{self.base_url}"

            # Note: X-HaijunBot-Token is not statically cached here; it is injected dynamically
            # via _get_proxy_extra_headers() on each API call so the Token does not expire after a master gateway restart

        # Only warn when llm_config is non-empty but lacks juglow_api_key and no environment variable is set either
        # An empty dict llm_config may mean config is not yet loaded; do not warn in that case (avoid a first-round false alarm)
        if not self.api_key and llm_config:
            PrettyOutput.auto_print(
                "⚠️ Juglow API Key not found; set juglow_api_key in llm_config or set the JUGLOW_API_KEY environment variable"
            )
        # model_name is already set in BasePlatform.__init__ according to platform_type

        # Initialize the Juglow client
        self.client = None
        try:
            # Note: X-HaijunBot-Token is no longer injected statically via default_headers;
            # it is injected dynamically via extra_headers on each API call
            from haijunbot.haijunbot_utils.config import get_request_timeout

            _req_timeout = get_request_timeout()

            def _build_client(**overrides: Any) -> Juglow:
                # Use Dict[str, Any] to hold the optional params, avoiding type-checker false positives on **kwargs expansion
                params: Dict[str, Any] = {
                    "api_key": self.api_key,
                }
                if self.base_url:
                    params["base_url"] = self.base_url
                if _req_timeout is not None:
                    params["timeout"] = _req_timeout
                params.update(overrides)
                return Juglow(**params)

            self.client = _build_client()
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Juglow client initialization failed: {e}")
        # Sampling params: llm_config can override max_tokens / temperature.
        # Default temperature=0.7: does not rely on the server's 1.0, using a moderate, convergence-friendly explicit value,
        # and not so low (0.x) that long duplicate loops quickly get stuck. Set to None to omit from requests.
        self.max_tokens: int = llm_config.get("max_tokens", 16000)
        self.temperature: Optional[float] = llm_config.get("temperature", 0.7)
        # Message history
        self.messages: List[Dict[str, Any]] = []
        self.system_message = ""

    def _get_next_api_key(self) -> Optional[str]:
        """Get next API key using round-robin rotation.

        Returns the next key in the api_keys list, advancing the index.
        If only one key is available, returns that key without rotation.
        If no keys are available, returns None.
        """
        if not self.api_keys:
            return None
        if len(self.api_keys) == 1:
            return self.api_keys[0]
        # Round-robin: get next key and advance index
        key = self.api_keys[self._api_key_index]
        self._api_key_index = (self._api_key_index + 1) % len(self.api_keys)
        return key

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Replace the conversation history

        Args:
            messages: The new conversation history list; each element contains role and content

        Note:
            - Recomputes conversation_turn from messages (counting user messages among non-system messages)
            - If the message list contains a system message, also updates the system_message attribute
        """
        self.messages = messages

        # If the message list contains a system message, update the system_message attribute
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                # For multimodal messages, content may be a list; extract the text parts
                if isinstance(content, list):
                    text_parts = [
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ]
                    self.system_message = " ".join(text_parts)
                else:
                    self.system_message = content
                break

        # Compute conversation_turn: count user messages among non-system messages
        non_system_messages = [msg for msg in messages if msg.get("role") != "system"]
        self._conversation_turn = sum(
            1 for msg in non_system_messages if msg.get("role") == "user"
        )

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the conversation history

        Returns:
            List[Dict[str, Any]]: The conversation history list; each element contains role and content
        """
        return self.messages

    def get_model_list(self) -> List[Tuple[str, str]]:
        """
        Get the list of available Haijun models

        Returns:
            List[Tuple[str, str]]: A list of (model ID, model name) tuples

        Raises:
            On API call failure, prints the error message and returns an empty list
        """
        if not self.client:
            PrettyOutput.auto_print("❌ Juglow client is not initialized")
            return []

        try:
            # Try the models API to fetch the real model list
            proxy_headers = self._get_proxy_extra_headers()
            model_response = (
                self.client.models.list(extra_headers=proxy_headers)
                if proxy_headers
                else self.client.models.list()
            )
            models = []
            for model in model_response.data:
                model_id = model.id if hasattr(model, "id") else str(model)
                model_name = model.id if hasattr(model, "id") else str(model)
                models.append((model_id, model_name))

            if models:
                PrettyOutput.auto_print("✅ Successfully fetched the model list from the API")
                return models
            else:
                PrettyOutput.auto_print("⚠️ No model list obtained from the API")
                return []
        except AttributeError:
            # The models API does not exist or is not supported
            PrettyOutput.auto_print("❌ The model list API is unavailable")
            return []
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to fetch the model list: {e}")
            return []

    def set_model_name(self, model_name: str):
        """
        Set the currently used model name

        Args:
            model_name: The model name to set
        """
        self.model_name = model_name

    def set_system_prompt(self, message: str):
        """
        Set the system message (role setting)

        Args:
            message: The system message content

        Note:
            After setting, it is immediately appended to the message history
        """
        self.messages = []
        self.system_message = message
        self.messages.append({"role": "system", "content": self.system_message})

    def chat(
        self, message: Union[str, List[ContentBlock]]
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Run a conversation and return a generator

        Args:
            message: The user input content; supports plain text (str) or multimodal content (List[ContentBlock])

        Returns:
            Generator[Tuple[str, str], None, None]: A generator yielding (type, content) tuples chunk by chunk
            type: "reason" means the reasoning process, "content" means the main body content
            Note: Haijun models have no reasoning_content; all content is of the content type

        Raises:
            On API call failure, raises an exception and prints the error message
        """
        if not self.client:
            PrettyOutput.auto_print("❌ Juglow client is not initialized")
            raise Exception("Juglow client not initialized")

        # Record the message list length before adding the user message, for rollback on failure
        messages_before_user = len(self.messages)

        # Rotate API key for round-robin support
        next_key = self._get_next_api_key()
        if next_key:
            self.api_key = next_key
            self.client.api_key = next_key

        try:
            # Convert the message format to Juglow format (handles role=tool / assistant tool_calls canonical messages) and extract the system message
            system_content, juglow_messages = to_juglow_messages(self.messages)
            if system_content:
                self.system_message = system_content

            # Add the current user message
            # Handle multimodal messages
            if isinstance(message, str):
                user_message_content = message
            else:
                # Check multimodal support; if unsupported, fall back to plain text
                if not self.supports_multimodal():
                    PrettyOutput.auto_print(
                        "⚠️ The current model does not support multimodal input; automatically fell back to plain text mode"
                    )
                    # Keep only the text content
                    text_parts = [
                        block["text"] for block in message if block["type"] == "text"
                    ]
                    user_message_content = (
                        "\n".join(text_parts) if text_parts else "[multimodal content skipped]"
                    )
                else:
                    # Convert List[ContentBlock] into the format expected by the Haijun API
                    user_message_content = []
                    for block in message:
                        if block["type"] == "text":
                            user_message_content.append(
                                {"type": "text", "text": block["text"]}
                            )
                        elif block["type"] == "image_url":
                            # The Haijun API expects the image type and requires a source field
                            # Here we assume image_url is a base64-encoded data URL or a plain URL
                            # A plain URL may need downloading and conversion to base64
                            # Simplified here: assume it is a base64 data URL
                            image_url_data = block["image_url"]
                            if isinstance(image_url_data, str):
                                # If it is a data URL (data:image/jpeg;base64,...)
                                if image_url_data.startswith("data:image"):
                                    # Parse the data URL
                                    header, data = image_url_data.split(",", 1)
                                    media_type = header.split(":")[1].split(";")[0]
                                    user_message_content.append(
                                        {
                                            "type": "image",
                                            "source": {
                                                "type": "base64",
                                                "media_type": media_type,
                                                "data": data,
                                            },
                                        }
                                    )
                                else:
                                    # If it is a plain URL, temporarily convert it to a text description
                                    # A real implementation may need to download the image and convert it to base64
                                    user_message_content.append(
                                        {
                                            "type": "text",
                                            "text": f"[Image URL: {image_url_data}]",
                                        }
                                    )
                            elif isinstance(image_url_data, dict):
                                # If it is already a dict, assume it matches the Haijun API format
                                user_message_content.append(image_url_data)
                    else:
                        # Unknown type; ignore or raise
                        pass

            juglow_messages.append(
                sanitize_message({"role": "user", "content": user_message_content})
            )

            # Accumulate the full response
            accumulated_response = ""

            # Prepare the system param: the backend expects an array format, not a string
            system_param = None
            if system_content:
                # Convert the string to an array format: [{"type": "text", "text": "system message content"}]
                system_param = [{"type": "text", "text": system_content}]

            # Call the Juglow API
            from typing import Union

            stream_kwargs: Dict[
                str,
                Union[
                    str,
                    List[MessageParam],
                    int,
                    float,
                    List[List[Dict[str, str]]],
                    List[Dict[str, str]],
                    Dict[str, str],
                ],
            ] = {
                "model": self.model_name,
                "messages": juglow_messages,
                "max_tokens": getattr(self, "max_tokens", None) or 16000,
            }
            _temperature = getattr(self, "temperature", 0.7)
            if _temperature is not None:
                stream_kwargs["temperature"] = _temperature
            if system_param:
                stream_kwargs["system"] = system_param

            # Inject the proxy auth header dynamically so Token updates take effect after a master gateway restart
            proxy_headers = self._get_proxy_extra_headers()
            if proxy_headers:
                stream_kwargs["extra_headers"] = proxy_headers
            with self.client.messages.stream(**stream_kwargs) as stream:  # type: ignore
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
                    accumulated_response += text
                    yield ("content", text)

            # Add the response to the message history
            if accumulated_response:
                # Store a string representation of the multimodal message in the history
                user_content = message if isinstance(message, str) else "[multimodal message]"
                self.messages.append(
                    sanitize_message({"role": "user", "content": user_content})
                )
                self.messages.append(
                    {"role": "assistant", "content": accumulated_response}
                )
            else:
                raise Exception("No response from model")

        except Exception as e:
            # On failure, roll back: remove the appended user message (if any)
            if len(self.messages) > messages_before_user:
                self.messages = self.messages[:messages_before_user]
            raise Exception(f"Chat failed: {str(e)}")

    def supports_native_tool_calls(self) -> bool:
        return True

    def chat_native_once(
        self,
        message: Optional[Union[str, List[ContentBlock]]],
        tools: List[Dict[str, Any]],
        append_user: bool = True,
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Streaming chat with native tools, returning (content, tool_calls).

        - tool_calls use the canonical format [{"id","name","arguments": <dict>}]; None when there are no tool calls
        - On success, the assistant (with tool_calls) is appended to the history as a canonical message
        - When the endpoint does not support tools, falls back to plain text and sets _native_disabled
        """
        if self._native_disabled or not tools:
            content, _ = self._haijun_fallback_text(message, append_user)
            return content, None
        if not self.client:
            raise Exception("Juglow client not initialized")

        # Multimodal list messages do not use native for now (main path is plain text); None means a tool continuation round, which still needs native
        if message is not None and not isinstance(message, str):
            content, _ = self._haijun_fallback_text(message, append_user)
            return content, None

        next_key = self._get_next_api_key()
        if next_key:
            self.api_key = next_key
            self.client.api_key = next_key

        # Append the user message (tool continuation rounds use append_user=False to avoid re-adding empty messages)
        # Also clean lone surrogate characters so the SDK does not throw UnicodeEncodeError when encoding the request body
        if append_user and message:
            self.messages.append(sanitize_message({"role": "user", "content": message}))

        system_text, juglow_messages = to_juglow_messages(self.messages)
        if append_user and message:
            juglow_messages.append(
                sanitize_message({"role": "user", "content": message})
            )

        stream_kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": juglow_messages,
            "max_tokens": getattr(self, "max_tokens", None) or 16000,
            "tools": tools,
        }
        _temperature = getattr(self, "temperature", 0.7)
        if _temperature is not None:
            stream_kwargs["temperature"] = _temperature
        if system_text:
            stream_kwargs["system"] = [{"type": "text", "text": system_text}]
        proxy_headers = self._get_proxy_extra_headers()
        if proxy_headers:
            stream_kwargs["extra_headers"] = proxy_headers

        # Reuse the streaming rendering pipeline from the text protocol path (pretty/simple/suppressed modes)
        import time
        from haijunbot.haijunbot_utils.config import get_pretty_output
        from haijunbot.haijunbot_utils.globals import get_interrupt

        # Tool continuation rounds may have message=None; the rendering layer needs a non-None display message (used to save history on interrupt)
        render_message: Union[str, List[ContentBlock]] = (
            message if message is not None else ""
        )

        # Retry loop: retry when the rendering pipeline detects the output is stuck in repetition (empty content and no tool_calls),
        # aligned with the while_true retry mechanism of chat_until_success on the text protocol path.
        max_retries = 7
        for attempt in range(max_retries):
            # Aligned with while_true/while_success on the text protocol path: check the interrupt signal before each round,
            # and stop retrying immediately after the user clicks "human intervention", avoiding futile retry loops.
            if get_interrupt() > 0:
                break
            try:
                # Accumulator: content is yielded chunk by chunk for streaming rendering; final_message is stored in the closure after the stream ends for external tool_calls parsing
                content_parts: List[str] = []
                final_message = None
                # Streaming exceptions (e.g. tools unsupported) swallowed by the rendering layer return empty content;
                # without recording it, the outer layer would misjudge this as "empty/repeated output" and retry needlessly with exponential backoff.
                gen_error: Optional[Exception] = None

                def _gen() -> Generator[Tuple[str, str], None, None]:
                    nonlocal final_message, gen_error
                    try:
                        with self.client.messages.stream(**stream_kwargs) as stream:  # type: ignore
                            for text in stream.text_stream:
                                content_parts.append(text)
                                yield ("content", text)
                            final_message = stream.get_final_message()
                    except Exception as _e:
                        gen_error = _e

                start_time = time.time()
                gen = _gen()
                # For models already confirmed to support native tools: streaming exceptions must propagate upward for the outer layer to decide,
                # avoiding silent downgrades when the rendering pipeline swallows the exception and misjudges it as "success but empty output".
                _raise_on_error = getattr(self, "_native_confirmed", False)
                # First-token time: the suppressed rendering path does not return this value; default it to 0.0
                # so both the type system and the later _print_response_stats stay well-defined.
                _ft = 0.0
                if not self.suppress_output:
                    if get_pretty_output():
                        content, _reasoning, _ft = self._chat_with_pretty_output(
                            render_message,
                            start_time,
                            chat_iterator=gen,
                            raise_on_error=_raise_on_error,
                        )
                    else:
                        content, _reasoning, _ft = self._chat_with_simple_output(
                            render_message,
                            start_time,
                            chat_iterator=gen,
                            raise_on_error=_raise_on_error,
                        )
                else:
                    content, _reasoning = self._chat_with_suppressed_output(
                        render_message,
                        chat_iterator=gen,
                        raise_on_error=_raise_on_error,
                    )
                # The rendering layer may break early without exhausting the generator; explicitly drain it here to trigger get_final_message and tool_calls parsing
                for _ in gen:
                    pass

                # Parse the canonical tool_calls from final_message
                tool_calls: List[Dict[str, Any]] = []
                for block in getattr(final_message, "content", None) or []:
                    if getattr(block, "type", None) == "tool_use":
                        tool_calls.append(
                            {
                                "id": getattr(block, "id", ""),
                                "name": getattr(block, "name", ""),
                                "arguments": getattr(block, "input", None) or {},
                            }
                        )

                # Streaming exceptions (e.g. tools unsupported) swallowed by the rendering layer return empty content;
                # without re-raising here, the outer layer would misjudge this as "empty/repeated output" and retry needlessly.
                # Let the outer except decide to retry or downgrade based on retryability.
                if gen_error is not None:
                    raise gen_error

                # The rendering pipeline returns empty content when it detects the output is stuck in repetition;
                # if there are also no tool_calls, treat it as repetition causing empty output, roll back this round and retry (consistent with the text protocol path).
                if not content and not tool_calls:
                    if attempt < max_retries - 1:
                        sleep_time = 2**attempt
                        PrettyOutput.auto_print(
                            f"⚠️ Model output is empty or stuck in repetition; retrying ({attempt + 1}/{max_retries}) in {sleep_time}s..."
                        )
                        # Sleep in segments so interrupt signals are handled promptly
                        for _ in range(sleep_time):
                            if get_interrupt() > 0:
                                break
                            time.sleep(1)
                        if get_interrupt() > 0:
                            break
                        continue
                    # Retries exhausted without valid output; break out and roll back uniformly
                    break

                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": content or None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                self.messages.append(assistant_msg)
                # Aligned with _chat on the text protocol path: print model response statistics (including tool-call tokens)
                if not self.suppress_output:
                    self._print_response_stats(
                        content or "",
                        _reasoning or "",
                        _ft,
                        start_time,
                        tool_calls=tool_calls or None,
                    )
                # A successful native request means the endpoint supports tools: record that the model supports native,
                # so later temporary errors no longer downgrade to the plain-text protocol.
                self.mark_native_supported()
                return (content or None), (tool_calls or None)
            except Exception as e:
                # Only retryable temporary errors are retried (reusing the outer 7-round loop with exponential backoff).
                # 429 rate-limit/overload honors the retry-after header first; only after retries are exhausted fall to the original logic.
                # Non-retryable deterministic errors (e.g. auth failures, tools unsupported) go straight to the original logic below.
                if _is_retryable_error(e) and attempt < max_retries - 1:
                    wait = 2**attempt
                    if _is_rate_limit_error(e):
                        retry_after = getattr(e, "headers", None)
                        if retry_after:
                            try:
                                wait = max(
                                    wait, float(retry_after.get("retry-after", 0))
                                )
                            except (ValueError, TypeError):
                                pass
                    PrettyOutput.auto_print(
                        f"⚠️ Model call failed ({str(e)}); retrying in {wait:.0f}s ({attempt + 1}/{max_retries})"
                    )
                    for _ in range(int(wait)):
                        if get_interrupt() > 0:
                            break
                        time.sleep(1)
                    if get_interrupt() > 0:
                        break
                    continue
                if getattr(self, "_native_confirmed", False):
                    # This model was previously confirmed to support native tool calls; do not downgrade to the plain-text protocol,
                    # raise directly instead, avoiding a silent degradation to the weaker-capability path.
                    raise
                PrettyOutput.auto_print(
                    f"⚠️ Native tool calls unavailable ({str(e)}); this model will fall back to the plain-text protocol"
                )
                self._native_disabled = True
                # Roll back the user message appended this round and let the plain-text path handle it again
                if (
                    append_user
                    and message
                    and self.messages
                    and self.messages[-1].get("role") == "user"
                ):
                    self.messages.pop()
                content, _ = self._haijun_fallback_text(message, append_user)
                return content, None

        # Retries exhausted without valid output; roll back the user message and return empty
        if (
            append_user
            and message
            and self.messages
            and self.messages[-1].get("role") == "user"
        ):
            self.messages.pop()
        return None, None

    def _haijun_fallback_text(
        self,
        message: Optional[Union[str, List[ContentBlock]]],
        append_user: bool,
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Plain-text fallback after native failure: reuse the existing chat() text protocol."""
        if message is None:
            return None, None
        parts: List[str] = []
        for typ, text in self.chat(message):
            if typ == "content":
                parts.append(text)
        joined = "".join(parts)
        return (joined or None), None

    def name(self) -> str:
        """
        Get the currently used model name

        Returns:
            str: The currently configured model name
        """
        return self.model_name

    @classmethod
    def platform_name(cls) -> str:
        """
        Get the current platform name

        Returns:
            str: The current platform name
        """
        return "haijun"

    def delete_chat(self) -> bool:
        """
        Delete the current conversation history

        Returns:
            bool: Whether the operation succeeded

        Note:
            The system message is kept if one was set
        """
        if self.system_message:
            self.messages = [{"role": "system", "content": self.system_message}]
        else:
            self.messages = []
        return True

    def trim_messages(self) -> bool:
        """Trim the message history to free up token space

        Keeps all system messages and drops the first 10 non-system messages.

        Returns:
            bool: True if space was successfully freed, otherwise False
        """
        if not self.messages:
            return False

        # Separate system and non-system messages
        system_messages = [msg for msg in self.messages if msg.get("role") == "system"]
        non_system_messages = [
            msg for msg in self.messages if msg.get("role") != "system"
        ]

        # Cannot trim if there are 10 or fewer non-system messages
        if len(non_system_messages) <= 10:
            PrettyOutput.auto_print("⚠️ Not enough non-system messages, cannot trim")
            return False

        # Drop the first 10 non-system messages
        trimmed_messages = non_system_messages[10:]
        trimmed_count = len(non_system_messages) - len(trimmed_messages)

        # Reassemble the message list: system messages + trimmed non-system messages
        self.messages = system_messages + trimmed_messages

        # Check whether there are remaining tokens after trimming
        remaining_tokens = self.get_remaining_token_count()
        if remaining_tokens > 0:
            PrettyOutput.auto_print(
                f"✅ Trim succeeded: dropped {trimmed_count} non-system messages, remaining tokens: {remaining_tokens}"
            )
            return True
        else:
            PrettyOutput.auto_print(f"⚠️ Trim failed: remaining tokens {remaining_tokens} are insufficient")
            return False

    @classmethod
    def get_required_env_keys(cls) -> List[str]:
        """
        Get the list of config keys required by the Haijun platform

        Returns:
            List[str]: The list of config keys (juglow_api_key in llm_config)
        """
        return ["JUGLOW_API_KEY"]

    @classmethod
    def get_env_config_guide(cls) -> Dict[str, str]:
        """
        Get the configuration guide

        Returns:
            Dict[str, str]: A mapping of config key names to configuration guidance
        """
        return {
            "JUGLOW_API_KEY": (
                "Enter your Juglow API Key:\n"
                "How to get it:\n"
                "1. Log in to the Juglow console: https://console.juglow.com/\n"
                "2. Go to the API Keys page\n"
                "3. Create a new API Key\n"
                "4. Copy the API Key"
            ),
        }

    @classmethod
    def get_env_defaults(cls) -> Dict[str, str]:
        """
        Get the default values of the Haijun platform environment variables

        Returns:
            Dict[str, str]: A dict of environment variable defaults
        """
        return {}
