"""pedidos-service (P03) — servicio CORE dueño de los pedidos, con Outbox.

Base propia: pg_pedidos (usuario usr_pedidos).

Rutas del contrato:
  POST /v1/pedidos                         crea el pedido + evento PedidoCreado (una transacción)
  GET  /v1/pedidos/{pedido_id}             consulta
  POST /v1/pedidos/{pedido_id}/cancelar    estado CANCELADO + evento PedidoCancelado
  GET  /v1/outbox/pendientes               eventos aún sin publicar
Ruta adicional (la usa el BFF cuando el pago se aprueba):
  POST /v1/pedidos/{pedido_id}/confirmar   estado CONFIRMADO
"""
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.bus_eventos import crear_bus
from app.cliente_config import ClienteConfiguracion
from app.errores import instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.publicador import PublicadorOutbox
from app.repository import RepositorioPedidos
from app.schemas import EventoPendiente, PedidoSolicitud, PedidoVista
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
CLAVE_PERMITIDA = r"^[A-Za-z0-9_.:\-]+$"


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    rotulo_instancia = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_pedidos = crear_motor(ajustes)
    sesion_nueva = crear_fabrica_sesiones(motor_pedidos)
    bus = crear_bus(ajustes)
    publicador = PublicadorOutbox(sesion_nueva, bus, ajustes.outbox_intervalo_segundos)
    ajustes_remotos = ClienteConfiguracion(ajustes)
    banderas = {"arranco": False}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await crear_tablas(motor_pedidos)
        if ajustes.publicador_activo:
            publicador.iniciar()
        ajustes_remotos.iniciar()
        await registro_consul.registrar(ajustes, rotulo_instancia)
        banderas["arranco"] = True
        yield
        banderas["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, rotulo_instancia)
        await ajustes_remotos.detener()
        await publicador.detener()
        await bus.cerrar()
        await motor_pedidos.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Pedidos de PiShop Cloud con Transactional Outbox (servicio core).")
    app.state.bus = bus                    # las pruebas inspeccionan el bus en memoria
    app.state.fabrica_sesiones = sesion_nueva
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    async def sesion_pedidos():
        async with sesion_nueva() as sesion:
            yield sesion

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": rotulo_instancia}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not banderas["arranco"]:
            respuesta.status_code = 503
        return {"started": banderas["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        base_arriba = await base_responde(motor_pedidos)
        configuracion_lista = ajustes_remotos.version_aplicada > 0 or ajustes.app_env == "dev"
        dispuesto = banderas["arranco"] and base_arriba and configuracion_lista
        if not dispuesto:
            respuesta.status_code = 503
        return {"ready": dispuesto, "base_datos": base_arriba,
                "config_version": ajustes_remotos.version_aplicada, "instance": rotulo_instancia}

    # ------------------------------------------------------------------ pedidos
    @app.post("/v1/pedidos", response_model=PedidoVista, status_code=201, tags=["pedidos"])
    async def registrar_pedido(
        solicitud: PedidoSolicitud,
        idempotency_key: str | None = Header(default=None, max_length=128, pattern=CLAVE_PERMITIDA),
        sesion: AsyncSession = Depends(sesion_pedidos),
    ):
        return await RepositorioPedidos(sesion).crear(solicitud, idempotency_key)

    @app.get("/v1/pedidos/{pedido_id}", response_model=PedidoVista, tags=["pedidos"])
    async def consultar_pedido(pedido_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_pedidos)):
        return await RepositorioPedidos(sesion).obtener(pedido_id)

    @app.post("/v1/pedidos/{pedido_id}/cancelar", response_model=PedidoVista, tags=["pedidos"])
    async def anular_pedido(pedido_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_pedidos)):
        return await RepositorioPedidos(sesion).cancelar(pedido_id)

    @app.post("/v1/pedidos/{pedido_id}/confirmar", response_model=PedidoVista, tags=["pedidos"])
    async def cerrar_pedido(pedido_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_pedidos)):
        return await RepositorioPedidos(sesion).confirmar(pedido_id)

    # ------------------------------------------------------------------ outbox
    @app.get("/v1/outbox/pendientes", response_model=list[EventoPendiente], tags=["outbox"])
    async def ver_outbox(sesion: AsyncSession = Depends(sesion_pedidos)):
        sin_enviar = await RepositorioPedidos(sesion).eventos_sin_publicar()
        return [EventoPendiente(evento_id=e.evento_id, tipo=e.tipo, contenido=json.loads(e.contenido_json),
                                registrado_en=e.registrado_en) for e in sin_enviar]

    return app


app = crear_app()
