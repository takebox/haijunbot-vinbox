# -*- coding: utf-8 -*-
"""History summary/compression responsibility cluster tests

Covers methods in the Agent class for the "history summary/compression" responsibility cluster:
- _validate_summary
- generate_summary
- _print_compression_summary
- _sliding_window_compression (edge case supplement)
- _check_and_use_pre_compressed_summary
- _format_compressed_summary
- _adaptive_compression
- _summarize_and_clear_history
- _format_summary_message

Test pattern follows tests/haijunbot_agent/test_sliding_window_compression.py:
Use Mock to construct agent, then bind real methods to avoid complex initialization.
"""

from unittest.mock import Mock

import pytest

from haijunbot.haijunbot_agent import Agent as RealAgent


def _bind(agent, method_name):
    """Bind real method from RealAgent to mock agent object

    After refactoring, real methods delegate to self._history_compressor, so when binding real methods
    this attribute must be completed; only inject when truly needed, to avoid Mock's auto-attributes masking
    ``self.agent.xxx`` delegation calls (otherwise .called assertions are invalid).
    """
    from haijunbot.haijunbot_agent.history_compressor import HistoryCompressor

    # Real method body delegates to self._history_compressor internally, must ensure it exists before binding
    agent._history_compressor = HistoryCompressor(agent)
    setattr(
        agent,
        method_name,
        getattr(RealAgent, method_name).__get__(agent, Mock),
    )
    return agent


def _make_agent(**attrs):
    """Create a Mock agent with required attributes set"""
    ag = Mock()
    # Pre-compression state related (most methods read/write)
    ag._pre_compressed_summary = None
    ag._pre_compress_snapshot_count = 0
    ag._pre_compressing = False
    ag.pin_content = ""
    ag.recent_memories = []
    # Mock() auto-generates any attribute (and truthy), explicitly set to None here
    # to avoid hasattr(self, "start_commit") always being True causing test invalidation
    ag.start_commit = None
    ag.summary_prompt = ""
    for k, v in attrs.items():
        setattr(ag, k, v)
    return ag


class TestValidateSummary:
    """_validate_summary basic length validation"""

    @pytest.fixture
    def agent(self):
        return _bind(_make_agent(), "_validate_summary")

    def test_empty_summary(self, agent):
        """Empty string fails validation"""
        ok, problems = agent._validate_summary("")
        assert ok is False
        assert problems == ["Summary content is empty"]

    def test_too_short_summary(self, agent):
        """Less than 20 characters after strip fails validation"""
        ok, problems = agent._validate_summary("abc")
        assert ok is False
        assert problems == ["Summary content is too short"]

    def test_whitespace_only_summary(self, agent):
        """Pure whitespace is empty after strip, fails validation"""
        ok, problems = agent._validate_summary("        ")
        assert ok is False
        # Non-empty string but strip length < 20
        assert problems == ["Summary content is too short"]

    def test_exactly_twenty_chars(self, agent):
        """Exactly 20 characters passes validation"""
        summary = "a" * 20
        ok, problems = agent._validate_summary(summary)
        assert ok is True
        assert problems == []

    def test_nineteen_chars_fails(self, agent):
        """19 characters fails validation (boundary)"""
        ok, problems = agent._validate_summary("a" * 19)
        assert ok is False
        assert problems == ["Summary content is too short"]

    def test_normal_long_summary(self, agent):
        """Normal long text passes validation"""
        ok, problems = agent._validate_summary(
            "This is a sufficiently long normal summary content for testing validation logic."
        )
        assert ok is True
        assert problems == []


