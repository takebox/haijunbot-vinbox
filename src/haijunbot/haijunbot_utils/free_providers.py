# -*- coding: utf-8 -*-
"""Free-tier LLM provider catalog.

Every provider here speaks the OpenAI-compatible chat protocol, so one
platform (``free``) covers all of them. The catalog keeps the base URL, the
environment variable that carries the key, and a few curated model names, so a
user holding only a free-tier key never needs a paid subscription. The paid
providers stay in the same table: they are optional and always come last.
"""

from __future__ import annotations

import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

TIER_FREE = "free"
TIER_PAID = "paid"

# Free tier first: this is the order used by the docs and the config wizard.
FREE_PRIORITY: List[str] = [
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
# Optional subscriptions. Never required, never tried before a free lane.
PAID_PRIORITY: List[str] = ["openai", "anthropic", "google"]

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openrouter": {
        "name": "OpenRouter",
        "tier": TIER_FREE,
        "base_url": "https://openrouter.ai/api/v1",
        "env_keys": ["OPENROUTER_API_KEY"],
        "env_base": "OPENROUTER_API_BASE",
        "signup_url": "https://openrouter.ai/keys",
        "models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ],
        "note": "Free models carry the ':free' suffix.",
    },
    "groq": {
        "name": "Groq",
        "tier": TIER_FREE,
        "base_url": "https://api.groq.com/openai/v1",
        "env_keys": ["GROQ_API_KEY"],
        "env_base": "GROQ_API_BASE",
        "signup_url": "https://console.groq.com/keys",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "note": "Free tier, fast inference.",
    },
    "together": {
        "name": "Together AI",
        "tier": TIER_FREE,
        "base_url": "https://api.together.xyz/v1",
        "env_keys": ["TOGETHER_API_KEY"],
        "env_base": "TOGETHER_API_BASE",
        "signup_url": "https://api.together.ai/settings/api-keys",
        "models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ],
        "note": "Free trial credit, no subscription needed to start.",
    },
    "huggingface": {
        "name": "Hugging Face",
        "tier": TIER_FREE,
        "base_url": "https://router.huggingface.co/v1",
        "env_keys": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],
        "env_base": "HUGGINGFACE_API_BASE",
        "signup_url": "https://huggingface.co/settings/tokens",
        "models": [
            "meta-llama/Llama-3.1-8B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
        "note": "Inference router; a free HF token is enough.",
    },
    "gemini": {
        "name": "Gemini",
        "tier": TIER_FREE,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "env_base": "GEMINI_API_BASE",
        "signup_url": "https://aistudio.google.com/apikey",
        "models": ["gemini-2.0-flash", "gemini-2.5-flash"],
        "note": "Google's OpenAI-compatible endpoint; free tier key works.",
    },
    "9router": {
        "name": "9Router",
        "tier": TIER_FREE,
        "base_url": "",
        "env_keys": ["NINE_ROUTER_API_KEY", "NINEROUTER_API_KEY"],
        "env_base": "NINE_ROUTER_API_BASE",
        "signup_url": "",
        "models": ["9router/auto"],
        "note": "Self-hosted router: set the base URL once.",
    },
    "omniroute": {
        "name": "OmniRoute",
        "tier": TIER_FREE,
        "base_url": "",
        "env_keys": ["OMNIROUTE_API_KEY"],
        "env_base": "OMNIROUTE_API_BASE",
        "signup_url": "",
        "models": ["omniroute/auto"],
        "note": "Self-hosted router: set the base URL once.",
    },
    "opencode": {
        "name": "OpenCode",
        "tier": TIER_FREE,
        "base_url": "",
        "env_keys": [],
        "env_base": "OPENCODE_BASE_URL",
        "signup_url": "",
        "models": ["opencode/default"],
        "note": "Local CLI/gateway; needs no paid API key.",
    },
    "freebuff": {
        "name": "FreeBuff",
        "tier": TIER_FREE,
        "base_url": "https://freebuff.com/api/v1/paid",
        "env_keys": ["FREEBUFF_API_KEY", "OPENAI_API_KEY"],
        "env_base": "FREEBUFF_API_BASE",
        "signup_url": "https://freebuff.com/account/api",
        "models": ["freebuff/auto"],
        "note": "OpenAI-compatible FreeBuff endpoint.",
    },
    "openai": {
        "name": "OpenAI",
        "tier": TIER_PAID,
        "base_url": "https://api.openai.com/v1",
        "env_keys": ["OPENAI_API_KEY"],
        "env_base": "OPENAI_API_BASE",
        "signup_url": "https://platform.openai.com/api-keys",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "note": "Optional subscription.",
    },
    "anthropic": {
        "name": "Anthropic",
        "tier": TIER_PAID,
        "base_url": "",
        "env_keys": ["ANTHROPIC_API_KEY"],
        "env_base": "ANTHROPIC_API_BASE",
        "signup_url": "https://console.anthropic.com/settings/keys",
        "models": ["claude-sonnet-4-5"],
        "note": (
            "Optional subscription. Anthropic's own API is not OpenAI-shaped, "
            "so point this provider at an OpenAI-compatible gateway."
        ),
    },
    "google": {
        "name": "Google (paid)",
        "tier": TIER_PAID,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "env_base": "GOOGLE_API_BASE",
        "signup_url": "https://aistudio.google.com/apikey",
        "models": ["gemini-2.5-pro"],
        "note": "Optional paid Google key; the free lane uses the same endpoint.",
    },
}

