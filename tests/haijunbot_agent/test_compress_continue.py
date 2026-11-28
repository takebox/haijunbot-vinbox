# -*- coding: utf-8 -*-
"""Tests for force-continue flag after full compression (issue #86)

Background: When a single tool call output is too long and triggers full compression (_summarize_and_clear_history),
session.prompt is cleared and the summary is placed in addon_prompt. If the model returns plain text without
tool calls in the next round, the main loop falls into _get_next_user_action waiting for user input, causing task interruption.

Fix: The full compression success path sets ag._force_continue_after_compress = True,
the main loop consumes this flag before _get_next_user_action and continues, allowing the Agent to keep executing.
"""

from unittest.mock import Mock

from haijunbot.haijunbot_agent.run_loop import AgentRunLoop


class _FakeSession:
    """Minimal Session stub: only exposes attributes needed for compression path"""

    def __init__(self):
        self.prompt = ""
        self.addon_prompt = ""


def _make_agent():
    """Construct a minimal agent mock covering check_and_compress_context full compression fallback path"""
    ag = Mock()
    ag.session = _FakeSession()
    # Pre-compressed state (compression path reads/writes)
    ag._pre_compressed_summary = None
    ag._pre_compress_snapshot_count = 0
    ag._pre_compressing = False
    # Compression flag (new in this fix)
    ag._force_continue_after_compress = False
    # Full compression: _adaptive_compression fails -> _summarize_and_clear_history returns summary
    ag._adaptive_compression = Mock(return_value=False)
    ag._summarize_and_clear_history = Mock(return_value="[Summary] Task reached stage X")
    return ag


def _make_model():
    """Construct a model mock that triggers token compression"""
    model = Mock()
    model.get_conversation_turn = Mock(return_value=10)
    model.get_remaining_token_count = Mock(return_value=100)
    model._get_platform_max_input_token_count = Mock(return_value=2000)
    return model


def test_full_compression_sets_force_continue_flag():
    """Full compression success path should set _force_continue_after_compress flag"""
    ag = _make_agent()
    loop = AgentRunLoop(ag)

    loop.check_and_compress_context(model_instance=_make_model())

    # Summary placed in addon_prompt, maintaining context continuity
    assert "[Summary]" in ag.session.addon_prompt
    # Key assertion: force-continue flag set after compression
    assert ag._force_continue_after_compress is True


def test_no_compression_keeps_flag_false():
    """Flag stays False when compression not triggered, does not affect interactive mode normal behavior"""
    ag = _make_agent()
    # Sufficient remaining tokens, no compression triggered
    model = Mock()
    model.get_conversation_turn = Mock(return_value=1)
    model.get_remaining_token_count = Mock(return_value=1900)
    model._get_platform_max_input_token_count = Mock(return_value=2000)
    loop = AgentRunLoop(ag)

    loop.check_and_compress_context(model_instance=model)

    assert ag._force_continue_after_compress is False
    assert ag._adaptive_compression.called is False


def test_adaptive_compression_success_keeps_flag_false():
    """Force-continue flag not set when adaptive compression succeeds (prompt not cleared, no need to force continue)"""
    ag = _make_agent()
    ag._adaptive_compression = Mock(return_value=True)
    loop = AgentRunLoop(ag)

    loop.check_and_compress_context(model_instance=_make_model())

    assert ag._force_continue_after_compress is False
    ag._summarize_and_clear_history.assert_not_called()
