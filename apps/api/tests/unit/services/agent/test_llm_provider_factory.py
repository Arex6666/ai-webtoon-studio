"""Test get_llm_provider factory dispatch."""
import pytest

from app.services.agent.llm_provider import get_llm_provider


def test_factory_invalid_provider_raises(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "nonsense")
    get_llm_provider.cache_clear()
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()
    get_llm_provider.cache_clear()


def test_factory_returns_openai_compatible_for_openai(monkeypatch):
    from app.core import config
    from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config.settings, "OPENAI_API_KEY", "test")
    get_llm_provider.cache_clear()
    p = get_llm_provider()
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.name == "openai"
    get_llm_provider.cache_clear()
