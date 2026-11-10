"""Middleware de medición y correlación (aplica a TODAS las rutas).

1. Mide cuánto tarda cada respuesta y la devuelve en la cabecera
   `X-Tiempo-Respuesta-ms`. Si supera el umbral configurado
   (PISHOP_UMBRAL_RESPUESTA_MS) deja una advertencia en el log.
2. Propaga un identificador de correlación `X-Correlacion-Id`: si la petición
   ya trae uno lo respeta, si no lo crea. Así se puede seguir una compra
   completa en los logs de varios servicios.
"""
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

CABECERA_CORRELACION = "X-Correlacion-Id"
correlacion_actual: ContextVar[str] = ContextVar("correlacion_actual", default="-")
bitacora = logging.getLogger("medicion")


class MedidorDeTiempos(BaseHTTPMiddleware):
    def __init__(self, app, umbral_ms: float):
        super().__init__(app)
        self._umbral_ms = umbral_ms

    async def dispatch(self, request, call_next):
        recibido = request.headers.get(CABECERA_CORRELACION, "")
        identificador = recibido if 0 < len(recibido) <= 64 and recibido.replace("-", "").isalnum() else uuid.uuid4().hex
        correlacion_actual.set(identificador)
        inicio = time.perf_counter_ns()
        respuesta = await call_next(request)
        duracion_ms = (time.perf_counter_ns() - inicio) / 1_000_000
        respuesta.headers["X-Tiempo-Respuesta-ms"] = f"{duracion_ms:.3f}"
        respuesta.headers[CABECERA_CORRELACION] = identificador
        if duracion_ms > self._umbral_ms and not request.url.path.startswith("/health"):
            bitacora.warning("respuesta lenta: %s %s tardó %.1f ms (umbral %.0f ms) [correlacion=%s]",
                             request.method, request.url.path, duracion_ms, self._umbral_ms, identificador)
        return respuesta
