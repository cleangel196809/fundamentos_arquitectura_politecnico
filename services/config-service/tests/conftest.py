"""Fixtures comunes: base SQLite en memoria y semilla vacía (sin servicios externos)."""
import pytest
from fastapi.testclient import TestClient

# Token de PRUEBA (no es un secreto real): se inyecta por variable de entorno como en producción.
TOKEN = "token-de-prueba-p08"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _token_de_la_api(monkeypatch):
    monkeypatch.setenv("PISHOP_API_TOKEN", TOKEN)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    vacia = tmp_path / "seed.json"
    vacia.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PISHOP_SEED_PATH", str(vacia))
    monkeypatch.setenv("PISHOP_APP_ENV", "dev")
    from app.main import app

    with TestClient(app, headers=AUTH) as c:   # `with` dispara el lifespan
        yield c
