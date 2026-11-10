"""
Punto de entrada principal para catalogo-service (Puerto 8001).
Autor: Diego Alejandro Rodríguez Moncada (P01)
Curso: Fundamentos de Arquitectura (1419) - Politécnico Internacional
Docente: Edgar Humberto Angel Millán
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import settings
from database import async_session_factory, init_db, seed_db
from health import health_router, marcar_startup_listo
from router import productos_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # 1. Inicialización de base de datos
    await init_db()
    # 2. Carga de semilla de 10 productos
    async with async_session_factory() as session:
        await seed_db(session)
    # 3. Notificar que startup probe está listo
    marcar_startup_listo()
    yield
    # Limpieza al apagar (graceful shutdown)


app = FastAPI(
    title="catalogo-service",
    description="Servicio Core de Catálogo de Productos para PiShop Cloud. Responsable de productos, precios y publicación.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS para integración con edge / BFF
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handlers personalizados para cumplir la Regla 6 de arquitectura:
# Errores en JSON {"detalle": "...", "codigo": "..."}
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detalle": exc.detail, "codigo": f"HTTP_{exc.status_code}"}
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = exc.errors()
    primer_error = errores[0]["msg"] if errores else "Datos de entrada inválidos"
    campo = ".".join(str(loc) for loc in errores[0].get("loc", [])) if errores else "desconocido"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detalle": f"Validación inválida en '{campo}': {primer_error}",
            "codigo": "VALIDACION_INVALIDA"
        }
    )


# Registrar routers
app.include_router(health_router)
app.include_router(productos_router)


@app.get("/", tags=["raiz"])
async def root() -> dict[str, str]:
    return {
        "servicio": settings.pishop_app_name,
        "entorno": settings.pishop_env,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health/ready"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.pishop_port, reload=True)
