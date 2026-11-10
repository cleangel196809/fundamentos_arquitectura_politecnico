"""
Sondas de salud con semántica diferenciada (Kubernetes / Twelve-Factor App).
Cumple con la Regla 3 de arquitectura:
- /health/live: El proceso está vivo (liveness probe).
- /health/ready: El servicio puede recibir tráfico (base de datos responde) (readiness probe).
- /health/startup: El servicio ha completado su inicialización (tablas creadas) (startup probe).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

health_router = APIRouter(prefix="/health", tags=["health"])

# Bandera de inicio completado
_STARTUP_COMPLETO = False


def marcar_startup_listo() -> None:
    global _STARTUP_COMPLETO
    _STARTUP_COMPLETO = True


@health_router.get("/live", status_code=status.HTTP_200_OK)
async def health_live() -> dict[str, str]:
    """Sonda liveness: verifica que el proceso está activo. No evalúa dependencias externas."""
    return {"status": "ALIVE", "servicio": "catalogo-service"}


@health_router.get("/ready")
async def health_ready(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Sonda readiness: verifica que el servicio puede atender tráfico (base de datos conectada)."""
    try:
        # Prueba de conectividad con timeout
        await db.execute(text("SELECT 1"))
        return {"status": "READY", "servicio": "catalogo-service", "database": "CONNECTED"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Base de datos no disponible: {str(e)}"
        )


@health_router.get("/startup")
async def health_startup(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Sonda startup: verifica que la inicialización inicial del servicio terminó con éxito."""
    if not _STARTUP_COMPLETO:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio en proceso de inicialización"
        )
    try:
        await db.execute(text("SELECT 1 FROM productos LIMIT 1"))
        return {"status": "STARTED", "servicio": "catalogo-service"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Inicialización incompleta: {str(e)}"
        )
