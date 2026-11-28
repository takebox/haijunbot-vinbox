# -*- coding: utf-8 -*-
"""Native tool calling "no longer degrades once support is confirmed" behavior tests (openai / haijun).

Core behavior:
- When a model has been confirmed to support native tool calling (_native_confirmed=True), native request failures must
  propagate upward and must not silently degrade to plain text protocol;
- Models without confirmed support maintain existing fault-tolerant behavior: when exceptions are swallowed by the
  rendering layer, an empty result is returned without raising an error.

Note: streaming exceptions are by default caught by the rendering pipeline (_chat_with_*_output) and return collected
content, so the degradation except branch of openai/haijun's chat_native_once is not triggered by default.
This test verifies via the raise_on_error chain that exceptions do propagate upward when "support is confirmed".
"""

import threading
from unittest.mock import MagicMock

import pytest

from haijunbot.haijunbot_platform.haijun import HaijunModel
from haijunbot.haijunbot_platform.openai import OpenAIModel

TOOLS = [{"name": "add", "description": "Sum", "input_schema": {"type": "object"}}]


def _make_openai_model():
    m = object.__new__(OpenAIModel)
    m.messages = []
    m._native_disabled = False
    m._native_confirmed = False
    m.api_keys = []
    m._api_key_index = 0
    m.model_name = "openai-test"
    m.agent = None
    m.suppress_output = True
    m._panel_lock = threading.RLock()
    m.temperature = None
    m.top_p = None
    m.max_tokens = None
    m.reasoning_effort = None
    m.extra_body = None
    m.client = MagicMock()
    return m


def _make_haijun_model():
    m = object.__new__(HaijunModel)
    m.messages = []
    m._native_disabled = False
    m._native_confirmed = False
    m.api_keys = []
    m._api_key_index = 0
    m.model_name = "haijun-test"
    m.agent = None
    m.suppress_output = True
    m._panel_lock = threading.RLock()
    m.client = MagicMock()
    return m


class _BoomStream:
    """Context manager: text_stream iteration raises immediately upon entry, simulating an endpoint that does not support tools."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        raise RuntimeError("tools unsupported")


def test_openai_confirmed_raises_instead_of_fallback(monkeypatch):
    m = _make_openai_model()
    m._native_confirmed = True
    fallback_called = []
    monkeypatch.setattr(
        OpenAIModel,
        "_native_fallback_text",
        lambda self, message, append_user: (
            fallback_called.append(True) or ("fallback", None)
        ),
    )
    m.client.chat.completions.create.side_effect = RuntimeError("tools unsupported")

    with pytest.raises(Exception):
        m.chat_native_once("hi", TOOLS)
    # No degradation: neither sets _native_disabled nor goes through text fallback
    assert m._native_disabled is False
    assert fallback_called == []


def test_openai_unconfirmed_does_not_raise(monkeypatch):
    """Models without confirmed support: failures do not propagate upward, but degrade to text protocol."""
    m = _make_openai_model()
    m._native_confirmed = False
    fallback_called = []
    monkeypatch.setattr(
        OpenAIModel,
        "_native_fallback_text",
        lambda self, message, append_user: (
            fallback_called.append(True) or ("fallback", None)
        ),
    )
    m.client.chat.completions.create.side_effect = RuntimeError("tools unsupported")

    content, calls = m.chat_native_once("hi", TOOLS)
    assert content == "fallback"
    assert calls is None
    assert fallback_called == [True]


def test_haijun_confirmed_raises_instead_of_fallback(monkeypatch):
    m = _make_haijun_model()
    m._native_confirmed = True
    fallback_called = []
    monkeypatch.setattr(
        HaijunModel,
        "_haijun_fallback_text",
        lambda self, message, append_user: (
            fallback_called.append(True) or ("fallback", None)
        ),
    )
    m.client.messages.stream.side_effect = lambda **kwargs: _BoomStream()

    with pytest.raises(Exception):
        m.chat_native_once("hi", TOOLS)
    assert m._native_disabled is False
    assert fallback_called == []


def test_haijun_unconfirmed_does_not_raise(monkeypatch):
    """Models without confirmed support: failures do not propagate upward (maintaining existing fault-tolerant behavior), degrade to text protocol."""
    m = _make_haijun_model()
    m._native_confirmed = False
    fallback_called = []
    monkeypatch.setattr(
        HaijunModel,
        "_haijun_fallback_text",
        lambda self, message, append_user: (
            fallback_called.append(True) or ("fallback", None)
        ),
    )
    m.client.messages.stream.side_effect = lambda **kwargs: _BoomStream()

    content, calls = m.chat_native_once("hi", TOOLS)
    assert content == "fallback"
    assert calls is None
    assert fallback_called == [True]


def test_raise_on_error_propagates_from_render_pipeline():
    """The rendering pipeline no longer swallows streaming exceptions when raise_on_error=True."""
    from haijunbot.haijunbot_utils.output import PrettyOutput

    def _boom():
        raise RuntimeError("stream boom")
        yield ("content", "x")  # pragma: no cover

    with pytest.raises(Exception):
        PrettyOutput.stream_chat_simple(
            chat_iterator=_boom(),
            prefix="Model output - test",
            start_time=0.0,
            raise_on_error=True,
        )
