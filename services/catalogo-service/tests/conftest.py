"""Las pruebas corren con SQLite en una carpeta temporal: no necesitan PostgreSQL."""
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


@pytest.fixture
def cliente(tmp_path):
    ajustes = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path}/catalogo.db")
    with TestClient(crear_app(ajustes)) as navegador:   # `with` dispara el lifespan
        yield navegador
