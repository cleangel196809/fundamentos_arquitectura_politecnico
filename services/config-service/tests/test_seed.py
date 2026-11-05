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
        assert c.get("/health/ready").status_code == 200
        assert c.get("/config/catalogo-service/prod").status_code == 404
