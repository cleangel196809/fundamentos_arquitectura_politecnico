"""Cliente del config-service: polling cada N segundos con ETag (semana 4).

- Si nada cambió, el config-service responde 304 y no se transfiere nada.
- Si el config-service está caído, el servicio sigue funcionando con su
  última configuración conocida (o con los valores por defecto).
- La versión aplicada se reporta en /health/ready (`config_version`).
"""
import asyncio
import contextlib
import logging

import httpx

bitacora = logging.getLogger("cliente-config")


class ClienteConfiguracion:
    def __init__(self, ajustes):
        self._ajustes = ajustes
        self.version_aplicada = 0
        self.valores: dict = {}
        self._etiqueta_etag: str | None = None
        self._tarea: asyncio.Task | None = None

    def valor(self, nombre: str, por_defecto=None):
        """Lee un parámetro remoto; si no existe devuelve el valor por defecto."""
        return self.valores.get(nombre, por_defecto)

    async def consultar_una_vez(self) -> None:
        ruta = f"{str(self._ajustes.config_service_url).rstrip('/')}/config/{self._ajustes.service_name}/{self._ajustes.app_env}"
        cabeceras = {"If-None-Match": self._etiqueta_etag} if self._etiqueta_etag else {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._ajustes.http_timeout_seconds)) as cliente:
                respuesta = await cliente.get(ruta, headers=cabeceras)
        except httpx.HTTPError as problema:
            bitacora.warning("config-service no disponible (%s); sigo con la versión %s",
                             problema.__class__.__name__, self.version_aplicada)
            return
        if respuesta.status_code == 304:
            return
        if respuesta.status_code != 200:
            bitacora.warning("config-service respondió %s para %s", respuesta.status_code, ruta)
            return
        cuerpo = respuesta.json()
        self.valores = dict(cuerpo.get("data", {}))
        self.version_aplicada = int(cuerpo.get("version", 0))
        self._etiqueta_etag = respuesta.headers.get("ETag")
        bitacora.info("configuración v%s aplicada", self.version_aplicada)

    async def _bucle(self) -> None:
        while True:
            await self.consultar_una_vez()
            await asyncio.sleep(self._ajustes.config_poll_seconds)

    def iniciar(self) -> None:
        if self._ajustes.consultar_config_remota:
            self._tarea = asyncio.create_task(self._bucle())

    async def detener(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea
