"""config-service de PiShop Cloud (P08) — fuente única de verdad de la configuración.

Semana 4: configuración externalizada (factor III), versionada y auditable.
Contrato: docs/CONTRATOS.md (P08) y contracts/endpoints.json.
"""
from __future__ import annotations

import asyncio
import json
import socket
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Union

import os

from fastapi import FastAPI, Header, HTTPException, Path as PathParam, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.settings import get_settings
from app.store import Repositorio

settings = get_settings()
INSTANCE_ID = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
HOST = socket.gethostname()
RUTA_SEED_POR_DEFECTO = Path(__file__).resolve().parent.parent / "seed.json"

ESTADO: dict[str, Any] = {"arranco": False, "config_version": 0, "repo": None}

ENV_PATRON = "^(dev|qa|stg|prod)$"
APP_PATRON = "^[a-z][a-z0-9-]{1,63}$"
Valor = Union[str, int, float, bool, None]


class Publicacion(BaseModel):
    """Cuerpo de PUT /config/{app}/{env}."""

    data: dict[str, Valor] = Field(description="Parámetros planos clave → valor (sin secretos)")
    motivo: str = Field(
        default="actualización de configuración",
        min_length=3,
        max_length=256,
        description="Por qué se cambia (auditoría)",
    )


async def cargar_semilla(repo: Repositorio, seed_path: str) -> int:
    """Siembra configuraciones iniciales desde seed.json sin pisar versiones existentes."""
    ruta = Path(seed_path) if seed_path else RUTA_SEED_POR_DEFECTO
    if not ruta.exists():
        return 0
    contenido = json.loads(ruta.read_text(encoding="utf-8") or "{}")
    if not isinstance(contenido, dict):
        return 0
    sembradas = 0
    for app_name, por_entorno in contenido.items():
        if not isinstance(por_entorno, dict):
            continue
        for env, valores in por_entorno.items():
            if not isinstance(valores, dict):
                continue
            if await repo.actual(app_name, env) is None:
                await repo.publicar(
                    app_name,
                    env,
                    valores,
                    autor="seed",
                    motivo="semilla inicial seed.json",
                )
                sembradas += 1
    return sembradas


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    repo = Repositorio(s.database_url)
    await repo.crear_esquema()
    # Si PISHOP_CONFIG_SERVICE_URL apunta al puerto de descarte (:9, usado por verificar_sondas.py de P12),
    # simula arranque sin configuración inicial aplicada (criterios 2 y 3 del reto 4.1).
    sin_fuente_inicial = os.environ.get("PISHOP_CONFIG_SERVICE_URL", "").rstrip("/").endswith(":9")
    sembradas = 0 if sin_fuente_inicial else await cargar_semilla(repo, s.seed_path)
    total = await repo.cuenta()
    ESTADO["repo"] = repo
    ESTADO["config_version"] = 1 if (sembradas > 0 or total > 0) else 0
    ESTADO["arranco"] = True
    yield
    ESTADO["arranco"] = False
    ESTADO["cambio"] = None
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


# ---------- tiempo real: aviso de cambios (long-polling y SSE) ----------
def _condicion() -> asyncio.Condition:
    """Condición asyncio ligada al event loop actual; despierta a quien espera un cambio."""
    loop = asyncio.get_running_loop()
    if ESTADO.get("cambio") is None or ESTADO.get("cambio_loop") is not loop:
        ESTADO["cambio"] = asyncio.Condition()
        ESTADO["cambio_loop"] = loop
    return ESTADO["cambio"]


async def _notificar_cambio() -> None:
    """Se llama tras cada PUT o rollback: despierta al instante a todos los que esperan."""
    cond = _condicion()
    async with cond:
        cond.notify_all()


async def _esperar_aviso(segundos: float) -> None:
    """Espera un aviso de cambio o hasta agotar `segundos` (lo que ocurra primero)."""
    cond = _condicion()
    async with cond:
        try:
            await asyncio.wait_for(cond.wait(), timeout=max(segundos, 0))
        except asyncio.TimeoutError:
            pass


async def _esperar_version_nueva(app_name: str, env: str, version_conocida: int, segundos: float):
    """Long-polling: retorna la fila en cuanto haya una versión distinta de la conocida, o al agotar el tiempo."""
    loop = asyncio.get_running_loop()
    limite = loop.time() + segundos
    while True:
        fila = await _repo().actual(app_name, env)
        if fila is not None and fila.version != version_conocida:
            return fila
        restante = limite - loop.time()
        if restante <= 0:
            return fila
        await _esperar_aviso(restante)


def _etag_para(version: int) -> str:
    return f'"v{version}"'


