# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_utils non-interactive quick configuration

Coverage:
1. Environment variable override in config.py (HAIJUNBOT_PLATFORM / HAIJUNBOT_MODEL), for CI runtime model/platform override
2. run_quick_config_noninteractive in quick_config.py, for CI persistent write to config.yaml
"""

import pathlib

import yaml
import pytest

from haijunbot.haijunbot_utils import config as config_mod
from haijunbot.haijunbot_utils import quick_config


@pytest.fixture(autouse=True)
def _standalone_config(monkeypatch):
    """These are standalone-config tests, not the Vinbox runtime.

    This checkout lives inside a real Vinbox tree, so ``is_vinbox()`` would
    otherwise pin platform/model to Vinbox's registry. The Vinbox behaviour is
    covered by ``test_vinbox_runtime.py``.
    """
    from haijunbot.haijunbot_utils import vinbox_runtime

    monkeypatch.delenv("VINBOX_HOME", raising=False)
    monkeypatch.setattr(vinbox_runtime, "is_vinbox", lambda: False)


@pytest.fixture
def clear_env_overrides(monkeypatch):
    """Clear environment variable overrides to ensure test isolation"""
    monkeypatch.delenv("HAIJUNBOT_PLATFORM", raising=False)
    monkeypatch.delenv("HAIJUNBOT_MODEL", raising=False)


class TestEnvVarOverride:
    """Tests for config.py environment variable override mechanism"""

    @pytest.fixture(autouse=True)
    def isolate_global_config(self):
        """Isolate GLOBAL_CONFIG_DATA to avoid real ~/.haijunbot/config.yaml polluting test results.

        When running full tests, GLOBAL_CONFIG_DATA may be populated by real config (e.g. normal model
        set to deepseek-flash), causing test_default_no_override default value assertions to fail. Here we
        remove keys affecting model resolution before tests, making assertions depend only on code defaults,
        and restore them after test completion.
        """
        # Keys affecting model resolution (read by _get_resolved_model_config)
        keys = ["model", "platform", "llm_group", "llm_groups"]
        snapshot = {}
        for key in keys:
            if key in config_mod.GLOBAL_CONFIG_DATA:
                snapshot[key] = config_mod.GLOBAL_CONFIG_DATA[key]
                del config_mod.GLOBAL_CONFIG_DATA[key]
        yield
        for key, value in snapshot.items():
            config_mod.GLOBAL_CONFIG_DATA[key] = value

    def test_default_no_override(self, clear_env_overrides):
        """Return default values when environment variables are not set"""
        assert config_mod.get_normal_platform_name() == "openai"
        assert config_mod.get_normal_model_name() == "gpt-5"

    def test_model_override(self, clear_env_overrides, monkeypatch):
        """HAIJUNBOT_MODEL overrides model"""
        monkeypatch.setenv("HAIJUNBOT_MODEL", "deepseek-chat")
        assert config_mod.get_normal_model_name() == "deepseek-chat"

    def test_platform_override(self, clear_env_overrides, monkeypatch):
        """HAIJUNBOT_PLATFORM overrides platform"""
        monkeypatch.setenv("HAIJUNBOT_PLATFORM", "haijun")
        assert config_mod.get_normal_platform_name() == "haijun"

    def test_both_override(self, clear_env_overrides, monkeypatch):
        """HAIJUNBOT_MODEL + HAIJUNBOT_PLATFORM override simultaneously"""
        monkeypatch.setenv("HAIJUNBOT_MODEL", "haijun-3-5-sonnet")
        monkeypatch.setenv("HAIJUNBOT_PLATFORM", "haijun")
        assert config_mod.get_normal_platform_name() == "haijun"
        assert config_mod.get_normal_model_name() == "haijun-3-5-sonnet"

    def test_env_priority_over_config(self, clear_env_overrides, monkeypatch):
        """Environment variables take priority over config in config.yaml"""
        original = config_mod.GLOBAL_CONFIG_DATA.get("model", None)
        try:
            config_mod.GLOBAL_CONFIG_DATA["model"] = "config-model"
            monkeypatch.setenv("HAIJUNBOT_MODEL", "env-model")
            assert config_mod.get_normal_model_name() == "env-model"
        finally:
            if original is not None:
                config_mod.GLOBAL_CONFIG_DATA["model"] = original
            else:
                config_mod.GLOBAL_CONFIG_DATA.pop("model", None)


class TestQuickConfigNoninteractive:
    """Tests for hqc non-interactive mode writing to config.yaml"""

    @pytest.fixture
    def isolated_home(self, tmp_path, monkeypatch):
        """Point HOME to temporary directory to avoid polluting real ~/.haijunbot"""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        # Windows ignores HOME: Path.home() reads USERPROFILE. Without these two
        # lines the writer lands in the real ~/.haijunbot/config.yaml.
        monkeypatch.setenv("USERPROFILE", str(home))
        monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: home))
        return home

    def test_writes_llms_and_groups(self, isolated_home, monkeypatch):
        """Non-interactive write of llms/llm_groups/llm_group structure is correct"""
        monkeypatch.setattr(quick_config, "init_env", lambda *a, **k: None)
        quick_config.run_quick_config_noninteractive(
            platform="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-123",
            model="gpt-4o",
            group="default",
            skip_test=True,
        )
        config_path = isolated_home / ".haijunbot" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        # llms contains this model's config
        llm_entry = next(v for v in data["llms"].values() if v.get("model") == "gpt-4o")
        assert llm_entry["platform"] == "openai"
        assert llm_entry["max_input_token_count"] == 200000
        assert llm_entry["llm_config"]["openai_api_key"] == "sk-test-123"
        assert llm_entry["llm_config"]["openai_api_base"] == "https://api.openai.com/v1"
        # llm_groups and default group
        assert (
            data["llm_groups"]["default"]["normal_llm"] == list(data["llms"].keys())[0]
        )
        assert data["llm_group"] == "default"

    def test_haijun_platform(self, isolated_home, monkeypatch):
        """haijun platform writes juglow fields"""
        monkeypatch.setattr(quick_config, "init_env", lambda *a, **k: None)
        quick_config.run_quick_config_noninteractive(
            platform="haijun",
            base_url="https://api.juglow.com",
            api_key="sk-juglow",
            model="haijun-3-5-sonnet",
            skip_test=True,
        )
        config_path = isolated_home / ".haijunbot" / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        llm_entry = next(
            v for v in data["llms"].values() if v.get("model") == "haijun-3-5-sonnet"
        )
        assert llm_entry["llm_config"]["juglow_api_key"] == "sk-juglow"
        assert (
            llm_entry["llm_config"]["juglow_base_url"] == "https://api.juglow.com"
        )

    def test_reuse_existing_model_config(self, isolated_home, monkeypatch):
        """Reusing existing llms config when configuring the same model again, no new entry"""
        monkeypatch.setattr(quick_config, "init_env", lambda *a, **k: None)
        quick_config.run_quick_config_noninteractive(
            platform="openai",
            base_url="https://api.openai.com/v1",
            api_key="k1",
            model="gpt-4o",
            skip_test=True,
        )
        quick_config.run_quick_config_noninteractive(
            platform="openai",
            base_url="https://api.openai.com/v1",
            api_key="k2",
            model="gpt-4o",
            skip_test=True,
        )
        config_path = isolated_home / ".haijunbot" / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        gpt4o_entries = [v for v in data["llms"].values() if v.get("model") == "gpt-4o"]
        assert len(gpt4o_entries) == 1
        assert gpt4o_entries[0]["llm_config"]["openai_api_key"] == "k2"

    def test_unsupported_platform_raises(self, isolated_home, monkeypatch):
        """Unsupported platform type raises error"""
        monkeypatch.setattr(quick_config, "init_env", lambda *a, **k: None)
        with pytest.raises(Exception):
            quick_config.run_quick_config_noninteractive(
                platform="foo",
                base_url="https://x",
                api_key="k",
                model="m",
                skip_test=True,
            )
