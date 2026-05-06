"""Tests for cancellation Redis flag."""
import pytest

from app.services.agent import cancellation


@pytest.fixture
def fake_redis(monkeypatch):
    import fakeredis.aioredis
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def _get():
        return fake
    monkeypatch.setattr(cancellation, "_get_redis", _get)
    return fake


@pytest.mark.asyncio
async def test_request_and_check_cancel(fake_redis):
    assert not await cancellation.is_canceled("c1")
    await cancellation.request_cancel("c1")
    assert await cancellation.is_canceled("c1")
    await cancellation.clear_cancel("c1")
    assert not await cancellation.is_canceled("c1")


@pytest.mark.asyncio
async def test_cancellation_per_conversation_isolation(fake_redis):
    await cancellation.request_cancel("c1")
    assert await cancellation.is_canceled("c1")
    assert not await cancellation.is_canceled("c2")


@pytest.mark.asyncio
async def test_is_canceled_handles_redis_failure(monkeypatch):
    async def _broken():
        raise ConnectionError("redis down")
    monkeypatch.setattr(cancellation, "_get_redis", _broken)

    # Should not raise; return False on error
    assert await cancellation.is_canceled("any") is False


@pytest.mark.asyncio
async def test_request_cancel_tolerates_redis_failure(monkeypatch):
    async def _broken():
        raise ConnectionError("redis down")
    monkeypatch.setattr(cancellation, "_get_redis", _broken)

    # Should not raise
    await cancellation.request_cancel("any")
