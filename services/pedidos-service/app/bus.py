"""
Event bus abstraction.

PISHOP_EVENT_BUS=memory  → in-process list (for tests)
PISHOP_EVENT_BUS=redis   → Redis Streams via redis.asyncio
"""

from __future__ import annotations

import uuid
from typing import Any

from app.settings import Settings

# Module-level store for MemoryBus – accessible from tests
_memory_events: list[dict[str, Any]] = []


def get_memory_events() -> list[dict[str, Any]]:
    """Return reference to the in-memory event list (for tests)."""
    return _memory_events


def clear_memory_events() -> None:
    _memory_events.clear()


class EventBus:
    async def publish(self, stream: str, fields: dict[str, str]) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        pass


class MemoryBus(EventBus):
    """Synchronous in-memory bus – no external dependencies."""

    async def publish(self, stream: str, fields: dict[str, str]) -> str:
        event_id = str(uuid.uuid4())
        _memory_events.append({"stream": stream, "id": event_id, **fields})
        return event_id


class RedisBus(EventBus):
    """Redis Streams bus using redis.asyncio."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis  # type: ignore

        self._client = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, stream: str, fields: dict[str, str]) -> str:
        msg_id = await self._client.xadd(stream, fields)
        return str(msg_id)

    async def close(self) -> None:
        await self._client.aclose()


def get_bus(settings: Settings) -> EventBus:
    if settings.event_bus.lower() == "redis":
        return RedisBus(settings.redis_url)
    return MemoryBus()
