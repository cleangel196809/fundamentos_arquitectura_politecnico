"""Al arrancar, la consola muestra las direcciones para abrir con un clic."""
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TOKEN


def test_al_arrancar_muestra_las_direcciones(capsys, monkeypatch):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    with TestClient(app):
        pass
    salida = capsys.readouterr().out
    for ruta in ("/docs", "/health/live", "/health/ready", "/health/startup", "/openapi.json"):
        assert f"http://127.0.0.1:8010{ruta}" in salida
    assert TOKEN in salida  # en dev muestra el token de prueba


def test_fuera_de_dev_no_muestra_el_token(capsys, monkeypatch):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PISHOP_APP_ENV", "prod")
    with TestClient(app):
        pass
    salida = capsys.readouterr().out
    assert "http://127.0.0.1:8010/docs" in salida and TOKEN not in salida
