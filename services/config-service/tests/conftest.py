"""Fixtures comunes: base SQLite en memoria y semilla vacía (sin servicios externos)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    vacia = tmp_path / "seed.json"
    vacia.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("PISHOP_SEED_PATH", str(vacia))
    from app.main import app

    with TestClient(app) as c:   # `with` dispara el lifespan
        yield c
