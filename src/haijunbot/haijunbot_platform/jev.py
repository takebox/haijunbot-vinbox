# -*- coding: utf-8 -*-
"""Jev (TypeSafe System One) platform adapter.

Jev's interface differs significantly from regular chat models:
- no chat, no streaming, no multimodality; one request returns a structured typed decision;
- the request body is ``{"state": ..., "model": ..., "questions": {...}}``;
- the response body is ``{"model": ..., "answers": {...}, "usage": {...}}``.

To preserve BasePlatform's ``chat()`` contract (a streaming text generator), this adapter uses the
**text protocol**: the caller passes ``state`` and ``questions`` into ``chat()`` as a JSON string,
parses them, calls ``POST /v1/systemone``, then yields the structured answers as readable text.

Input format (message is a JSON string)::

    {
      "state": "content to evaluate, which can be a string/object/array",
      "questions": {
        "is_urgent": {"type": "noul", "instructions": "Does it express urgency?"},
        "team": {"type": "choice", "instructions": "Which team should handle it?",
                 "criteria": {"billing": "billing", "tech": "tech"}},
        "level": {"type": "score", "instructions": "Severity?",
                  "criteria": ["low", "medium", "high"]}
      }
    }

If message is not valid JSON, or lacks ``state``/``questions``, an exception is raised describing the
expected format, avoiding silent wrong behavior caused by fabricating default questions.
"""

import json
import os
import time
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import httpx

import haijunbot.haijunbot_utils.globals as jglobals
from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.config import get_request_timeout
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.output import PrettyOutput

# Default API address and model
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL_NAME = "jev-latest"

# Retry policy: exponential backoff on 429 (rate limited) / 529 (service overloaded)
MAX_RETRIES = 4
RETRY_BACKOFF_BASE = 1.0  # seconds; actual wait is base * 2**attempt

# Per-request timeout (seconds): Jev latency is 70~500ms; leave margin for network jitter
DEFAULT_TIMEOUT = 60.0


