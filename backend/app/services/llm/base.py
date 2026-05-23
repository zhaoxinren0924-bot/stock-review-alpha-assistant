"""Provider-agnostic LLM interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    """Single-turn model request used by the research assistant."""

    prompt: str
    response_format: str = "json_object"
    temperature: float = 0.2
    max_tokens: int = 1200


@dataclass(frozen=True)
class LLMResponse:
    """Provider-normalized model response."""

    text: str
    provider: str
    model: str


class LLMProvider(Protocol):
    """Common interface for Claude, Kimi, Minimax and compatible APIs."""

    provider_name: str

    def is_configured(self) -> bool:
        """Return whether required credentials are configured."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return model text for a single prompt."""


class LLMProviderError(RuntimeError):
    """Raised when a provider is configured but cannot complete a request."""
