"""ModelRouter — selects model per agent step based on context.

Three tiers:
- FLAGSHIP: complex reasoning, first step
- MID: tool-result summarization
- FAST: simple chat, no tool history
"""
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class StepContext:
    is_first_step: bool
    has_tool_results: bool      # any tool calls executed in earlier steps
    is_simple_chat: bool         # no tools available OR no tool calls in last step
    user_force_model: str | None = None


class ModelRouter:
    def select(self, sc: StepContext) -> str:
        if sc.user_force_model:
            return sc.user_force_model
        if sc.is_simple_chat:
            return settings.LLM_MODEL_FAST
        if sc.has_tool_results and not sc.is_first_step:
            return settings.LLM_MODEL_MID
        return settings.LLM_MODEL_FLAGSHIP


MODEL_ROUTER = ModelRouter()
