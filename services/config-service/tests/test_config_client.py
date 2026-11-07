"""Activity 6: pruebas de config_client.py (ETag 304, polling, tolerancia a fallo y defaults)."""
import asyncio

import httpx

from app.config_client import ESTADO, ConfigClient
from app.main import RUTA_SEED_POR_DEFECTO, app, cargar_semilla
from app.store import Repositorio


def _run(coro):
    return asyncio.run(coro)


def test_arranca_con_defaults_si_config_service_esta_caido():
    def _caido(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    estado_srv = {"arranco": True, "config_version": 0}
    cliente = ConfigClient(
        base_url="http://config-service:8010",
        service_name="catalogo-service",
        app_env="prod",
        defaults={"pagina_tamano": 20, "timeout_inventario_s": 3.0},
        timeout_seconds=0.5,
        transport=httpx.MockTransport(_caido),
        estado_externo=estado_srv,
    )
    cambio = _run(cliente.refrescar())
    assert cambio is False
    # Criterio 2 y 3 del reto 4.1: usa defaults, no explota y mantiene config_version == 0
    assert cliente.version == 0
    assert estado_srv["config_version"] == 0
    assert cliente.obtener("pagina_tamano") == 20
    assert cliente.ultimo_error is not None


def test_refrescar_usa_etag_recibe_304_y_recarga_en_caliente_nueva_version():
    async def _escenario():
        repo = Repositorio("sqlite+aiosqlite:///:memory:")
        await repo.crear_esquema()
        await cargar_semilla(repo, str(RUTA_SEED_POR_DEFECTO))
        from app import main as main_mod

        main_mod.ESTADO["repo"] = repo
        main_mod.ESTADO["arranco"] = True

        transporte = httpx.ASGITransport(app=app)
        estado_srv = {"arranco": True, "config_version": 0}
        cliente = ConfigClient(
            base_url="http://config-service:8010",
            service_name="catalogo-service",
            app_env="prod",
            defaults={"pagina_tamano": 10},
            transport=transporte,
            estado_externo=estado_srv,
        )

        # 1) Primer refresco: recibe v1 de la semilla (pagina_tamano=50 en prod)
        assert await cliente.refrescar() is True
        assert cliente.version == 1
        assert cliente.etag == '"v1"'
        assert cliente.obtener("pagina_tamano") == 50
        assert estado_srv["config_version"] == 1
        assert ESTADO["version"] == 1

        # 2) Segundo refresco sin cambios: envía If-None-Match '"v1"' y recibe 304
        assert await cliente.refrescar() is False
        assert cliente.version == 1

        # 3) Publicamos v2 en el servidor (cambio en caliente de pagina_tamano a 80)
        async with httpx.AsyncClient(transport=transporte, base_url="http://config-service:8010") as c:
            r = await c.put(
                "/config/catalogo-service/prod",
                json={"data": {"pagina_tamano": 80, "timeout_inventario_s": 1.2}, "motivo": "campaña cosecha"},
                headers={"X-Autor": "fnavarro"},
            )
            assert r.status_code == 201

        # 4) Siguiente refresco: detecta ETag nuevo y actualiza a v2 sin reiniciar
        assert await cliente.refrescar() is True
        assert cliente.version == 2
        assert cliente.etag == '"v2"'
        assert cliente.obtener("pagina_tamano") == 80
        assert estado_srv["config_version"] == 2

        await repo.cerrar()

    _run(_escenario())


def test_conserva_ultima_version_si_el_servidor_cae_despues_de_arrancar():
    fallar = {"activo": False}

    def _simulador(request: httpx.Request) -> httpx.Response:
        if fallar["activo"]:
            raise httpx.ReadTimeout("timeout leyendo config-service")
        return httpx.Response(
            200,
            headers={"ETag": '"v4"'},
            json={"version": 4, "data": {"pagina_tamano": 45}},
        )

    cliente = ConfigClient(
        base_url="http://config-service:8010",
        service_name="catalogo-service",
        app_env="prod",
        defaults={"pagina_tamano": 20},
        transport=httpx.MockTransport(_simulador),
    )
    assert _run(cliente.refrescar()) is True
    assert cliente.version == 4 and cliente.obtener("pagina_tamano") == 45

    # Ahora el config-service cae: el cliente conserva v4 y pagina_tamano=45
    fallar["activo"] = True
    assert _run(cliente.refrescar()) is False
    assert cliente.version == 4 and cliente.obtener("pagina_tamano") == 45


def test_bucle_de_polling_iniciar_y_detener():
    llamadas = {"n": 0}

    def _simulador(request: httpx.Request) -> httpx.Response:
        llamadas["n"] += 1
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304, headers={"ETag": '"v1"'})
        return httpx.Response(
            200,
            headers={"ETag": '"v1"'},
            json={"version": 1, "data": {"pagina_tamano": 30}},
        )

    async def _correr():
        c = ConfigClient(
            base_url="http://config-service:8010",
            service_name="catalogo-service",
            app_env="dev",
            poll_seconds=0.03,
            transport=httpx.MockTransport(_simulador),
        )
        await c.iniciar()
        await asyncio.sleep(0.08)
        await c.detener()
        assert llamadas["n"] >= 2
        assert c.version == 1

    _run(_correr())


def test_callback_on_update_se_dispara_solo_cuando_cambia_la_version():
    eventos: list[tuple[int, int]] = []
    version_actual = {"v": 1, "tam": 25}

    def _simulador(request: httpx.Request) -> httpx.Response:
        etag = f'"v{version_actual["v"]}"'
        if request.headers.get("If-None-Match") == etag:
            return httpx.Response(304, headers={"ETag": etag})
        return httpx.Response(
            200,
            headers={"ETag": etag},
            json={"version": version_actual["v"], "data": {"pagina_tamano": version_actual["tam"]}},
        )

    cliente = ConfigClient(
        base_url="http://config-service:8010",
        service_name="catalogo-service",
        app_env="prod",
        transport=httpx.MockTransport(_simulador),
        on_update=lambda v, d: eventos.append((v, d["pagina_tamano"])),
    )
    assert _run(cliente.refrescar()) is True
    assert _run(cliente.refrescar()) is False  # 304 -> no dispara callback
    version_actual.update(v=2, tam=60)
    assert _run(cliente.refrescar()) is True
    assert eventos == [(1, 25), (2, 60)]

