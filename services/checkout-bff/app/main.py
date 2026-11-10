"""checkout-bff (P06) — servicio COMPUESTO (Backend For Frontend).

No tiene base de datos propia: compone a los servicios core.

Rutas del contrato:
  POST /v1/checkout                      ejecuta la saga de compra (exige Idempotency-Key)
                                         201 CONFIRMADO · 409 FALLIDO (con el detalle de pasos)
  GET  /v1/checkout/{pedido_id}/estado   estado actual de la compra
  GET  /v1/vitrina                       productos publicados + disponibilidad, solo los
                                         campos que necesita la app móvil
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app import registro_consul
from app.clientes import ClienteInterno, FalloDePaso
from app.cliente_config import ClienteConfiguracion
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.saga import Destinos, ejecutar_compra
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
FORMATO_SEGURO = r"^[A-Za-z0-9_.:\-]+$"


class SolicitudCheckout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: str = Field(min_length=1, max_length=64, pattern=FORMATO_SEGURO)
    sku: str = Field(min_length=1, max_length=40, pattern=FORMATO_SEGURO)
    cantidad: int = Field(gt=0, le=1000)
    medio_pago: str = Field(min_length=2, max_length=32, pattern=FORMATO_SEGURO)


class ArticuloVitrina(BaseModel):
    sku: str
    nombre: str
    precio_cop: int
    categoria: str
    disponible: int | None          # None = inventario no respondió (se muestra igual el producto)
    agotado: bool | None


def crear_app(ajustes: Settings | None = None, transporte: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    nombre_proceso = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    config_dinamica = ClienteConfiguracion(ajustes)
    # Memoria de compras ya resueltas: Idempotency-Key -> resultado.
    # (Si el BFF se reinicia se pierde, pero no pasa nada: las claves derivadas
    #  hacen que los servicios core devuelvan lo que ya hicieron.)
    compras_resueltas: dict[str, dict] = {}
    candados_por_clave: dict[str, asyncio.Lock] = {}
    marcha = {"arranco": False}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(ajustes.http_timeout_seconds),
                                           limits=httpx.Limits(max_connections=50), transport=transporte)
        app.state.destinos = Destinos(
            catalogo=ClienteInterno(app.state.http, "catalogo-service", ajustes.catalogo_url, ajustes.timeout_catalogo),
            inventario=ClienteInterno(app.state.http, "inventario-service", ajustes.inventario_url, ajustes.timeout_inventario),
            pedidos=ClienteInterno(app.state.http, "pedidos-service", ajustes.pedidos_url, ajustes.timeout_pedidos),
            pagos=ClienteInterno(app.state.http, "pagos-service", ajustes.pagos_url, ajustes.timeout_pagos),
        )
        config_dinamica.iniciar()
        await registro_consul.registrar(ajustes, nombre_proceso)
        marcha["arranco"] = True
        yield
        marcha["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, nombre_proceso)
        await config_dinamica.detener()
        await app.state.http.aclose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="BFF de checkout: orquesta la saga de compra de PiShop Cloud.")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": nombre_proceso}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not marcha["arranco"]:
            respuesta.status_code = 503
        return {"started": marcha["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    def listo(respuesta: Response) -> dict:
        """No consulta a los core en cadena (antipatrón): solo su propio estado."""
        apto = marcha["arranco"] and (config_dinamica.version_aplicada > 0 or ajustes.app_env == "dev")
        if not apto:
            respuesta.status_code = 503
        return {"ready": apto, "config_version": config_dinamica.version_aplicada, "instance": nombre_proceso}

    # ------------------------------------------------------------------ checkout
    @app.post("/v1/checkout", tags=["checkout"], status_code=201)
    async def comprar(
        request: Request,
        solicitud: SolicitudCheckout,
        idempotency_key: str | None = Header(default=None, min_length=8, max_length=100, pattern=FORMATO_SEGURO),
    ):
        if not idempotency_key:
            raise ErrorDeNegocio(400, "La cabecera Idempotency-Key es obligatoria", "FALTA_IDEMPOTENCY_KEY")
        candado = candados_por_clave.setdefault(idempotency_key, asyncio.Lock())
        async with candado:                       # dos reintentos simultáneos no corren la saga dos veces
            resultado = compras_resueltas.get(idempotency_key)
            if resultado is None:
                rastro = await ejecutar_compra(request.app.state.destinos, solicitud.model_dump(), idempotency_key)
                resultado = rastro.como_dict()
                compras_resueltas[idempotency_key] = resultado
        return JSONResponse(status_code=201 if resultado["estado"] == "CONFIRMADO" else 409, content=resultado)

    @app.get("/v1/checkout/{pedido_id}/estado", tags=["checkout"])
    async def estado_compra(request: Request, pedido_id: str = Path(max_length=40, pattern=FORMATO_SEGURO)):
        try:
            pedido = await request.app.state.destinos.pedidos.pedir("GET", f"/v1/pedidos/{pedido_id}")
        except FalloDePaso as error:
            raise ErrorDeNegocio(error.estado_http or 502, error.motivo)
        traduccion = {"CONFIRMADO": "CONFIRMADO", "CANCELADO": "FALLIDO", "CREADO": "EN_CURSO"}
        return {"pedido_id": pedido_id, "estado": traduccion.get(pedido["estado"], pedido["estado"]),
                "estado_pedido": pedido["estado"], "monto_cop": pedido["monto_cop"]}

    # ------------------------------------------------------------------ vitrina
    @app.get("/v1/vitrina", response_model=list[ArticuloVitrina], tags=["vitrina"])
    async def vitrina(request: Request):
        destinos: Destinos = request.app.state.destinos
        try:
            pagina = await destinos.catalogo.pedir("GET", "/v1/productos", params={"solo_publicados": "true", "tamano": 100})
        except FalloDePaso as error:
            raise ErrorDeNegocio(error.estado_http or 502, error.motivo)

        # Bulkhead: como mucho N consultas de stock a la vez, para no ahogar a inventario.
        semaforo = asyncio.Semaphore(ajustes.max_consultas_paralelas)

        async def unidades_de(sku: str) -> int | None:
            async with semaforo:
                try:
                    return int((await destinos.inventario.pedir("GET", f"/v1/stock/{sku}"))["disponible"])
                except (FalloDePaso, KeyError, TypeError, ValueError):
                    return None           # fallback: se muestra el producto sin disponibilidad

        productos = pagina.get("items", [])
        existencias = await asyncio.gather(*(unidades_de(p["sku"]) for p in productos))
        return [ArticuloVitrina(sku=p["sku"], nombre=p["nombre"], precio_cop=p["precio_cop"], categoria=p["categoria"],
                                disponible=cantidad, agotado=None if cantidad is None else cantidad <= 0)
                for p, cantidad in zip(productos, existencias)]

    return app


app = crear_app()
