# -*- coding: utf-8 -*-
"""openai native tool calling: streaming tool_calls accumulation/parsing unit tests"""

from types import SimpleNamespace

from haijunbot.haijunbot_platform.openai import PARSE_ERROR_KEY, _accumulate_openai_stream


def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content)
    delta.tool_calls = tool_calls
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_call(index, id_, name=None, arguments=None):
    fn = None
    if name is not None or arguments is not None:
        fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id_, function=fn)


def test_content_only_stream():
    stream = [_chunk("you"), _chunk("are"), _chunk("。")]
    content, calls = _accumulate_openai_stream(stream)
    assert content == "youare。"
    assert calls is None


def test_tool_calls_split_arguments_merged():
    # Concatenation of argument fragments at the same index
    stream = [
        _chunk(tool_calls=[_tool_call(0, "call_x", "add", '{"a": ')]),
        _chunk(tool_calls=[_tool_call(0, None, None, "17, ")]),
        _chunk(tool_calls=[_tool_call(0, None, None, '"b": 25}')]),
    ]
    content, calls = _accumulate_openai_stream(stream)
    assert content is None
    assert len(calls) == 1
    assert calls[0]["id"] == "call_x"
    assert calls[0]["name"] == "add"
    assert calls[0]["arguments"] == {"a": 17, "b": 25}


def test_multiple_parallel_tool_calls():
    stream = [
        _chunk(
            tool_calls=[
                _tool_call(0, "id_1", "read_code", '{"path": "a.py"}'),
                _tool_call(1, "id_2", "search_web", '{"q": "x"}'),
            ]
        )
    ]
    content, calls = _accumulate_openai_stream(stream)
    assert calls[0]["name"] == "read_code"
    assert calls[1]["name"] == "search_web"
    assert calls[0]["arguments"] == {"path": "a.py"}


def test_malformed_arguments_not_crash():
    stream = [_chunk(tool_calls=[_tool_call(0, "id", "t", "{not json}")])]
    content, calls = _accumulate_openai_stream(stream)
    # Invalid JSON is preserved as-is, for the tool layer to give a self-correctable hint
    assert calls[0]["arguments"] == {PARSE_ERROR_KEY: "{not json}"}


def test_truncated_arguments_preserved_for_tool_layer():
    # Simulate streaming fragments being truncated (e.g. edit_file's large arguments hitting output limit)
    truncated = '{"files": [{"file_path": "/home/skyfire/code/Ja'
    stream = [_chunk(tool_calls=[_tool_call(0, "id", "edit_file", truncated)])]
    content, calls = _accumulate_openai_stream(stream)
    assert calls[0]["arguments"] == {PARSE_ERROR_KEY: truncated}


def test_raw_arguments_not_special_cased():
    # raw_arguments is no longer special-cased: it is just a normal parameter name, passed through as-is
    import json

    inner = json.dumps({"files": [{"file_path": "a.py"}]})
    wrapped = json.dumps({"raw_arguments": inner})
    stream = [_chunk(tool_calls=[_tool_call(0, "id", "edit_file", wrapped)])]
    content, calls = _accumulate_openai_stream(stream)
    assert calls[0]["arguments"] == {"raw_arguments": inner}
