"""Look up a chapter previously committed for the same (conversation, episode)."""
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session

from app.models.chapter import Chapter


def find_existing_chapter(
    db: Session, *, project_id: str, conversation_id: str, episode_number: int,
) -> Optional[Chapter]:
    """Scan chapters for matching layout_json.source. O(n) but n is small."""
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
    for ch in chapters:
        source = (ch.layout_json or {}).get("source")
        if not source:
            continue
        if (source.get("type") == "agent"
                and source.get("conversation_id") == conversation_id
                and source.get("episode_number") == episode_number):
            return ch
    return None
