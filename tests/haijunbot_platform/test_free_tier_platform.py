# -*- coding: utf-8 -*-
"""The ``free`` platform registers and keeps paid lanes optional."""

from haijunbot.haijunbot_platform.free_tier import FreeTierModel


def test_platform_name_is_free():
    assert FreeTierModel.platform_name() == "free"


def test_no_environment_key_is_required():
    assert FreeTierModel.get_required_env_keys() == []
    assert FreeTierModel.get_env_defaults() == {}


def test_env_guide_covers_free_providers_first():
    guide = FreeTierModel.get_env_config_guide()
    for key in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY", "HF_TOKEN"):
        assert key in guide
    assert "free" in guide["GROQ_API_KEY"]
    assert "free" in guide["OPENROUTER_API_KEY"]
    assert "paid" in guide["OPENAI_API_KEY"]


def test_platform_is_registered_by_the_registry():
    from haijunbot.haijunbot_platform.registry import PlatformRegistry

    registry = PlatformRegistry()
    assert "free" in registry.get_available_platforms()
