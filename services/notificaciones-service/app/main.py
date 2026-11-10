"""notificaciones-service (P05) — consumidor ASÍNCRONO de eventos de pedidos.

Base propia: pg_notif (usuario usr_notif).

No recibe llamadas del flujo de compra: se entera de los pedidos leyendo el
stream `pishop.pedidos` de Redis (grupo `notificaciones`). Si este servicio
se cae, la compra NO falla; los eventos esperan en el stream y se procesan
cuando vuelve (ese es el valor de la comunicación asíncrona).

Rutas del contrato:
  GET  /v1/notificaciones?pedido_id=    lo que se le "envió" a los clientes
  POST /v1/notificaciones/prueba        inyecta un evento sin Redis (pruebas/demo)
"""
import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app import registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.bus_eventos import crear_bus
from app.cliente_config import ClienteConfiguracion
from app.consumidor import procesar_evento
from app.errores import instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.models import NotificacionFila
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class NotificacionVista(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evento_id: str
    pedido_id: str
    cliente_id: str
    tipo_evento: str
    canal: str
    mensaje: str
    enviada_en: datetime


class EventoDePrueba(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evento_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=40)
    tipo: str = Field(default="PedidoCreado", pattern="^(PedidoCreado|PedidoCancelado)$")
    payload: dict = Field(default_factory=lambda: {"pedido_id": "PED-PRUEBA", "cliente_id": "C-PRUEBA",
                                                   "sku": "CAFE-500G", "cantidad": 1, "monto_cop": 18000})


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    instancia_actual = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_mensajes = crear_motor(ajustes)
    sesion_mensajes = crear_fabrica_sesiones(motor_mensajes)
    canal_eventos = crear_bus(ajustes)
    lectura_remota = ClienteConfiguracion(ajustes)
    vida = {"arranco": False, "oyente": None}

    async def manejar(campos: dict) -> None:
        await procesar_evento(sesion_mensajes, campos)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await crear_tablas(motor_mensajes)
        vida["oyente"] = asyncio.create_task(canal_eventos.escuchar(ajustes.grupo_consumidor, instancia_actual, manejar))
        lectura_remota.iniciar()
        await registro_consul.registrar(ajustes, instancia_actual)
        vida["arranco"] = True
        yield
        vida["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, instancia_actual)
        await lectura_remota.detener()
        vida["oyente"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vida["oyente"]
        await canal_eventos.cerrar()
        await motor_mensajes.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Notificaciones a clientes por eventos (consumidor asíncrono).")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        """No depende del bus ni de la base: si Redis cae, el proceso NO se reinicia."""
        return {"status": "alive", "instance": instancia_actual}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not vida["arranco"]:
            respuesta.status_code = 503
        return {"started": vida["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        """503 si el bus configurado no responde (contrato P05)."""
        bus_ok = await canal_eventos.esta_vivo()
        base_ok = await base_responde(motor_mensajes)
        config_ok = lectura_remota.version_aplicada > 0 or ajustes.app_env == "dev"
        habilitado = vida["arranco"] and bus_ok and base_ok and config_ok
        if not habilitado:
            respuesta.status_code = 503
        return {"ready": habilitado, "bus": bus_ok, "base_datos": base_ok,
                "config_version": lectura_remota.version_aplicada, "instance": instancia_actual}

    # ------------------------------------------------------------------ consultas
    @app.get("/v1/notificaciones", response_model=list[NotificacionVista], tags=["notificaciones"])
    async def listar(pedido_id: str | None = Query(None, max_length=40), limite: int = Query(50, ge=1, le=500)):
        async with sesion_mensajes() as sesion:
            consulta = select(NotificacionFila).order_by(NotificacionFila.id.desc()).limit(limite)
            if pedido_id:
                consulta = consulta.where(NotificacionFila.pedido_id == pedido_id)
            return list(await sesion.scalars(consulta))

    @app.post("/v1/notificaciones/prueba", tags=["notificaciones"])
    async def inyectar_evento(evento: EventoDePrueba):
        resultado = await procesar_evento(sesion_mensajes, {"evento_id": evento.evento_id, "tipo": evento.tipo,
                                                             "payload": json.dumps(evento.payload)})
        return {"evento_id": evento.evento_id, "resultado": resultado}

    return app


app = crear_app()
