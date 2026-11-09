import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_checkout_exitoso():
    with TestClient(app) as c:
        payload = {
            "cliente_id": "CLI-123",
            "sku": "CAFE-500G",
            "cantidad": 2,
            "medio_pago": "tarjeta",
        }
        res = c.post("/v1/checkout", json=payload, headers={"Idempotency-Key": "key-test-1"})
        assert res.status_code == 200
        data = res.json()
        assert data["estado"] == "CONFIRMADO"
        assert "pedido_id" in data
        assert len(data["pasos"]) == 4


def test_checkout_idempotencia():
    with TestClient(app) as c:
        payload = {
            "cliente_id": "CLI-123",
            "sku": "CAFE-500G",
            "cantidad": 1,
            "medio_pago": "nequi",
        }
        res1 = c.post("/v1/checkout", json=payload, headers={"Idempotency-Key": "key-idempotente-99"})
        res2 = c.post("/v1/checkout", json=payload, headers={"Idempotency-Key": "key-idempotente-99"})
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["pedido_id"] == res2.json()["pedido_id"]


def test_obtener_estado_checkout():
    with TestClient(app) as c:
        res = c.get("/v1/checkout/PED-TEST123/estado")
        assert res.status_code == 200
        data = res.json()
        assert data["pedido_id"] == "PED-TEST123"


def test_vitrina():
    with TestClient(app) as c:
        res = c.get("/v1/vitrina")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) > 0
        assert data["total"] > 0

