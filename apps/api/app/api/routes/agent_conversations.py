"""GET/POST/DELETE /api/v1/agent/conversations/* — conversation management."""
from typing import Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.agent.cancellation import request_cancel

router = APIRouter(prefix="/agent/conversations", tags=["Agent"])


class ConversationOut(BaseModel):
    id: str
    project_id: str
    episode_number: Optional[int]
    title: str
    status: str
    agent_state: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("")
def list_conversations(
    project_id: str, episode_number: Optional[int] = None,
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db),
):
    q = db.query(Conversation).filter(
        Conversation.project_id == project_id, Conversation.status != "deleted",
    )
    if episode_number is not None:
        q = q.filter(Conversation.episode_number == episode_number)
    rows = q.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset).all()
    return [ConversationOut.model_validate(r) for r in rows]


@router.get("/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    row = db.query(Conversation).filter_by(id=conv_id).first()
    if not row or row.status == "deleted":
        raise HTTPException(404)
    return row


@router.get("/{conv_id}/messages")
def list_messages(conv_id: str, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    rows = (
        db.query(ConversationMessage)
        .filter_by(conversation_id=conv_id)
        .order_by(ConversationMessage.created_at.asc())
        .limit(limit).offset(offset).all()
    )
    return [{
        "id": m.id, "role": m.role, "content": m.content,
        "tool_calls_json": m.tool_calls_json, "finish_reason": m.finish_reason,
        "trace_id": m.trace_id, "created_at": m.created_at,
    } for m in rows]


@router.post("/{conv_id}/cancel")
async def cancel_conversation(conv_id: str, db: Session = Depends(get_db)):
    row = db.query(Conversation).filter_by(id=conv_id).first()
    if not row:
        raise HTTPException(404)
    await request_cancel(conv_id)
    return {"ok": True}


class CreateConversationRequest(BaseModel):
    project_id: str
    episode_number: Optional[int] = None
    chapter_id: Optional[str] = None
    title: Optional[str] = None


@router.post("", response_model=ConversationOut)
def create_conversation(req: CreateConversationRequest, db: Session = Depends(get_db)):
    conv = Conversation(
        id=str(uuid.uuid4()),
        project_id=req.project_id,
        episode_number=req.episode_number,
        chapter_id=req.chapter_id,
        title=req.title or "New chat",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conv_id}")
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    row = db.query(Conversation).filter_by(id=conv_id).first()
    if not row:
        raise HTTPException(404)
    row.status = "deleted"
    db.commit()
    return {"ok": True}
