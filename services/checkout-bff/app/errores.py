"""Formato único de errores de los servicios internos (docs/CONTRATOS.md, regla 6).

Todos los errores salen como JSON {"detalle": "...", "codigo": "..."}.
Nunca se devuelve la traza de Python al cliente: solo se escribe en el log.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

bitacora = logging.getLogger("errores")

CODIGOS_POR_ESTADO = {
    400: "SOLICITUD_INVALIDA", 401: "NO_AUTENTICADO", 404: "NO_ENCONTRADO",
    409: "CONFLICTO", 422: "VALIDACION", 502: "RESPUESTA_INVALIDA",
    503: "NO_DISPONIBLE", 504: "TIEMPO_AGOTADO",
}


class ErrorDeNegocio(Exception):
    """Error esperado del dominio (ej.: stock insuficiente). Se traduce a JSON."""

    def __init__(self, estado_http: int, detalle: str, codigo: str | None = None):
        super().__init__(detalle)
        self.estado_http = estado_http
        self.detalle = detalle
        self.codigo = codigo or CODIGOS_POR_ESTADO.get(estado_http, "ERROR")


def _cuerpo(estado: int, detalle: str, codigo: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"detalle": detalle, "codigo": codigo, **extra})


def instalar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorDeNegocio)
    async def _de_negocio(_: Request, falla: ErrorDeNegocio):
        return _cuerpo(falla.estado_http, falla.detalle, falla.codigo)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, falla: StarletteHTTPException):
        return _cuerpo(falla.status_code, str(falla.detail), CODIGOS_POR_ESTADO.get(falla.status_code, "ERROR"))

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, falla: RequestValidationError):
        # Se omite el valor recibido ("input") para no reflejar datos del cliente.
        campos = [{"campo": ".".join(str(p) for p in e["loc"]), "problema": e["msg"]} for e in falla.errors()]
        return _cuerpo(422, "La solicitud no cumple el contrato.", "VALIDACION", errores=campos)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, _falla: Exception):
        bitacora.exception("error no controlado en %s %s", request.method, request.url.path)
        return _cuerpo(500, "Ocurrió un error inesperado.", "ERROR_INTERNO")
