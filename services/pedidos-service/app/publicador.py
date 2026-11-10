"""Publicador en segundo plano: outbox -> stream `pishop.pedidos`.

Garantía: AL MENOS UNA VEZ (at-least-once). Si el proceso muere justo después
de publicar y antes de marcar `publicado_en`, al volver a arrancar publica el
mismo evento otra vez. Por eso los consumidores (notificaciones y reportes)
descartan duplicados por `evento_id`.

¿Por qué no "exactamente una vez"? Porque publicar en Redis y marcar en
PostgreSQL son dos sistemas distintos: no hay una transacción que abarque a
ambos. Lo que se complementa es la IDEMPOTENCIA del consumidor.
"""
import asyncio
import contextlib
import json
import logging
from datetime import datetime, timezone

from app.repository import RepositorioPedidos

bitacora = logging.getLogger("publicador-outbox")


async def publicar_lote(fabrica_sesiones, bus, antes_de_marcar=None) -> int:
    """Publica los eventos pendientes y los marca. Devuelve cuántos publicó.

    `antes_de_marcar` solo existe para la prueba que simula una caída entre
    "publicar" y "marcar".
    """
    async with fabrica_sesiones() as sesion:
        pendientes = await RepositorioPedidos(sesion).eventos_sin_publicar()
        for evento in pendientes:
            await bus.publicar(evento.evento_id, evento.tipo, json.loads(evento.contenido_json))
            if antes_de_marcar:
                antes_de_marcar(evento)
            evento.publicado_en = datetime.now(timezone.utc)
            await sesion.commit()
        return len(pendientes)


class PublicadorOutbox:
    def __init__(self, fabrica_sesiones, bus, cada_segundos: float):
        self._fabrica = fabrica_sesiones
        self._bus = bus
        self._pausa = cada_segundos
        self._tarea: asyncio.Task | None = None

    async def _girar(self) -> None:
        while True:
            try:
                enviados = await publicar_lote(self._fabrica, self._bus)
                if enviados:
                    bitacora.info("outbox: %s evento(s) publicados en pishop.pedidos", enviados)
            except asyncio.CancelledError:
                raise
            except Exception as problema:  # noqa: BLE001 - Redis caído: se reintenta en la próxima vuelta
                bitacora.warning("no se pudo publicar la outbox (%s); se reintenta", problema.__class__.__name__)
            await asyncio.sleep(self._pausa)

    def iniciar(self) -> None:
        self._tarea = asyncio.create_task(self._girar())

    async def detener(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea
