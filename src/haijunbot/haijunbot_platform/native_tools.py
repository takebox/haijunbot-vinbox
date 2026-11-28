# -*- coding: utf-8 -*-
"""Provider-neutral message model and tool schema utilities for native function calling.

This module defines a platform-neutral "canonical message" dict shared by the OpenAI and Juglow platforms:
- assistant with tool calls: ``{"role": "assistant", "content": <str|None>,
  "tool_calls": [{"id", "name", "arguments": <dict>}]}``
- tool result: ``{"role": "tool", "tool_call_id", "name", "content": <str>}``

Provides serialization to the OpenAI / Juglow message arrays, and the ``to_text``
flattening used by plain-text consumers such as compression, summary, and session recovery.
"""

import json
from typing import Any, Dict, List, Optional


def _sanitize_surrogates(text: str) -> str:
    """Replace lone UTF-16 surrogate characters with U+FFFD so text can be UTF-8 encoded.

    Background: message history may contain lone surrogate characters (U+D800-U+DFFF
    appearing alone, which is invalid Unicode). Common sources:
    - decoding invalid bytes with ``errors="surrogateescape"`` (the default Python
      filesystem encoding is ``utf-8/surrogateescape``);
    - the frontend JS ``JSON.stringify`` escaping lone surrogates as ``\\udXXX``, which
      Python ``json.loads`` restores into actual surrogate characters.

    ``json.dumps`` handles such characters fine, but when sending the request httpx runs
    ``json_dumps(..., ensure_ascii=False).encode("utf-8")``, which throws
    ``UnicodeEncodeError: surrogates not allowed``, causing native tool calls to fail and
    fall back to the plain-text protocol. Hence this cleanup is done uniformly at the serialization exit.

    Note: legal non-BMP characters in Python (e.g. ``😀`` U+1F600) are single code points,
    not in the surrogate range, and are naturally unaffected and passed through unchanged.
    """
    if not text:
        return text
    # Fast path: most text contains no surrogates, avoid a per-character scan
    if not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text
    return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text)


def _sanitize_value(value: Any) -> Any:
    """Recursively clean lone surrogate characters in arbitrarily nested structures, returning a new object (does not modify the input)."""
    if isinstance(value, str):
        return _sanitize_surrogates(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(v) for v in value)
    return value


def sanitize_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Clean lone surrogate characters in all string fields of a canonical message.

    Covers content, tool_calls name/arguments, tool_call_id, name, etc.
    Returns a new object; the input is not modified in place.
    """
    if not isinstance(msg, dict):
        return msg
    return {k: _sanitize_value(v) for k, v in msg.items()}


def make_tool_call_msg(
    content: Optional[str], tool_calls: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Construct a canonical assistant message with tool calls."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": list(tool_calls),
    }


def make_tool_call(
    call_id: str, name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Construct a single tool call item."""
    return {"id": call_id, "name": name, "arguments": dict(arguments)}


