"""Tests for the outbox endpoint and publisher marking."""

from __future__ import annotations

import pytest

from app.bus import get_memory_events
from app.database import get_session_factory
from app.models import OutboxEvent
from app.publisher import OutboxPublisher
from app.settings import get_settings

PAYLOAD = {
    "cliente_id": "cli-outbox",
    "sku": "SKU-X1",
    "cantidad": 2,
    "monto_cop": 10000,
}


@pytest.mark.asyncio
async def test_outbox_pendientes_on_create(client):
    """Creating a pedido must leave one pending outbox event."""
    await client.post("/v1/pedidos", json=PAYLOAD)
    resp = await client.get("/v1/outbox/pendientes")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["tipo"] == "PedidoCreado"


@pytest.mark.asyncio
async def test_outbox_pendientes_after_cancel(client):
    """Cancel creates a second pending event."""
    create_resp = await client.post("/v1/pedidos", json=PAYLOAD)
    pedido_id = create_resp.json()["pedido_id"]
    await client.post(f"/v1/pedidos/{pedido_id}/cancelar")

    resp = await client.get("/v1/outbox/pendientes")
    events = resp.json()
    tipos = {e["tipo"] for e in events}
    assert "PedidoCancelado" in tipos


@pytest.mark.asyncio
async def test_publisher_marks_publicado_en(client):
    """After publisher runs, outbox events are marked and no longer pending."""
    await client.post("/v1/pedidos", json=PAYLOAD)

    settings = get_settings()
    from app.bus import MemoryBus
    bus = MemoryBus()
    publisher = OutboxPublisher(settings, bus)

    count = await publisher.publish_once()
    assert count >= 1

    # No more pending
    resp = await client.get("/v1/outbox/pendientes")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_publisher_puts_event_on_bus(client):
    """Publisher puts the PedidoCreado event onto the memory bus."""
    from app.bus import clear_memory_events, get_memory_events
    clear_memory_events()

    await client.post("/v1/pedidos", json=PAYLOAD)

    settings = get_settings()
    from app.bus import MemoryBus
    bus = MemoryBus()
    publisher = OutboxPublisher(settings, bus)
    await publisher.publish_once()

    events = get_memory_events()
    assert len(events) >= 1
    tipos = [e["tipo"] for e in events]
    assert "PedidoCreado" in tipos
