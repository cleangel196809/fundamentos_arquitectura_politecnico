"""Errores en application/problem+json (RFC 9457)."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"


class ProblemaError(Exception):
    def __init__(self, status: int, title: str, detail: str, codigo: str,
                 headers: dict[str, str] | None = None) -> None:
        self.status, self.title, self.detail = status, title, detail
        self.codigo, self.headers = codigo, headers or {}


def _respuesta(status: int, title: str, detail: str, codigo: str, instance: str,
               headers: dict[str, str] | None = None) -> JSONResponse:
    cuerpo = {"type": "about:blank", "title": title, "status": status,
              "detail": detail, "instance": instance, "codigo": codigo}
    return JSONResponse(cuerpo, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemaError)
    async def _problema(request: Request, exc: ProblemaError):
        return _respuesta(exc.status, exc.title, exc.detail, exc.codigo,
                          request.url.path, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codigo = "no_encontrado" if exc.status_code == 404 else "error_http"
        return _respuesta(exc.status_code, "Error HTTP", str(exc.detail), codigo, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError):
        return _respuesta(422, "Solicitud inválida", str(exc.errors()), "validacion", request.url.path)
