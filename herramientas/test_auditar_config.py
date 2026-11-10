"""Pruebas del auditor: demuestran que DETECTA violaciones reales y no marca código limpio.

Ejecutar:  python -m pytest herramientas -q
"""
from pathlib import Path

import pytest

import auditar_config as aud

RAIZ = Path(__file__).resolve().parent.parent


def repo(tmp_path: Path, codigo: dict[str, str] | None = None, compose: str | None = None, extra: dict[str, str] | None = None) -> Path:
    """Crea un repositorio mínimo: services/svc/app/<archivo>.py, docker-compose.yml y otros archivos."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for nombre, texto in (codigo or {}).items():
        f = tmp_path / "services" / "svc" / "app" / nombre
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(texto, encoding="utf-8")
    if compose is not None:
        (tmp_path / "docker-compose.yml").write_text(compose, encoding="utf-8")
    for nombre, texto in (extra or {}).items():
        f = tmp_path / nombre
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(texto, encoding="utf-8")
    return tmp_path


def reglas(raiz: Path, **kw) -> list[str]:
    return [h.regla for h in aud.auditar(raiz, **kw)]


# ------------------------------------------------------------------------- R1
def test_detecta_el_ejemplo_inseguro_del_pdf_sin_filtrar_el_secreto(tmp_path):
    r = repo(tmp_path, {"main.py": 'if not api_key or api_key != "secret_pishop_key_2026":\n    raise ValueError\n'})
    hallazgos = aud.auditar(r)
    assert [h.regla for h in hallazgos] == ["R1"]
    assert "secret_pishop_key_2026" not in hallazgos[0].detalle   # el informe enmascara el literal


@pytest.mark.parametrize("linea", [
    'DB_PASSWORD = "PiSh0p_2026!"',
    'password: str = "abc12345"',
    'cfg = {"token": "abcd1234"}',
    'INVENTARIO_URL = "http://10.0.3.17:8002"',
    'REDIS = "redis://10.0.0.5:6379"',
    'engine = crear("postgresql://app:clave123@db/pishop")',
])
def test_detecta_cadenas_sensibles(tmp_path, linea):
    assert reglas(repo(tmp_path, {"m.py": linea + "\n"})) == ["R1"]


@pytest.mark.parametrize("linea", [
    "db_password: SecretStr = Field(..., description='x')",
    "clave = settings.db_password.get_secret_value()",
    'api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)',
    'headers = {"X-API-Key": clave}',
    'token = os.environ["PISHOP_TOKEN"]',
    'raise HTTPException(401, detail="Falta o es inválida la cabecera X-API-Key")',
])
def test_no_marca_codigo_limpio(tmp_path, linea):
    assert reglas(repo(tmp_path, {"m.py": linea + "\n"})) == []


def test_settings_puede_tener_defaults_pero_no_ips_ni_credenciales(tmp_path):
    limpio = 'from pydantic import SecretStr\nclass S(BaseSettings):\n    database_password: SecretStr = SecretStr("cambiar-en-entorno")\n'
    assert reglas(repo(tmp_path, {"settings.py": limpio})) == []
    sucio = 'url = "postgresql://app:clave123@db/x"\nhost = "10.0.0.5"\n'
    assert reglas(repo(tmp_path / "otro", {"settings.py": sucio})) == ["R1", "R1"]   # credenciales + IP


# ------------------------------------------------------------------------- R2
def test_r2_campo_sensible_debe_ser_secretstr(tmp_path):
    malo = "class Settings(BaseSettings):\n    api_key: str\n    db_password: SecretStr\n"
    hallazgos = aud.auditar(repo(tmp_path, {"settings.py": malo}))
    assert [(h.regla, "api_key" in h.detalle) for h in hallazgos] == [("R2", True)]


# ------------------------------------------------------------------------- R3
@pytest.mark.parametrize("codigo,esperado", [
    ("c = httpx.AsyncClient()", ["R3"]),
    ("c = httpx.AsyncClient(timeout=None)", ["R3"]),
    ("c = httpx.Client(base_url='x')", ["R3"]),
    ("r = httpx.get(url)", ["R3"]),
    ("c = AsyncClient()", ["R3"]),
    ("c = httpx.AsyncClient(timeout=httpx.Timeout(2.0))", []),
    ("r = httpx.get(url, timeout=2)", []),
    ("c = httpx.AsyncClient(**opciones)", []),     # no se puede saber: no se acusa sin evidencia
])
def test_r3_timeouts_explicitos(tmp_path, codigo, esperado):
    assert reglas(repo(tmp_path, {"m.py": "import httpx\n" + codigo + "\n"})) == esperado


# ------------------------------------------------------------------------- R4
def test_r4_secretos_en_compose_y_dockerfile(tmp_path):
    compose = "services:\n  db:\n    environment:\n      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?defina en .env}\n"
    assert reglas(repo(tmp_path, compose=compose)) == []
    malo = "services:\n  db:\n    environment:\n      POSTGRES_PASSWORD: super-secreta\n"
    assert reglas(repo(tmp_path / "a", compose=malo)) == ["R4"]
    assert reglas(repo(tmp_path / "b", extra={"services/svc/Dockerfile": "ENV PISHOP_API_KEY=abc123\n"})) == ["R4"]
    assert reglas(repo(tmp_path / "c", extra={"services/svc/Dockerfile": "ENV PISHOP_HTTP_PORT=8000\nARG TOKEN\n"})) == []


# ------------------------------------------------------------------------- R5
BASE = """services:
  api-publica:
    ports: ["8000:8000"]
  redis:
    ports: ["6379:6379"]
  postgres:
    image: postgres:17
