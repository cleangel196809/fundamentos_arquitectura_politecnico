"""Swagger listo para probar: campos editables, ejemplos y, solo en dev, autorizado con el token."""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TOKEN


def test_docs_en_dev_viene_autorizado_y_con_try_it_out(client):
    html = client.get("/docs").text
    assert '"tryItOutEnabled": true' in html
    assert "authActions.authorize" in html and TOKEN in html


def test_docs_fuera_de_dev_no_expone_el_token(client, monkeypatch):
    monkeypatch.setenv("PISHOP_APP_ENV", "prod")
    html = client.get("/docs").text
    assert '"tryItOutEnabled": true' in html
    assert TOKEN not in html and "authActions.authorize" not in html


def test_docs_no_exige_token():
    with TestClient(app) as anonimo:
        assert anonimo.get("/docs").status_code == 200


def test_openapi_trae_ejemplos_para_probar(client):
    spec = client.get("/openapi.json").json()
    put = spec["paths"]["/config/{app_name}/{env}"]["put"]
    params = {p["name"]: p for p in put["parameters"]}
    assert params["app_name"]["examples"]["catalogo"]["value"] == "catalogo-service"
    assert params["x-autor"]["examples"]["autor"]["value"] == "fnavarro"


def test_put_se_muestra_en_verde_en_swagger(client):
    html = client.get("/docs").text
    assert ".opblock.opblock-put .opblock-summary-method{background:#49cc90!important}" in html
    assert html.index("swagger-ui.css") < html.index("opblock-put")  # el estilo va después del CSS de Swagger
