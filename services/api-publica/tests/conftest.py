"""Fixtures: la app se prueba sin servicios externos (transporte httpx simulado)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings

CLAVE = "clave-de-prueba-0123456789"   # solo para pruebas; nunca se usa fuera de tests/


def handler_ok(request: httpx.Request) -> httpx.Response:
    """Doble de catalogo-service y checkout-bff que respeta docs/CONTRATOS.md."""
    ruta = request.url.path
    if request.method == "GET" and ruta == "/v1/productos":
        return httpx.Response(200, json={"total": 3, "pagina": 1, "tamano": 20, "items": [
            {"id": 1, "sku": "CAFE-500G", "nombre": "Café", "precio_cop": 18000, "categoria": "cafe", "publicado": True, "costo_interno": 9000},
            {"id": 2, "sku": "PANELA-1K", "nombre": "Panela", "precio_cop": 7000, "categoria": "dulces", "publicado": True},
            {"id": 3, "sku": "BORRADOR-1", "nombre": "Sin publicar", "precio_cop": 1000, "categoria": "x", "publicado": False},
        ]})
    if request.method == "POST" and ruta == "/v1/checkout":
        return httpx.Response(201, json={"pedido_id": "P-1", "estado": "CONFIRMADO", "pasos": [{"paso": "pago", "resultado": "ok"}]})
    if request.method == "GET" and ruta == "/v1/checkout/P-1/estado":
        return httpx.Response(200, json={"pedido_id": "P-1", "estado": "CONFIRMADO"})
    return httpx.Response(404, json={"detalle": "no existe", "codigo": "NO_ENCONTRADO"})


@pytest.fixture
def cliente():
    """Fábrica: cliente(handler=..., **ajustes_de_settings) -> TestClient con lifespan activo."""
    abiertos: list[TestClient] = []

    def fabrica(handler=handler_ok, **ajustes) -> TestClient:
        settings = Settings(_env_file=None, **{"api_key": CLAVE, **ajustes})
        # raise_server_exceptions=False: así vemos el 500 que recibiría un cliente real
        c = TestClient(crear_app(settings, httpx.MockTransport(handler)), raise_server_exceptions=False)
        c.__enter__()
        abiertos.append(c)
        return c

    yield fabrica
    for c in abiertos:
        c.__exit__(None, None, None)


@pytest.fixture
def auth():
    return {"X-API-Key": CLAVE}
