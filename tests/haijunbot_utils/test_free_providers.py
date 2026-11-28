# -*- coding: utf-8 -*-
"""The free-tier provider catalog: free first, paid optional."""

from haijunbot.haijunbot_utils import free_providers as fp

FREE_EXPECTED = [
    "openrouter",
    "groq",
    "together",
    "huggingface",
    "gemini",
    "9router",
    "omniroute",
    "opencode",
    "freebuff",
]
PAID_EXPECTED = ["openai", "anthropic", "google"]


def test_every_requested_provider_exists():
    for pid in FREE_EXPECTED + PAID_EXPECTED:
        spec = fp.get_provider(pid)
        assert spec["name"]
        assert spec["models"]
        assert spec["tier"] in (fp.TIER_FREE, fp.TIER_PAID)


def test_free_first_order():
    assert fp.free_provider_ids() == FREE_EXPECTED
    assert fp.paid_provider_ids() == PAID_EXPECTED
    assert fp.provider_ids()[: len(FREE_EXPECTED)] == FREE_EXPECTED
    assert fp.is_free("groq") is True
    assert fp.is_free("openai") is False


def test_defaults_fill_base_url_from_catalog(monkeypatch):
    monkeypatch.delenv("GROQ_API_BASE", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = fp.apply_defaults({"provider": "groq"})
    assert result["openai_api_base"] == "https://api.groq.com/openai/v1"
    assert "openai_api_key" not in result
    assert result["provider"] == "groq"


def test_env_key_fills_missing_key(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf-free-token")
    monkeypatch.delenv("HUGGINGFACE_API_BASE", raising=False)
    result = fp.apply_defaults({"provider": "huggingface"})
    assert result["openai_api_key"] == "hf-free-token"
    assert result["openai_api_base"] == "https://router.huggingface.co/v1"


def test_explicit_key_wins_over_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    result = fp.apply_defaults({"provider": "groq", "openai_api_key": "config-key"})
    assert result["openai_api_key"] == "config-key"


def test_provider_inferred_from_base_url():
    block = {"openai_api_base": "https://api.together.xyz/v1"}
    assert fp.provider_for(block) == "together"
    assert fp.apply_defaults(block)["provider"] == "together"


def test_no_provider_means_untouched():
    block = {"openai_api_base": "https://example.invalid/v1"}
    assert fp.provider_for(block) is None
    assert fp.apply_defaults(block) == block
    assert fp.apply_defaults({}) == {}


def test_applies_to_every_resolved_block(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk-free")
    resolved = {
        "llm_config": {"provider": "groq"},
        "smart_llm_config": {"provider": "gemini"},
        "cheap_llm_config": {},
        "eval_llm_config": None,
    }
    out = fp.apply_to_resolved_config(resolved)
    assert out["llm_config"]["openai_api_key"] == "gsk-free"
    assert out["smart_llm_config"]["openai_api_base"].startswith(
        "https://generativelanguage.googleapis.com"
    )
    assert out["cheap_llm_config"] == {}
    assert out["eval_llm_config"] is None


def test_providers_table_is_free_first():
    rows = fp.providers_table()
    tiers = [row["tier"] for row in rows]
    assert tiers == [fp.TIER_FREE] * len(FREE_EXPECTED) + [fp.TIER_PAID] * len(
        PAID_EXPECTED
    )
    assert rows[0]["id"] == "openrouter"
