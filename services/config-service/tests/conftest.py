import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


@pytest.fixture
def cliente():
    with TestClient(crear_app(Settings(_env_file=None))) as navegador:
        yield navegador


@pytest.fixture
def cliente_protegido():
    with TestClient(crear_app(Settings(_env_file=None, admin_token="token-admin-de-prueba-123"))) as navegador:
        yield navegador
