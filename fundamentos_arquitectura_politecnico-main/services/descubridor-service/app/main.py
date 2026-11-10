"""Descubridor Service (P09): consulta de servicios registrados en Consul."""
import itertools
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Response

from app.registro import dar_de_baja, registrar
from app.settings import settings

ESTADO = {"arranco": False}
# Contador por servicio para el balanceo round-robin.
_CONTADORES: dict[str, itertools.count] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await registrar()
    ESTADO["arranco"] = True
    yield
    ESTADO["arranco"] = False
    await dar_de_baja()


app = FastAPI(title="Descubridor Service", version="1.0.0", lifespan=lifespan)


def _consul_get(ruta: str):
    """GET a Consul; si no responde devuelve 503 (dependencia caída, no error interno)."""
    try:
        r = httpx.get(f"{settings.consul_url}{ruta}", timeout=settings.http_timeout_seconds)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Consul no disponible: {e}")


def _instancias_sanas(nombre: str) -> list[dict]:
    data = _consul_get(f"/v1/health/service/{nombre}?passing=true")
    return [
        {
            "id": item["Service"]["ID"],
            "nombre": item["Service"]["Service"],
            "direccion": item["Service"]["Address"],
            "puerto": item["Service"]["Port"],
        }
        for item in data
    ]


@app.get("/v1/servicios", tags=["descubrimiento"])
def listar_servicios():
    """Servicios registrados en Consul (nombre -> tags)."""
    return _consul_get("/v1/catalog/services")


@app.get("/v1/servicios/{nombre}/instancias", tags=["descubrimiento"])
def listar_instancias(nombre: str):
    """Instancias en estado passing de un servicio."""
    return {"servicio": nombre, "instancias": _instancias_sanas(nombre)}


@app.get("/v1/servicios/{nombre}/resolver", tags=["descubrimiento"])
def resolver_servicio(nombre: str):
    """Devuelve una instancia sana, rotando en round-robin."""
    instancias = _instancias_sanas(nombre)
    if not instancias:
        raise HTTPException(status_code=404, detail="No hay instancias sanas para este servicio")
    contador = _CONTADORES.setdefault(nombre, itertools.count())
    inst = instancias[next(contador) % len(instancias)]
    return {**inst, "url": f"http://{inst['direccion']}:{inst['puerto']}"}


@app.get("/health/live", tags=["salud"])
def health_live():
    """Barata y local: nunca toca dependencias."""
    return {"status": "alive"}


@app.get("/health/startup", tags=["salud"])
def health_startup(resp: Response):
    if not ESTADO["arranco"]:
        resp.status_code = 503
    return {"started": ESTADO["arranco"]}


@app.get("/health/ready", tags=["salud"])
def health_ready(resp: Response):
    """Listo si arrancó y Consul responde."""
    try:
        httpx.get(f"{settings.consul_url}/v1/status/leader", timeout=settings.http_timeout_seconds).raise_for_status()
        consul_ok = True
    except httpx.HTTPError:
        consul_ok = False
    ok = ESTADO["arranco"] and consul_ok
    if not ok:
        resp.status_code = 503
    return {"ready": ok, "consul": consul_ok}
