"""Cancellation — Redis flag checked at agent loop step boundaries."""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300   # 5 minutes


def _key(conversation_id: str) -> str:
    return f"agent:cancel:{conversation_id}"


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def request_cancel(conversation_id: str) -> None:
    """Set the cancel flag with 5-minute TTL. Tolerates Redis errors silently."""
    try:
        r = await _get_redis()
        await r.set(_key(conversation_id), "1", ex=_TTL_SECONDS)
    except Exception as e:
        logger.warning("request_cancel failed for %s: %s", conversation_id, e)


async def is_canceled(conversation_id: str) -> bool:
    """Check whether the cancel flag exists. Treat Redis errors as 'not canceled'."""
    try:
        r = await _get_redis()
        return bool(await r.exists(_key(conversation_id)))
    except Exception as e:
        logger.warning("Cancel check failed (treating as not canceled): %s", e)
        return False


async def clear_cancel(conversation_id: str) -> None:
    """Remove the cancel flag (called when a new agent loop starts)."""
    try:
        r = await _get_redis()
        await r.delete(_key(conversation_id))
    except Exception as e:
        logger.warning("clear_cancel failed for %s: %s", conversation_id, e)
