# -*- coding: utf-8 -*-
"""Vinbox runtime adapter tests (no Docker, no network)."""

import json
import os
from pathlib import Path

import pytest

from haijunbot.haijunbot_utils import vinbox_runtime


def _fake_vinbox(tmp_path: Path, model_id: str = "opencode:deepseek-v4.1-flash-free") -> Path:
    home = tmp_path / "vinbox"
    (home / "app" / "llm").mkdir(parents=True)
    (home / "app" / "llm" / "model_registry.py").write_text(
        "# fake registry\n", encoding="utf-8"
    )
    (home / "app" / "program-file").mkdir(parents=True)
    (home / "data").mkdir(parents=True)
    (home / "data" / "models.json").write_text(
        json.dumps({"current": model_id, "providers": {}}), encoding="utf-8"
    )
    return home


@pytest.fixture
def vinbox_home(tmp_path, monkeypatch):
    home = _fake_vinbox(tmp_path)
    monkeypatch.setenv("VINBOX_HOME", str(home))
    monkeypatch.delenv("HAIJUNBOT_DATA_DIR", raising=False)
    return home


def test_detects_vinbox_and_persistent_data_dir(vinbox_home):
    assert vinbox_runtime.is_vinbox() is True
    assert vinbox_runtime.data_dir() == vinbox_home / "data" / "haijunbot"
    assert vinbox_runtime.program_file_dir() == vinbox_home / "app" / "program-file"
    assert vinbox_runtime.current_model_id() == "opencode:deepseek-v4.1-flash-free"


def test_no_vinbox_returns_standalone_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("VINBOX_HOME", raising=False)
    # Point the container default at a directory that cannot exist, and hide the
    # structural markers: this checkout lives inside a real Vinbox tree, so
    # without this the adapter would legitimately find it.
    monkeypatch.setattr(vinbox_runtime, "DEFAULT_VINBOX_HOME", tmp_path / "missing")
    monkeypatch.setattr(vinbox_runtime, "_structural_home", lambda: None)
    assert vinbox_runtime.is_vinbox() is False
    assert vinbox_runtime.current_model_id() is None


def test_process_env_mirrors_vinbox_terminal(vinbox_home, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    # pwsh is required; the test must not depend on the host having it.
    monkeypatch.setenv("HAIJUNBOT_SHELL", "/opt/pwsh")
    env = vinbox_runtime.process_env()

    assert env["VINBOX_HOME"] == str(vinbox_home)
    assert env["DISPLAY"] == ":99"
    assert env["HAIJUNBOT_DATA_DIR"] == str(vinbox_home / "data" / "haijunbot")
    assert env["PIP_TARGET"] == str(vinbox_home / "app" / "program-file" / "packages")
    parts = env["PATH"].split(os.pathsep)
    assert parts[0] == str(vinbox_home / "app" / "program-file" / "bin")
    assert env["SHELL"] == "/opt/pwsh"


def test_apply_process_defaults_sets_data_dir(vinbox_home, monkeypatch):
    monkeypatch.delenv("HAIJUNBOT_DATA_DIR", raising=False)
    monkeypatch.setenv("HAIJUNBOT_SHELL", "/opt/pwsh")
    assert vinbox_runtime.apply_process_defaults() is True
    assert os.environ["HAIJUNBOT_DATA_DIR"] == str(vinbox_home / "data" / "haijunbot")
    assert vinbox_runtime.data_dir().is_dir()


def _hide_pwsh(monkeypatch):
    monkeypatch.delenv("HAIJUNBOT_SHELL", raising=False)
    monkeypatch.setattr(vinbox_runtime.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        vinbox_runtime, "_PWSH_CANDIDATES", {"nt": (), "posix": ()}
    )


def test_pwsh_path_raises_when_missing(monkeypatch):
    _hide_pwsh(monkeypatch)
    with pytest.raises(vinbox_runtime.PwshNotFound) as excinfo:
        vinbox_runtime.pwsh_path()
    assert "pwsh" in str(excinfo.value)
    assert "Pasang dulu" in str(excinfo.value)


def test_status_reports_missing_pwsh_without_raising(vinbox_home, monkeypatch):
    _hide_pwsh(monkeypatch)
    status = vinbox_runtime.status()
    assert status["inside_vinbox"] is True
    assert status["shell"] is None
    assert status["pwsh_present"] is False


def test_command_argv_never_uses_cmd_or_bash(monkeypatch):
    monkeypatch.setenv("HAIJUNBOT_SHELL", "/opt/pwsh")
    assert vinbox_runtime.pwsh_argv("Get-Date") == [
        "/opt/pwsh",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        "Get-Date",
    ]
    assert vinbox_runtime.command_argv(None, "Get-Date") == [
        "/opt/pwsh",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        "Get-Date",
    ]
    # A non-shell interpreter keeps its own flag, still without a shell.
    assert vinbox_runtime.command_argv("/usr/bin/python3", "print(1)") == [
        "/usr/bin/python3",
        "-c",
        "print(1)",
    ]


def test_working_dir_is_file_manager(vinbox_home):
    assert vinbox_runtime.working_dir() == str(vinbox_home / "app" / "program-file")


def test_config_uses_vinbox_data_dir(vinbox_home, monkeypatch):
    from haijunbot.haijunbot_utils import config

    monkeypatch.delenv("HAIJUNBOT_DATA_DIR", raising=False)
    assert config.get_data_dir() == str(vinbox_home / "data" / "haijunbot")


def test_config_pins_vinbox_platform_and_model(vinbox_home, monkeypatch):
    from haijunbot.haijunbot_utils import config

    monkeypatch.setattr(config, "GLOBAL_CONFIG_DATA", {"platform": "openai", "model": "gpt-4o"})
    resolved = config._get_resolved_model_config()
    assert resolved["platform"] == "vinbox"
    assert resolved["model"] == "opencode:deepseek-v4.1-flash-free"
    assert "llm_config" not in resolved


class _FakeContextManager:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *exc):
        return False


