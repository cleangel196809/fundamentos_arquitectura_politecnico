"""descubridor-service (P09) — consulta a Consul y balancea entre instancias sanas.

Descubrimiento del lado del CLIENTE: quien necesita llamar a otro servicio
pregunta aquí (o a Consul) qué instancias están "passing" y elige una con
round-robin. Ver docs/descubrimiento.md para la comparación con el lado del
servidor.

Rutas del contrato:
  GET /v1/servicios                          nombres registrados en Consul
  GET /v1/servicios/{nombre}/instancias      solo las instancias sanas (passing)
  GET /v1/servicios/{nombre}/resolver        una URL, rotando entre las sanas
"""
import itertools
import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Path, Request, Response

from app import registro_consul
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
NOMBRE_SERVICIO = r"^[a-z0-9][a-z0-9-]{1,48}$"


def crear_app(ajustes: Settings | None = None, transporte: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    yo_mismo = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    raiz_consul = str(ajustes.consul_url).rstrip("/")
    turnos: dict[str, itertools.count] = {}        # un contador de round-robin por servicio
    encendido = {"arranco": False}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(ajustes.http_timeout_seconds), transport=transporte)
        await registro_consul.registrar(ajustes, yo_mismo)
        encendido["arranco"] = True
        yield
        encendido["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, yo_mismo)
        await app.state.http.aclose()

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Descubrimiento de servicios sobre Consul con balanceo round-robin.")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    async def preguntar_a_consul(request: Request, ruta: str, **parametros):
        try:
            respuesta = await request.app.state.http.get(f"{raiz_consul}{ruta}", params=parametros)
            respuesta.raise_for_status()
            return respuesta.json()
        except httpx.TimeoutException:
            raise ErrorDeNegocio(504, "Consul no respondió a tiempo")
        except httpx.HTTPError:
            raise ErrorDeNegocio(503, "Consul no está disponible")

    async def sanas(request: Request, nombre: str) -> list[dict]:
        entradas = await preguntar_a_consul(request, f"/v1/health/service/{nombre}", passing="true")
        return [{"id": e["Service"]["ID"], "direccion": e["Service"]["Address"], "puerto": e["Service"]["Port"],
                 "url": f"http://{e['Service']['Address']}:{e['Service']['Port']}"} for e in entradas]

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": yo_mismo}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not encendido["arranco"]:
            respuesta.status_code = 503
        return {"started": encendido["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    def listo(respuesta: Response) -> dict:
        if not encendido["arranco"]:
            respuesta.status_code = 503
        return {"ready": encendido["arranco"], "config_version": 0, "instance": yo_mismo}

    # ------------------------------------------------------------------ descubrimiento
    @app.get("/v1/servicios", tags=["descubrimiento"])
    async def servicios(request: Request) -> list[str]:
        catalogo_consul = await preguntar_a_consul(request, "/v1/catalog/services")
        return sorted(nombre for nombre in catalogo_consul if nombre != "consul")

    @app.get("/v1/servicios/{nombre}/instancias", tags=["descubrimiento"])
    async def instancias(request: Request, nombre: str = Path(pattern=NOMBRE_SERVICIO)) -> list[dict]:
        return await sanas(request, nombre)

    @app.get("/v1/servicios/{nombre}/resolver", tags=["descubrimiento"])
    async def resolver(request: Request, nombre: str = Path(pattern=NOMBRE_SERVICIO)) -> dict:
        disponibles = await sanas(request, nombre)
        if not disponibles:
            raise ErrorDeNegocio(503, f"No hay instancias sanas de {nombre}", "SIN_INSTANCIAS")
        turno = next(turnos.setdefault(nombre, itertools.count()))
        elegida = disponibles[turno % len(disponibles)]
        return {"servicio": nombre, "url": elegida["url"], "instancia": elegida["id"], "sanas": len(disponibles)}

    return app


app = crear_app()
