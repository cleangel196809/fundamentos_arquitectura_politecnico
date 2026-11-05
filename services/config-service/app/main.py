"""config-service de PiShop Cloud (P08) — fuente única de verdad de la configuración.

Semana 4: configuración externalizada (factor III), versionada y auditable.
Contrato: docs/CONTRATOS.md (P08) y contracts/endpoints.json.
"""
import socket
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.settings import get_settings
from app.store import Repositorio

settings = get_settings()
INSTANCE_ID = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
HOST = socket.gethostname()

ESTADO: dict[str, Any] = {"arranco": False, "config_version": 0, "repo": None}

ENV_PATRON = "^(dev|qa|stg|prod)$"
APP_PATRON = "^[a-z][a-z0-9-]{1,63}$"
Valor = str | int | float | bool | None


class Publicacion(BaseModel):
    """Cuerpo de PUT /config/{app}/{env}."""

    data: dict[str, Valor] = Field(description="Parámetros planos clave → valor (sin secretos)")
    motivo: str = Field(min_length=3, max_length=256, description="Por qué se cambia (auditoría)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    repo = Repositorio(s.database_url)
    await repo.crear_esquema()
    ESTADO["repo"] = repo
    ESTADO["config_version"] = 1
    ESTADO["arranco"] = True
    yield
    ESTADO["arranco"] = False
    await repo.cerrar()
    ESTADO["repo"] = None


app = FastAPI(title=settings.service_name, version="1.0.0", lifespan=lifespan)


# ---------- errores con el formato del contrato: {"detalle", "codigo"} ----------
def _error(status: int, detalle: str, codigo: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"detalle": detalle, "codigo": codigo})


@app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    cuerpo = exc.detail if isinstance(exc.detail, dict) else {"detalle": str(exc.detail), "codigo": "ERROR"}
    return JSONResponse(cuerpo, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
    campos = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
    return JSONResponse({"detalle": f"Solicitud inválida: {campos}", "codigo": "VALIDACION"}, status_code=422)


def _repo() -> Repositorio:
    return ESTADO["repo"]


AppNombre = Path(pattern=APP_PATRON, description="Nombre del servicio, p. ej. catalogo-service")
Entorno = Path(pattern=ENV_PATRON, description="dev | qa | stg | prod")


# ---------- API de configuración ----------
@app.get("/config/{app_name}/{env}", tags=["config"])
async def obtener(app_name: str = AppNombre, env: str = Entorno) -> dict[str, Any]:
    fila = await _repo().actual(app_name, env)
    if fila is None:
        raise _error(404, f"No hay configuración para {app_name}/{env}", "CONFIG_NO_ENCONTRADA")
    return fila.a_dict()


@app.put("/config/{app_name}/{env}", tags=["config"], status_code=201)
async def publicar(
    cuerpo: Publicacion,
    app_name: str = AppNombre,
    env: str = Entorno,
    x_autor: str = Header(default="anonimo"),
) -> dict[str, Any]:
    fila = await _repo().publicar(app_name, env, cuerpo.data, x_autor, cuerpo.motivo)
    ESTADO["config_version"] = max(int(ESTADO["config_version"]), fila.version)
    return fila.a_dict()


@app.get("/config/{app_name}/{env}/versions", tags=["config"])
async def historial(app_name: str = AppNombre, env: str = Entorno) -> list[dict[str, Any]]:
    filas = await _repo().historial(app_name, env)
    if not filas:
        raise _error(404, f"No hay historial para {app_name}/{env}", "CONFIG_NO_ENCONTRADA")
    return [f.a_dict(con_data=False) for f in filas]


# ---------- sondas de salud (semántica diferenciada) ----------
@app.get("/health/live", tags=["salud"])
def live() -> dict[str, str]:
    """Barata, local, NUNCA toca dependencias."""
    return {"status": "alive", "instance": INSTANCE_ID}


@app.get("/health/startup", tags=["salud"])
def startup(resp: Response) -> dict[str, bool]:
    """¿Terminó de arrancar? (esquema creado y semilla cargada)."""
    if not ESTADO["arranco"]:
        resp.status_code = 503
    return {"started": ESTADO["arranco"]}


@app.get("/health/ready", tags=["salud"])
async def ready(resp: Response) -> dict[str, object]:
    """¿Puede atender tráfico? Verifica su propia base de datos (no llama a otros servicios)."""
    repo = ESTADO["repo"]
    base_ok = bool(repo) and await repo.ping()
    ok = ESTADO["arranco"] and base_ok
    if not ok:
        resp.status_code = 503
    return {
        "ready": ok,
        "config_version": ESTADO["config_version"],
        "base_datos": base_ok,
        "instance": INSTANCE_ID,
    }
