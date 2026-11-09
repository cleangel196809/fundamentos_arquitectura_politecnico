"""Token de la API: todo /config/* exige Authorization: Bearer <PISHOP_API_TOKEN>; las sondas no."""
import asyncio

import httpx
from fastapi.testclient import TestClient

from app.config_client import ConfigClient
from app.main import app
from tests.conftest import TOKEN

RUTAS = [
    ("GET", "/config/catalogo-service/prod"),
    ("PUT", "/config/catalogo-service/prod"),
    ("GET", "/config/catalogo-service/prod/versions"),
    ("POST", "/config/catalogo-service/prod/rollback/1"),
    ("GET", "/config/catalogo-service/prod/eventos"),
]


def test_sin_token_todo_config_responde_401(client):
    with TestClient(app) as anonimo:  # sin cabecera Authorization
        for metodo, ruta in RUTAS:
            r = anonimo.request(metodo, ruta, json={"data": {"a": 1}}, headers={"X-Autor": "fnavarro"})
            assert r.status_code == 401, f"{metodo} {ruta} debió exigir token"
            assert r.json()["codigo"] == "TOKEN_INVALIDO"
            assert r.headers["WWW-Authenticate"] == "Bearer"


def test_token_incorrecto_responde_401(client):
    with TestClient(app, headers={"Authorization": "Bearer otro-token"}) as intruso:
        assert intruso.get("/config/catalogo-service/prod").status_code == 401


def test_token_correcto_permite_leer_y_escribir(client):
    r = client.put("/config/catalogo-service/prod", json={"data": {"a": 1}}, headers={"X-Autor": "fnavarro"})
    assert r.status_code == 201
    assert client.get("/config/catalogo-service/prod").status_code == 200


def test_sondas_no_exigen_token(client):
    with TestClient(app) as anonimo:
        assert anonimo.get("/health/live").status_code == 200
        assert anonimo.get("/health/startup").status_code == 200
        assert anonimo.get("/health/ready").status_code == 200


def test_sin_token_configurado_la_api_queda_cerrada_503(client, monkeypatch):
    monkeypatch.setenv("PISHOP_API_TOKEN", "")
    r = client.get("/config/catalogo-service/prod")
    assert r.status_code == 503 and r.json()["codigo"] == "TOKEN_NO_CONFIGURADO"


def test_config_client_envia_el_token_como_bearer():
    vistos = []

    def _servidor(request: httpx.Request) -> httpx.Response:
        vistos.append(request.headers.get("Authorization"))
        return httpx.Response(200, headers={"ETag": '"v1"'}, json={"version": 1, "data": {}})

    cliente = ConfigClient(
        base_url="http://config-service:8010", service_name="catalogo-service",
        transport=httpx.MockTransport(_servidor), api_token=TOKEN,
    )
    assert asyncio.run(cliente.refrescar()) is True
    assert vistos == [f"Bearer {TOKEN}"]