def make_tool_result_msg(tool_call_id: str, name: str, content: str) -> Dict[str, Any]:
    """Construct the tool result message (role=tool)."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }


def is_tool_call_msg(msg: Any) -> bool:
    return (
        isinstance(msg, dict)
        and msg.get("role") == "assistant"
        and bool(msg.get("tool_calls"))
    )


def is_tool_result_msg(msg: Any) -> bool:
    return isinstance(msg, dict) and msg.get("role") == "tool"


def msg_content_text(msg: Any) -> str:
    """Robustly extract the readable text of a message (handles str / content-block list / plain-text dict)."""
    if not isinstance(msg, dict):
        return str(msg) if msg is not None else ""
    content = msg.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: List[str] = []
    blocks = content if isinstance(content, list) else [content]
    for block in blocks:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type in (None, "text"):
                parts.append(block.get("text", ""))
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        else:
            parts.append(str(block))
    return "".join(parts)


def to_text(msg: Any) -> str:
    """Flatten any message (including native tool ones) into a single text, for compression/summary consumers."""
    if is_tool_result_msg(msg):
        return f"[tool {msg.get('name', '')} result]\n{msg.get('content') or ''}"
    if is_tool_call_msg(msg):
        text = msg_content_text(msg)
        for tc in msg.get("tool_calls") or []:
            args = tc.get("arguments")
            arg_str = (
                json.dumps(args, ensure_ascii=False)
                if isinstance(args, dict)
                else str(args)
            )
            text += f"\n[tool call {tc.get('name')} arguments: {arg_str}]"
        return text
    return msg_content_text(msg)


def ensure_tool_pairing(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean the canonical message history so tool_calls and role=tool responses stay properly paired.

    When history is truncated/compressed and breaks the pairing, OpenAI/Juglow returns 400
    (assistant tool_calls missing the matching tool message). This function:
    - drops assistant messages "with tool_calls but no matching tool response afterwards";
    - drops orphan tool results without a preceding matching tool_calls;
    - keeps properly paired messages.
    """
    out: List[Dict[str, Any]] = []
    pending_ids = set()
    open_idx: Optional[int] = None
    # Indexes in out of tool results already kept under the currently unclosed assistant(tool_calls).
    # If that assistant is deleted for incomplete pairing, these results must be deleted too,
    # otherwise orphan tool messages would remain and cause API 400.
    matched_result_idx: List[int] = []

    def _drop_open_assistant() -> None:
        """Delete the unclosed assistant(tool_calls) and its kept tool results."""
        nonlocal open_idx
        if open_idx is None:
            return
        # Delete higher indexes first to avoid index shifts after deletion
        for idx in sorted(matched_result_idx, reverse=True):
            del out[idx]
        del out[open_idx]
        open_idx = None
        matched_result_idx.clear()

    for msg in messages:
        if is_tool_call_msg(msg):
            _drop_open_assistant()
            ids = {(tc.get("id") or "") for tc in msg.get("tool_calls") or []}
            ids.discard("")
            if not ids:
                out.append(msg)
            else:
                out.append(msg)
                pending_ids = set(ids)
                open_idx = len(out) - 1
                matched_result_idx = []
        elif is_tool_result_msg(msg):
            tid = msg.get("tool_call_id") or ""
            if tid and tid in pending_ids:
                pending_ids.discard(tid)
                out.append(msg)
                matched_result_idx.append(len(out) - 1)
                if not pending_ids:
                    open_idx = None
                    matched_result_idx = []
            # Orphan tool result: drop it
        else:
            _drop_open_assistant()
            pending_ids = set()
            out.append(msg)

    _drop_open_assistant()
    return out


def to_openai_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Single canonical message -> OpenAI ChatCompletion message."""
    if is_tool_call_msg(msg):
        content = msg.get("content") or ""
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            args = tc.get("arguments")
            arg_str = (
                json.dumps(args, ensure_ascii=False)
                if isinstance(args, dict)
                else str(args)
            )
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": arg_str,
                    },
                }
            )
        return {"role": "assistant", "content": content, "tool_calls": tool_calls}
    if is_tool_result_msg(msg):
        return {
            "role": "tool",
            "tool_call_id": msg.get("tool_call_id", ""),
            "content": msg.get("content") or "",
        }
    out = dict(msg)
    if out.get("content") is None:
        out["content"] = ""
    return out


def to_openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Clean lone surrogate characters uniformly at the exit so httpx does not throw
    # UnicodeEncodeError when encoding the request body as UTF-8 (see _sanitize_surrogates).
    return [
        to_openai_message(sanitize_message(m)) for m in ensure_tool_pairing(messages)
    ]


def to_juglow_messages(
    messages: List[Dict[str, Any]],
) -> tuple[Optional[str], List[Dict[str, Any]]]:
    """Canonical message list -> (system_text, juglow message list).

    - system messages are concatenated into the top-level system text;
    - assistant tool calls become content blocks (text + tool_use);
    - consecutive role=tool results are merged into the tool_result content blocks of the following user message.

    Lone surrogate characters are cleaned uniformly at the exit so the Juglow SDK does not throw
    UnicodeEncodeError when encoding the request body as UTF-8 (see _sanitize_surrogates).
    """
    system_parts: List[str] = []
    out: List[Dict[str, Any]] = []
    pending_results: List[Dict[str, Any]] = []

    def flush_results() -> None:
        if not pending_results:
            return
        blocks = [
            {
                "type": "tool_result",
                "tool_use_id": r.get("tool_call_id", ""),
                "content": r.get("content") or "",
            }
            for r in pending_results
        ]
        pending_results.clear()
        # Tool results must be placed in a user message; merging into a previous plain-text user message would misalign content,
        # so always open a new user message containing only tool_result (allowed by Juglow).
        out.append({"role": "user", "content": blocks})

    for raw_msg in ensure_tool_pairing(messages):
        msg = sanitize_message(raw_msg)
        role = msg.get("role")
        if role == "system":
            system_parts.append(msg_content_text(msg))
            continue
        if is_tool_result_msg(msg):
            pending_results.append(msg)
            continue
        flush_results()
        if is_tool_call_msg(msg):
            blocks: List[Dict[str, Any]] = []
            text = msg_content_text(msg)
            if text:
                blocks.append({"type": "text", "text": text})
            for tc in msg.get("tool_calls") or []:
                args = tc.get("arguments")
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": args if isinstance(args, dict) else {},
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue
        content = msg.get("content")
        out.append({"role": role, "content": content if content is not None else ""})
    flush_results()
    return ("\n".join(system_parts) if system_parts else None, out)


# Timer/delay call parameters consistent with the text protocol: attachable to any tool parameter schema,
# so the model can declare after/at/loop natively.
_TIMER_PROPERTIES: Dict[str, Any] = {
    "after": {
        "type": "integer",
        "description": "Execute this tool after a delay of N seconds (use together with other arguments, not alone)",
    },
    "at": {
        "type": "string",
        "description": "Execute this tool at the given ISO8601 time point (use together with other arguments, not alone)",
    },
    "loop": {
        "type": "integer",
        "description": "Repeat this tool every N seconds (use together with other arguments, not alone)",
    },
}
_TIMER_KEYS = ("after", "at", "loop")


def with_timer_params(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Attach optional timer parameters to a tool parameter schema (unless the tool already defines parameters with the same names)."""
    if not isinstance(schema, dict):
        return schema
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema
    if any(key in properties for key in _TIMER_KEYS):
        return schema
    merged = dict(properties)
    merged.update(_TIMER_PROPERTIES)
    out = dict(schema)
    out["properties"] = merged
    return out


