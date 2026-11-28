# -*- coding: utf-8 -*-
"""The wizard only demands a key when the provider actually has one."""

import pathlib

import pytest
import yaml

from haijunbot.haijunbot_utils import quick_config


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(
        quick_config.PrettyOutput, "auto_print", staticmethod(lambda *a, **k: None)
    )
    monkeypatch.setattr(quick_config, "init_env", lambda *a, **k: None)


def _answers(monkeypatch, values):
    queue = iter(values)

    def fake_input(*args, **kwargs):
        return next(queue)

    monkeypatch.setattr(quick_config, "get_single_line_input", fake_input)


def test_opencode_needs_base_url_but_no_key(monkeypatch):
    """opencode has no env key: base URL is enough, the wizard continues."""
    _answers(monkeypatch, ["opencode", "http://127.0.0.1:4096/v1"])
    result = quick_config._ask_provider_and_key()
    assert result == ("free", "opencode", "http://127.0.0.1:4096/v1", "")


def test_opencode_still_needs_a_base_url(monkeypatch):
    _answers(monkeypatch, ["opencode", ""])
    assert quick_config._ask_provider_and_key() is None


def test_keyless_provider_is_recognised():
    assert quick_config._provider_needs_key("opencode") is False
    assert quick_config._provider_needs_key("groq") is True
    assert quick_config._provider_needs_key("openai") is True
    assert quick_config._provider_needs_key("unknown") is True


def test_groq_keeps_catalog_base_url_and_accepts_key(monkeypatch):
    _answers(monkeypatch, ["groq", "gsk-valid-looking-key"])
    result = quick_config._ask_provider_and_key()
    assert result == (
        "free",
        "groq",
        "https://api.groq.com/openai/v1",
        "gsk-valid-looking-key",
    )


def test_key_provider_still_cancels_on_empty_key(monkeypatch):
    _answers(monkeypatch, ["groq", ""])
    assert quick_config._ask_provider_and_key() is None


def test_noninteractive_opencode_writes_no_key(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: home))

    quick_config.run_quick_config_noninteractive(
        platform="opencode",
        base_url="http://127.0.0.1:4096/v1",
        api_key="",
        model="opencode/default",
        skip_test=True,
    )

    config_path = home / ".haijunbot" / "config.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    entry = next(v for v in data["llms"].values() if v["model"] == "opencode/default")
    assert entry["platform"] == "free"
    assert entry["llm_config"]["provider"] == "opencode"
    assert entry["llm_config"]["openai_api_base"] == "http://127.0.0.1:4096/v1"
    assert entry["llm_config"]["openai_api_key"] == ""