class TestGenerateSummary:
    """generate_summary generates summary"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.summary_prompt = ""
        ag.model = Mock()
        ag.model.model_name = "test-model"
        ag.model.chat_until_success = Mock(return_value="a" * 50)
        ag.session = Mock()
        ag.session.prompt = "Session prompt"
        _bind(ag, "generate_summary")
        return ag

    def test_for_token_limit_returns_summary(self, agent):
        """for_token_limit=True returns summary normally"""
        result = agent.generate_summary(for_token_limit=True)
        assert result == "a" * 50
        assert agent.model.chat_until_success.call_count == 1

    def test_token_limit_prompt_contains_session_prompt(self, agent):
        """for_token_limit=True prompt contains session.prompt and SUMMARY_REQUEST_PROMPT"""
        agent.generate_summary(for_token_limit=True)
        used_prompt = agent.model.chat_until_success.call_args[0][0]
        assert "Session prompt" in used_prompt

    def test_for_token_limit_with_list_prompt(self, agent):
        """When session.prompt is multimodal list, only text parts are extracted"""
        agent.session.prompt = [
            {"type": "text", "text": "Text A"},
            {"type": "image", "url": "http://x"},
            {"type": "text", "text": "Text B"},
        ]
        agent.generate_summary(for_token_limit=True)
        used_prompt = agent.model.chat_until_success.call_args[0][0]
        assert "Text A" in used_prompt
        assert "Text B" in used_prompt

    def test_task_complete_uses_summary_prompt(self, agent):
        """for_token_limit=False uses custom summary_prompt"""
        agent.summary_prompt = "Custom summary prompt content"
        agent.generate_summary(for_token_limit=False)
        used_prompt = agent.model.chat_until_success.call_args[0][0]
        assert used_prompt == "Custom summary prompt content"

    def test_task_complete_default_prompt_when_empty(self, agent):
        """Uses DEFAULT_SUMMARY_PROMPT when summary_prompt is empty"""
        from haijunbot.haijunbot_agent import DEFAULT_SUMMARY_PROMPT

        agent.summary_prompt = ""
        agent.generate_summary(for_token_limit=False)
        used_prompt = agent.model.chat_until_success.call_args[0][0]
        assert used_prompt == DEFAULT_SUMMARY_PROMPT

    def test_empty_response_returns_empty(self, agent):
        """Returns empty string and does not retry when model returns empty response"""
        agent.model.chat_until_success = Mock(return_value="")
        result = agent.generate_summary(for_token_limit=True)
        assert result == ""
        assert agent.model.chat_until_success.call_count == 1

    def test_model_none_returns_empty(self, agent):
        """Exception is caught when model is None, returns empty string"""
        agent.model = None
        result = agent.generate_summary(for_token_limit=False)
        assert result == ""

    def test_start_commit_hint_appended(self, agent):
        """When start_commit exists, prompt appends start_commit hint"""
        agent.start_commit = "abc123"
        agent.generate_summary(for_token_limit=False)
        used_prompt = agent.model.chat_until_success.call_args[0][0]
        assert "abc123" in used_prompt
        assert "<start_commit_context>" in used_prompt


class TestPrintCompressionSummary:
    """_print_compression_summary prints compression summary"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.model = Mock()
        ag.model.model_name = "test-model"
        _bind(ag, "_print_compression_summary")
        return ag

    def test_calls_print_markdown(self, agent, monkeypatch):
        """Normal path calls PrettyOutput.print_markdown"""
        import haijunbot.haijunbot_agent as mod

        called = {}
        monkeypatch.setattr(
            mod.PrettyOutput,
            "print_markdown",
            lambda *a, **k: called.setdefault("md", (a, k)),
        )
        agent._print_compression_summary("Summary content", "Sliding window compression")
        assert "md" in called
        # Title should include compression type
        assert "Sliding window compression" in called["md"][1]["title"]

    def test_fallback_on_error(self, agent, monkeypatch):
        """Falls back to auto_print when print_markdown raises exception"""
        import haijunbot.haijunbot_agent as mod

        def _raise(*a, **k):
            raise RuntimeError("boom")

        printed = []
        monkeypatch.setattr(mod.PrettyOutput, "print_markdown", _raise)
        monkeypatch.setattr(
            mod.PrettyOutput, "auto_print", lambda *a, **k: printed.append(a)
        )
        agent._print_compression_summary("Summary content", "Sliding window compression")
        assert len(printed) == 1
        assert "Sliding window compression" in printed[0][0]


