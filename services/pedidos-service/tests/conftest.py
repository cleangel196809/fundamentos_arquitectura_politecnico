"""Pruebas con SQLite temporal y bus en memoria (sin PostgreSQL ni Redis)."""
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


@pytest.fixture
def cliente(tmp_path):
    # El publicador automático se apaga para controlar a mano cuándo se publica.
    ajustes = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path}/pedidos.db",
                       event_bus="memory", publicador_activo=False)
    with TestClient(crear_app(ajustes)) as navegador:
        yield navegador
