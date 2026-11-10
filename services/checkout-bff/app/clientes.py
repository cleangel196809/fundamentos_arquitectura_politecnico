"""Llamadas salientes del BFF a los servicios core.

Un solo httpx.AsyncClient por proceso (reutiliza conexiones) y un timeout
distinto por destino. Cada fallo de red se convierte en un `FalloDePaso`
legible, que la saga usa para decidir qué compensar.
"""
import httpx

from app.medicion import CABECERA_CORRELACION, correlacion_actual


class FalloDePaso(Exception):
    def __init__(self, motivo: str, estado_http: int | None = None, cuerpo: dict | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.estado_http = estado_http
        self.cuerpo = cuerpo or {}


class ClienteInterno:
    def __init__(self, http: httpx.AsyncClient, nombre: str, url_base, timeout: float):
        self._http = http
        self._nombre = nombre
        self._raiz = str(url_base).rstrip("/")
        self._timeout = httpx.Timeout(timeout)

    async def pedir(self, metodo: str, ruta: str, *, clave_idempotencia: str | None = None, **opciones) -> dict:
        cabeceras = {CABECERA_CORRELACION: correlacion_actual.get()}
        if clave_idempotencia:
            cabeceras["Idempotency-Key"] = clave_idempotencia
        try:
            respuesta = await self._http.request(metodo, f"{self._raiz}{ruta}", headers=cabeceras,
                                                 timeout=self._timeout, **opciones)
        except httpx.TimeoutException:
            raise FalloDePaso(f"{self._nombre} no respondió a tiempo", 504)
        except httpx.RequestError:
            raise FalloDePaso(f"{self._nombre} no está disponible", 503)
        try:
            cuerpo = respuesta.json()
        except ValueError:
            cuerpo = {}
        if respuesta.status_code >= 400:
            detalle = cuerpo.get("detalle") if isinstance(cuerpo, dict) else None
            raise FalloDePaso(detalle or f"{self._nombre} respondió {respuesta.status_code}", respuesta.status_code, cuerpo)
        return cuerpo