class JevPlatform(BasePlatform):
    """Jev (TypeSafe System One) platform implementation.

    Jev only does "typed decisions" (Choice/Score/Noul) — it does not generate free text, does not support
    multimodality, and has no chat history, so this class downgrades the chat semantics to "one state evaluation".
    """

    def __init__(
        self,
        platform_type: str = "normal",
        agent: Optional[Any] = None,
    ):
        """Initialize the Jev platform.

        Args:
            platform_type: The platform type; one of 'normal', 'cheap', or 'smart'
            agent: The Agent instance, used for callbacks such as triggering summaries
        """
        super().__init__(platform_type=platform_type, agent=agent)
        self.system_message = ""
        self.messages: List[Dict[str, Any]] = []
        llm_config = self._llm_config or {}

        # The base class picks model_name from the global config by platform_type, but without a Jev config it grabs
        # another platform's model name (e.g. gpt-5). Fall back here: any non-Jev model name reverts to jev-latest.
        if not self._is_jev_model_name(self.model_name):
            self.model_name = DEFAULT_MODEL_NAME

        # Config reading: llm_config takes precedence (used if the key exists, even empty), otherwise fall back to env vars
        if llm_config:
            if "typesafe_api_key" in llm_config:
                self.api_key = llm_config.get("typesafe_api_key")
            else:
                self.api_key = os.getenv("TYPESAFE_API_KEY")
            if "typesafe_api_base" in llm_config:
                self.base_url = llm_config.get("typesafe_api_base")
            else:
                self.base_url = os.getenv("TYPESAFE_API_BASE", DEFAULT_BASE_URL)
        else:
            self.api_key = os.getenv("TYPESAFE_API_KEY")
            self.base_url = os.getenv("TYPESAFE_API_BASE", DEFAULT_BASE_URL)

        # Normalize into an api_keys list to support multi-key rotation (consistent with the openai/haijun platforms)
        if isinstance(self.api_key, list):
            self.api_keys = self.api_key
        elif isinstance(self.api_key, str) and self.api_key:
            self.api_keys = [k.strip() for k in self.api_key.split(",") if k.strip()]
        else:
            self.api_keys = [self.api_key] if self.api_key else []
        if self.api_keys:
            self.api_key = self.api_keys[0]
        self._api_key_index = 0

        # Fall back to the default when base_url is empty, avoiding an invalid concatenated URL
        if not self.base_url:
            self.base_url = DEFAULT_BASE_URL
        self.base_url = str(self.base_url).rstrip("/")

        # Proxy mode: route the original base_url under the gateway's http_proxy route
        if jglobals.proxy_node and jglobals.master_url:
            self.base_url = (
                f"{jglobals.master_url}/api/node/{jglobals.proxy_node}"
                f"/http_proxy/{self.base_url}"
            )

        # Only warn when llm_config was explicitly set but no key was obtained, avoiding false alarms before config load completes
        if not self.api_key and llm_config:
            PrettyOutput.auto_print(
                "⚠️ TypeSafe API Key not found; set typesafe_api_key in llm_config "
                "or set the TYPESAFE_API_KEY environment variable"
            )

        # Request timeout: prefer the request_timeout config, otherwise use the default
        self.timeout: float = get_request_timeout() or DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Internal tools
    # ------------------------------------------------------------------
    @staticmethod
    def _is_jev_model_name(model_name: Any) -> bool:
        """Check whether the model name belongs to the Jev family.

        Args:
            model_name: The model name to check

        Returns:
            bool: True if it is a Jev model
        """
        return isinstance(model_name, str) and model_name.strip().lower().startswith(
            "jev"
        )

    def _get_next_api_key(self) -> Optional[str]:
        """Rotate to the next API Key for multi-key load balancing."""
        if not self.api_keys:
            return None
        if len(self.api_keys) == 1:
            return self.api_keys[0]
        key = self.api_keys[self._api_key_index]
        self._api_key_index = (self._api_key_index + 1) % len(self.api_keys)
        return key

    def _build_headers(self) -> Dict[str, str]:
        """Build the request headers, including the dynamically injected gateway auth header."""
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        # In proxy mode, read the Token in real time on each request so it does not expire after a master gateway restart
        headers.update(self._get_proxy_extra_headers())
        return headers

    def _truncate_message_if_needed(self, message: str) -> str:
        """Truncate an oversized message by JSON structure so the result stays valid JSON.

        Jev's input is a JSON protocol string; the base class's generic truncation hard-cuts by character
        count and appends a bare newline hint, which breaks the JSON (reporting "Invalid control character" /
        "Unterminated string"). Here we instead parse the JSON, truncate only the ``state`` field value, and
        re-serialize, always producing valid JSON.

        Args:
            message: The raw message (a JSON string)

        Returns:
            str: The truncated valid JSON string; returns the original message when no truncation is needed or parsing fails
        """
        try:
            remaining_tokens = self.get_remaining_token_count()

            # When remaining tokens are low, first try trimming the history to free space (consistent with the base class).
            # Jev has no chat context; trim_messages clears non-system messages, usually freeing space immediately.
            if remaining_tokens <= 0:
                PrettyOutput.auto_print("⚠️ Warning: remaining tokens are 0, trying to trim the message history...")
                if self.trim_messages():
                    remaining_tokens = self.get_remaining_token_count()
                    PrettyOutput.auto_print(
                        f"✅ Trim succeeded, remaining tokens: {remaining_tokens}"
                    )
                if remaining_tokens <= 0:
                    # Trimming failed or there is still no space after trimming: cannot safely truncate a JSON protocol message,
                    # so return the original message to the upper layer (returning an empty string would make the upper layer
                    # report "Expecting value: line 1 column 1", masking the real cause).
                    PrettyOutput.auto_print("⚠️ Warning: still no remaining tokens after trimming, sending the original message")
                    return message

            message_tokens = get_context_token_count(message)
            if message_tokens <= remaining_tokens:
                return message

            # Truncation needed: keep 80% of the remaining tokens as a safety margin
            target_tokens = int(remaining_tokens * 0.8)
            if target_tokens <= 0:
                PrettyOutput.auto_print("⚠️ Warning: not enough remaining tokens, cannot send the message")
                return ""

            target_chars = target_tokens * 4
            if len(message) <= target_chars:
                return message

            try:
                payload = json.loads(message, strict=False)
            except Exception:
                # If it cannot be parsed as JSON, do not rewrite it; let the upper layer handle it as-is
                return message

            if not isinstance(payload, dict) or not isinstance(
                payload.get("state"), str
            ):
                # If state is not a string (e.g. object/array), it cannot be truncated safely; keep as-is
                return message

            # Compute the fixed overhead excluding state, then give all remaining budget to state
            state = payload["state"]
            overhead = len(json.dumps({**payload, "state": ""}, ensure_ascii=False))
            budget = max(0, target_chars - overhead - 64)  # reserve space for the truncation note
            if budget <= 0:
                # The fixed overhead has consumed the budget: truncating state cannot make the message validly shorter,
                # so return the original message to the upper layer, avoiding an empty string with no semantics.
                PrettyOutput.auto_print("⚠️ Warning: not enough remaining tokens, sending the original message")
                return message

            note = "\n\n... (message too long, truncated to stay within the context limit)"
            payload["state"] = state[:budget] + note
            truncated = json.dumps(payload, ensure_ascii=False)
            PrettyOutput.auto_print(
                f"⚠️ Warning: message too long ({message_tokens} tokens), "
                f"truncated by JSON structure to about {target_tokens} tokens"
            )
            return truncated
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Warning: error checking message length: {e}, using the original message")
            return message

    @staticmethod
    def _validate_questions(questions: Any) -> Dict[str, Any]:
        """Validate and normalize the questions field.
        Args:
            questions: The question mapping to validate

        Returns:
            Dict[str, Any]: The normalized question mapping

        Raises:
            ValueError: Raised when questions are invalid, describing the expected format
        """
        if not isinstance(questions, dict) or not questions:
            raise ValueError(
                "questions must be a non-empty object like "
                '{"<question_id>": {"type": "noul|choice|score", "instructions": "..."}}'
            )
        normalized: Dict[str, Any] = {}
        for qid, question in questions.items():
            if not isinstance(question, dict):
                raise ValueError(
                    f"question '{qid}' must be an object containing the type and instructions fields"
                )
            qtype = question.get("type")
            if qtype not in ("noul", "choice", "score"):
                raise ValueError(
                    f"question '{qid}' has an invalid type: {qtype!r}, "
                    "only 'noul', 'choice', 'score' are supported"
                )
            if not question.get("instructions"):
                raise ValueError(f"question '{qid}' is missing the instructions field")
            # criteria is required by the API for choice/score; validating early avoids a 422 only at the server
            criteria = question.get("criteria")
            if qtype == "choice":
                if not isinstance(criteria, dict) or not criteria:
                    raise ValueError(
                        f"question '{qid}' (choice) must have a non-empty criteria object, "
                        'like {"option name": "option description"}'
                    )
            elif qtype == "score":
                if not isinstance(criteria, list) or len(criteria) < 2:
                    raise ValueError(
                        f"question '{qid}' (score) must have a criteria array of at least 2 items, "
                        'like ["low", "medium", "high"]'
                    )
                if len(criteria) > 10:
                    raise ValueError(
                        f"question '{qid}' (score) can have at most 10 criteria items, "
                        f"currently has {len(criteria)}"
                    )
            normalized[str(qid)] = question
        return normalized

    @classmethod
    def parse_state_and_questions(
        cls, message: Union[str, List[ContentBlock], Dict[str, Any]]
    ) -> Tuple[Any, Dict[str, Any]]:
        """Parse chat()'s message into (state, questions).

        Args:
            message: A JSON string, or an already-parsed dict (for direct in-program calls)

        Returns:
            Tuple[Any, Dict[str, Any]]: (state, the normalized questions)

        Raises:
            ValueError: Raised when the input does not match the agreed format, describing the expected format
        """
        if isinstance(message, list):
            # Multimodal input is not supported: only concatenate text blocks to avoid a hard crash
            text_parts = [
                block.get("text", "")
                for block in message
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            message = "\n".join(text_parts)

        if isinstance(message, str):
            raw = message.strip()
            try:
                # strict=False tolerates bare control characters inside strings (newlines/tabs etc.),
                # as extra defense against raw control characters possibly introduced upstream.
                payload = json.loads(raw, strict=False)
            except Exception as e:
                raise ValueError(
                    "Jev requires the input to be a JSON string like "
                    '{"state": <content to evaluate>, "questions": {<question id>: <question definition>}}; '
                    f"the current input could not be parsed as JSON: {e}"
                )
        elif isinstance(message, dict):
            payload = message
        else:
            raise ValueError(
                "Jev input must be a JSON string or a dict, "
                f"the current type is {type(message).__name__}"
            )

        if not isinstance(payload, dict):
            raise ValueError(
                "Jev input JSON must be an object like "
                '{"state": <content to evaluate>, "questions": {<question id>: <question definition>}}'
            )
        if "state" not in payload:
            raise ValueError("Jev input is missing the 'state' field")
        if "questions" not in payload:
            raise ValueError("Jev input is missing the 'questions' field")

        return payload["state"], cls._validate_questions(payload["questions"])

    @classmethod
    def build_request_body(
        cls,
        state: Any,
        questions: Dict[str, Any],
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> Dict[str, Any]:
        """Build the /v1/systemone request body (a pure function for independent verification).

        Args:
            state: The content to evaluate
            questions: The validated question mapping
            model_name: The model name, defaults to jev-latest

        Returns:
            Dict[str, Any]: The request body
        """
        return {
            "state": state,
            "model": model_name or DEFAULT_MODEL_NAME,
            "questions": questions,
        }

    @staticmethod
    def format_answers(response: Dict[str, Any]) -> str:
        """Serialize the Jev response into readable text (a pure function for independent verification).

        Args:
            response: The Jev response body

        Returns:
            str: Human-readable answer text, including values, confidence, and probability distributions
        """
        lines: List[str] = []
        model = response.get("model", DEFAULT_MODEL_NAME)
        lines.append(f"Jev model: {model}")

        answers = response.get("answers") or {}
        if not answers:
            lines.append("(no answers)")
        for qid, answer in answers.items():
            if not isinstance(answer, dict):
                lines.append(f"- {qid}: {answer}")
                continue
            atype = answer.get("type", "unknown")
            if atype == "noul":
                # Noul returns the probability of "yes", 0~1
                lines.append(f"- {qid} [noul]: {answer.get('noul')}")
            elif atype == "choice":
                lines.append(f"- {qid} [choice]: {answer.get('choice')}")
            elif atype == "score":
                lines.append(f"- {qid} [score]: {answer.get('score')}")
            else:
                lines.append(f"- {qid} [{atype}]: {answer}")

            confidence = answer.get("confidence")
            if confidence is not None:
                lines.append(f"    confidence: {confidence}")
            probabilities = answer.get("probabilities")
            if probabilities is not None:
                lines.append(f"    probabilities: {probabilities}")
            legend = answer.get("legend")
            if legend is not None:
                lines.append(f"    legend: {legend}")

        usage = response.get("usage") or {}
        if usage:
            lines.append(
                f"usage: input_tokens={usage.get('input_tokens')}, "
                f"output_tokens={usage.get('output_tokens')}"
            )
        return "\n".join(lines)

    def _post_systemone(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Call POST /v1/systemone, handling retries and errors.

        Args:
            body: The request body

        Returns:
            Dict[str, Any]: The response body

        Raises:
            RuntimeError: Raised when the request fails and retries are exhausted; the message includes the response body
        """
        url = f"{self.base_url}/v1/systemone"
        last_error: Optional[str] = None

        for attempt in range(MAX_RETRIES):
            # Rotate the API Key each round for multi-key load balancing
            next_key = self._get_next_api_key()
            if next_key:
                self.api_key = next_key
            try:
                resp = httpx.post(
                    url,
                    json=body,
                    headers=self._build_headers(),
                    timeout=self.timeout,
                )
            except Exception as e:
                # Network-level exception: also retry with backoff
                last_error = f"request error: {e}"
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF_BASE * (2**attempt))
                    continue
                raise RuntimeError(f"Jev request failed ({url}): {last_error}")

            # Rate limited/overloaded: retry with exponential backoff, honoring the retry-after header
            if resp.status_code in (429, 529):
                last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE * (2**attempt)
                    retry_after = resp.headers.get("retry-after")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    PrettyOutput.auto_print(
                        f"⚠️ Jev rate limited/overloaded (HTTP {resp.status_code}), "
                        f"retrying in {wait:.0f}s ({attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(wait)
                    continue
                raise RuntimeError(
                    f"Jev request failed (rate limited/overloaded, retried {MAX_RETRIES} times): {last_error}"
                )

            # Auth/parameter errors: not retryable, throw directly with the response body
            if resp.status_code in (401, 422):
                raise RuntimeError(
                    f"Jev request failed (HTTP {resp.status_code}): {resp.text[:1000]}"
                )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Jev request failed (HTTP {resp.status_code}): {resp.text[:1000]}"
                )

            try:
                return resp.json()
            except Exception as e:
                raise RuntimeError(
                    f"Jev response parse failed: {e}, raw response: {resp.text[:500]}"
                )

        raise RuntimeError(f"Jev request failed: {last_error}")

    # ------------------------------------------------------------------
    # BasePlatform required interfaces
    # ------------------------------------------------------------------
    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Replace the conversation history.

        Jev has no chat semantics; here only the latest user message is kept as the input to evaluate,
        so the upper layer can reuse a unified session management interface.
        """
        self.messages = messages
        for msg in messages:
            if msg.get("role") == "system":
                self.system_message = msg.get("content", "")
                break

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self.messages

    def set_model_name(self, model_name: str):
        """Set the model name."""
        self.model_name = model_name

    def set_system_prompt(self, message: str):
        """Set the system prompt.

        Jev does not support a system prompt; this is only recorded here and is not part of the request construction.
        """
        self.messages = []
        self.system_message = message
        self.messages.append({"role": "system", "content": self.system_message})

    def get_model_list(self) -> List[Tuple[str, str]]:
        """Get the available model list (GET /v1/models).

        Returns:
            List[Tuple[str, str]]: A list of (model ID, description); an empty list on failure
        """
        try:
            next_key = self._get_next_api_key()
            if next_key:
                self.api_key = next_key
            resp = httpx.get(
                f"{self.base_url}/v1/models",
                headers=self._build_headers(),
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                PrettyOutput.auto_print(
                    f"❌ Failed to get the Jev model list: HTTP {resp.status_code} "
                    f"{resp.text[:200]}"
                )
                return []
            models = (resp.json() or {}).get("models") or []
            return [
                (str(m.get("name", "")), str(m.get("description", "")))
                for m in models
                if isinstance(m, dict) and m.get("name")
            ]
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to get the Jev model list: {str(e)}")
            return []

    def chat(
        self, message: Union[str, List[ContentBlock]]
    ) -> Generator[Tuple[str, str], None, None]:
        """Run one Jev evaluation.

        Args:
            message: A JSON string containing state and questions (see the module docs)

        Returns:
            Generator[Tuple[str, str], None, None]: yields only ("content", text)

        Raises:
            ValueError: The input format does not match the convention
            RuntimeError: The API call failed
        """
        # Record the length before appending so we can roll back on failure without polluting the history
        messages_before_user = len(self.messages)
        try:
            state, questions = self.parse_state_and_questions(message)
            body = self.build_request_body(state, questions, self.model_name)

            # Record the user message (the raw JSON text) so the chat history stays traceable
            user_content = (
                message
                if isinstance(message, str)
                else json.dumps(message, ensure_ascii=False)
            )
            self.messages.append({"role": "user", "content": user_content})

            response = self._post_systemone(body)
            text = self.format_answers(response)

            self.messages.append({"role": "assistant", "content": text})
            yield ("content", text)
        except Exception:
            # On failure, roll back the appended user message
            if len(self.messages) > messages_before_user:
                self.messages = self.messages[:messages_before_user]
            raise

    def name(self) -> str:
        """Get the currently used model name."""
        return self.model_name

    @classmethod
    def platform_name(cls) -> str:
        """Get the platform name (used in the platform field of the config)."""
        return "jev"

    def delete_chat(self) -> bool:
        """Clear the chat history (keeping the system message)."""
        if self.system_message:
            self.messages = [{"role": "system", "content": self.system_message}]
        else:
            self.messages = []
        return True

    def trim_messages(self) -> bool:
        """Trim the message history.

        Jev has no chat context; each request only depends on the current input, so simply clearing non-system messages is enough.
        """
        if not self.messages:
            return False
        system_messages = [m for m in self.messages if m.get("role") == "system"]
        non_system = [m for m in self.messages if m.get("role") != "system"]
        if not non_system:
            PrettyOutput.auto_print("⚠️ Not enough non-system messages, cannot trim")
            return False
        self.messages = system_messages
        return True

    def supports_multimodal(self) -> bool:
        """Jev only supports text input."""
        return False

    def supports_native_tool_calls(self) -> bool:
        """Jev does not support native function calling."""
        return False

    @classmethod
    def get_required_env_keys(cls) -> List[str]:
        """Get the config keys required by the Jev platform.

        Returns:
            List[str]: The config key list (typesafe_api_key/typesafe_api_base in llm_config)
        """
        return ["TYPESAFE_API_KEY", "TYPESAFE_API_BASE"]

    @classmethod
    def get_env_config_guide(cls) -> Dict[str, str]:
        """Get the configuration guide."""
        return {
            "TYPESAFE_API_KEY": (
                "Enter your TypeSafe API Key:\n"
                "1. Log in to the TypeSafe console: https://console.typesafe.ai/\n"
                "2. Go to the API Keys page and create a key\n"
                "3. Copy the API Key and fill it in (llm_config key name: typesafe_api_key)"
            ),
            "TYPESAFE_API_BASE": (
                "Enter the API Base URL:\n"
                "- Official API: https://api.typesafe.ai\n"
                "- If using a proxy or third-party gateway, enter the corresponding Base URL"
            ),
        }

    @classmethod
    def get_env_defaults(cls) -> Dict[str, str]:
        """Get the default environment variable values."""
        return {"TYPESAFE_API_BASE": DEFAULT_BASE_URL}