class TestSlidingWindowCompressionEdge:
    """_sliding_window_compression edge case supplement (basic path already in test_sliding_window_compression.py)"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.model = Mock()
        _bind(ag, "_sliding_window_compression")
        _bind(ag, "_validate_summary")
        return ag

    def test_empty_history_returns_false(self, agent):
        """Empty history returns False"""
        agent.model.get_messages = Mock(return_value=[])
        assert agent._sliding_window_compression(window_size=5) is False

    def test_all_system_messages_returns_false(self, agent):
        """Returns False when all messages are system messages"""
        agent.model.get_messages = Mock(
            return_value=[
                {"role": "system", "content": "s1"},
                {"role": "system", "content": "s2"},
            ]
        )
        assert agent._sliding_window_compression(window_size=5) is False

    def test_insufficient_messages_returns_false(self, agent):
        """Returns False when non-system messages are less than window_size"""
        agent.model.get_messages = Mock(
            return_value=[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
            ]
        )
        assert agent._sliding_window_compression(window_size=5) is False

    def test_model_without_set_messages_returns_false(self, agent):
        """Returns False when model has no set_messages method"""
        # Construct enough messages to pass preconditions
        msgs = [{"role": "system", "content": "s"}]
        for i in range(12):
            msgs.append({"role": "user", "content": f"u{i}"})
            msgs.append({"role": "assistant", "content": f"a{i}"})
        agent.model.get_messages = Mock(return_value=msgs)
        # Use a Mock without set_messages as temp_model
        temp_model = Mock(spec=["chat_until_success"])
        temp_model.chat_until_success = Mock(return_value="a" * 50)
        agent._create_temp_model = Mock(return_value=temp_model)
        agent._format_compressed_summary = Mock(side_effect=lambda x: x)
        agent._print_compression_summary = Mock()
        # model itself also has no set_messages
        del agent.model.set_messages
        assert agent._sliding_window_compression(window_size=5) is False


class TestCheckAndUsePreCompressedSummary:
    """_check_and_use_pre_compressed_summary uses pre-compressed summary"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.model = Mock()
        _bind(ag, "_check_and_use_pre_compressed_summary")
        return ag

    def test_hit_uses_summary_and_clears_state(self, agent):
        """Hit: has pre-compressed summary and model supports set_messages, returns True and state is cleared"""
        agent._pre_compressed_summary = "[History Summary] Pre-compressed content"
        agent._pre_compress_snapshot_count = 5
        agent.model.get_messages = Mock(
            return_value=[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
            ]
        )
        result = agent._check_and_use_pre_compressed_summary()
        assert result is True
        assert agent.model.set_messages.called
        # State cleared
        assert agent._pre_compressed_summary is None
        assert agent._pre_compress_snapshot_count == 0
        assert agent._pre_compressing is False
        # Rebuilt history contains system message + compressed summary
        new_history = agent.model.set_messages.call_args[0][0]
        assert new_history[0]["role"] == "system"
        assert new_history[1]["content"] == "[History Summary] Pre-compressed content"

    def test_miss_returns_false_and_clears_state(self, agent):
        """Miss: no pre-compressed summary, returns False and state is cleared"""
        agent._pre_compressed_summary = None
        agent._pre_compress_snapshot_count = 3
        result = agent._check_and_use_pre_compressed_summary()
        assert result is False
        assert agent._pre_compressed_summary is None
        assert agent._pre_compress_snapshot_count == 0
        assert agent._pre_compressing is False

    def test_hit_but_no_set_messages_returns_false(self, agent):
        """Hit but model does not support set_messages, returns False and state cleared"""
        agent._pre_compressed_summary = "[History Summary] Content"
        agent.model.get_messages = Mock(
            return_value=[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u1"},
            ]
        )
        agent.model = Mock(spec=["get_messages"])
        agent.model.get_messages = Mock(
            return_value=[
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u1"},
            ]
        )
        result = agent._check_and_use_pre_compressed_summary()
        assert result is False
        assert agent._pre_compressed_summary is None


class TestAdaptiveCompression:
    """_adaptive_compression branch selection

    After refactoring, _adaptive_compression implementation is in HistoryCompressor, Agent side only
    delegates. Real implementation internally calls Agent's same-named delegate method via ``self.agent.xxx``
    (maintaining externally overridable semantics), so here we mock Agent's delegate method.
    """

    @pytest.fixture
    def agent(self):
        from haijunbot.haijunbot_agent.history_compressor import HistoryCompressor

        ag = _make_agent()
        hc = HistoryCompressor(ag)
        # Bind real implementation to hc instance, simulating actual execution after Agent-side delegation
        hc.adaptive_compression = HistoryCompressor.adaptive_compression.__get__(
            hc, Mock
        )
        ag._history_compressor = hc
        return ag

    def test_uses_pre_compressed_when_hit(self, agent):
        """When pre-compression hits, takes True branch, does not call sliding window"""
        agent._check_and_use_pre_compressed_summary = Mock(return_value=True)
        agent._sliding_window_compression = Mock(return_value=True)
        result = agent._history_compressor.adaptive_compression()
        assert result is True
        assert agent._check_and_use_pre_compressed_summary.called
        assert not agent._sliding_window_compression.called

    def test_fallback_to_sliding_window(self, agent):
        """Falls back to sliding window compression on miss"""
        agent._check_and_use_pre_compressed_summary = Mock(return_value=False)
        agent._sliding_window_compression = Mock(return_value=True)
        result = agent._history_compressor.adaptive_compression()
        assert result is True
        assert agent._sliding_window_compression.called
        # Clear pre-compressed state before fallback
        assert agent._pre_compressed_summary is None
        assert agent._pre_compressing is False

    def test_exception_returns_false(self, agent):
        """Returns False on exception and clears state"""
        agent._check_and_use_pre_compressed_summary = Mock(
            side_effect=RuntimeError("boom")
        )
        result = agent._history_compressor.adaptive_compression()
        assert result is False
        assert agent._pre_compressed_summary is None


