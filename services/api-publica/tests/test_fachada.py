import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seguridad import LimitadorTasa

KEY = {"X-API-Key": "clave-de-prueba"}
PRODUCTOS = {"items": [{"sku": "A", "publicado": True}, {"sku": "B", "publicado": False}],
             "total": 2, "pagina": 1, "tamano": 20}
VISTO: list[httpx.Request] = []


def _internos(request: httpx.Request) -> httpx.Response:
    VISTO.append(request)
    ruta = request.url.path
    if ruta == "/v1/productos":
        return httpx.Response(200, json=PRODUCTOS)
    if ruta == "/v1/checkout":
        return httpx.Response(201, json={"pedido_id": "P1", "estado": "CONFIRMADO", "pasos": []})
    if ruta == "/v1/checkout/P1/estado":
        return httpx.Response(200, json={"pedido_id": "P1", "estado": "CONFIRMADO"})
    if ruta == "/v1/checkout/caido/estado":
        raise httpx.ConnectError("caído")
    if ruta == "/v1/checkout/lento/estado":
        raise httpx.ReadTimeout("lento")
    return httpx.Response(404, json={"detalle": "no existe", "codigo": "no_encontrado"})


@pytest.fixture()
def cliente():
    VISTO.clear()
    app.state.limitador = LimitadorTasa(60)
    with TestClient(app) as c:
        app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(_internos))
        yield c


def test_sin_clave_401_problem_json(cliente):
    r = cliente.get("/v1/catalogo/productos")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["status"] == 401


def test_clave_incorrecta_401(cliente):
    assert cliente.get("/v1/catalogo/productos", headers={"X-API-Key": "mala"}).status_code == 401


def test_catalogo_solo_publicados(cliente):
    r = cliente.get("/v1/catalogo/productos", headers=KEY)
    assert r.status_code == 200
    assert [p["sku"] for p in r.json()["items"]] == ["A"]


def test_crear_compra_enruta_al_bff_y_reenvia_idempotency_key(cliente):
    cuerpo = {"cliente_id": "C-1", "sku": "A", "cantidad": 2, "medio_pago": "tarjeta"}
    r = cliente.post("/v1/compras", json=cuerpo, headers={**KEY, "Idempotency-Key": "k-1"})
    assert r.status_code == 201 and r.json()["pedido_id"] == "P1"
    assert VISTO[-1].url.path == "/v1/checkout"
    assert VISTO[-1].headers["Idempotency-Key"] == "k-1"


def test_compra_invalida_422(cliente):
    r = cliente.post("/v1/compras", json={"sku": "A", "cantidad": 0}, headers=KEY)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_estado_compra_y_404(cliente):
    assert cliente.get("/v1/compras/P1", headers=KEY).json()["estado"] == "CONFIRMADO"
    r = cliente.get("/v1/compras/zzz", headers=KEY)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")


def test_upstream_caido_502_y_timeout_504(cliente):
    assert cliente.get("/v1/compras/caido", headers=KEY).status_code == 502
    assert cliente.get("/v1/compras/lento", headers=KEY).status_code == 504


def test_limite_de_tasa_429_con_retry_after(cliente):
    app.state.limitador = LimitadorTasa(3)
    for _ in range(3):
        assert cliente.get("/v1/catalogo/productos", headers=KEY).status_code == 200
    r = cliente.get("/v1/catalogo/productos", headers=KEY)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert r.headers["content-type"].startswith("application/problem+json")


def test_ventana_se_libera_con_el_tiempo():
    t = [0.0]
    lim = LimitadorTasa(2, ventana=60, reloj=lambda: t[0])
    assert lim.intentar("k") is None and lim.intentar("k") is None
    assert lim.intentar("k") == 60
    t[0] = 61
    assert lim.intentar("k") is None
