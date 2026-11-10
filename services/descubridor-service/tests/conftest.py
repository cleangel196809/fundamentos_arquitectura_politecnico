"""Consul falso: tres instancias de catalogo-service, todas 'passing'."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


def consul_falso(peticion: httpx.Request) -> httpx.Response:
    if peticion.url.path == "/v1/catalog/services":
        return httpx.Response(200, json={"consul": [], "catalogo-service": [], "pedidos-service": []})
    if peticion.url.path == "/v1/health/service/catalogo-service":
        return httpx.Response(200, json=[{"Service": {"ID": f"cat-{n}", "Address": f"10.0.0.{n}", "Port": 8001}} for n in (1, 2, 3)])
    return httpx.Response(200, json=[])


@pytest.fixture
def cliente():
    with TestClient(crear_app(Settings(_env_file=None), httpx.MockTransport(consul_falso))) as navegador:
        yield navegador
