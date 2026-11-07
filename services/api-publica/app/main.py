"""api-publica (P07): fachada pública de PiShop Cloud.

Autentica (X-API-Key), limita la tasa y enruta a catalogo-service y checkout-bff.
No contiene lógica de negocio.
"""
import socket
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response

from app.errores import registrar_handlers
from app.routers import router
from app.seguridad import LimitadorTasa
from app.settings import get_settings

settings = get_settings()
INSTANCE_ID = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
HOST = socket.gethostname()

ESTADO = {"arranco": False, "config_version": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Un único AsyncClient por proceso, con timeout explícito (semana 3).
    app.state.http = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    ESTADO["arranco"] = True
    yield
    ESTADO["arranco"] = False
    await app.state.http.aclose()


app = FastAPI(title=settings.service_name, version="1.0.0", lifespan=lifespan)
app.state.settings = settings
app.state.limitador = LimitadorTasa(settings.rate_limit_per_minute)
registrar_handlers(app)
app.include_router(router)


@app.get("/health/live", tags=["salud"])
def live() -> dict[str, str]:
    """Barata, local, NUNCA toca dependencias."""
    return {"status": "alive", "instance": INSTANCE_ID}


@app.get("/health/startup", tags=["salud"])
def startup(resp: Response) -> dict[str, bool]:
    if not ESTADO["arranco"]:
        resp.status_code = 503
    return {"started": ESTADO["arranco"]}


@app.get("/health/ready", tags=["salud"])
def ready(resp: Response) -> dict[str, object]:
    ok = ESTADO["arranco"] and (ESTADO["config_version"] > 0 or settings.app_env == "dev")
    if not ok:
        resp.status_code = 503
    return {"ready": ok, "config_version": ESTADO["config_version"], "instance": INSTANCE_ID}