"""


def test_r5_detecta_puertos_expuestos(tmp_path):
    hallazgos = aud.auditar(repo(tmp_path, compose=BASE))
    assert [h.regla for h in hallazgos] == ["R5"] and "redis" in hallazgos[0].detalle and "6379" in hallazgos[0].detalle


def test_r5_el_override_con_reset_aisla_la_red(tmp_path):
    r = repo(tmp_path, compose=BASE, extra={"docker-compose.seguro.yml": "services:\n  redis:\n    ports: !reset []\n"})
    assert reglas(r) == []


def test_r5_override_sin_reset_no_quita_puertos_y_postgres_publico_se_detecta(tmp_path):
    r = repo(tmp_path, compose=BASE + "    ports:\n      - '5432:5432'\n", extra={"docker-compose.seguro.yml": "services:\n  redis:\n    environment: {A: b}\n"})
    detalles = " ".join(h.detalle for h in aud.auditar(r))
    assert "redis publica el puerto 6379" in detalles and "postgres publica el puerto 5432" in detalles


def test_r5_loopback_y_formas_largas(tmp_path):
    compose = ("services:\n  postgres:\n    ports:\n      - '127.0.0.1:5432:5432'\n"
               "  redis:\n    ports:\n      - target: 6379\n        published: 6379\n")
    detalles = [h.detalle for h in aud.auditar(repo(tmp_path, compose=compose))]
    assert len(detalles) == 1 and "redis" in detalles[0]   # loopback permitido; forma larga detectada


# ------------------------------------------------------------------------- CLI
def test_main_devuelve_1_y_no_imprime_el_secreto(tmp_path, capsys):
    r = repo(tmp_path, {"m.py": 'API_KEY = "valor-ultra-secreto"\n'})
    assert aud.main(["--raiz", str(r)]) == 1
    salida = capsys.readouterr().out
    assert "FALTA" in salida and "valor-ultra-secreto" not in salida


def test_main_devuelve_0_en_repositorio_limpio(tmp_path):
    assert aud.main(["--raiz", str(repo(tmp_path, {"m.py": "x = 1\n"}))]) == 0


def test_api_publica_del_repositorio_cumple_las_reglas_de_codigo():
    propios = [h for h in aud.auditar(RAIZ, servicio="api-publica") if h.regla in {"R1", "R2", "R3"}]
    assert propios == []