def ensure_object_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a tool parameter schema into a function-required object-typed JSON Schema.

    Many built-in/custom tools write only properties/required in parameters and lack a top-level type,
    which OpenAI/Juglow reject ("schema must be a JSON Schema of type object").
    Here the top-level type=object is added, and properties is guaranteed to exist.
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    out = dict(schema)
    if not out.get("type"):
        out["type"] = "object"
    if not isinstance(out.get("properties"), dict):
        out["properties"] = {}
    return out


# Tool parameter description truncation limit: overly long descriptions significantly bloat the tools input;
# after truncation the key semantics remain, so the model can still build correct parameters.
_TOOL_DESC_LIMIT = 200


def _compact_tool_schema(schema: Any, desc_limit: int = _TOOL_DESC_LIMIT) -> Any:
    """Compact a tool parameters schema to reduce the tokens injected into tools.

    Keeps the key constraints needed for tool calls (type/required/enum/properties/items),
    omits redundant fields that do not affect call correctness (default etc.), and truncates overly long descriptions.
    Recursively processes nested object/array. This compaction only reduces the "tool schema input
    given to the model on each call"; it does not change tool callability.

    Returns:
        The compacted schema dict. Non-dict inputs are returned unchanged.
    """
    if not isinstance(schema, dict):
        return schema
    out: Dict[str, Any] = {}
    if "type" in schema:
        out["type"] = schema["type"]
    if "description" in schema:
        desc = schema["description"]
        out["description"] = (
            desc if len(desc) <= desc_limit else desc[:desc_limit] + "..."
        )
    # required / enum are key constraints for tool call correctness and must be kept
    if "required" in schema:
        out["required"] = schema["required"]
    if "enum" in schema:
        out["enum"] = schema["enum"]
    if "properties" in schema and isinstance(schema["properties"], dict):
        out["properties"] = {
            k: _compact_tool_schema(v, desc_limit)
            for k, v in schema["properties"].items()
        }
    if "items" in schema:
        out["items"] = _compact_tool_schema(schema["items"], desc_limit)
    # Remaining fields (default/additionalProperties etc.) are omitted without affecting call correctness
    return out


def build_openai_tools(registry: Any) -> List[Dict[str, Any]]:
    """Build the OpenAI tools array from a ToolRegistry."""
    tools = []
    for tool in registry.tools.values():
        parameters = getattr(tool, "parameters", None) or {}
        parameters = with_timer_params(ensure_object_schema(parameters))
        parameters = _compact_tool_schema(parameters)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", "") or "",
                    "parameters": parameters,
                },
            }
        )
    return tools


def build_juglow_tools(registry: Any) -> List[Dict[str, Any]]:
    """Build the Juglow tools array from a ToolRegistry."""
    tools = []
    for tool in registry.tools.values():
        parameters = getattr(tool, "parameters", None) or {}
        parameters = with_timer_params(ensure_object_schema(parameters))
        parameters = _compact_tool_schema(parameters)
        tools.append(
            {
                "name": tool.name,
                "description": getattr(tool, "description", "") or "",
                "input_schema": parameters,
            }
        )
    return tools
