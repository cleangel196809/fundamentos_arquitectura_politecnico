"""inventario-service (P02) — servicio CORE dueño de las existencias.

Base propia: pg_inventario (usuario usr_inventario).

Rutas del contrato:
  GET  /v1/stock/{sku}                      {sku, cantidad, reservado, disponible}
  PUT  /v1/stock/{sku}                      fija la cantidad (>= 0)
  POST /v1/reservas                         aparta unidades (exige Idempotency-Key) · 409 sin stock
  POST /v1/reservas/{reserva_id}/liberar    compensación idempotente
Ruta adicional (la usa el BFF al final de una compra exitosa):
  POST /v1/reservas/{reserva_id}/confirmar  descuenta definitivamente de bodega

Eje del cubo de escalabilidad: Y (descomposición funcional, ya aplicada) y,
si crece, Z (particionar por SKU): las reservas de un mismo SKU compiten entre
sí, pero SKU distintos no, así que se pueden repartir en particiones.
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Path, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.cliente_config import ClienteConfiguracion
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.repository import RepositorioInventario
from app.schemas import ReservaSolicitud, ReservaVista, StockAjuste, StockVista
from app.semilla import existencias_de_ejemplo
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
bitacora = logging.getLogger("inventario-service")
CLAVE_SEGURA = r"^[A-Za-z0-9_.:\-]+$"


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    nombre_instancia = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_bodega = crear_motor(ajustes)
    nueva_sesion = crear_fabrica_sesiones(motor_bodega)
    parametros_remotos = ClienteConfiguracion(ajustes)
    estado_proceso = {"arranco": False}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await crear_tablas(motor_bodega)
        if ajustes.sembrar_datos:
            async with nueva_sesion() as sesion:
                if not await RepositorioInventario(sesion).hay_existencias():
                    sesion.add_all(existencias_de_ejemplo())
                    await sesion.commit()
                    bitacora.info("inventario sembrado con existencias de ejemplo")
        parametros_remotos.iniciar()
        await registro_consul.registrar(ajustes, nombre_instancia)
        estado_proceso["arranco"] = True
        yield
        estado_proceso["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, nombre_instancia)
        await parametros_remotos.detener()
        await motor_bodega.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Existencias y reservas de PiShop Cloud (servicio core).")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    async def sesion_bodega():
        async with nueva_sesion() as sesion:
            yield sesion

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": nombre_instancia}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not estado_proceso["arranco"]:
            respuesta.status_code = 503
        return {"started": estado_proceso["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        base_viva = await base_responde(motor_bodega)
        hay_config = parametros_remotos.version_aplicada > 0 or ajustes.app_env == "dev"
        apto = estado_proceso["arranco"] and base_viva and hay_config
        if not apto:
            respuesta.status_code = 503
        return {"ready": apto, "base_datos": base_viva,
                "config_version": parametros_remotos.version_aplicada, "instance": nombre_instancia}

    # ------------------------------------------------------------------ existencias
    @app.get("/v1/stock/{sku}", response_model=StockVista, tags=["stock"])
    async def ver_stock(sku: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_bodega)):
        return await RepositorioInventario(sesion).consultar(sku)

    @app.put("/v1/stock/{sku}", response_model=StockVista, tags=["stock"])
    async def ajustar_stock(ajuste: StockAjuste, sku: str = Path(max_length=40),
                            sesion: AsyncSession = Depends(sesion_bodega)):
        return await RepositorioInventario(sesion).fijar_cantidad(sku, ajuste.cantidad)

    # ------------------------------------------------------------------ reservas
    @app.post("/v1/reservas", status_code=201, response_model=ReservaVista, tags=["reservas"])
    async def apartar_unidades(
        solicitud: ReservaSolicitud,
        idempotency_key: str | None = Header(default=None, max_length=128, pattern=CLAVE_SEGURA),
        sesion: AsyncSession = Depends(sesion_bodega),
    ):
        if not idempotency_key:
            raise ErrorDeNegocio(400, "La cabecera Idempotency-Key es obligatoria", "FALTA_IDEMPOTENCY_KEY")
        codigo, cuerpo = await RepositorioInventario(sesion).reservar(solicitud, idempotency_key)
        return JSONResponse(status_code=codigo, content=cuerpo)

    @app.post("/v1/reservas/{reserva_id}/liberar", response_model=ReservaVista, tags=["reservas"])
    async def liberar_reserva(reserva_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_bodega)):
        return await RepositorioInventario(sesion).liberar(reserva_id)

    @app.post("/v1/reservas/{reserva_id}/confirmar", response_model=ReservaVista, tags=["reservas"])
    async def confirmar_reserva(reserva_id: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_bodega)):
        return await RepositorioInventario(sesion).confirmar(reserva_id)

    return app


app = crear_app()
