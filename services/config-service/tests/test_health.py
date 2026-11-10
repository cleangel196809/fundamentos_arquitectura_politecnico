import asyncio

from fastapi.testclient import TestClient

from app import main as main_mod
from app.main import app


def test_las_tres_sondas():
    with TestClient(app) as c:   # `with` dispara el lifespan
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/startup").status_code == 200
        r = c.get("/health/ready")
        assert r.status_code == 200 and "config_version" in r.json()


def test_readiness_devuelve_503_si_base_de_datos_falla_pero_liveness_sigue_200(client):
    # Semántica diferenciada (semana 4): caída de BD saca la instancia del balanceo (ready=503)
    # sin reiniciar el contenedor (live=200).
    asyncio.run(main_mod.ESTADO["repo"].cerrar())
    assert client.get("/health/live").status_code == 200
    r_ready = client.get("/health/ready")
    assert r_ready.status_code == 503
    assert r_ready.json()["ready"] is False and r_ready.json()["base_datos"] is False
