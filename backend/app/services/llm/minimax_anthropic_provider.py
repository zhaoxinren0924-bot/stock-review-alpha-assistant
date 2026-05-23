"""MiniMax Anthropic-compatible provider."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.llm.base import LLMProviderError, LLMRequest, LLMResponse


class MinimaxAnthropicProvider:
    """MiniMax adapter for Anthropic-compatible /v1/messages endpoints."""

    provider_name = "minimax"

    def __init__(self) -> None:
        self.api_key = os.environ.get("MINIMAX_API_KEY")
        self.base_url = os.environ.get("MINIMAX_ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic").rstrip("/")
        self.model = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("MINIMAX_API_KEY is required")

        payload = {
            "model": self.model,
            "max_tokens": max(request.max_tokens, int(os.environ.get("MINIMAX_MIN_OUTPUT_TOKENS", "2000"))),
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        http_request = Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=60) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
            text_parts: list[str] = []
            for block in data.get("content", []):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
            text = "".join(text_parts)
            if not text:
                raise LLMProviderError("MiniMax Anthropic response did not include text content")
            return LLMResponse(text=text, provider=self.provider_name, model=self.model)
        except (HTTPError, URLError, json.JSONDecodeError) as exc:
            raise LLMProviderError(str(exc)) from exc
