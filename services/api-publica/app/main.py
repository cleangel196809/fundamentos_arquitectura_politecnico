"""api-publica (P07): fachada pública de PiShop Cloud.

Responsabilidad: seguridad del perímetro y enrutamiento. NO contiene lógica de
negocio: el gateway enruta, el BFF agrega (docs/CONTRATOS.md).

Seguridad aplicada aquí:
  * X-API-Key obligatoria (401)                     -> app/seguridad.py
  * 40 peticiones/min por clave (429 + Retry-After)  -> app/seguridad.py
  * Cabeceras de seguridad HTTP en todas las respuestas
  * Tiempo de respuesta y correlación (X-Tiempo-Respuesta-ms, X-Correlacion-Id)
  * Entradas validadas con Pydantic v2 (422)         -> modelos de este archivo
  * Errores application/problem+json sin trazas      -> app/errores.py
  * Un único httpx.AsyncClient con timeout explícito (Bulkhead)
"""
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from slowapi.middleware import SlowAPIMiddleware

from app import registro_consul
from app.cliente_config import ClienteConfiguracion
from app.errores import problema, registrar_manejadores
from app.medicion import CABECERA_CORRELACION, MedidorDeTiempos, correlacion_actual
from app.seguridad import crear_limiter, crear_validador_api_key
from app.settings import Settings, get_settings

ID_SEGURO = r"^[A-Za-z0-9_.\-]+$"   # evita '/', '..', espacios, etc. en identificadores


# ---------------------------------------------------------------- modelos públicos
class ProductoPublico(BaseModel):
    """Modelo estable de consumo (ACL): no expone campos internos del catálogo."""
    sku: str
    nombre: str
    precio_cop: int | float
    categoria: str


class ProductoCatalogo(ProductoPublico):
    publicado: bool = False


class CatalogoPagina(BaseModel):
    items: list[ProductoPublico]
    pagina: int
    tamano: int


class CompraSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")   # campos desconocidos -> 422
    cliente_id: str = Field(min_length=1, max_length=64, pattern=ID_SEGURO)
    sku: str = Field(min_length=1, max_length=64, pattern=ID_SEGURO)
    cantidad: int = Field(gt=0, le=1_000_000)
    medio_pago: str = Field(min_length=1, max_length=32, pattern=ID_SEGURO)


class CompraRespuesta(BaseModel):
    pedido_id: str
    estado: str


# ---------------------------------------------------------------- llamadas internas
def _base(url) -> str:
    return str(url).rstrip("/")


# Cabeceras de seguridad que se agregan a TODAS las respuestas (OWASP Secure Headers).
CABECERAS_SEGURAS = {
    "X-Content-Type-Options": "nosniff",               # el navegador no "adivina" tipos de contenido
    "X-Frame-Options": "DENY",                         # nadie puede incrustar la API en un iframe
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",                       # respuestas con datos de clientes no se cachean
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}
RUTAS_DOCUMENTACION = ("/docs", "/redoc", "/openapi.json")


async def _llamar(request: Request, metodo: str, url: str, aceptar: tuple[int, ...] = (), **kwargs) -> httpx.Response:
    """Llamada saliente con el cliente compartido. Traduce fallos a 5xx/4xx públicos.

    `aceptar`: códigos 4xx que se devuelven tal cual al llamador en vez de convertirse en error.
    """
    cabeceras = {**kwargs.pop("headers", {}), CABECERA_CORRELACION: correlacion_actual.get()}
    try:
        r = await request.app.state.http.request(metodo, url, headers=cabeceras, **kwargs)
    except httpx.TimeoutException:
        raise HTTPException(504, "El servicio interno no respondió a tiempo.")
    except httpx.RequestError:
        raise HTTPException(503, "El servicio interno no está disponible.")
    if r.status_code >= 500:
        raise HTTPException(502, "El servicio interno devolvió una respuesta inválida.")
    if r.status_code in aceptar:
        return r
    if r.status_code >= 400:
        detalle = "Recurso no encontrado." if r.status_code == 404 else "La solicitud fue rechazada."
        raise HTTPException(r.status_code, detalle)
    return r


def _json(r: httpx.Response):
    try:
        return r.json()
    except ValueError:
        raise HTTPException(502, "El servicio interno devolvió una respuesta inválida.")


