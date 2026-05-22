"""OpenAI-compatible chat completion provider for Kimi, Minimax and others."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.services.llm.base import LLMProviderError, LLMRequest, LLMResponse


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible adapter using stdlib HTTP."""

    def __init__(
        self,
        *,
        provider_name: str,
        api_key_env: str,
        base_url_env: str,
        model_env: str,
        default_base_url: str,
        default_model: str,
    ) -> None:
        self.provider_name = provider_name
        self.api_key = os.environ.get(api_key_env)
        self.base_url = os.environ.get(base_url_env, default_base_url).rstrip("/")
        self.model = os.environ.get(model_env, default_model)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError(f"{self.provider_name} API key is required")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        http_request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=60) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str):
                raise LLMProviderError("Provider response content is not text")
            return LLMResponse(text=text, provider=self.provider_name, model=self.model)
        except (HTTPError, URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMProviderError(str(exc)) from exc


class KimiProvider(OpenAICompatibleProvider):
    """Moonshot/Kimi OpenAI-compatible provider."""

    def __init__(self) -> None:
        super().__init__(
            provider_name="kimi",
            api_key_env="KIMI_API_KEY",
            base_url_env="KIMI_BASE_URL",
            model_env="KIMI_MODEL",
            default_base_url="https://api.moonshot.cn/v1",
            default_model="moonshot-v1-8k",
        )


class MinimaxProvider(OpenAICompatibleProvider):
    """Minimax OpenAI-compatible provider."""

    def __init__(self) -> None:
        super().__init__(
            provider_name="minimax",
            api_key_env="MINIMAX_API_KEY",
            base_url_env="MINIMAX_BASE_URL",
            model_env="MINIMAX_MODEL",
            default_base_url="https://api.minimax.chat/v1",
            default_model="abab6.5s-chat",
        )


class GenericOpenAICompatibleProvider(OpenAICompatibleProvider):
    """User-defined OpenAI-compatible provider."""

    def __init__(self) -> None:
        super().__init__(
            provider_name=os.environ.get("LLM_PROVIDER_NAME", "openai_compatible"),
            api_key_env="LLM_API_KEY",
            base_url_env="LLM_BASE_URL",
            model_env="LLM_MODEL",
            default_base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
        )
