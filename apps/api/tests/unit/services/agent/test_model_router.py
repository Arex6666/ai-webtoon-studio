from app.services.agent.model_router import ModelRouter, StepContext
from app.core.config import settings


def test_force_overrides():
    r = ModelRouter()
    sc = StepContext(is_first_step=True, has_tool_results=False, is_simple_chat=False,
                     user_force_model="custom-model")
    assert r.select(sc) == "custom-model"


def test_simple_chat_picks_fast():
    r = ModelRouter()
    sc = StepContext(is_first_step=True, has_tool_results=False, is_simple_chat=True)
    assert r.select(sc) == settings.LLM_MODEL_FAST


def test_tool_summary_picks_mid():
    r = ModelRouter()
    sc = StepContext(is_first_step=False, has_tool_results=True, is_simple_chat=False)
    assert r.select(sc) == settings.LLM_MODEL_MID


def test_default_picks_flagship():
    r = ModelRouter()
    sc = StepContext(is_first_step=True, has_tool_results=False, is_simple_chat=False)
    assert r.select(sc) == settings.LLM_MODEL_FLAGSHIP
