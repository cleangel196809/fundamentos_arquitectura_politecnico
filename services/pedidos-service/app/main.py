"""
pedidos-service – FastAPI application entry point.
"""

import socket
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace
import structlog

from app.bus import get_bus
from app.database import check_db_ready, create_all, init_db
from app.observabilidad import configurar_registros, configurar_trazas, instrumentar_aplicacion, log
from app.publisher import OutboxPublisher
from app.routers import outbox, pedidos
from app.settings import get_settings

configurar_registros()
tracer = configurar_trazas("pedidos-service")

settings = get_settings()

INSTANCE_ID = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
HOST = socket.gethostname()

ESTADO: dict = {"arranco": False}

_publisher: OutboxPublisher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _publisher

    log.info("servicio_iniciando", service=settings.service_name, instance=INSTANCE_ID)

    # Initialise DB
    init_db(settings)
    await create_all()

    # Initialise bus & publisher
    bus = get_bus(settings)
    _publisher = OutboxPublisher(settings, bus)
    _publisher.start()

    ESTADO["arranco"] = True
    yield

    # Shutdown
    ESTADO["arranco"] = False
    if _publisher:
        await _publisher.stop()
    log.info("servicio_detenido", service=settings.service_name)


app = FastAPI(
    title="pedidos-service",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Middleware de Correlacion (X-Request-Id y W3C trace_id) ─────────────────
@app.middleware("http")
async def correlacion(request: Request, call_next):
    """Propaga o genera X-Request-Id y lo enlaza al contexto structlog."""
    cid = request.headers.get("X-Request-Id") or uuid.uuid4().hex

    ctx = trace.get_current_span().get_span_context()
    trace_id_str = format(ctx.trace_id, "032x") if ctx and ctx.trace_id else ""

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=cid,
        trace_id=trace_id_str,
        service=settings.service_name,
    )

    respuesta = await call_next(request)
    respuesta.headers["X-Request-Id"] = cid
    return respuesta


# ── Instrumentacion automatica OTel ──────────────────────────────────────────
instrumentar_aplicacion(app)


# ── Custom validation error handler ──────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detalle": str(exc.errors()), "codigo": "VALIDATION_ERROR"},
    )


# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(pedidos.router)
app.include_router(outbox.router)


# ── Health probes ─────────────────────────────────────────────────────────────

@app.get("/health/live", tags=["salud"])
def live() -> dict:
    """Liveness: service process is running."""
    return {"status": "alive", "instance": INSTANCE_ID, "host": HOST}


@app.get("/health/startup", tags=["salud"])
def startup_probe(resp: Response) -> dict:
    """Startup: application has completed initialisation."""
    if not ESTADO["arranco"]:
        resp.status_code = 503
    return {"started": ESTADO["arranco"]}


@app.get("/health/ready", tags=["salud"])
async def ready(resp: Response) -> dict:
    """Readiness: DB reachable and service started."""
    db_ok = await check_db_ready()
    ok = ESTADO["arranco"] and db_ok
    if not ok:
        resp.status_code = 503
    return {"ready": ok, "instance": INSTANCE_ID, "db": db_ok}
