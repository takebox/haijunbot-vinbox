# -*- coding: utf-8 -*-
"""native_tools message model and serialization unit tests"""

import json

from haijunbot.haijunbot_platform.native_tools import (
    _compact_tool_schema,
    _sanitize_surrogates,
    build_juglow_tools,
    build_openai_tools,
    make_tool_call,
    make_tool_call_msg,
    make_tool_result_msg,
    sanitize_message,
    to_juglow_messages,
    to_openai_messages,
    to_text,
)


class _FakeTool:
    def __init__(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters


class _FakeRegistry:
    def __init__(self, tools):
        self.tools = {t.name: t for t in tools}


def _sample_tool_call_msg():
    return make_tool_call_msg(
        "Let me check",
        [make_tool_call("call_1", "read_code", {"path": "a.py"})],
    )


class TestMessageModel:
    def test_to_text_tool_call(self):
        text = to_text(_sample_tool_call_msg())
        assert "Let me check" in text
        assert "read_code" in text
        assert "a.py" in text

    def test_to_text_tool_result(self):
        msg = make_tool_result_msg("call_1", "read_code", "OK content")
        text = to_text(msg)
        assert "read_code" in text and "OK content" in text

    def test_to_text_plain(self):
        assert to_text({"role": "user", "content": "hello"}) == "hello"
        assert to_text({"role": "assistant", "content": None}) == ""


class TestToolPairing:
    def _asst_tool_call(self, cid="c1", name="read_code"):
        return make_tool_call_msg(None, [make_tool_call(cid, name, {"path": "a.py"})])

    def test_drops_trailing_tool_calls_without_results(self):
        msgs = [
            {"role": "user", "content": "hi"},
            self._asst_tool_call(),
        ]
        out = to_openai_messages(msgs)
        # Trailing orphan tool_calls assistant is dropped to avoid pairing 400
        assert out == [{"role": "user", "content": "hi"}]

    def test_drops_orphan_tool_result(self):
        msgs = [
            {"role": "user", "content": "hi"},
            make_tool_result_msg("gone_id", "read_code", "x"),
        ]
        out = to_openai_messages(msgs)
        assert out == [{"role": "user", "content": "hi"}]

    def test_keeps_valid_pair(self):
        msgs = [
            {"role": "user", "content": "hi"},
            self._asst_tool_call(),
            make_tool_result_msg("c1", "read_code", "content"),
            {"role": "assistant", "content": "done"},
        ]
        out = to_openai_messages(msgs)
        assert len(out) == 4
        assert out[1]["tool_calls"][0]["id"] == "c1"
        assert out[2]["role"] == "tool"

    def test_drops_partial_multi_call_and_its_results(self):
        # Assistant initiates multiple tool_calls, only partial results returned before new message:
        # The entire group (assistant + returned tool results) should be dropped, no orphan tool messages should remain.
        msgs = [
            {"role": "user", "content": "hi"},
            make_tool_call_msg(
                None,
                [
                    make_tool_call("c1", "read_code", {"path": "a.py"}),
                    make_tool_call("c2", "read_code", {"path": "b.py"}),
                ],
            ),
            make_tool_result_msg("c1", "read_code", "content a"),
            {"role": "user", "content": "continue"},
        ]
        out = to_openai_messages(msgs)
        assert out == [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "continue"},
        ]

    def test_drops_partial_multi_call_at_end(self):
        # Trailing unclosed multi tool_calls: returned results should also be dropped
        msgs = [
            {"role": "user", "content": "hi"},
            make_tool_call_msg(
                None,
                [
                    make_tool_call("c1", "read_code", {"path": "a.py"}),
                    make_tool_call("c2", "read_code", {"path": "b.py"}),
                ],
            ),
            make_tool_result_msg("c1", "read_code", "content a"),
        ]
        out = to_openai_messages(msgs)
        assert out == [{"role": "user", "content": "hi"}]

    def test_juglow_drops_unpaired_tool_use(self):
        msgs = [
            {"role": "user", "content": "hi"},
            self._asst_tool_call(),
            {"role": "assistant", "content": "finished"},
        ]
        system, amsgs = to_juglow_messages(msgs)
        # Orphan tool_use assistant is dropped; only user and subsequent assistant text remain
        roles = [m["role"] for m in amsgs]
        assert roles == ["user", "assistant"]