# ---------------------------------------------------------------- fábrica de la app
def crear_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or get_settings()
    instancia = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
    limiter = crear_limiter(settings)
    exigir_api_key = Depends(crear_validador_api_key(settings))
    catalogo, checkout = _base(settings.catalogo_url), _base(settings.checkout_url)
    config_remota = ClienteConfiguracion(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds),           # timeout explícito
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),   # Bulkhead
            transport=transport,
        )
        config_remota.iniciar()
        await registro_consul.registrar(settings, instancia)
        app.state.estado["arranco"] = True
        yield
        app.state.estado["arranco"] = False
        await registro_consul.dar_de_baja(settings, instancia)
        await config_remota.detener()
        await app.state.http.aclose()

    # En producción no se publica la documentación interactiva (menos superficie de ataque).
    en_produccion = settings.app_env == "prod"
    app = FastAPI(title=settings.service_name, version="1.0.0", lifespan=lifespan,
                  docs_url=None if en_produccion else "/docs", redoc_url=None if en_produccion else "/redoc")
    app.state.estado = {"arranco": False, "config_version": 0}
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)      # cuenta TODAS las rutas no exentas (incluidos los 401)
    app.add_middleware(MedidorDeTiempos, umbral_ms=settings.umbral_respuesta_ms)
    registrar_manejadores(app)

    @app.middleware("http")
    async def cabeceras_de_seguridad(request: Request, call_next):
        respuesta = await call_next(request)
        for nombre, valor in CABECERAS_SEGURAS.items():
            # /docs necesita cargar JS y CSS: ahí no se aplica la CSP estricta.
            if nombre == "Content-Security-Policy" and request.url.path.startswith(RUTAS_DOCUMENTACION):
                continue
            respuesta.headers.setdefault(nombre, valor)
        return respuesta

    # ------------------------------------------------ sondas (sin autenticación, sin límite)
    @app.get("/health/live", tags=["salud"])
    @limiter.exempt
    def live() -> dict[str, str]:
        """Barata, local, NUNCA toca dependencias."""
        return {"status": "alive", "instance": instancia}

    @app.get("/health/startup", tags=["salud"])
    @limiter.exempt
    def startup(resp: Response) -> dict[str, bool]:
        if not app.state.estado["arranco"]:
            resp.status_code = 503
        return {"started": app.state.estado["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    @limiter.exempt
    def ready(resp: Response) -> dict[str, object]:
        estado = app.state.estado
        estado["config_version"] = config_remota.version_aplicada
        ok = estado["arranco"] and (estado["config_version"] > 0 or settings.app_env == "dev")
        if not ok:
            resp.status_code = 503
        return {"ready": ok, "config_version": estado["config_version"], "instance": instancia}

    # ------------------------------------------------ rutas protegidas (contrato P07)
    @app.get("/v1/catalogo/productos", response_model=CatalogoPagina, dependencies=[exigir_api_key], tags=["catalogo"])
    async def listar_productos(
        request: Request,
        pagina: int = Query(1, ge=1, le=10_000),
        tamano: int = Query(20, ge=1, le=100),
    ):
        r = await _llamar(request, "GET", f"{catalogo}/v1/productos", params={"pagina": pagina, "tamano": tamano})
        try:
            productos = [ProductoCatalogo.model_validate(p) for p in _json(r)["items"]]
        except (KeyError, TypeError, ValueError):
            raise HTTPException(502, "El servicio interno devolvió una respuesta inválida.")
        publicos = [ProductoPublico(**p.model_dump(exclude={"publicado"})) for p in productos if p.publicado]
        return CatalogoPagina(items=publicos, pagina=pagina, tamano=tamano)

    @app.post("/v1/compras", response_model=CompraRespuesta, status_code=201, dependencies=[exigir_api_key], tags=["compras"])
    async def crear_compra(
        request: Request,
        compra: CompraSolicitud,
        idempotency_key: str | None = Header(default=None, min_length=8, max_length=128, pattern=ID_SEGURO),
    ):
        # El checkout exige Idempotency-Key; si el cliente no la envía se genera una,
        # pero solo reenviar la MISMA clave protege contra compras duplicadas.
        clave = idempotency_key or uuid.uuid4().hex
        r = await _llamar(request, "POST", f"{checkout}/v1/checkout", aceptar=(409,),
                          json=compra.model_dump(), headers={"Idempotency-Key": clave})
        datos = _json(r)
        if r.status_code == 409:
            # La saga terminó FALLIDA (stock insuficiente, pago rechazado...): ya se compensó todo.
            return problema(request, 409, str(datos.get("motivo") or "La compra no se pudo completar."),
                            "compra-fallida", pedido_id=datos.get("pedido_id"), estado=datos.get("estado", "FALLIDO"))
        try:
            return CompraRespuesta(pedido_id=str(datos["pedido_id"]), estado=str(datos["estado"]))
        except (KeyError, TypeError):
            raise HTTPException(502, "El servicio interno devolvió una respuesta inválida.")

    @app.get("/v1/compras/{pedido_id}", response_model=CompraRespuesta, dependencies=[exigir_api_key], tags=["compras"])
    async def consultar_compra(request: Request, pedido_id: str = Path(min_length=1, max_length=64, pattern=ID_SEGURO)):
        r = await _llamar(request, "GET", f"{checkout}/v1/checkout/{pedido_id}/estado")
        datos = _json(r)
        if not isinstance(datos, dict) or "estado" not in datos:
            raise HTTPException(502, "El servicio interno devolvió una respuesta inválida.")
        return CompraRespuesta(pedido_id=pedido_id, estado=str(datos["estado"]))

    return app


app = crear_app()
