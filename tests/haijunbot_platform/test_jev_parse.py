# -*- coding: utf-8 -*-
"""JevPlatform input parsing and truncation unit tests.

Covers two types of issues:
1. When messages are too long, the base class's generic truncation hard-cuts by character and appends a bare newline,
   producing invalid JSON ("Invalid control character" / "Unterminated string"). JevPlatform overrides
   _truncate_message_if_needed to do JSON structured truncation, ensuring the result is still valid JSON.
2. parse_state_and_questions tolerance for bare control characters (strict=False).
"""

import json
from unittest.mock import patch

import pytest

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.jev import JevPlatform


def _make_platform():
    """Construct a non-networked JevPlatform instance (only for calling pure logic methods)."""
    p = JevPlatform.__new__(JevPlatform)
    p.platform_type = "eval"
    p.messages = []
    p.suppress_output = True
    p._llm_config = {}
    return p


def _big_payload(state_len: int = 2000) -> str:
    return json.dumps(
        {
            "state": "Task description: " + ("x" * state_len),
            "questions": {"q1": {"type": "noul", "instructions": "Is it relevant?"}},
        },
        ensure_ascii=False,
    )


# --------------------------------------------------------------------------
# Truncation: before fix, base class produced invalid JSON; after fix, JEV produces valid JSON
# --------------------------------------------------------------------------


def test_base_truncation_breaks_json():
    """Document that base class truncation breaks JSON (regression guard: explains why override is needed)."""
    raw = _big_payload()
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=300),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=10000
        ),
    ):
        broken = BasePlatform._truncate_message_if_needed(p, raw)

    with pytest.raises(Exception):
        json.loads(broken)


def test_jev_truncation_keeps_valid_json():
    raw = _big_payload()
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=300),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=10000
        ),
    ):
        truncated = JevPlatform._truncate_message_if_needed(p, raw)

    # Truncation result must be valid JSON, and questions must be fully preserved
    payload = json.loads(truncated)
    assert "q1" in payload["questions"]
    assert "truncated" in payload["state"]
    assert len(truncated) < len(raw)


def test_jev_truncation_result_parses():
    """End-to-end: truncation result can be directly consumed by parse_state_and_questions."""
    raw = _big_payload()
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=300),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=10000
        ),
    ):
        truncated = JevPlatform._truncate_message_if_needed(p, raw)

    state, questions = JevPlatform.parse_state_and_questions(truncated)
    assert "q1" in questions
    assert state.endswith("truncated to stay within the context limit)")


def test_jev_truncation_noop_when_fits():
    """Return as-is when message is not over the limit, do not make any modifications."""
    raw = _big_payload(state_len=10)
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=100000),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=100000
        ),
    ):
        assert JevPlatform._truncate_message_if_needed(p, raw) == raw


def test_jev_truncation_keeps_non_string_state():
    """Do not truncate when state is not a string (e.g. an object), to avoid breaking the structure."""
    raw = json.dumps(
        {
            "state": {"nested": "x" * 2000},
            "questions": {"q1": {"type": "noul", "instructions": "Is it relevant?"}},
        },
        ensure_ascii=False,
    )
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=300),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=10000
        ),
    ):
        assert JevPlatform._truncate_message_if_needed(p, raw) == raw


def test_jev_truncation_keeps_invalid_json_as_is():
    """Do not modify when input is not valid JSON, leave it for the upper layer to handle."""
    raw = "This is not JSON" + "x" * 5000
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=300),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=10000
        ),
    ):
        assert JevPlatform._truncate_message_if_needed(p, raw) == raw


# --------------------------------------------------------------------------
# Insufficient remaining tokens: must first try to trim history, never return an empty string
# --------------------------------------------------------------------------


def test_truncation_trims_history_when_no_remaining_tokens():
    """When remaining tokens is 0, first trim history; after successful trimming, return the original message normally.

    Regression guard: previously, due to missing the base class's trimming branch, an empty string was returned
    when remaining<=0, causing the upper layer's json.loads("") to report
    "Expecting value: line 1 column 1 (char 0)".
    """
    raw = _big_payload(state_len=10)
    p = _make_platform()
    # First query returns 0 (triggering trim), after trimming, re-query returns sufficient quota
    with (
        patch.object(JevPlatform, "get_remaining_token_count", side_effect=[0, 100000]),
        patch.object(JevPlatform, "trim_messages", return_value=True) as mock_trim,
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=100000
        ),
    ):
        out = JevPlatform._truncate_message_if_needed(p, raw)

    mock_trim.assert_called_once()
    assert out == raw
    assert json.loads(out)["state"]  # Still valid JSON


def test_truncation_never_returns_empty_string_when_trim_fails():
    """When trimming fails and there are no remaining tokens, return the original message, not an empty string."""
    raw = _big_payload(state_len=10)
    p = _make_platform()
    with (
        patch.object(JevPlatform, "get_remaining_token_count", return_value=0),
        patch.object(JevPlatform, "trim_messages", return_value=False),
        patch.object(
            JevPlatform, "_get_platform_max_input_token_count", return_value=100000
        ),
    ):
        out = JevPlatform._truncate_message_if_needed(p, raw)

    # Key: must not be an empty string, otherwise the upper layer's parse reports "Expecting value ... char 0"
    assert out != ""
    assert out == raw
    # And must be parseable normally, without raising ValueError
    state, questions = JevPlatform.parse_state_and_questions(out)
    assert "q1" in questions


# --------------------------------------------------------------------------
# Parsing: bare control character tolerance
# --------------------------------------------------------------------------


def test_parse_accepts_raw_newline_in_string():
    payload = {
        "state": "Task description: first line\nsecond line",
        "questions": {"q1": {"type": "noul", "instructions": "Is it relevant?"}},
    }
    raw = json.dumps(payload, ensure_ascii=False).replace("\\n", "\n")

    # Default strict=True should reject
    with pytest.raises(Exception):
        json.loads(raw)

    state, questions = JevPlatform.parse_state_and_questions(raw)
    assert "first line" in state and "second line" in state
    assert "q1" in questions


def test_parse_accepts_raw_tab_in_string():
    payload = {
        "state": "Task description: A\tB",
        "questions": {"q1": {"type": "noul", "instructions": "Is it relevant?"}},
    }
    raw = json.dumps(payload, ensure_ascii=False).replace("\\t", "\t")

    state, questions = JevPlatform.parse_state_and_questions(raw)
    assert "\t" in state
    assert "q1" in questions


def test_parse_invalid_json_raises_value_error():
    with pytest.raises(ValueError) as exc:
        JevPlatform.parse_state_and_questions("This is not JSON")
    assert "JSON" in str(exc.value)


def test_parse_missing_state_raises():
    with pytest.raises(ValueError) as exc:
        JevPlatform.parse_state_and_questions('{"questions": {}}')
    assert "state" in str(exc.value)


def test_parse_accepts_dict_input():
    state, questions = JevPlatform.parse_state_and_questions(
        {
            "state": "Content",
            "questions": {"q1": {"type": "noul", "instructions": "Is it relevant?"}},
        }
    )
    assert state == "Content"
    assert "q1" in questions