class TestOpenAISerialization:
    def test_tool_call_and_result(self):
        history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            _sample_tool_call_msg(),
            make_tool_result_msg("call_1", "read_code", "result"),
        ]
        msgs = to_openai_messages(history)
        assert msgs[0] == {"role": "system", "content": "sys"}
        assert msgs[2]["role"] == "assistant"
        tc = msgs[2]["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "read_code"
        assert json.loads(tc["function"]["arguments"]) == {"path": "a.py"}
        assert msgs[3]["role"] == "tool"
        assert msgs[3]["tool_call_id"] == "call_1"
        assert msgs[3]["content"] == "result"


class TestJuglowSerialization:
    def test_system_extracted_and_tool_use_blocks(self):
        history = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hi"},
            make_tool_call_msg(
                "Let me check",
                [
                    make_tool_call("call_1", "read_code", {"path": "a.py"}),
                    make_tool_call("call_2", "search_web", {"q": "x"}),
                ],
            ),
            make_tool_result_msg("call_1", "read_code", "result A"),
            make_tool_result_msg("call_2", "search_web", "result B"),
            {"role": "assistant", "content": "done"},
        ]
        system, msgs = to_juglow_messages(history)
        assert system == "system prompt"
        assert all(m["role"] != "system" for m in msgs)
        tool_msg = msgs[1]
        assert tool_msg["role"] == "assistant"
        assert tool_msg["content"][0]["type"] == "text"
        assert tool_msg["content"][1] == {
            "type": "tool_use",
            "id": "call_1",
            "name": "read_code",
            "input": {"path": "a.py"},
        }
        # Two consecutive tool results are merged into two tool_result blocks of one user message
        user_tool = msgs[2]
        assert user_tool["role"] == "user"
        assert len(user_tool["content"]) == 2
        assert user_tool["content"][0]["type"] == "tool_result"
        assert user_tool["content"][0]["tool_use_id"] == "call_1"
        assert user_tool["content"][1]["tool_use_id"] == "call_2"
        assert msgs[3] == {"role": "assistant", "content": "done"}


