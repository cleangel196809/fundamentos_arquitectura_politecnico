"""reportes-service (P10) — MODELO DE LECTURA (CQRS) de las ventas.

Base propia: pg_reportes (usuario usr_reportes).

Escritura y lectura separadas: pedidos-service escribe pedidos; este servicio
solo LEE eventos del stream `pishop.pedidos` (grupo `reportes`) y mantiene
totales listos para consultar, sin tocar la base de nadie más.

Consistencia: EVENTUAL. Un pedido recién creado aparece en el reporte uno o
dos segundos después (lo que tarda la outbox en publicar y el consumidor en leer).

Rutas del contrato:
  GET  /v1/reportes/resumen          {pedidos_total, unidades_total, monto_total_cop}
  GET  /v1/reportes/ventas-por-sku   detalle por producto
  POST /v1/reportes/reconstruir      borra la proyección y la rehace desde el stream
Ruta de apoyo para pruebas sin Redis:
  POST /v1/reportes/eventos/prueba   aplica un evento a mano
"""
import asyncio
import contextlib
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app import registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.bus_eventos import BusEnMemoria, crear_bus
from app.cliente_config import ClienteConfiguracion
from app.errores import instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.models import VentaPorSkuFila
from app.proyeccion import aplicar_evento, borrar_proyeccion
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
bitacora = logging.getLogger("reportes-service")


class Resumen(BaseModel):
    pedidos_total: int
    unidades_total: int
    monto_total_cop: int


class VentaSku(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sku: str
    pedidos: int
    unidades: int
    monto_cop: int


class EventoManual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evento_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=40)
    tipo: str = Field(pattern="^(PedidoCreado|PedidoCancelado)$")
    payload: dict


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    quien_soy = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_reportes = crear_motor(ajustes)
    sesion_lectura = crear_fabrica_sesiones(motor_reportes)
    flujo_eventos = crear_bus(ajustes)
    config_externa = ClienteConfiguracion(ajustes)
    situacion = {"arranco": False, "escucha": None}

    async def al_recibir(campos: dict) -> None:
        await aplicar_evento(sesion_lectura, campos)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await crear_tablas(motor_reportes)
        situacion["escucha"] = asyncio.create_task(flujo_eventos.escuchar(ajustes.grupo_consumidor, quien_soy, al_recibir))
        config_externa.iniciar()
        await registro_consul.registrar(ajustes, quien_soy)
        situacion["arranco"] = True
        yield
        situacion["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, quien_soy)
        await config_externa.detener()
        situacion["escucha"].cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await situacion["escucha"]
        await flujo_eventos.cerrar()
        await motor_reportes.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Reportes de ventas (CQRS, consistencia eventual).")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": quien_soy}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not situacion["arranco"]:
            respuesta.status_code = 503
        return {"started": situacion["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        stream_ok = await flujo_eventos.esta_vivo()
        datos_ok = await base_responde(motor_reportes)
        version_ok = config_externa.version_aplicada > 0 or ajustes.app_env == "dev"
        en_linea = situacion["arranco"] and stream_ok and datos_ok and version_ok
        if not en_linea:
            respuesta.status_code = 503
        return {"ready": en_linea, "bus": stream_ok, "base_datos": datos_ok,
                "config_version": config_externa.version_aplicada, "instance": quien_soy}

    # ------------------------------------------------------------------ consultas
    @app.get("/v1/reportes/resumen", response_model=Resumen, tags=["reportes"])
    async def resumen():
        async with sesion_lectura() as sesion:
            fila = (await sesion.execute(select(
                func.coalesce(func.sum(VentaPorSkuFila.pedidos), 0),
                func.coalesce(func.sum(VentaPorSkuFila.unidades), 0),
                func.coalesce(func.sum(VentaPorSkuFila.monto_cop), 0),
            ))).one()
        return Resumen(pedidos_total=int(fila[0]), unidades_total=int(fila[1]), monto_total_cop=int(fila[2]))

    @app.get("/v1/reportes/ventas-por-sku", response_model=list[VentaSku], tags=["reportes"])
    async def ventas_por_sku():
        async with sesion_lectura() as sesion:
            return list(await sesion.scalars(select(VentaPorSkuFila).order_by(VentaPorSkuFila.monto_cop.desc())))

    @app.post("/v1/reportes/reconstruir", tags=["reportes"])
    async def reconstruir():
        """Rehace todo desde cero leyendo el stream completo. El resultado debe ser idéntico."""
        historial = await flujo_eventos.leer_historial()
        await borrar_proyeccion(sesion_lectura)
        contador = {"aplicado": 0, "duplicado": 0, "ignorado": 0}
        for campos in historial:
            contador[await aplicar_evento(sesion_lectura, campos)] += 1
        bitacora.info("proyección reconstruida: %s", contador)
        return {"eventos_leidos": len(historial), **contador}

    @app.post("/v1/reportes/eventos/prueba", tags=["reportes"])
    async def aplicar_manual(evento: EventoManual):
        campos = {"evento_id": evento.evento_id, "tipo": evento.tipo, "payload": json.dumps(evento.payload)}
        if isinstance(flujo_eventos, BusEnMemoria):
            flujo_eventos.publicados.append(campos)      # así /reconstruir también funciona sin Redis
        return {"evento_id": evento.evento_id, "resultado": await aplicar_evento(sesion_lectura, campos)}

    return app


app = crear_app()