# llm_config blocks that may carry a provider.
CONFIG_KEYS = ("llm_config", "cheap_llm_config", "smart_llm_config", "eval_llm_config")


def provider_ids() -> List[str]:
    """Every provider id, free tier first."""
    return free_provider_ids() + paid_provider_ids()


def free_provider_ids() -> List[str]:
    """Free-tier provider ids, in preference order."""
    return [pid for pid in FREE_PRIORITY if pid in PROVIDERS]


def paid_provider_ids() -> List[str]:
    """Paid provider ids, in preference order. Optional by design."""
    return [pid for pid in PAID_PRIORITY if pid in PROVIDERS]


def get_provider(provider_id: str) -> Dict[str, Any]:
    """Return the catalog entry for a provider id."""
    return PROVIDERS[str(provider_id).strip().lower()]


def is_free(provider_id: str) -> bool:
    """Whether the provider is on the free tier."""
    spec = PROVIDERS.get(str(provider_id).strip().lower())
    return bool(spec) and spec["tier"] == TIER_FREE


def provider_api_key(provider_id: str) -> str:
    """The first non-empty key found in the provider's environment variables."""
    spec = PROVIDERS.get(str(provider_id).strip().lower())
    if not spec:
        return ""
    for env_key in spec["env_keys"]:
        value = os.environ.get(env_key, "").strip()
        if value:
            return value
    return ""


def provider_base_url(provider_id: str) -> str:
    """Configured base URL, falling back to the catalog default."""
    spec = PROVIDERS.get(str(provider_id).strip().lower())
    if not spec:
        return ""
    env_value = os.environ.get(spec["env_base"], "").strip()
    return env_value or str(spec["base_url"] or "")


def provider_for(llm_config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Identify the provider of an llm_config block, or return None.

    Explicit ``provider`` wins; otherwise the block's base URL is matched
    against the catalog so existing configs keep working untouched.
    """
    if not isinstance(llm_config, dict):
        return None
    explicit = str(
        llm_config.get("provider") or os.environ.get("HAIJUNBOT_PROVIDER") or ""
    ).strip().lower()
    if explicit in PROVIDERS:
        return explicit
    base = str(llm_config.get("openai_api_base") or "").strip().lower()
    if not base:
        return None
    for pid in provider_ids():
        catalog_base = str(PROVIDERS[pid]["base_url"] or "").lower()
        if catalog_base and base.startswith(catalog_base):
            return pid
    return None


def apply_defaults(llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """Fill base URL and key from the catalog for a block naming a provider.

    Missing keys stay missing on purpose: the platform then reports the absence
    honestly instead of pretending a paid key exists.
    """
    if not isinstance(llm_config, dict) or not llm_config:
        return llm_config
    provider = provider_for(llm_config)
    if not provider:
        return llm_config
    result = dict(llm_config)
    if not result.get("openai_api_base"):
        base = provider_base_url(provider)
        if base:
            result["openai_api_base"] = base
    if not result.get("openai_api_key"):
        key = provider_api_key(provider)
        if key:
            result["openai_api_key"] = key
    result["provider"] = provider
    return result


def apply_to_resolved_config(resolved_config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply provider defaults to every resolved llm_config block."""
    if not isinstance(resolved_config, dict):
        return resolved_config
    for key in CONFIG_KEYS:
        block = resolved_config.get(key)
        if isinstance(block, dict) and block:
            resolved_config[key] = apply_defaults(block)
    return resolved_config


def providers_table() -> List[Dict[str, Any]]:
    """Rows for documentation and UIs: free first, paid last."""
    rows: List[Dict[str, Any]] = []
    for pid in provider_ids():
        spec = PROVIDERS[pid]
        rows.append(
            {
                "id": pid,
                "name": spec["name"],
                "tier": spec["tier"],
                "base_url": provider_base_url(pid),
                "env_keys": list(spec["env_keys"]),
                "models": list(spec["models"]),
                "signup_url": spec["signup_url"],
                "note": spec["note"],
            }
        )
    return rows