class TestSchema:
    def test_build_openai_tools(self):
        reg = _FakeRegistry(
            [
                _FakeTool(
                    "read_code",
                    "Read file",
                    {"type": "object", "properties": {"path": {"type": "string"}}},
                )
            ]
        )
        tools = build_openai_tools(reg)
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "read_code"
        assert (
            tools[0]["function"]["parameters"]["properties"]["path"]["type"] == "string"
        )

    def test_build_juglow_tools(self):
        reg = _FakeRegistry(
            [
                _FakeTool(
                    "read_code",
                    "Read file",
                    {"type": "object", "properties": {"path": {"type": "string"}}},
                )
            ]
        )
        tools = build_juglow_tools(reg)
        assert tools[0]["name"] == "read_code"
        assert tools[0]["input_schema"]["properties"]["path"]["type"] == "string"

    def test_missing_top_level_type_normalized_to_object(self):
        reg = _FakeRegistry(
            [
                # Tools like read_code that only write properties/required, missing top-level type
                _FakeTool(
                    "read_code",
                    "Read file",
                    {
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                )
            ]
        )
        otools = build_openai_tools(reg)
        params = otools[0]["function"]["parameters"]
        assert params.get("type") == "object"
        assert params["properties"]["path"]["type"] == "string"

        atools = build_juglow_tools(reg)
        assert atools[0]["input_schema"].get("type") == "object"

    def test_empty_parameters_become_object_schema(self):
        reg = _FakeRegistry([_FakeTool("noop", "No parameters", {})])
        otools = build_openai_tools(reg)
        assert otools[0]["function"]["parameters"]["type"] == "object"

    def test_want_not_advertised_in_schema(self):
        reg = _FakeRegistry(
            [
                _FakeTool(
                    "read_code",
                    "Read file",
                    {"type": "object", "properties": {"path": {"type": "string"}}},
                )
            ]
        )
        otools = build_openai_tools(reg)
        props = otools[0]["function"]["parameters"]["properties"]
        assert "want" not in props
        assert "after" in props and "at" in props and "loop" in props
        atools = build_juglow_tools(reg)
        assert "want" not in atools[0]["input_schema"]["properties"]


class TestSurrogateSanitization:
    """Orphan UTF-16 surrogate character cleanup: prevents UnicodeEncodeError during UTF-8 encoding.

    Background: if orphan surrogates (like \\ud83d) are mixed into message history, the OpenAI/Juglow SDK
    serialized via httpx with ensure_ascii=False then .encode("utf-8") will raise
    UnicodeEncodeError: surrogates not allowed, causing native tool calls to degrade to plain text.
    """

    def test_sanitize_isolated_high_surrogate(self):
        assert _sanitize_surrogates("abc\ud83ddef") == "abc\ufffddef"

    def test_sanitize_isolated_low_surrogate(self):
        assert _sanitize_surrogates("x\udcffy") == "x\ufffdy"

    def test_sanitize_multiple_consecutive_surrogates(self):
        assert _sanitize_surrogates("\ud83d\udc4d") == "\ufffd\ufffd"

    def test_sanitize_no_surrogate_returns_same_object(self):
        text = "normal text \U0001f600"
        assert _sanitize_surrogates(text) is text

    def test_sanitize_keeps_valid_astral_chars(self):
        # U+1F600 is a valid code point, not in the surrogate range, must be preserved as-is
        assert _sanitize_surrogates("\U0001f600") == "\U0001f600"

    def test_sanitize_message_does_not_mutate_input(self):
        msg = {"role": "user", "content": "abc\ud83ddef"}
        out = sanitize_message(msg)
        assert out["content"] == "abc\ufffddef"
        assert msg["content"] == "abc\ud83ddef"

    def test_openai_user_content_encodable(self):
        msgs = to_openai_messages([{"role": "user", "content": "abc\ud83ddef"}])
        assert msgs[0]["content"] == "abc\ufffddef"
        json.dumps(msgs, ensure_ascii=False).encode("utf-8")

    def test_openai_tool_result_encodable(self):
        msgs = to_openai_messages(
            [
                {"role": "user", "content": "hi"},
                make_tool_call_msg(None, [make_tool_call("c1", "read_code", {})]),
                make_tool_result_msg("c1", "read_code", "x\udcffy"),
            ]
        )
        assert msgs[2]["content"] == "x\ufffdy"
        json.dumps(msgs, ensure_ascii=False).encode("utf-8")

    def test_openai_tool_call_arguments_encodable(self):
        msgs = to_openai_messages(
            [
                {"role": "user", "content": "hi"},
                make_tool_call_msg(
                    "check",
                    [make_tool_call("c1", "read_code", {"path": "a\ud83d.py"})],
                ),
                make_tool_result_msg("c1", "read_code", "ok"),
            ]
        )
        args = msgs[1]["tool_calls"][0]["function"]["arguments"]
        assert "\ud83d" not in args and "\ufffd" in args
        json.dumps(msgs, ensure_ascii=False).encode("utf-8")

    def test_juglow_path_encodable(self):
        history = [
            {"role": "system", "content": "system\ud83d prompt"},
            {"role": "user", "content": "abc\ud83ddef"},
            make_tool_call_msg(None, [make_tool_call("c1", "read_code", {})]),
            make_tool_result_msg("c1", "read_code", "x\udcffy"),
        ]
        system, msgs = to_juglow_messages(history)
        assert system == "system\ufffd prompt"
        assert msgs[0]["content"] == "abc\ufffddef"
        json.dumps({"system": system, "messages": msgs}, ensure_ascii=False).encode(
            "utf-8"
        )

    def test_normal_text_unchanged_regression(self):
        history = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "test \U0001f600 normal text"},
            make_tool_call_msg(
                None, [make_tool_call("c1", "read_code", {"p": "chinese"})]
            ),
            make_tool_result_msg("c1", "read_code", "result \U0001f600"),
        ]
        o_msgs = to_openai_messages(history)
        assert o_msgs[1]["content"] == "test \U0001f600 normal text"
        assert o_msgs[3]["content"] == "result \U0001f600"
        assert json.loads(o_msgs[2]["tool_calls"][0]["function"]["arguments"]) == {
            "p": "chinese"
        }
        system, a_msgs = to_juglow_messages(history)
        assert system == "system prompt"
        assert a_msgs[0]["content"] == "test \U0001f600 normal text"

    def test_timer_params_advertised_in_schema(self):
        reg = _FakeRegistry(
            [
                _FakeTool(
                    "read_code",
                    "Read file",
                    {"type": "object", "properties": {"path": {"type": "string"}}},
                )
            ]
        )
        otools = build_openai_tools(reg)
        props = otools[0]["function"]["parameters"]["properties"]
        assert "after" in props and "loop" in props and "at" in props

        atools = build_juglow_tools(reg)
        assert "after" in atools[0]["input_schema"]["properties"]


