"""Mock LLMProvider that returns scripted responses — used for runner integration tests."""
import pytest
from typing import AsyncIterator

from app.services.agent.llm_provider import LLMProvider
from app.services.agent.llm_types import StreamChunk


class ScriptedProvider(LLMProvider):
    """Yields a pre-programmed sequence of StreamChunks per call."""

    def __init__(self, scripts: list[list[StreamChunk]]):
        self._scripts = list(scripts)
        self._idx = 0

    async def stream(self, system, messages, tools, model, **kwargs) -> AsyncIterator[StreamChunk]:
        if self._idx >= len(self._scripts):
            raise RuntimeError("ScriptedProvider exhausted")
        for chunk in self._scripts[self._idx]:
            yield chunk
        self._idx += 1

    @property
    def name(self): return "scripted"
    @property
    def supports_tools(self): return True
    @property
    def supports_streaming_tool_calls(self): return True


@pytest.fixture
def db_session():
    """In-memory SQLite session with all models created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Trigger all model registrations
    from app import models  # noqa: F401
    from app.models.base import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