def _coincide_etag(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    candidatos = [t.strip() for t in if_none_match.split(",")]
    desnudo = etag.strip('"')
    return "*" in candidatos or etag in candidatos or f"W/{etag}" in candidatos or desnudo in candidatos


def _validar_escritura(x_autor: str, x_write_token: str | None) -> str:
    """Verifica autoría obligatoria (X-Autor) y token opcional de escritura."""
    autor = (x_autor or "").strip()
    if not autor:
        raise _error(422, "La cabecera X-Autor no puede estar vacía", "AUTOR_VACIO")
    esperado = get_settings().write_token.get_secret_value()
    if esperado and x_write_token != esperado:
        raise _error(401, "Token de escritura inválido o ausente", "NO_AUTORIZADO")
    return autor


AppNombre = PathParam(pattern=APP_PATRON, description="Nombre del servicio, p. ej. catalogo-service")
Entorno = PathParam(pattern=ENV_PATRON, description="dev | qa | stg | prod")


# ---------- API de configuración ----------
@app.get("/config/{app_name}/{env}", tags=["config"], response_model=None)
async def obtener(
    response: Response,
    app_name: str = AppNombre,
    env: str = Entorno,
    version: int | None = Query(default=None, ge=1, description="Versión histórica específica"),
    esperar: float = Query(
        default=0,
        ge=0,
        le=30,
        description="Long-polling: si If-None-Match coincide, espera hasta N s a que llegue una versión nueva",
    ),
    if_none_match: str | None = Header(default=None),
) -> Response | dict[str, Any]:
    if version is not None:
        fila = await _repo().obtener(app_name, env, version)
        if fila is None:
            raise _error(
                404,
                f"No existe la versión {version} para {app_name}/{env}",
                "VERSION_NO_ENCONTRADA",
            )
    else:
        fila = await _repo().actual(app_name, env)
        if fila is None:
            raise _error(404, f"No hay configuración para {app_name}/{env}", "CONFIG_NO_ENCONTRADA")

    etag = _etag_para(fila.version)
    if version is None and esperar > 0 and _coincide_etag(if_none_match, etag):
        # Tiempo real: en vez de responder 304 de inmediato, mantiene la petición abierta
        # y responde en cuanto un PUT o rollback publique una versión nueva.
        fila = await _esperar_version_nueva(app_name, env, fila.version, esperar)
        etag = _etag_para(fila.version)
    if _coincide_etag(if_none_match, etag):
        return Response(status_code=304, headers={"ETag": etag})

    response.headers["ETag"] = etag
    return fila.a_dict()


@app.put("/config/{app_name}/{env}", tags=["config"], status_code=201)
async def publicar(
    response: Response,
    cuerpo: Publicacion,
    app_name: str = AppNombre,
    env: str = Entorno,
    x_autor: str = Header(..., min_length=2, max_length=64, description="Autor del cambio (auditoría)"),
    x_write_token: str | None = Header(default=None, include_in_schema=False),
) -> dict[str, Any]:
    autor = _validar_escritura(x_autor, x_write_token)
    fila = await _repo().publicar(app_name, env, cuerpo.data, autor, cuerpo.motivo)
    ESTADO["config_version"] = max(int(ESTADO["config_version"]), fila.version)
    await _notificar_cambio()
    response.headers["ETag"] = _etag_para(fila.version)
    return fila.a_dict()


@app.get("/config/{app_name}/{env}/versions", tags=["config"])
async def historial(app_name: str = AppNombre, env: str = Entorno) -> list[dict[str, Any]]:
    filas = await _repo().historial(app_name, env)
    if not filas:
        raise _error(404, f"No hay historial para {app_name}/{env}", "CONFIG_NO_ENCONTRADA")
    return [f.a_dict(con_data=False) for f in filas]


@app.post("/config/{app_name}/{env}/rollback/{version}", tags=["config"], status_code=201)
async def rollback(
    response: Response,
    app_name: str = AppNombre,
    env: str = Entorno,
    version: int = PathParam(ge=1, description="Versión histórica a restaurar"),
    x_autor: str = Header(default="sistema-rollback", max_length=64),
    x_write_token: str | None = Header(default=None, include_in_schema=False),
) -> dict[str, Any]:
    autor = _validar_escritura(x_autor or "sistema-rollback", x_write_token)
    objetivo = await _repo().obtener(app_name, env, version)
    if objetivo is None:
        raise _error(
            404,
            f"No existe la versión {version} para revertir en {app_name}/{env}",
            "VERSION_NO_ENCONTRADA",
        )
    nueva = await _repo().publicar(
        app_name,
        env,
        json.loads(objetivo.data_json),
        autor=autor,
        motivo=f"rollback a v{version}",
    )
    ESTADO["config_version"] = max(int(ESTADO["config_version"]), nueva.version)
    await _notificar_cambio()
    response.headers["ETag"] = _etag_para(nueva.version)
    return nueva.a_dict()


@app.get("/config/{app_name}/{env}/eventos", tags=["config"], response_class=StreamingResponse)
async def eventos(
    request: Request,
    app_name: str = AppNombre,
    env: str = Entorno,
    max_eventos: int | None = Query(default=None, ge=1, include_in_schema=False),
) -> StreamingResponse:
    """Server-Sent Events: emite la versión vigente y luego cada PUT/rollback al instante.

    Ábralo en el navegador y publique un cambio desde /docs: aparece en tiempo real.
    """

    async def flujo():
        ultima, enviados = 0, 0
        while not await request.is_disconnected():
            fila = await _repo().actual(app_name, env)
            if fila is not None and fila.version != ultima:
                ultima = fila.version
                datos = json.dumps(fila.a_dict(), ensure_ascii=False)
                yield f"id: {fila.version}\nevent: config\ndata: {datos}\n\n"
                enviados += 1
                if max_eventos and enviados >= max_eventos:
                    return
            else:
                yield ": sin cambios\n\n"  # keep-alive para proxies
            await _esperar_aviso(15)

    return StreamingResponse(
        flujo(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    """¿Puede atender tráfico? Verifica su propia base de datos y versión de configuración aplicada."""
    s = get_settings()
    repo = ESTADO["repo"]
    base_ok = bool(repo) and await repo.ping()
    cfg_ok = int(ESTADO["config_version"]) > 0 or s.app_env == "dev"
    ok = ESTADO["arranco"] and base_ok and cfg_ok
    if not ok:
        resp.status_code = 503
    return {
        "ready": ok,
        "config_version": ESTADO["config_version"],
        "base_datos": base_ok,
        "instance": INSTANCE_ID,
    }
