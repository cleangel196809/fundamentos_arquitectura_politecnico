"""catalogo-service (P01) — servicio CORE dueño de los productos de PiShop.

Responsabilidad única: qué se vende y a qué precio. No sabe de existencias
(inventario), ni de pedidos, ni de pagos.

Base propia: pg_catalogo (usuario usr_catalogo).

Rutas del contrato (docs/CONTRATOS.md):
  GET   /v1/productos                  lista paginada (tamano máximo 100)
  POST  /v1/productos                  crea (201) · SKU repetido 409 · precio <= 0 422
  GET   /v1/productos/{sku}            detalle (200 / 404)
  PATCH /v1/productos/{sku}/publicar   lo deja visible en la tienda (200 / 404)
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import registro_consul
from app.base_datos import base_responde, crear_fabrica_sesiones, crear_motor, crear_tablas
from app.cliente_config import ClienteConfiguracion
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.repository import RepositorioCatalogo
from app.schemas import PaginaDeProductos, ProductoDetalle, ProductoNuevo
from app.semilla import filas_de_ejemplo
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
bitacora = logging.getLogger("catalogo-service")


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    id_instancia = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    motor_catalogo = crear_motor(ajustes)
    abrir_sesion = crear_fabrica_sesiones(motor_catalogo)
    configuracion_remota = ClienteConfiguracion(ajustes)
    ciclo_de_vida = {"arranco": False}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # 1) Tablas y datos ficticios (solo si la tabla está vacía)
        await crear_tablas(motor_catalogo)
        if ajustes.sembrar_datos:
            async with abrir_sesion() as sesion:
                if await RepositorioCatalogo(sesion).esta_vacio():
                    sesion.add_all(filas_de_ejemplo())
                    await sesion.commit()
                    bitacora.info("catálogo sembrado con productos de ejemplo")
        # 2) Configuración remota y registro en Consul (ambos tolerantes a fallo)
        configuracion_remota.iniciar()
        await registro_consul.registrar(ajustes, id_instancia)
        ciclo_de_vida["arranco"] = True
        yield
        ciclo_de_vida["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, id_instancia)
        await configuracion_remota.detener()
        await motor_catalogo.dispose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Catálogo de productos de PiShop Cloud (servicio core).")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    async def sesion_por_peticion():
        async with abrir_sesion() as sesion:
            yield sesion

    # ------------------------------------------------------------------ sondas de salud
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        """Barata y local: NUNCA consulta la base ni otros servicios."""
        return {"status": "alive", "instance": id_instancia}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not ciclo_de_vida["arranco"]:
            respuesta.status_code = 503
        return {"started": ciclo_de_vida["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    async def listo(respuesta: Response) -> dict:
        """Listo = arrancó + la base responde + (en qa/stg/prod) hay configuración aplicada."""
        base_ok = await base_responde(motor_catalogo)
        config_ok = configuracion_remota.version_aplicada > 0 or ajustes.app_env == "dev"
        preparado = ciclo_de_vida["arranco"] and base_ok and config_ok
        if not preparado:
            respuesta.status_code = 503
        return {"ready": preparado, "base_datos": base_ok,
                "config_version": configuracion_remota.version_aplicada, "instance": id_instancia}

    # ------------------------------------------------------------------ rutas del contrato
    @app.get("/v1/productos", response_model=PaginaDeProductos, tags=["productos"])
    async def listar_productos(
        pagina: int = Query(1, ge=1),
        tamano: int | None = Query(None, ge=1, le=100, description="Por defecto lo define el config-service"),
        categoria: str | None = Query(None, max_length=40),
        solo_publicados: bool = Query(False),
        sesion: AsyncSession = Depends(sesion_por_peticion),
    ):
        # Recarga en caliente: si el config-service cambia "pagina_tamano", se nota aquí sin reiniciar.
        tamano_efectivo = tamano or int(configuracion_remota.valor("pagina_tamano", ajustes.tamano_pagina_defecto))
        tamano_efectivo = max(1, min(tamano_efectivo, 100))
        encontrados, total = await RepositorioCatalogo(sesion).listar(pagina, tamano_efectivo, categoria, solo_publicados)
        return PaginaDeProductos(items=[ProductoDetalle.model_validate(p) for p in encontrados],
                                 total=total, pagina=pagina, tamano=tamano_efectivo)

    @app.post("/v1/productos", response_model=ProductoDetalle, status_code=201, tags=["productos"])
    async def crear_producto(nuevo: ProductoNuevo, sesion: AsyncSession = Depends(sesion_por_peticion)):
        creado = await RepositorioCatalogo(sesion).crear(nuevo)
        return ProductoDetalle.model_validate(creado)

    @app.get("/v1/productos/{sku}", response_model=ProductoDetalle, tags=["productos"])
    async def ver_producto(sku: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_por_peticion)):
        hallado = await RepositorioCatalogo(sesion).buscar_por_sku(sku)
        if hallado is None:
            raise ErrorDeNegocio(404, f"No existe el producto {sku}")
        return ProductoDetalle.model_validate(hallado)

    @app.patch("/v1/productos/{sku}/publicar", response_model=ProductoDetalle, tags=["productos"])
    async def publicar_producto(sku: str = Path(max_length=40), sesion: AsyncSession = Depends(sesion_por_peticion)):
        return ProductoDetalle.model_validate(await RepositorioCatalogo(sesion).publicar(sku))

    return app


app = crear_app()
