"""Smoke test for LLMProvider abstract base."""
import pytest

from app.services.agent.llm_provider import LLMProvider, LLMProviderError


def test_cannot_instantiate_abstract_provider():
    with pytest.raises(TypeError):
        LLMProvider()


def test_llm_provider_error_is_exception():
    e = LLMProviderError("boom")
    assert isinstance(e, Exception)
    assert "boom" in str(e)
