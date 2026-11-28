# -*- coding: utf-8 -*-
"""haijun native function calling unit tests (fake Juglow stream)"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from haijunbot.haijunbot_platform.haijun import HaijunModel

JUGLOW_TOOLS = [
    {"name": "add", "description": "Sum", "input_schema": {"type": "object"}}
]


def _make_model(stream):
    m = object.__new__(HaijunModel)
    m.messages = []
    m._native_disabled = False
    m.api_keys = []
    m._api_key_index = 0
    m.model_name = "haijun-test"
    m.agent = None
    # Instance attributes required by the rendering pipeline (defined in BasePlatform.__init__, need to be supplemented after object.__new__ bypass)
    m.suppress_output = False
    m._panel_lock = threading.RLock()
    m.client = MagicMock()
    m.client.messages.stream.return_value = stream
    return m


def _text_stream(text_parts, content_blocks, stop_reason="end_turn"):
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = text_parts
    final = SimpleNamespace(stop_reason=stop_reason, content=content_blocks)
    stream.get_final_message.return_value = final
    return stream


def _tool_use_block(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def test_chat_native_once_tool_use():
    stream = _text_stream(
        ["Let me calculate"],
        [_tool_use_block("tu_1", "add", {"a": 1, "b": 2})],
        stop_reason="tool_use",
    )
    m = _make_model(stream)
    content, calls = m.chat_native_once("Please calculate 1+2", JUGLOW_TOOLS)
    assert content == "Let me calculate"
    assert calls == [{"id": "tu_1", "name": "add", "arguments": {"a": 1, "b": 2}}]
    # History: user + assistant(tool_calls)
    assert [msg["role"] for msg in m.messages] == ["user", "assistant"]
    assert m.messages[1].get("tool_calls") == calls
    # Request indeed carried tools and system processing
    kwargs = m.client.messages.stream.call_args.kwargs
    assert kwargs["tools"] == JUGLOW_TOOLS


def test_tool_round_without_new_user_message():
    # First simulate the previous round already produced assistant(tool_use)
    m = object.__new__(HaijunModel)
    m.messages = []
    m._native_disabled = False
    m.api_keys = []
    m._api_key_index = 0
    m.model_name = "haijun-test"
    m.agent = None
    m.suppress_output = False
    m._panel_lock = threading.RLock()
    stream = _text_stream(
        [],
        [_tool_use_block("tu_1", "add", {"a": 1, "b": 2})],
        stop_reason="tool_use",
    )
    m.client = MagicMock()
    m.client.messages.stream.return_value = stream
    _, calls = m.chat_native_once("Calculate", JUGLOW_TOOLS)
    # Write back tool result
    m.append_native_tool_result("tu_1", "add", "3")

    stream2 = _text_stream(["The result is 3"], [])
    m.client.messages.stream.return_value = stream2
    content, calls2 = m.chat_native_once(None, JUGLOW_TOOLS, append_user=False)
    assert content == "The result is 3"
    assert calls2 is None
    # No additional user message
    assert m.messages[-1]["role"] == "assistant"
    assert sum(1 for msg in m.messages if msg["role"] == "user") == 1


def test_sampling_overrides_reach_stream_kwargs():
    stream = _text_stream(
        ["OK"],
        [_tool_use_block("tu_1", "add", {"a": 1, "b": 2})],
        stop_reason="tool_use",
    )
    m = _make_model(stream)
    m.max_tokens = 4096
    m.temperature = 0.7
    m.chat_native_once("Calculate", JUGLOW_TOOLS)
    kwargs = m.client.messages.stream.call_args.kwargs
    assert kwargs["max_tokens"] == 4096
    assert kwargs["temperature"] == 0.7
