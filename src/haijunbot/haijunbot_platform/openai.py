# -*- coding: utf-8 -*-
import json
import logging
import os
import re
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from typing import cast

from openai import OpenAI
from openai import RateLimitError
from openai import APIConnectionError
from openai import APITimeoutError
from openai import InternalServerError

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.native_tools import sanitize_message, to_openai_messages
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot, ct
import haijunbot.haijunbot_utils.globals as jglobals

# Configure logging
logger = logging.getLogger(__name__)

# When the model's returned tool_calls.arguments is not valid JSON (truncated, mixed-in text, etc.),
# use this as the key to pass the raw string to the tool layer, which can then give a self-correcting hint.
PARSE_ERROR_KEY = "__argument_parse_error__"


def _is_rate_limit_error(e: Exception) -> bool:
    """Check whether the exception is a rate-limit/overload error (HTTP 429 or 529).

    Compatible with the openai SDK's RateLimitError and any exception carrying a status_code.
    """
    if isinstance(e, RateLimitError):
        return True
    status = getattr(e, "status_code", None)
    if status in (429, 529):
        return True
    # Handle cases such as APIStatusError using .status_code as a property rather than a field
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


def _accumulate_openai_stream(
    stream: Any,
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """Accumulate the OpenAI streaming response, returning (content, tool_calls).

    tool_calls use the canonical format [{"id","name","arguments": <dict>}]; None when there are no tool calls.
    Merges id/name/arguments fragments by the index of delta.tool_calls.
    """
    content_parts: List[str] = []
    tool_calls_acc: Dict[int, Dict[str, str]] = {}
    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        content_piece = getattr(delta, "content", None)
        if content_piece:
            content_parts.append(content_piece)
        for tc in getattr(delta, "tool_calls", None) or []:
            idx = getattr(tc, "index", 0) or 0
            entry = tool_calls_acc.setdefault(
                idx, {"id": "", "name": "", "arguments": ""}
            )
            if getattr(tc, "id", None):
                entry["id"] = tc.id
            fn = getattr(tc, "function", None)
            if fn is not None:
                if getattr(fn, "name", None):
                    entry["name"] = fn.name
                if getattr(fn, "arguments", None):
                    entry["arguments"] += fn.arguments or ""

    content = "".join(content_parts)
    tool_calls: List[Dict[str, Any]] = []
    for idx in sorted(tool_calls_acc.keys()):
        e = tool_calls_acc[idx]
        raw_args = e.get("arguments", "")
        try:
            args = json.loads(raw_args) if raw_args.strip() else {}
        except Exception:
            # When the arguments are not valid JSON (truncated/mixed-in text, etc.), keep the raw text so the tool layer can give a self-correcting hint
            args = {PARSE_ERROR_KEY: raw_args}
        tool_calls.append(
            {"id": e.get("id", ""), "name": e.get("name", ""), "arguments": args}
        )
    return (content or None), (tool_calls or None)


class OpenAIModel(BasePlatform):
    def __init__(
        self,
        platform_type: str = "normal",
        agent: Optional[Any] = None,
    ):
        """
        Initialize OpenAI model

        Args:
            platform_type: The platform type; one of 'normal', 'cheap', or 'smart'
        """
        super().__init__(platform_type=platform_type, agent=agent)
        self.system_message = ""
        self.extra_headers: Dict[str, str] = {}  # Init extra request headers
        llm_config = self._llm_config or {}

        # If llm_config was passed in (non-empty dict), read from it first to avoid environment variable pollution
        # Only read from environment variables when the corresponding key is missing from llm_config (backward compatible)
        # Note: if a key exists in llm_config but its value is None or an empty string, that value is used; never falls to env vars
        if llm_config:
            # llm_config was passed in; prefer its values
            # Use get(); if the key is absent, returns None, then fall back to environment variables
            # However, if llm_config is an empty dict {}, it's an explicitly passed empty config; read from env vars
            # If a key exists in llm_config but its value is None, that None is used; reading from env vars is skipped
            if "openai_api_key" in llm_config:
                # The key exists; use the value from llm_config (even if None or an empty string)
                self.api_key = llm_config.get("openai_api_key")
            else:
                # The key is absent; read from environment variables (backward compatible)
                self.api_key = os.getenv("OPENAI_API_KEY")

            if "openai_api_base" in llm_config:
                # The key exists; use the value from llm_config (even if None or an empty string)
                self.base_url = llm_config.get("openai_api_base")
            else:
                # The key is absent; read from environment variables (backward compatible)
                self.base_url = os.getenv(
                    "OPENAI_API_BASE", "https://api.openai.com/v1"
                )
        else:
            # No llm_config passed; read from environment variables (backward compatible)
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

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
        if jglobals.proxy_node and jglobals.master_url:
            # Concatenate base_url into the proxy format
            # Note: the /api/node/{node_id}/ prefix is required to match the FastAPI route
            self.base_url = f"{jglobals.master_url}/api/node/{jglobals.proxy_node}/http_proxy/{self.base_url}"
            # Note: X-HaijunBot-Token is not statically cached here; it is injected dynamically
            # via _get_proxy_extra_headers() on each API call so the Token does not expire after a master gateway restart

        # Only warn when llm_config is non-empty but lacks openai_api_key and no environment variable is set either
        # An empty dict llm_config may mean config is not yet loaded; do not warn in that case (avoid a first-round false alarm)
        if not self.api_key and llm_config:
            PrettyOutput.auto_print(
                "⚠️ OpenAI API Key not found; set openai_api_key in llm_config or set the OPENAI_API_KEY environment variable"
            )
        # model_name is already set in BasePlatform.__init__ according to platform_type

        # Optional: Inject extra HTTP headers via llm_config or environment variable
        # Expected format: openai_extra_headers='{"Header-Name": "value", "X-Trace": "abc"}'
        headers_value = llm_config.get("openai_extra_headers")
        if headers_value is None:
            headers_str = os.getenv("OPENAI_EXTRA_HEADERS")
        else:
            headers_str = (
                headers_value
                if isinstance(headers_value, str)
                else json.dumps(headers_value)
            )

        # Note: do not reinitialize self.extra_headers; keep the headers already set under proxy mode
        # self.extra_headers: Dict[str, str] = {}  # This line was removed
        if headers_str:
            try:
                parsed = (
                    json.loads(headers_str)
                    if isinstance(headers_str, str)
                    else headers_str
                )
                if isinstance(parsed, dict):
                    # Ensure all header keys/values are strings
                    self.extra_headers = {str(k): str(v) for k, v in parsed.items()}
                else:
                    PrettyOutput.auto_print(
                        "⚠️ openai_extra_headers format is wrong; it should be a JSON string"
                    )
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️ Failed to parse openai_extra_headers: {e}")
        # Add a browser User-Agent by default to avoid being blocked by some API gateways
        if "User-Agent" not in self.extra_headers:
            # Detect the Kimi API and use a dedicated User-Agent for it
            if self.base_url and "https://api.kimi.com" in self.base_url:
                self.extra_headers["User-Agent"] = "KimiCLI/1.6"
            else:
                self.extra_headers["User-Agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

        # Optional: Set reasoning effort for o1 series models via llm_config or environment variable
        # Expected format: openai_reasoning_effort="low" or "medium" or "high" or "xhigh"
        reasoning_effort_value = llm_config.get("openai_reasoning_effort")
        if reasoning_effort_value is None:
            reasoning_effort_value = os.getenv("OPENAI_REASONING_EFFORT")

        self.reasoning_effort: Optional[str] = (
            reasoning_effort_value if reasoning_effort_value else None
        )

        # Optional: Set extra_body for additional API parameters via llm_config
        # Expected format: openai_extra_body='{"key": "value"}' or dict
        extra_body_value = llm_config.get("openai_extra_body")
        if extra_body_value is None:
            extra_body_str = os.getenv("OPENAI_EXTRA_BODY")
        else:
            extra_body_str = (
                extra_body_value
                if isinstance(extra_body_value, str)
                else json.dumps(extra_body_value)
            )

        self.extra_body: Optional[Dict[str, Any]] = None
        if extra_body_str:
            try:
                parsed = (
                    json.loads(extra_body_str)
                    if isinstance(extra_body_str, str)
                    else extra_body_str
                )
                if isinstance(parsed, dict):
                    self.extra_body = parsed
                else:
                    PrettyOutput.auto_print("⚠️ openai_proxy format is wrong; it should be a string")
            except Exception as e:
                PrettyOutput.auto_print(f"⚠️ Failed to set the OpenAI proxy: {e}")
        # Sampling params: can be overridden in llm_config (temperature/top_p/max_tokens).
        # Default temperature=0.7 (moderate, not greedy, avoiding long repetitions from too-low temperature);
        # top_p defaults to None and is not sent (i.e. the server's default 1.0), avoiding double narrowing with temperature+top_p.
        # A field of None means it is omitted from the request.
        self.temperature: Optional[float] = llm_config.get("temperature", 0.7)
        self.top_p: Optional[float] = llm_config.get("top_p")
        _mt = llm_config.get("max_tokens")
        self.max_tokens: Optional[int] = _mt if _mt not in (None, "") else None

        # Initialize OpenAI client, try to pass default headers if SDK supports it
        from haijunbot.haijunbot_utils.config import get_request_timeout

        _req_timeout = get_request_timeout()

        def _build_client(**overrides: Any) -> OpenAI:
            # Use Dict[str, Any] to hold the optional params, avoiding type-checker false positives on **kwargs expansion
            params: Dict[str, Any] = {
                "api_key": self.api_key,
                "base_url": self.base_url,
            }
            if _req_timeout is not None:
                params["timeout"] = _req_timeout
            params.update(overrides)
            return OpenAI(**params)

        try:
            if self.extra_headers:
                self.client = _build_client(default_headers=self.extra_headers)
            else:
                self.client = _build_client()
        except TypeError:
            # Fallback: SDK version may not support default_headers
            self.client = _build_client()
            if self.extra_headers:
                PrettyOutput.auto_print(
                    "⚠️ The current OpenAI SDK version does not support default_headers; extra_headers were ignored"
                )
        self.messages: List[Dict[str, Any]] = []
        self.system_message = ""
        self._streaming_disabled: Optional[bool] = None

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
                self.system_message = msg.get("content", "")
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

    def _filter_think_tags(self, content: str) -> str:
        """Filter think tag content

        Args:
            content: The original content

        Returns:
            str: The filtered content
        """
        # Filter <think> tags
        content = re.sub(
            ot("think") + r".*?" + ct("think"), "", content, flags=re.DOTALL
        )
        # Filter <thinking> tags
        content = re.sub(
            ot("thinking") + r".*?" + ct("thinking"), "", content, flags=re.DOTALL
        )
        return content

    def get_model_list(self) -> List[Tuple[str, str]]:
        """
        Get the list of available OpenAI models

        Returns:
            List[Tuple[str, str]]: A list of (model ID, model name) tuples

        Raises:
            On API call failure, prints the error message and returns an empty list
        """
        try:
            proxy_headers = self._get_proxy_extra_headers()
            models = (
                self.client.models.list(extra_headers=proxy_headers)
                if proxy_headers
                else self.client.models.list()
            )
            model_list = []
            for model in models:
                model_list.append((model.id, model.id))
            return model_list
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to fetch the model list: {str(e)}")
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
            Generator[Tuple[str, str], None, None]: A generator yielding AI response content chunk by chunk

        Raises:
            On API call failure, raises an exception and prints the error message
        """
        # Record the message list length before adding the user message, for rollback on failure
        messages_before_user = len(self.messages)

        # Rotate API key for round-robin support
        next_key = self._get_next_api_key()
        if next_key:
            self.api_key = next_key
            self.client.api_key = next_key

        try:
            # Handle multimodal messages
            if isinstance(message, str):
                user_message_content = message
            else:
                # Check multimodal support; if unsupported, fall back to plain text
                if not self.supports_multimodal():
                    from haijunbot.haijunbot_utils.output import PrettyOutput

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
                    # Convert List[ContentBlock] into the format expected by the OpenAI API
                    user_message_content = []
                    for block in message:
                        if block["type"] == "text":
                            user_message_content.append(
                                {"type": "text", "text": block["text"]}
                            )
                        elif block["type"] == "image_url":
                            # The OpenAI API expects image_url to be an object with a url field
                            image_url_data = block["image_url"]
                            if isinstance(image_url_data, str):
                                image_url_data = {"url": image_url_data}
                            user_message_content.append(
                                {"type": "image_url", "image_url": image_url_data}
                            )
                    else:
                        # Unknown type; ignore or raise
                        pass

            # Clean lone surrogate characters: the current user message may come back from frontends such as eval_js,
            # and a lone surrogate throws UnicodeEncodeError when httpx encodes the request body.
            self.messages.append(
                sanitize_message({"role": "user", "content": user_message_content})
            )

            # Loop until it stops for reasons other than a length limit
            # Build the API call parameters
            # Send the canonical message sequence so role=tool/tool_calls entries in the history are also expressed correctly
            use_streaming = not self._streaming_disabled
            api_params: Dict[str, Any] = {
                "model": self.model_name,
                "messages": to_openai_messages(self.messages),
                "stream": use_streaming,
            }
            _temperature = getattr(self, "temperature", 0.7)
            _top_p = getattr(self, "top_p", None)
            _max_tokens = getattr(self, "max_tokens", None)
            if _temperature is not None:
                api_params["temperature"] = _temperature
            if _top_p is not None:
                api_params["top_p"] = _top_p
            if _max_tokens is not None:
                api_params["max_tokens"] = _max_tokens
            # Only add the reasoning_effort parameter when it is configured
            if self.reasoning_effort:
                api_params["reasoning_effort"] = self.reasoning_effort

            # Only add the extra_body parameter when it is configured
            if self.extra_body:
                api_params["extra_body"] = self.extra_body

            # If max_tokens was not specified, do not set a default; let the model use its own default

            # Inject the proxy auth header dynamically so Token updates take effect after a master gateway restart
            proxy_headers = self._get_proxy_extra_headers()
            if proxy_headers:
                api_params["extra_headers"] = proxy_headers
            response = self.client.chat.completions.create(**api_params)

            full_response = ""
            full_reasoning = ""

            if use_streaming:
                # Streaming mode: iterate over the chunk increments
                for chunk in response:
                    # Use a type annotation to pin the chunk type, avoiding union type errors
                    from openai.types.chat import ChatCompletionChunk

                    chunk_typed: ChatCompletionChunk = cast(ChatCompletionChunk, chunk)
                    if chunk_typed.choices and len(chunk_typed.choices) > 0:
                        choice = chunk_typed.choices[0]

                        # Get the content increment
                        if choice.delta:
                            # Handle reasoning_content (the reasoning process, e.g. GLM models)
                            if (
                                hasattr(choice.delta, "reasoning_content")
                                and choice.delta.reasoning_content
                            ):
                                text: str = str(choice.delta.reasoning_content)
                                full_reasoning = full_reasoning + text
                                yield ("reason", text)
                            # Handle content (the main body)
                            if choice.delta.content:
                                text: str = str(choice.delta.content)
                                full_response = full_response + text
                                yield ("content", text)
                if full_response:
                    # It succeeded before, so streaming requests work
                    self._streaming_disabled = False
                    assistant_message = {"role": "assistant", "content": full_response}
                    if full_reasoning:
                        assistant_message["reasoning_content"] = full_reasoning
                    self.messages.append(assistant_message)
                else:
                    # Only set to True when the state is unset
                    if self._streaming_disabled is None:
                        self._streaming_disabled = True
                    fallback_params = api_params.copy()
                    fallback_params["stream"] = False
                    fallback_headers = self._get_proxy_extra_headers()
                    if fallback_headers:
                        fallback_params["extra_headers"] = fallback_headers
                    fallback_response = self.client.chat.completions.create(
                        **fallback_params
                    )
                    if fallback_response.choices and len(fallback_response.choices) > 0:
                        fallback_message = fallback_response.choices[0].message
                        fallback_reasoning = (
                            getattr(fallback_message, "reasoning_content", None) or ""
                        )
                        fallback_text = fallback_message.content or ""
                        fallback_content = fallback_text
                        if fallback_content:
                            assistant_message = {
                                "role": "assistant",
                                "content": fallback_content,
                            }
                            if fallback_reasoning:
                                assistant_message["reasoning_content"] = (
                                    fallback_reasoning
                                )
                            self.messages.append(assistant_message)
                            yield ("content", fallback_content)
                            return
                    raise Exception("No response from model")
            else:
                # Non-streaming mode: fetch the full response directly
                if response.choices and len(response.choices) > 0:
                    response_message = response.choices[0].message
                    # Handle reasoning_content (the reasoning process, e.g. GLM models)
                    reasoning = (
                        getattr(response_message, "reasoning_content", None) or ""
                    )
                    content = response_message.content or ""
                    full_response = content
                    full_reasoning = reasoning
                if full_response:
                    assistant_message = {"role": "assistant", "content": full_response}
                    if full_reasoning:
                        assistant_message["reasoning_content"] = full_reasoning
                    self.messages.append(assistant_message)
                    yield ("content", full_response)
                else:
                    raise Exception("No response from model")
        except Exception as e:
            # On failure, roll back: remove the appended user message
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
        """Stream one conversation round with native tools.

        Returns (content, tool_calls):
        - content: the assistant's text (may be None)
        - tool_calls: the canonical format [{"id","name","arguments": <dict>}]; None when there are no tool calls

        On success, the assistant message (including tool_calls) is appended to the history as a canonical message.
        If the endpoint does not support tools, it falls back to plain text, sets _native_disabled, and this instance no longer tries again.
        """
        # Already downgraded or native capability not enabled; use plain text
        if self._native_disabled or not tools:
            content, _ = self._native_fallback_text(message, append_user)
            return content, None

        # Append the user message (tool continuation rounds use append_user=False to avoid re-adding empty messages)
        # Also clean lone surrogate characters so httpx does not throw UnicodeEncodeError when encoding the request body
        if append_user and message:
            self.messages.append(sanitize_message({"role": "user", "content": message}))
        next_key = self._get_next_api_key()
        if next_key:
            self.api_key = next_key
            self.client.api_key = next_key

        proxy_headers = self._get_proxy_extra_headers()
        api_params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": to_openai_messages(self.messages),
            "stream": True,
            "tools": tools,
        }
        _temperature = getattr(self, "temperature", 0.7)
        _top_p = getattr(self, "top_p", None)
        _max_tokens = getattr(self, "max_tokens", None)
        if _temperature is not None:
            api_params["temperature"] = _temperature
        if _top_p is not None:
            api_params["top_p"] = _top_p
        if _max_tokens is not None:
            api_params["max_tokens"] = _max_tokens
        if self.reasoning_effort:
            api_params["reasoning_effort"] = self.reasoning_effort
        if self.extra_body:
            api_params["extra_body"] = self.extra_body
        if proxy_headers:
            api_params["extra_headers"] = proxy_headers

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
                response = self.client.chat.completions.create(**api_params)

                # Accumulator: content is yielded chunk by chunk for streaming rendering; tool_calls fragments are merged by index
                content_parts: List[str] = []
                tool_calls_acc: Dict[int, Dict[str, str]] = {}

                def _gen() -> Generator[Tuple[str, str], None, None]:
                    for chunk in response:
                        if not getattr(chunk, "choices", None):
                            continue
                        delta = chunk.choices[0].delta
                        if delta is None:
                            continue
                        piece = getattr(delta, "content", None)
                        if piece:
                            content_parts.append(piece)
                            yield ("content", piece)
                        for tc in getattr(delta, "tool_calls", None) or []:
                            idx = getattr(tc, "index", 0) or 0
                            entry = tool_calls_acc.setdefault(
                                idx, {"id": "", "name": "", "arguments": ""}
                            )
                            if getattr(tc, "id", None):
                                entry["id"] = tc.id
                            fn = getattr(tc, "function", None)
                            if fn is not None:
                                if getattr(fn, "name", None):
                                    entry["name"] = fn.name
                                if getattr(fn, "arguments", None):
                                    entry["arguments"] += fn.arguments or ""

                start_time = time.time()
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
                            chat_iterator=_gen(),
                            raise_on_error=_raise_on_error,
                        )
                    else:
                        content, _reasoning, _ft = self._chat_with_simple_output(
                            render_message,
                            start_time,
                            chat_iterator=_gen(),
                            raise_on_error=_raise_on_error,
                        )
                else:
                    content, _reasoning = self._chat_with_suppressed_output(
                        render_message,
                        chat_iterator=_gen(),
                        raise_on_error=_raise_on_error,
                    )

                # Parse the canonical format from the accumulated tool_calls fragments
                tool_calls: List[Dict[str, Any]] = []
                for idx in sorted(tool_calls_acc.keys()):
                    e = tool_calls_acc[idx]
                    raw_args = e.get("arguments", "")
                    try:
                        args = json.loads(raw_args) if raw_args.strip() else {}
                    except Exception:
                        # When the arguments are not valid JSON (truncated/mixed-in text, etc.), keep the raw text so the tool layer can give a self-correcting hint
                        args = {PARSE_ERROR_KEY: raw_args}
                    tool_calls.append(
                        {
                            "id": e.get("id", ""),
                            "name": e.get("name", ""),
                            "arguments": args,
                        }
                    )

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
                    "content": content,
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
                # Only retryable temporary errors (rate-limit/overload/5xx/network/timeout) enter the retry loop,
                # reusing the outer 7-round loop for exponential backoff; 429 honors the retry-after header first.
                # Deterministic errors (auth/parameter/tools unsupported, etc.) go straight to the original logic.
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
                content, _ = self._native_fallback_text(message, append_user)
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

    def _native_fallback_text(
        self,
        message: Optional[Union[str, List[ContentBlock]]],
        append_user: bool,
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """Plain-text fallback after native failure: reuse the existing chat() text protocol."""
        if message is None:
            # In theory a tool round should never be a plain-text round; if it happens, just return None
            return None, None
        text_parts: List[str] = []
        for typ, text in self.chat(message):
            if typ == "content":
                text_parts.append(text)
        joined = "".join(text_parts)
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
        return "openai"

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
        Get the list of config keys required by the OpenAI platform (deprecated: use llm_config instead)

        Returns:
            List[str]: The list of config keys (openai_api_key, openai_api_base in llm_config)
        """
        return ["OPENAI_API_KEY", "OPENAI_API_BASE"]

    @classmethod
    def get_env_config_guide(cls) -> Dict[str, str]:
        """
        Get the configuration guide (deprecated: use llm_config instead)

        Returns:
            Dict[str, str]: A mapping of config key names to configuration guidance
        """
        return {
            "OPENAI_API_KEY": (
                "Enter your OpenAI API Key:\n"
                "Method 1 (official):\n"
                "1. Log in to the OpenAI platform: https://platform.openai.com/\n"
                "2. Go to the API Keys page\n"
                "3. Create a new API Key or use an existing one\n"
                "4. Copy the API Key (starts with sk-)\n"
                "\nMethod 2 (third-party proxy):\n"
                "If using a third-party proxy service, get the API Key from the proxy provider"
            ),
            "OPENAI_API_BASE": (
                "Enter the API Base URL:\n"
                "- Official API: https://api.openai.com/v1\n"
                "- If using a proxy or third-party service, enter the matching Base URL\n"
                "- For example: https://your-proxy.com/v1"
            ),
        }

    @classmethod
    def get_env_defaults(cls) -> Dict[str, str]:
        """
        Get the default values of the OpenAI platform environment variables

        Returns:
            Dict[str, str]: A dict of environment variable defaults
        """
        return {"OPENAI_API_BASE": "https://api.openai.com/v1"}
