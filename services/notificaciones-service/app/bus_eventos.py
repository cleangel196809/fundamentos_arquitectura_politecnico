"""Bus de eventos de PiShop (semana 3: comunicación asíncrona).

Dos implementaciones con la MISMA interfaz:
  * BusEnMemoria -> para pruebas (PISHOP_EVENT_BUS=memory), sin Redis.
  * BusRedis     -> Redis 8 Streams (PISHOP_EVENT_BUS=redis), en docker-compose.

Stream: `pishop.pedidos`. Cada entrada lleva: evento_id, tipo y payload (JSON).
Entrega "al menos una vez": los consumidores deben descartar duplicados
usando evento_id.
"""
import asyncio
import json
import logging

bitacora = logging.getLogger("bus-eventos")
STREAM_PEDIDOS = "pishop.pedidos"
ESPERA_LECTURA_MS = 2000      # cuánto espera XREADGROUP por mensajes nuevos


class BusEnMemoria:
    """Bus falso para pruebas: guarda los eventos en una lista."""

    def __init__(self):
        self.publicados: list[dict] = []

    async def publicar(self, evento_id: str, tipo: str, contenido: dict) -> None:
        self.publicados.append({"evento_id": evento_id, "tipo": tipo, "payload": json.dumps(contenido)})

    async def esta_vivo(self) -> bool:
        return True

    async def leer_historial(self) -> list[dict]:
        return list(self.publicados)

    async def escuchar(self, grupo: str, consumidor: str, manejar) -> None:
        # En memoria no hay nada que escuchar: los eventos se inyectan con /prueba.
        await asyncio.Event().wait()

    async def cerrar(self) -> None:
        return None


class BusRedis:
    def __init__(self, url_redis: str, timeout_segundos: float):
        import redis.asyncio as redis_asincrono   # import tardío: las pruebas no lo necesitan
        # El timeout del socket debe ser MAYOR que la espera bloqueante de XREADGROUP (2 s),
        # si no, cada lectura sin mensajes nuevos se confundiría con un Redis caído.
        self._redis = redis_asincrono.from_url(
            url_redis, decode_responses=True,
            socket_timeout=timeout_segundos + ESPERA_LECTURA_MS / 1000, socket_connect_timeout=timeout_segundos,
        )

    async def publicar(self, evento_id: str, tipo: str, contenido: dict) -> None:
        await self._redis.xadd(STREAM_PEDIDOS, {"evento_id": evento_id, "tipo": tipo, "payload": json.dumps(contenido)})

    async def esta_vivo(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:  # noqa: BLE001
            return False

    async def leer_historial(self) -> list[dict]:
        """Todo el stream desde el principio (lo usa la reconstrucción CQRS)."""
        entradas = await self._redis.xrange(STREAM_PEDIDOS, "-", "+")
        return [campos for _id, campos in entradas]

    async def escuchar(self, grupo: str, consumidor: str, manejar) -> None:
        """Bucle consumidor con grupo: lee, procesa y confirma (XACK)."""
        try:
            await self._redis.xgroup_create(STREAM_PEDIDOS, grupo, id="0", mkstream=True)
        except Exception as problema:  # noqa: BLE001 - BUSYGROUP = el grupo ya existe
            if "BUSYGROUP" not in str(problema):
                bitacora.warning("no se pudo crear el grupo %s: %s", grupo, problema)
        # Primero los pendientes propios (mensajes leídos pero no confirmados antes de una caída),
        # después los nuevos (">").
        posicion = "0"
        while True:
            try:
                lote = await self._redis.xreadgroup(grupo, consumidor, {STREAM_PEDIDOS: posicion},
                                                    count=20, block=ESPERA_LECTURA_MS)
            except asyncio.CancelledError:
                raise
            except Exception as problema:  # noqa: BLE001
                bitacora.warning("Redis no responde (%s); reintento en 2 s", problema.__class__.__name__)
                await asyncio.sleep(2)
                continue
            mensajes = lote[0][1] if lote else []
            if posicion == "0" and not mensajes:
                posicion = ">"
                continue
            for id_mensaje, campos in mensajes:
                try:
                    await manejar(campos)
                    await self._redis.xack(STREAM_PEDIDOS, grupo, id_mensaje)
                except Exception:  # noqa: BLE001 - se reintenta en la próxima lectura de pendientes
                    bitacora.exception("falló el procesamiento de %s; queda pendiente", id_mensaje)

    async def cerrar(self) -> None:
        await self._redis.aclose()


def crear_bus(ajustes):
    if ajustes.event_bus == "redis":
        return BusRedis(ajustes.redis_url, ajustes.http_timeout_seconds)
    return BusEnMemoria()
