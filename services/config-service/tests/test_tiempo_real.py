"""Tiempo real: el PUT llega a los clientes al instante (long-polling y SSE), sin esperar 15 s."""
import asyncio
import json
import time

import httpx

from app import main as main_mod
from app.config_client import ConfigClient
from app.main import app
from app.store import Repositorio

BASE = "http://config-service:8010"
RUTA = "/config/catalogo-service/prod"


async def _preparar() -> Repositorio:
    repo = Repositorio("sqlite+aiosqlite:///:memory:")
    await repo.crear_esquema()
    await repo.publicar("catalogo-service", "prod", {"pagina_tamano": 50}, "seed", "semilla")
    main_mod.ESTADO.update(repo=repo, arranco=True, config_version=1, cambio=None)
    return repo


async def _put_tras(c: httpx.AsyncClient, segundos: float, tam: int) -> None:
    await asyncio.sleep(segundos)
    r = await c.put(RUTA, json={"data": {"pagina_tamano": tam}, "motivo": "cambio en vivo"}, headers={"X-Autor": "fnavarro"})
    assert r.status_code == 201


def test_long_polling_recibe_el_put_al_instante():
    async def escenario():
        repo = await _preparar()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE, timeout=10) as c:
            inicio = time.perf_counter()
            espera = c.get(RUTA, params={"esperar": 10}, headers={"If-None-Match": '"v1"'})
            r, _ = await asyncio.gather(espera, _put_tras(c, 0.2, 80))
            transcurrido = time.perf_counter() - inicio
        await repo.cerrar()
        assert r.status_code == 200
        assert r.headers["ETag"] == '"v2"'
        assert r.json()["data"]["pagina_tamano"] == 80
        assert transcurrido < 2, f"tardó {transcurrido:.2f} s; debía llegar casi al instante"

    asyncio.run(escenario())


def test_long_polling_sin_cambios_responde_304_al_agotar_la_espera():
    async def escenario():
        repo = await _preparar()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE, timeout=10) as c:
            inicio = time.perf_counter()
            r = await c.get(RUTA, params={"esperar": 0.3}, headers={"If-None-Match": '"v1"'})
            transcurrido = time.perf_counter() - inicio
        await repo.cerrar()
        assert r.status_code == 304
        assert 0.25 <= transcurrido < 2

    asyncio.run(escenario())


def test_config_client_recarga_en_tiempo_real_sin_esperar_el_polling():
    async def escenario():
        repo = await _preparar()
        transporte = httpx.ASGITransport(app=app)
        cliente = ConfigClient(
            base_url=BASE, service_name="catalogo-service", app_env="prod",
            poll_seconds=15, espera_seconds=10, transport=transporte,
        )
        await cliente.iniciar()
        assert cliente.version == 1
        async with httpx.AsyncClient(transport=transporte, base_url=BASE) as c:
            await _put_tras(c, 0.1, 99)
        for _ in range(40):  # hasta 2 s, muy por debajo de los 15 s del polling
            if cliente.version == 2:
                break
            await asyncio.sleep(0.05)
        await cliente.detener()
        await repo.cerrar()
        assert cliente.version == 2
        assert cliente.obtener("pagina_tamano") == 99

    asyncio.run(escenario())


def test_eventos_sse_emite_version_vigente_y_cada_cambio():
    async def escenario():
        repo = await _preparar()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE, timeout=10) as c:
            flujo = c.get(f"{RUTA}/eventos", params={"max_eventos": 2})
            r, _ = await asyncio.gather(flujo, _put_tras(c, 0.2, 70))
        await repo.cerrar()
        assert r.headers["content-type"].startswith("text/event-stream")
        datos = [json.loads(l[len("data: "):]) for l in r.text.splitlines() if l.startswith("data: ")]
        assert [d["version"] for d in datos] == [1, 2]
        assert datos[1]["data"]["pagina_tamano"] == 70

    asyncio.run(escenario())
