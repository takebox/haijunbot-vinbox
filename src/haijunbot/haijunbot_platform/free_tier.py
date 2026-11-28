# -*- coding: utf-8 -*-
"""The ``free`` platform: any free-tier provider over the OpenAI protocol.

OpenRouter, Groq, Together, Hugging Face, Gemini, 9Router, OmniRouter,
OpenCode and FreeBuff all speak the same OpenAI-compatible chat API, so one
platform covers them and the provider name only selects base URL, key and
curated models. OpenAI, Anthropic and Google stay available as optional paid
lanes in the same catalog: nothing here requires a paid subscription.
"""

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_platform.openai import OpenAIModel
from haijunbot.haijunbot_utils.free_providers import FREE_PRIORITY
from haijunbot.haijunbot_utils.free_providers import PAID_PRIORITY
from haijunbot.haijunbot_utils.free_providers import PROVIDERS
from haijunbot.haijunbot_utils.free_providers import provider_for
from haijunbot.haijunbot_utils.output import PrettyOutput


class FreeTierModel(OpenAIModel):
    """OpenAI-compatible client for the free tier and the optional paid lanes."""

    def __init__(
        self,
        platform_type: str = "normal",
        agent: Optional[Any] = None,
    ):
        """Resolve the provider from llm_config, then reuse the OpenAI client.

        The resolved llm_config already carries the provider's base URL and key
        (see ``haijunbot_utils.free_providers.apply_to_resolved_config``), so
        the OpenAI transport is reused unchanged.
        """
        super().__init__(platform_type=platform_type, agent=agent)
        llm_config = dict(self._llm_config or {})
        self.provider = provider_for(llm_config) or ""
        spec = PROVIDERS.get(self.provider)
        self._provider_models: List[str] = list(spec["models"]) if spec else []
        if spec is None:
            PrettyOutput.auto_print(
                "⚠️ Free tier: no provider selected. Set llm_config.provider to one of: "
                + ", ".join(FREE_PRIORITY + PAID_PRIORITY)
            )
            return
        if not self.api_key and spec["tier"] == "free" and spec["env_keys"]:
            PrettyOutput.auto_print(
                f"⚠️ {spec['name']}: no API key yet. Set one of "
                f"{', '.join(spec['env_keys'])} (free tier) or put it in llm_config.openai_api_key."
            )
        if not self.base_url and not spec["base_url"]:
            PrettyOutput.auto_print(
                f"⚠️ {spec['name']}: base URL is empty. Set llm_config.openai_api_base "
                f"or the {spec['env_base']} environment variable."
            )

    def get_model_list(self) -> List[Tuple[str, str]]:
        """Curated models for the selected provider, without an extra API call.

        Falls back to the provider's /models endpoint when the catalog has no
        entry, so behaviour stays unchanged for unknown providers.
        """
        if self._provider_models:
            return [(name, name) for name in self._provider_models]
        return super().get_model_list()

    @classmethod
    def platform_name(cls) -> str:
        """Platform name used in ``llms.<name>.platform``."""
        return "free"

    @classmethod
    def get_required_env_keys(cls) -> List[str]:
        """No key is required: every free-tier key is optional until chosen."""
        return []

    @classmethod
    def get_env_config_guide(cls) -> Dict[str, str]:
        """Guide for every catalog key, free tier first."""
        guide: Dict[str, str] = {}
        for provider_id in FREE_PRIORITY + PAID_PRIORITY:
            spec = PROVIDERS.get(provider_id)
            if not spec:
                continue
            for env_key in spec["env_keys"]:
                guide[env_key] = (
                    f"{spec['name']} ({spec['tier']}): {spec['note']} "
                    f"Provider id: {provider_id}."
                )
        return guide

    @classmethod
    def get_env_defaults(cls) -> Dict[str, str]:
        """Free tier ships no mandatory environment defaults."""
        return {}