def test_new_cdp_page_never_launches(monkeypatch):
    calls = {"launch": 0, "connect": 0}

    class FakePage:
        pass

    class FakeContext:
        def new_page(self):
            return FakePage()

    class FakeBrowser:
        contexts = [FakeContext()]

        def new_context(self):
            return FakeContext()

        def close(self):
            raise AssertionError("Vinbox browser must stay open")

    class FakeChromium:
        def launch(self, **kwargs):
            calls["launch"] += 1
            return FakeBrowser()

        def connect_over_cdp(self, url):
            calls["connect"] += 1
            assert url == "http://127.0.0.1:9222"
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    browser, page = vinbox_runtime.new_cdp_page(FakePlaywright())
    assert calls == {"launch": 0, "connect": 1}
    assert isinstance(page, FakePage)


def test_search_web_fallback_uses_cdp_inside_vinbox(vinbox_home, monkeypatch):
    from haijunbot.haijunbot_tools import search_web

    calls = {"launch": 0, "connect": 0}

    class FakePage:
        def set_default_timeout(self, *_):
            pass

        def goto(self, *_a, **_k):
            pass

        def wait_for_selector(self, *_a, **_k):
            raise RuntimeError("no results")

        def content(self):
            return ""

        def close(self):
            pass

    class FakeContext:
        def new_page(self):
            return FakePage()

    class FakeBrowser:
        contexts = [FakeContext()]

    class FakeChromium:
        def launch(self, **_k):
            calls["launch"] += 1
            return FakeBrowser()

        def connect_over_cdp(self, url):
            calls["connect"] += 1
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    fake_pw = _FakeContextManager(FakePlaywright())
    monkeypatch.setattr(search_web, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(search_web, "sync_playwright", lambda: fake_pw)
    monkeypatch.setattr(
        search_web.SearchWebTool,
        "_parse_bing_results",
        lambda self, html: [],
    )

    tool = search_web.SearchWebTool()
    assert tool._search_bing_with_playwright("https://www.bing.com/search?q=x") == []
    assert calls == {"launch": 0, "connect": 1}


def test_panel_reports_real_vinbox_state(vinbox_home, monkeypatch):
    from haijunbot.haijunbot_vinbox import panel

    monkeypatch.setattr(panel, "_cdp_alive", lambda timeout=1.0: {
        "alive": True,
        "browser": "Chrome/141.0",
        "url": "http://127.0.0.1:9222/json/version",
    })

    payload = panel.collect_status()
    assert payload["runtime"]["inside_vinbox"] is True
    assert payload["runtime"]["model"] == "opencode:deepseek-v4.1-flash-free"
    assert payload["cdp"]["alive"] is True
    assert payload["data"]["path"] == str(vinbox_home / "data" / "haijunbot")

    html = panel.render_html(payload)
    assert "HaijunBot" in html
    assert "opencode:deepseek-v4.1-flash-free" in html
    assert "Chrome/141.0" in html
    assert "{{" not in html  # every placeholder was filled


def test_panel_without_vinbox_says_standalone(tmp_path, monkeypatch):
    from haijunbot.haijunbot_vinbox import panel

    monkeypatch.delenv("VINBOX_HOME", raising=False)
    monkeypatch.setattr(vinbox_runtime, "DEFAULT_VINBOX_HOME", tmp_path / "missing")
    monkeypatch.setattr(vinbox_runtime, "_structural_home", lambda: None)

    payload = panel.collect_status()
    assert payload["runtime"]["inside_vinbox"] is False
    assert payload["cdp"]["alive"] is False
    assert "standalone" in panel.render_html(payload)
