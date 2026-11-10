"""pagos-service (P04) — servicio CORE de cobros, con ACL hacia la pasarela.

Base propia: pg_pagos (usuario usr_pagos).

Rutas del contrato:
  POST /v1/pagos                        cobra (exige Idempotency-Key) -> APROBADO | RECHAZADO
  GET  /v1/pagos/{pago_id}              consulta
  POST /v1/pagos/{pago_id}/reembolso    compensación idempotente
  POST /_simulador/pasarela/cobrar      la pasarela FALSA (modos ok | rechaza | lenta | falla)
Ruta de apoyo para demos (deshabilitada en prod):
  PUT  /_simulador/pasarela/modo        cambia el modo sin reiniciar el contenedor

Resiliencia: un único httpx.AsyncClient por proceso con timeout explícito. Si
la pasarela es lenta, el cliente recibe 504 ANTES de que pase el timeout; si
está caída, 503. Nunca se queda colgado.
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, Header, Path, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import adaptador_pasarela, registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.cliente_config import ClienteConfiguracion
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.models import PagoFila
from app.schemas import CobroSolicitud, ModoPasarela, PagoVista
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
bitacora = logging.getLogger("pagos-service")
CLAVE_VALIDA = r"^[A-Za-z0-9_.:\-]+$"


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    etiqueta_instancia = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_pagos = crear_motor(ajustes)
    sesion_de_pagos = crear_fabrica_sesiones(motor_pagos)
    configuracion_viva = ClienteConfiguracion(ajustes)
    indicadores = {"arranco": False}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await crear_tablas(motor_pagos)
        # UN cliente HTTP por proceso (no uno por petición) con timeout explícito.
        app.state.cliente_pasarela = httpx.AsyncClient(
            timeout=httpx.Timeout(ajustes.http_timeout_seconds),
            limits=httpx.Limits(max_connections=20),
            transport=getattr(app.state, "transporte_pasarela", None),   # las pruebas inyectan uno en memoria
        )
        configuracion_viva.iniciar()
        await registro_consul.registrar(ajustes, etiqueta_instancia)
        indicadores["arranco"] = True
        yield
        indicadores["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, etiqueta_instancia)
        await configuracion_viva.detener()
        await app.state.cliente_pasarela.aclose()
        await motor_pagos.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Cobros y reembolsos de PiShop Cloud (servicio core con ACL).")
    app.state.modo_pasarela = ajustes.pasarela_modo
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    async def sesion_cobros():
        async with sesion_de_pagos() as sesion:
            yield sesion

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": etiqueta_instancia}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not indicadores["arranco"]:
            respuesta.status_code = 503
        return {"started": indicadores["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        base_disponible = await base_responde(motor_pagos)
        parametros_ok = configuracion_viva.version_aplicada > 0 or ajustes.app_env == "dev"
        operativo = indicadores["arranco"] and base_disponible and parametros_ok
        if not operativo:
            respuesta.status_code = 503
        return {"ready": operativo, "base_datos": base_disponible,
                "config_version": configuracion_viva.version_aplicada, "instance": etiqueta_instancia}

    # ------------------------------------------------------------------ cobros
    @app.post("/v1/pagos", response_model=PagoVista, status_code=201, tags=["pagos"])
    async def cobrar_pedido(
        request: Request,
        cobro: CobroSolicitud,
        idempotency_key: str | None = Header(default=None, max_length=128, pattern=CLAVE_VALIDA),
        sesion: AsyncSession = Depends(sesion_cobros),
    ):
        if not idempotency_key:
            raise ErrorDeNegocio(400, "La cabecera Idempotency-Key es obligatoria", "FALTA_IDEMPOTENCY_KEY")

        # 1) ¿Ya existe un pago con esta clave? Si terminó, se devuelve tal cual (no se cobra dos veces).
        pago = await sesion.scalar(select(PagoFila).where(PagoFila.clave_idempotencia == idempotency_key))
        if pago and pago.estado != "PENDIENTE":
            return PagoVista.model_validate(pago)

        # 2) Si es nuevo, se registra PENDIENTE antes de hablar con la pasarela (deja rastro aunque falle).
        if pago is None:
            pago = PagoFila(pago_id=f"PAG-{uuid.uuid4().hex[:12]}", clave_idempotencia=idempotency_key,
                            estado="PENDIENTE", **cobro.model_dump())
            sesion.add(pago)
            try:
                await sesion.commit()
            except IntegrityError:
                await sesion.rollback()
                raise ErrorDeNegocio(409, "Este cobro ya se está procesando", "COBRO_EN_CURSO")

        # 3) Cobro real a través de la ACL (fuera de cualquier transacción de base de datos).
        try:
            resultado = await adaptador_pasarela.cobrar(request.app.state.cliente_pasarela, str(ajustes.pasarela_url),
                                                        pago.pago_id, pago.monto_cop)
        except adaptador_pasarela.PasarelaNoResponde:
            raise ErrorDeNegocio(504, "La pasarela de pagos no respondió a tiempo", "PASARELA_LENTA")
        except adaptador_pasarela.PasarelaCaida:
            raise ErrorDeNegocio(503, "La pasarela de pagos no está disponible", "PASARELA_CAIDA")

        pago.estado = resultado.estado
        pago.codigo_autorizacion = resultado.codigo_autorizacion
        await sesion.commit()
        bitacora.info("pago %s del pedido %s: %s", pago.pago_id, pago.pedido_id, pago.estado)
        return PagoVista.model_validate(pago)

    @app.get("/v1/pagos/{pago_id}", response_model=PagoVista, tags=["pagos"])
    async def ver_pago(pago_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_cobros)):
        registro = await sesion.get(PagoFila, pago_id)
        if registro is None:
            raise ErrorDeNegocio(404, f"No existe el pago {pago_id}")
        return PagoVista.model_validate(registro)

    @app.post("/v1/pagos/{pago_id}/reembolso", response_model=PagoVista, tags=["pagos"])
    async def reembolsar(pago_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_cobros)):
        """Compensación: devolver el dinero. Repetirlo no devuelve dos veces."""
        registro = await sesion.get(PagoFila, pago_id)
        if registro is None:
            raise ErrorDeNegocio(404, f"No existe el pago {pago_id}")
        if registro.estado == "APROBADO":
            registro.estado = "REEMBOLSADO"
            registro.reembolsado_en = datetime.now(timezone.utc)
            await sesion.commit()
        elif registro.estado != "REEMBOLSADO":
            raise ErrorDeNegocio(409, f"Un pago {registro.estado} no se puede reembolsar", "NO_REEMBOLSABLE")
        return PagoVista.model_validate(registro)

    # ------------------------------------------------------------------ pasarela simulada
    @app.post("/_simulador/pasarela/cobrar", tags=["simulador"])
    async def pasarela_falsa(request: Request):
        """Imita a un proveedor externo: responde en SU vocabulario (inglés)."""
        modo = request.app.state.modo_pasarela
        if modo == "lenta":
            await asyncio.sleep(ajustes.pasarela_demora_lenta_segundos)
            return {"status": "APPROVED", "auth_code": f"AUT-{uuid.uuid4().hex[:6].upper()}"}
        if modo == "falla":
            return JSONResponse(status_code=500, content={"error": "gateway internal error"})
        if modo == "rechaza":
            return {"status": "DECLINED", "auth_code": None}
        return {"status": "APPROVED", "auth_code": f"AUT-{uuid.uuid4().hex[:6].upper()}"}

    @app.put("/_simulador/pasarela/modo", tags=["simulador"])
    async def cambiar_modo(nuevo: ModoPasarela, request: Request):
        if ajustes.app_env == "prod":
            raise ErrorDeNegocio(404, "No disponible en producción")
        request.app.state.modo_pasarela = nuevo.modo
        bitacora.warning("modo de la pasarela simulada cambiado a '%s'", nuevo.modo)
        return {"modo": nuevo.modo}

    return app


app = crear_app()
