"""Cliente reutilizable de configuración para servicios de PiShop Cloud (P08).

Implementa los criterios de la semana 4 (diapositivas 23-28 y 48, Reto 4.1):
  - Tiempo real por long-polling: el bucle deja abierta la petición con
    `?esperar=25` + If-None-Match y recibe el cambio en cuanto ocurre el PUT.
  - Respaldo por polling periódico (cada 15 s) si el servidor no soporta long-polling o falla.
  - Cabecera If-None-Match con ETag: si responde 304 Not Modified no toca el estado.
  - Timeout explícito con httpx.AsyncClient (regla 4 del contrato).
  - Tolerancia a fallo: si el config-service está caído al arrancar o durante un
    refresco, el servicio NO muere; conserva los defaults o la última versión
    conocida en caché local y registra el incidente en el log.
  - Expone ESTADO["version"] (y sincroniza estado_externo["config_version"] si se
    entrega el diccionario ESTADO de la plantilla) para la sonda /health/ready.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx

logger = logging.getLogger("pishop.config_client")

# Estado global compatible con la demo de la semana 4 (`from config_client import ESTADO`)
ESTADO: dict[str, Any] = {"version": 0, "data": {}, "etag": None}


class ConfigClient:
    """Cliente asíncrono con caché local, ETag y recarga en caliente por polling."""

    def __init__(
        self,
        base_url: str,
        service_name: str,
        app_env: str = "dev",
        defaults: dict[str, Any] | None = None,
        poll_seconds: float = 15.0,
        timeout_seconds: float = 2.0,
        espera_seconds: float = 25.0,
        transport: httpx.AsyncBaseTransport | None = None,
        estado_externo: dict[str, Any] | None = None,
        on_update: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.service_name = service_name
        self.app_env = app_env
        self.defaults: dict[str, Any] = dict(defaults or {})
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.espera_seconds = espera_seconds  # long-polling; 0 = polling clásico
        self._transport = transport
        self._estado_externo = estado_externo
        self._on_update = on_update

        self.version: int = 0
        self.etag: str | None = None
        self.data: dict[str, Any] = dict(self.defaults)
        self.ultimo_error: str | None = None
        self._tarea: asyncio.Task[None] | None = None
        self._sincronizar_estado()

    def _sincronizar_estado(self) -> None:
        ESTADO["version"] = self.version
        ESTADO["data"] = dict(self.data)
        ESTADO["etag"] = self.etag
        if self._estado_externo is not None:
            self._estado_externo["config_version"] = self.version

    def obtener(self, clave: str, defecto: Any = None) -> Any:
        """Devuelve el valor efectivo (remoto sobre default)."""
        return self.data.get(clave, self.defaults.get(clave, defecto))

    async def refrescar(self, esperar: float = 0.0) -> bool:
        """Consulta el config-service una vez.

        Con `esperar` > 0 y un ETag conocido hace long-polling: el servidor retiene
        la petición hasta que haya una versión nueva (tiempo real) o pasen `esperar` s.
        Retorna True si aplicó una versión nueva, False si hubo 304 o si falló
        (en cuyo caso conserva la versión previa o los defaults).
        """
        cabeceras = {"If-None-Match": self.etag} if self.etag else {}
        url = f"{self.base_url}/config/{self.service_name}/{self.app_env}"
        params = {"esperar": esperar} if (esperar > 0 and self.etag) else None
        # Timeout explícito: conexión = timeout_seconds; lectura = espera del long-poll + margen.
        espera_lectura = esperar if params else 0.0
        timeout = httpx.Timeout(self.timeout_seconds, read=self.timeout_seconds + espera_lectura)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as c:
                r = await c.get(url, headers=cabeceras, params=params)
            if r.status_code == 304:
                self.ultimo_error = None
                return False
            r.raise_for_status()
            cuerpo = r.json()
            remoto = cuerpo.get("data", {})
            self.version = int(cuerpo.get("version", 1))
            self.etag = r.headers.get("ETag") or f'"v{self.version}"'
            self.data = {**self.defaults, **remoto}
            self.ultimo_error = None
            self._sincronizar_estado()
            if self._on_update is not None:
                self._on_update(self.version, dict(self.data))
            return True
        except httpx.HTTPError as exc:
            self.ultimo_error = str(exc)
            logger.warning(
                "[config] fallo consultando %s, conservo v%s (defaults=%s): %s",
                url,
                self.version,
                bool(self.defaults),
                exc,
            )
            self._sincronizar_estado()
            return False

    async def iniciar(self) -> None:
        """Hace un primer refresco tolerante a fallo y lanza el bucle de polling."""
        await self.refrescar()
        if self._tarea is None or self._tarea.done():
            self._tarea = asyncio.create_task(self._bucle())

    async def _bucle(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            if self.espera_seconds > 0 and self.etag and self.ultimo_error is None:
                inicio = loop.time()
                cambio = await self.refrescar(esperar=self.espera_seconds)
                # Si el servidor respondió 304 al instante (no soporta long-polling)
                # o falló, se cae al polling clásico para no saturarlo.
                rapido = (loop.time() - inicio) < self.espera_seconds / 2
                if not cambio and (rapido or self.ultimo_error):
                    await asyncio.sleep(self.poll_seconds)
            else:
                await asyncio.sleep(self.poll_seconds)
                await self.refrescar()

    async def detener(self) -> None:
        """Detiene limpiamente la tarea de polling en el cierre del lifespan."""
        if self._tarea is not None:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass
            self._tarea = None


async def refrescar(
    base: str,
    app: str,
    env: str,
    timeout_s: float = 2.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """Función compatible con la Demo 1 (4/4) de la semana 4."""
    cab = {"If-None-Match": ESTADO["etag"]} if ESTADO["etag"] else {}
    async with httpx.AsyncClient(timeout=timeout_s, transport=transport) as c:
        r = await c.get(f"{base.rstrip('/')}/config/{app}/{env}", headers=cab)
    if r.status_code != 304:
        r.raise_for_status()
        cuerpo = r.json()
        ESTADO.update(
            version=cuerpo["version"],
            data=cuerpo["data"],
            etag=r.headers.get("ETag"),
        )


async def bucle(s: Any, cada_s: float = 15.0) -> None:
    """Bucle de polling compatible con Settings de cualquier servicio."""
    while True:
        try:
            await refrescar(
                str(s.config_service_url),
                s.service_name,
                s.app_env,
                timeout_s=getattr(s, "http_timeout_seconds", 2.0),
            )
        except httpx.HTTPError as e:
            logger.warning("[config] fallo, conservo v%s: %s", ESTADO["version"], e)
        await asyncio.sleep(cada_s)
