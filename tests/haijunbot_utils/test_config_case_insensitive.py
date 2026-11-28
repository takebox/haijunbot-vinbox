# -*- coding: utf-8 -*-
"""
Test case-insensitive config key functionality

Verify that after GLOBAL_CONFIG_DATA uses CaseInsensitiveDict, config key access is no longer case-sensitive
"""

import pytest

from haijunbot.haijunbot_utils.config import (
    GLOBAL_CONFIG_DATA,
    set_config,
    is_print_prompt,
    get_normal_platform_name,
    get_normal_model_name,
)
from haijunbot.haijunbot_utils.collections import CaseInsensitiveDict


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


def test_global_config_is_case_insensitive():
    """Verify global config uses CaseInsensitiveDict"""
    assert isinstance(GLOBAL_CONFIG_DATA, CaseInsensitiveDict)


def test_case_insensitive_key_access():
    """Test case-insensitive key access"""
    # Clean up test environment
    original_data = dict(GLOBAL_CONFIG_DATA)
    GLOBAL_CONFIG_DATA.clear()

    try:
        # Set config
        set_config("Test_Key", "test_value")

        # Verify access with different cases
        assert GLOBAL_CONFIG_DATA.get("TEST_KEY") == "test_value"
        assert GLOBAL_CONFIG_DATA.get("test_key") == "test_value"
        assert GLOBAL_CONFIG_DATA.get("Test_Key") == "test_value"

        # Verify overwrite behavior
        set_config("TEST_key", "new_value")
        assert GLOBAL_CONFIG_DATA.get("test_KEY") == "new_value"
        assert len(GLOBAL_CONFIG_DATA) == 1

    finally:
        # Restore original data
        GLOBAL_CONFIG_DATA.clear()
        GLOBAL_CONFIG_DATA.update(original_data)


def test_config_functions_case_insensitive():
    """Test case-insensitive access in config functions"""
    # Save original data
    original_data = dict(GLOBAL_CONFIG_DATA)
    GLOBAL_CONFIG_DATA.clear()

    try:
        # Test platform config (using new key name, without HAIJUNBOT_ prefix)
        set_config("platform", "test_platform")
        assert get_normal_platform_name() == "test_platform"

        # Test model config
        set_config("model", "test_model")
        assert get_normal_model_name() == "test_model"

        # Test data path config (note: get_data_dir() does not read config, it always returns ~/.haijunbot)
        set_config("data_path", "/test/path")
        # get_data_dir() does not read from config, so skip assertion here

        # Test print prompt config
        set_config("print_prompt", True)
        assert is_print_prompt() is True

        # Test shell config (note: get_shell_name() reads from environment variable, not config)
        # set_config("SHELL", "/bin/zsh")
        # assert get_shell_name() == "zsh"

        # Verify case-insensitive access
        set_config("PLATFORM", "upper_platform")
        assert get_normal_platform_name() == "upper_platform"

    finally:
        # Restore original data
        GLOBAL_CONFIG_DATA.clear()
        GLOBAL_CONFIG_DATA.update(original_data)


def test_case_insensitive_dict_behavior():
    """Test basic behavior of CaseInsensitiveDict"""
    # Clean up test environment
    original_data = dict(GLOBAL_CONFIG_DATA)
    GLOBAL_CONFIG_DATA.clear()

    try:
        # Add data
        data = {
            "Content-Type": "text/plain",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }

        for key, value in data.items():
            set_config(key, value)

        # Verify case-insensitive access
        assert GLOBAL_CONFIG_DATA.get("content-type") == "text/plain"
        assert GLOBAL_CONFIG_DATA.get("ACCEPT") == "application/json"
        assert GLOBAL_CONFIG_DATA.get("user-agent") == "Mozilla/5.0"

        # Verify key existence check
        assert "content-type" in GLOBAL_CONFIG_DATA
        assert "CONTENT-TYPE" in GLOBAL_CONFIG_DATA
        assert "Content-Type" in GLOBAL_CONFIG_DATA

        # Verify iteration
        keys = list(GLOBAL_CONFIG_DATA.keys())
        values = list(GLOBAL_CONFIG_DATA.values())
        assert len(keys) == 3
        assert "text/plain" in values

    finally:
        # Restore original data
        GLOBAL_CONFIG_DATA.clear()
        GLOBAL_CONFIG_DATA.update(original_data)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