class TestCompactToolSchema:
    """Test _compact_tool_schema compaction function"""

    def test_keeps_required_type_enum(self):
        """Preserve key tool call constraints: type/required/enum"""
        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "cancel", "list"],
                    "description": "Operation type",
                }
            },
            "required": ["action"],
        }
        out = _compact_tool_schema(schema)
        assert out["type"] == "object"
        assert out["required"] == ["action"]
        assert out["properties"]["action"]["enum"] == ["add", "cancel", "list"]

    def test_omits_default(self):
        """Omit the default field which does not affect call correctness"""
        schema = {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "string",
                    "enum": ["low", "high", "auto"],
                    "default": "auto",
                    "description": "Precision",
                }
            },
        }
        out = _compact_tool_schema(schema)
        assert "default" not in out["properties"]["detail"]

    def test_truncates_long_description(self):
        """Overly long description is truncated"""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "x" * 500}},
        }
        out = _compact_tool_schema(schema, desc_limit=100)
        desc = out["properties"]["path"]["description"]
        assert len(desc) <= 104  # 100 + "..."
        assert desc.endswith("...")

    def test_keeps_short_description(self):
        """Short description is not truncated"""
        schema = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "file path"}},
        }
        out = _compact_tool_schema(schema)
        assert out["properties"]["path"]["description"] == "file path"

    def test_recursive_nested_object(self):
        """Nested object/array recursive compaction"""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "x" * 500,
                                "default": "",
                            }
                        },
                        "required": ["path"],
                    },
                }
            },
        }
        out = _compact_tool_schema(schema, desc_limit=50)
        inner = out["properties"]["items"]["items"]
        assert inner["required"] == ["path"]
        assert "default" not in inner["properties"]["path"]
        assert inner["properties"]["path"]["description"].endswith("...")

    def test_non_dict_returns_as_is(self):
        """Non-dict input is returned as-is"""
        assert _compact_tool_schema(None) is None
        assert _compact_tool_schema("str") == "str"

    def test_build_tools_applies_compact(self):
        """build_openai_tools/build_juglow_tools apply compaction"""
        reg = _FakeRegistry(
            [
                _FakeTool(
                    "demo",
                    "Demo tool",
                    {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["a", "b"],
                                "default": "a",
                                "description": "x" * 500,
                            }
                        },
                        "required": ["mode"],
                    },
                )
            ]
        )
        otools = build_openai_tools(reg)
        oparams = otools[0]["function"]["parameters"]
        assert oparams["required"] == ["mode"]
        assert "default" not in oparams["properties"]["mode"]
        assert oparams["properties"]["mode"]["enum"] == ["a", "b"]
        assert oparams["properties"]["mode"]["description"].endswith("...")

        atools = build_juglow_tools(reg)
        aparams = atools[0]["input_schema"]
        assert aparams["required"] == ["mode"]
        assert "default" not in aparams["properties"]["mode"]