class TestSummarizeAndClearHistory:
    """_summarize_and_clear_history sets trigger reason and delegates"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        _bind(ag, "_summarize_and_clear_history")
        return ag

    def test_sets_trigger_reason_and_returns(self, agent):
        """trigger_reason is saved and return value comes from _handle_history_with_summary"""
        agent._history_compressor.handle_history_with_summary = Mock(
            return_value="Result summary"
        )
        result = agent._summarize_and_clear_history(trigger_reason="Manual trigger")
        assert result == "Result summary"
        assert agent._history_compressor._summary_trigger_reason == "Manual trigger"

    def test_default_trigger_reason(self, agent):
        """Default trigger_reason is "Token limit triggered" """
        agent._history_compressor.handle_history_with_summary = Mock(return_value="x")
        agent._summarize_and_clear_history()
        assert agent._history_compressor._summary_trigger_reason == "Token limit triggered"


class TestFormatSummaryMessage:
    """_format_summary_message formats summary message"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.rules_manager = Mock()
        ag.rules_manager.loaded_rules = set()
        ag._get_task_list_info = Mock(return_value="")
        _bind(ag, "_format_summary_message")
        return ag

    def test_contains_summary_title(self, agent):
        """Return content includes summary title and summary body"""
        result = agent._format_summary_message("This is summary body content")
        assert "The following is a summary of key points extracted from the previous conversation" in result
        assert "This is summary body content" in result

    def test_contains_initial_commit_when_present(self, agent):
        """Includes initial commit hint when start_commit exists"""
        agent.start_commit = "deadbeef"
        result = agent._format_summary_message("Summary")
        assert "Initial Git Commit" in result
        assert "deadbeef" in result

    def test_no_commit_section_when_absent(self, agent):
        """Does not include initial commit hint when start_commit is absent"""
        # Do not set start_commit attribute
        result = agent._format_summary_message("Summary")
        assert "Initial Git Commit" not in result

    def test_task_list_info_appended(self, agent):
        """Task list info is appended to end of message"""
        agent._get_task_list_info = Mock(return_value="## Task list status")
        result = agent._format_summary_message("Summary")
        assert "## Task list status" in result


class TestFormatCompressedSummary:
    """_format_compressed_summary formats compressed summary"""

    @pytest.fixture
    def agent(self):
        ag = _make_agent()
        ag.task_list_manager = Mock()
        ag.task_list_manager.task_lists = {}
        _bind(ag, "_format_compressed_summary")
        return ag

    def test_prefix(self, agent):
        """Prefix is [History Summary]"""
        result = agent._format_compressed_summary("Compressed content")
        assert result.startswith("[History Summary] Compressed content")

    def test_pin_content_injected(self, agent):
        """Injects user pinned content when pin_content is non-empty"""
        agent.pin_content = "Pinned content ABC"
        result = agent._format_compressed_summary("Compressed content")
        assert "The user's original needs and requirements" in result
        assert "Pinned content ABC" in result

    def test_recent_memories_injected(self, agent):
        """Injects recent memories when recent_memories is non-empty"""
        agent.recent_memories = ["Memory 1", "Memory 2"]
        result = agent._format_compressed_summary("Compressed content")
        assert "Recent memories" in result
        assert "Memory 1" in result
        assert "Memory 2" in result

    def test_start_commit_injected(self, agent):
        """Injects initial commit hint when start_commit is non-empty"""
        agent.start_commit = "cafe1234"
        result = agent._format_compressed_summary("Compressed content")
        assert "Initial Git Commit" in result
        assert "cafe1234" in result

    def test_no_extra_sections_when_empty(self, agent):
        """Only returns prefix + content when no extra info"""
        result = agent._format_compressed_summary("Compressed content")
        assert "The user's original needs and requirements" not in result
        assert "Recent memories" not in result
        assert "Initial Git Commit" not in result
