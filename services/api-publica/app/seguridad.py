"""Autenticación por X-API-Key y límite de tasa por clave."""
import math
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Header, Request

from app.errores import ProblemaError


class LimitadorTasa:
    """Ventana deslizante en memoria: máximo `maximo` peticiones por `ventana` segundos."""

    def __init__(self, maximo: int, ventana: float = 60.0,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.maximo, self.ventana, self.reloj = maximo, ventana, reloj
        self._eventos: dict[str, deque[float]] = defaultdict(deque)

    def intentar(self, clave: str) -> int | None:
        """None si se permite; si no, segundos a esperar (Retry-After)."""
        ahora = self.reloj()
        cola = self._eventos[clave]
        while cola and ahora - cola[0] >= self.ventana:
            cola.popleft()
        if len(cola) >= self.maximo:
            return max(1, math.ceil(self.ventana - (ahora - cola[0])))
        cola.append(ahora)
        return None


async def exigir_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    esperada = request.app.state.settings.api_key.get_secret_value()
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), esperada.encode()):
        raise ProblemaError(401, "No autorizado", "Falta o es inválida la cabecera X-API-Key.",
                            "api_key_invalida")
    espera = request.app.state.limitador.intentar(x_api_key)
    if espera is not None:
        raise ProblemaError(429, "Demasiadas peticiones",
                            "Superó el límite de peticiones por minuto.", "limite_excedido",
                            headers={"Retry-After": str(espera)})
    return x_api_key
