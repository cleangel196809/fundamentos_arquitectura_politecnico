"""Errores en application/problem+json (RFC 9457, antes RFC 7807).

Regla de seguridad: el cliente nunca recibe trazas, rutas internas ni valores
de entrada; el detalle completo se escribe solo en el log del servidor.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("api-publica")
BASE_TIPOS = "https://pishop.cloud/errors"
TITULOS = {
    400: "Solicitud inválida", 401: "No autenticado", 403: "Prohibido", 404: "No encontrado",
    405: "Método no permitido", 422: "Entidad no procesable", 429: "Demasiadas solicitudes",
    500: "Error interno del servidor", 502: "Respuesta inválida del servicio interno",
    503: "Servicio no disponible", 504: "Tiempo de espera agotado",
}


def problema(request: Request, status: int, detail: str, slug: str, headers: dict | None = None, **extra) -> JSONResponse:
    cuerpo = {
        "type": f"{BASE_TIPOS}/{slug}",
        "title": TITULOS.get(status, "Error"),
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        **extra,
    }
    return JSONResponse(status_code=status, content=cuerpo, media_type="application/problem+json", headers=headers)


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return problema(request, exc.status_code, str(exc.detail), f"http-{exc.status_code}", headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validacion(request: Request, exc: RequestValidationError):
        # Solo ubicación, mensaje y tipo: se descarta 'input' (podría reflejar datos del cliente).
        errores = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problema(request, 422, "La solicitud no cumple el contrato.", "validation-error", errors=errores)

    # OJO: debe ser función síncrona (def). El middleware de slowapi ignora los
    # manejadores async para RateLimitExceeded y usaría su respuesta por defecto.
    def limite_excedido(request: Request, exc: RateLimitExceeded):
        espera = 60
        vista = getattr(request.state, "view_rate_limit", None)
        if vista:
            reinicio, _ = request.app.state.limiter.limiter.get_window_stats(vista[0], *vista[1])
            espera = max(1, int(reinicio - time.time()) + 1)
        return problema(
            request, 429, "Superó el límite de peticiones permitido.", "rate-limit",
            headers={"Retry-After": str(espera)},
        )

    app.add_exception_handler(RateLimitExceeded, limite_excedido)

    @app.exception_handler(Exception)
    async def no_controlado(request: Request, exc: Exception):
        log.exception("Error no controlado en %s %s", request.method, request.url.path)
        return problema(request, 500, "Ocurrió un error inesperado al procesar la solicitud.", "internal-error")
