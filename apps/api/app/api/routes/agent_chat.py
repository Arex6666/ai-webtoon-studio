"""POST /v1/agent/chat — main streaming chat entry."""
import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.conversation import Conversation
from app.services.agent.runner import AgentRunner
from app.services.agent.sse import DISPATCHER, stream_response

router = APIRouter(prefix="/v1/agent", tags=["Agent"])
logger = logging.getLogger(__name__)


class ChatContext(BaseModel):
    project_id: str
    episode_number: Optional[int] = None
    chapter_id: Optional[str] = None
    panel_id: Optional[str] = None


class ChatOptions(BaseModel):
    max_steps: Optional[int] = 10
    tools_allowlist: Optional[list[str]] = None
    model: Optional[str] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    context: ChatContext
    options: Optional[ChatOptions] = None


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # Get or create conversation
    if req.conversation_id:
        conv = db.query(Conversation).filter_by(id=req.conversation_id).first()
        if not conv:
            raise HTTPException(404, "Conversation not found")
        if conv.agent_state == "running":
            raise HTTPException(409, "Conversation has an active agent loop (CONVERSATION_BUSY)")
    else:
        conv = Conversation(
            id=str(uuid.uuid4()),
            project_id=req.context.project_id,
            episode_number=req.context.episode_number,
            chapter_id=req.context.chapter_id,
            title=(req.message[:60] or "New chat"),
        )
        db.add(conv)
        db.commit()

    listener_q = await DISPATCHER.register(conv.id)
    runner = AgentRunner(db)
    options_dict = req.options.model_dump() if req.options else {}

    asyncio.create_task(_run_safely(runner, conv.id, req.message, req.context.model_dump(), options_dict))

    async def _stream():
        try:
            async for chunk in stream_response(conv.id, listener_q):
                yield chunk
        finally:
            await DISPATCHER.unregister(conv.id, listener_q)

    return StreamingResponse(_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


async def _run_safely(runner, conversation_id, message, context, options):
    try:
        await runner.run(conversation_id, message, context, options)
    except Exception:
        logger.exception("Agent loop crashed for conversation %s", conversation_id)
        await DISPATCHER.emit(conversation_id, "error", {
            "code": "INTERNAL_ERROR", "message": "Agent loop crashed", "recoverable": False,
        })
        await DISPATCHER.emit(conversation_id, "agent_done", {"reason": "error"})
