"""LLM provider selection."""

from __future__ import annotations

import os

from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMProvider
from app.services.llm.minimax_anthropic_provider import MinimaxAnthropicProvider
from app.services.llm.openai_compatible_provider import (
    GenericOpenAICompatibleProvider,
    KimiProvider,
    MinimaxProvider,
)


def get_llm_provider() -> LLMProvider | None:
    """Return the configured provider, or None for local fallback."""
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    provider: LLMProvider

    if provider_name in {"anthropic", "claude"}:
        provider = AnthropicProvider()
    elif provider_name in {"kimi", "moonshot"}:
        provider = KimiProvider()
    elif provider_name == "minimax":
        protocol = os.environ.get("MINIMAX_PROTOCOL", "anthropic").lower()
        provider = MinimaxProvider() if protocol in {"openai", "openai_compatible"} else MinimaxAnthropicProvider()
    elif provider_name in {"openai_compatible", "openai-compatible", "generic"}:
        provider = GenericOpenAICompatibleProvider()
    else:
        return None

    return provider if provider.is_configured() else None
