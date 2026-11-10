"""
At-least-once delivery test.

Demonstrates that the outbox publisher re-publishes events whose publicado_en
is still NULL (i.e. a crash between publish and mark causes a re-publish).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.bus import MemoryBus, clear_memory_events, get_memory_events
from app.database import get_session_factory
from app.models import OutboxEvent, Pedido
from app.publisher import OutboxPublisher
from app.settings import get_settings

STREAM = "pishop.pedidos"


async def _create_raw_outbox_event(pedido_id: str, tipo: str) -> OutboxEvent:
    """Insert an outbox event directly (publicado_en = None)."""
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            event = OutboxEvent(
                id=str(uuid.uuid4()),
                pedido_id=pedido_id,
                tipo=tipo,
                payload=json.dumps(
                    {
                        "pedido_id": pedido_id,
                        "cliente_id": "cli-test",
                        "sku": "SKU-AT",
                        "cantidad": 1,
                        "monto_cop": 5000,
                        "ocurrido_en": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                publicado_en=None,
            )
            session.add(event)
    return event


async def _create_raw_pedido() -> Pedido:
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            pedido = Pedido(
                cliente_id="cli-at",
                sku="SKU-AT",
                cantidad=1,
                monto_cop=5000,
            )
            session.add(pedido)
    return pedido


@pytest.mark.asyncio
async def test_at_least_once_publishes_pending():
    """
    Scenario: outbox event exists with publicado_en=NULL.
    Publisher must publish it and then mark it.
    """
    pedido = await _create_raw_pedido()
    event = await _create_raw_outbox_event(pedido.id, "PedidoCreado")

    bus = MemoryBus()
    clear_memory_events()

    settings = get_settings()
    publisher = OutboxPublisher(settings, bus)
    count = await publisher.publish_once()

    assert count >= 1
    mem_events = get_memory_events()
    assert any(e["tipo"] == "PedidoCreado" for e in mem_events)

    # Event must now be marked
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event.id))
        saved = result.scalar_one()
        assert saved.publicado_en is not None


@pytest.mark.asyncio
async def test_at_least_once_republishes_if_not_marked():
    """
    Simulate crash: event exists with publicado_en=NULL even though it was
    'conceptually' published once.  Running the publisher again re-publishes it
    and then marks it.
    """
    pedido = await _create_raw_pedido()
    # Intentionally leave publicado_en=None (simulates crash after publish but before mark)
    event = await _create_raw_outbox_event(pedido.id, "PedidoCreado")

    bus = MemoryBus()
    clear_memory_events()

    settings = get_settings()
    publisher = OutboxPublisher(settings, bus)

    # First run
    await publisher.publish_once()
    count_first = len(get_memory_events())

    # Manually reset publicado_en back to None to simulate the crash scenario
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            result = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event.id))
            ev = result.scalar_one()
            ev.publicado_en = None
            session.add(ev)

    clear_memory_events()

    # Second run – must re-publish
    count2 = await publisher.publish_once()
    assert count2 >= 1
    assert len(get_memory_events()) >= 1


@pytest.mark.asyncio
async def test_already_marked_events_not_republished():
    """Events already marked publicado_en must NOT be re-published."""
    pedido = await _create_raw_pedido()
    event = await _create_raw_outbox_event(pedido.id, "PedidoCreado")

    # Pre-mark the event
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            result = await session.execute(select(OutboxEvent).where(OutboxEvent.id == event.id))
            ev = result.scalar_one()
            ev.publicado_en = datetime.now(timezone.utc)
            session.add(ev)

    bus = MemoryBus()
    clear_memory_events()
    settings = get_settings()
    publisher = OutboxPublisher(settings, bus)
    count = await publisher.publish_once()

    assert count == 0
    assert get_memory_events() == []
