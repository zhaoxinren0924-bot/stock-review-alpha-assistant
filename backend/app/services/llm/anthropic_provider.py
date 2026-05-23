"""Anthropic Claude provider."""

from __future__ import annotations

import os
from importlib import import_module

from app.services.llm.base import LLMProviderError, LLMRequest, LLMResponse


class AnthropicProvider:
    """Claude Messages API adapter."""

    provider_name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        self.model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_MODEL", "claude-3-5-haiku-latest")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY or CLAUDE_API_KEY is required")
        try:
            anthropic_module = import_module("anthropic")
            client = anthropic_module.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                messages=[{"role": "user", "content": request.prompt}],
            )
            text_parts: list[str] = []
            for block in response.content:
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str):
                    text_parts.append(block_text)
            return LLMResponse(text="".join(text_parts), provider=self.provider_name, model=self.model)
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
