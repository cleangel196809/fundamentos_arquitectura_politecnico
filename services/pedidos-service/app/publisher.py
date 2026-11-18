"""
Background Outbox Publisher.

Reads outbox_events where publicado_en IS NULL, publishes to the event bus,
then marks publicado_en.  Publishing BEFORE marking enables at-least-once
delivery: a crash between publish and mark causes a re-publish on restart.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bus import EventBus
from app.database import get_session_factory
from app.models import OutboxEvent
from app.settings import Settings

logger = logging.getLogger(__name__)

STREAM = "pishop.pedidos"


class OutboxPublisher:
    def __init__(self, settings: Settings, bus: EventBus) -> None:
        self._settings = settings
        self._bus = bus
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="outbox-publisher")
        logger.info("OutboxPublisher started (interval=%ss)", self._settings.publish_interval_seconds)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OutboxPublisher stopped")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._publish_pending()
            except Exception:
                logger.exception("Error in outbox publisher loop")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._settings.publish_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass

    async def publish_once(self) -> int:
        """Publish pending events once; return count published (useful for tests)."""
        return await self._publish_pending()

    async def _publish_pending(self) -> int:
        factory = get_session_factory()
        published = 0
        async with factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.publicado_en.is_(None))
                .order_by(OutboxEvent.creado_en)
                .limit(100)
            )
            events = list(result.scalars().all())

            for event in events:
                try:
                    await self._bus.publish(
                        STREAM,
                        {
                            "evento_id": event.id,
                            "tipo": event.tipo,
                            "payload": event.payload,
                        },
                    )
                    event.publicado_en = datetime.now(timezone.utc)
                    published += 1
                except Exception:
                    logger.exception("Failed to publish event %s", event.id)

            if published > 0:
                await session.commit()

        return published
