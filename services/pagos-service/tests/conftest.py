"""La pasarela simulada se llama en memoria (ASGITransport): sin red ni puertos."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


@pytest.fixture
def fabricar(tmp_path):
    abiertos = []

    def _crear(modo="ok", transporte=None):
        ajustes = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path}/pagos-{len(abiertos)}.db",
                           pasarela_modo=modo, pasarela_url="http://pagos.local/_simulador/pasarela/cobrar")
        aplicacion = crear_app(ajustes)
        aplicacion.state.transporte_pasarela = transporte or httpx.ASGITransport(app=aplicacion)
        navegador = TestClient(aplicacion)
        navegador.__enter__()
        abiertos.append(navegador)
        return navegador

    yield _crear
    for navegador in abiertos:
        navegador.__exit__(None, None, None)
