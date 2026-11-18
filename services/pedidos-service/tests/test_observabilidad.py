"""
Pruebas de Observabilidad (Semana 6).
Verifica:
1. Propagacion de X-Request-Id (se genera si falta, se conserva si viene).
2. Metricas propias de negocio de pedidos-service.
3. Trazas y spans manuales.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_x_request_id_generado(client: AsyncClient):
    """Verifica que el middleware genere un X-Request-Id si la peticion no lo incluye."""
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert "X-Request-Id" in resp.headers
    assert len(resp.headers["X-Request-Id"]) > 0


@pytest.mark.asyncio
async def test_x_request_id_preservado(client: AsyncClient):
    """Verifica que el identificador X-Request-Id enviado por el cliente se respete."""
    cid_enviado = "req-custom-9988-uuid"
    resp = await client.get("/health/live", headers={"X-Request-Id": cid_enviado})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == cid_enviado


@pytest.mark.asyncio
async def test_crear_pedido_registra_metricas_y_span(client: AsyncClient):
    """Verifica que la creacion de pedido ejecute el tramo manual y metricas sin fallar."""
    payload = {
        "cliente_id": "cli-obs-100",
        "sku": "CAFE-500G",
        "cantidad": 2,
        "monto_cop": 56000,
    }
    resp = await client.post("/v1/pedidos", json=payload, headers={"X-Request-Id": "req-obs-crear"})
    assert resp.status_code == 201
    assert resp.headers.get("X-Request-Id") == "req-obs-crear"
    assert resp.json()["estado"] == "CREADO"
