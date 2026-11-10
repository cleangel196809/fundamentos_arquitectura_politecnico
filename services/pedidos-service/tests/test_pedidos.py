"""Tests for POST/GET/CANCEL pedidos endpoints and idempotency-key."""

from __future__ import annotations

import pytest


PAYLOAD = {
    "cliente_id": "cli-001",
    "sku": "SKU-ABC",
    "cantidad": 3,
    "monto_cop": 56000,
}


@pytest.mark.asyncio
async def test_crear_pedido_201(client):
    resp = await client.post("/v1/pedidos", json=PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "pedido_id" in body
    assert body["estado"] == "CREADO"


@pytest.mark.asyncio
async def test_crear_pedido_missing_field_422(client):
    resp = await client.post("/v1/pedidos", json={"cliente_id": "cli-001"})
    assert resp.status_code == 422
    body = resp.json()
    assert "detalle" in body
    assert "codigo" in body


@pytest.mark.asyncio
async def test_obtener_pedido_200(client):
    create_resp = await client.post("/v1/pedidos", json=PAYLOAD)
    pedido_id = create_resp.json()["pedido_id"]

    resp = await client.get(f"/v1/pedidos/{pedido_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pedido_id"] == pedido_id
    assert body["cliente_id"] == PAYLOAD["cliente_id"]
    assert body["sku"] == PAYLOAD["sku"]
    assert body["cantidad"] == PAYLOAD["cantidad"]
    assert body["monto_cop"] == PAYLOAD["monto_cop"]
    assert body["estado"] == "CREADO"


@pytest.mark.asyncio
async def test_obtener_pedido_404(client):
    resp = await client.get("/v1/pedidos/no-existe-este-id")
    assert resp.status_code == 404
    body = resp.json()
    # FastAPI wraps HTTPException detail in {"detail": ...}
    assert "detail" in body or "detalle" in str(body)


@pytest.mark.asyncio
async def test_cancelar_pedido(client):
    create_resp = await client.post("/v1/pedidos", json=PAYLOAD)
    pedido_id = create_resp.json()["pedido_id"]

    cancel_resp = await client.post(f"/v1/pedidos/{pedido_id}/cancelar")
    assert cancel_resp.status_code == 200
    body = cancel_resp.json()
    assert body["estado"] == "CANCELADO"


@pytest.mark.asyncio
async def test_cancelar_idempotente(client):
    """Cancelling twice must succeed both times and keep state CANCELADO."""
    create_resp = await client.post("/v1/pedidos", json=PAYLOAD)
    pedido_id = create_resp.json()["pedido_id"]

    await client.post(f"/v1/pedidos/{pedido_id}/cancelar")
    cancel2 = await client.post(f"/v1/pedidos/{pedido_id}/cancelar")
    assert cancel2.status_code == 200
    assert cancel2.json()["estado"] == "CANCELADO"


@pytest.mark.asyncio
async def test_cancelar_404(client):
    resp = await client.post("/v1/pedidos/no-existe/cancelar")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_response(client):
    headers = {"Idempotency-Key": "test-idem-key-001"}

    resp1 = await client.post("/v1/pedidos", json=PAYLOAD, headers=headers)
    assert resp1.status_code == 201
    pedido_id_1 = resp1.json()["pedido_id"]

    # Second call with same key – must return same pedido_id, no new pedido
    resp2 = await client.post("/v1/pedidos", json=PAYLOAD, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["pedido_id"] == pedido_id_1


@pytest.mark.asyncio
async def test_idempotency_key_different_keys(client):
    resp1 = await client.post(
        "/v1/pedidos", json=PAYLOAD, headers={"Idempotency-Key": "key-A"}
    )
    resp2 = await client.post(
        "/v1/pedidos", json=PAYLOAD, headers={"Idempotency-Key": "key-B"}
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    # Different keys → different pedido_ids
    assert resp1.json()["pedido_id"] != resp2.json()["pedido_id"]
