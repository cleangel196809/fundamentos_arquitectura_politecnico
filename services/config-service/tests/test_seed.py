"""Activity 5: carga de seed.json (7 servicios x 4 entornos) y arranque con semilla vacía."""
from fastapi.testclient import TestClient

from app.main import RUTA_SEED_POR_DEFECTO, app

SERVICIOS_DOMINIO = (
    "catalogo-service",
    "inventario-service",
    "pedidos-service",
    "pagos-service",
    "notificaciones-service",
    "checkout-bff",
    "api-publica",
)
ENTORNOS = ("dev", "qa", "stg", "prod")


def test_seed_json_carga_los_7_servicios_en_los_4_entornos(monkeypatch):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PISHOP_SEED_PATH", str(RUTA_SEED_POR_DEFECTO))
    with TestClient(app) as c:
        for srv in SERVICIOS_DOMINIO:
            for env in ENTORNOS:
                r = c.get(f"/config/{srv}/{env}")
                assert r.status_code == 200, f"Falta semilla para {srv}/{env}"
                cuerpo = r.json()
                assert cuerpo["version"] == 1
                assert cuerpo["autor"] == "seed"
                assert isinstance(cuerpo["data"], dict) and len(cuerpo["data"]) > 0


def test_arranca_con_configuracion_vacia_si_no_hay_seed(monkeypatch, tmp_path):
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PISHOP_SEED_PATH", str(tmp_path / "no-existe.json"))
    with TestClient(app) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/startup").status_code == 200
        assert c.get("/health/ready").status_code == 200  # en dev permite config_version == 0
        assert c.get("/config/catalogo-service/prod").status_code == 404


def test_ready_devuelve_503_en_qa_si_no_hay_configuracion_aplicada(monkeypatch, tmp_path):
    # Criterio 2 y 3 del reto 4.1: arranca en qa aunque no haya semilla/configuración,
    # pero /health/ready responde 503 mientras config_version == 0.
    monkeypatch.setenv("PISHOP_APP_ENV", "qa")
    monkeypatch.setenv("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PISHOP_SEED_PATH", str(tmp_path / "no-existe.json"))
    with TestClient(app) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/startup").status_code == 200
        r = c.get("/health/ready")
        assert r.status_code == 503 and r.json()["config_version"] == 0
