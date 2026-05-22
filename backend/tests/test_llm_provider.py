"""Tests for provider-agnostic LLM selection."""

from app.main import parse_llm_json
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.factory import get_llm_provider
from app.services.llm.minimax_anthropic_provider import MinimaxAnthropicProvider
from app.services.llm.openai_compatible_provider import KimiProvider, MinimaxProvider


def test_default_provider_uses_anthropic_when_key_exists(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, AnthropicProvider)


def test_kimi_provider_can_be_selected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.setenv("KIMI_API_KEY", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, KimiProvider)


def test_minimax_provider_can_be_selected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, MinimaxAnthropicProvider)


def test_minimax_openai_provider_can_be_selected(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_PROTOCOL", "openai")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, MinimaxProvider)


def test_unconfigured_provider_returns_none(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    assert get_llm_provider() is None


def test_parse_llm_json_extracts_object_from_text() -> None:
    text = 'Here is JSON:\n```json\n{"reply":"ok","actions":[]}\n```'

    assert parse_llm_json(text) == {"reply": "ok", "actions": []}
