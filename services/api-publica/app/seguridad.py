"""Seguridad del perímetro: autenticación por X-API-Key y límite de tasa."""
import hashlib
import hmac

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.settings import Settings

NOMBRE_CABECERA = "X-API-Key"
api_key_header = APIKeyHeader(name=NOMBRE_CABECERA, auto_error=False)


def es_clave_valida(candidata: str | None, esperada: str) -> bool:
    """Comparación en tiempo constante (evita ataques de temporización)."""
    if not esperada or not candidata:
        return False
    return hmac.compare_digest(candidata.encode("utf-8"), esperada.encode("utf-8"))


def crear_validador_api_key(settings: Settings):
    """Devuelve la dependencia de FastAPI que exige una X-API-Key válida (401 si no)."""
    esperada = settings.api_key.get_secret_value()

    async def validar_api_key(api_key: str | None = Security(api_key_header)) -> None:
        if not es_clave_valida(api_key, esperada):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta o es inválida la cabecera X-API-Key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    return validar_api_key


def crear_limiter(settings: Settings) -> Limiter:
    """Límite de tasa compartido por TODAS las rutas protegidas.

    - Clave válida   -> un cubo por clave (hash, nunca el valor en claro).
    - Clave ausente o inválida -> un cubo por IP: así adivinar claves también
      queda limitado (no se evade rotando valores de X-API-Key).
    """
    esperada = settings.api_key.get_secret_value()

    def clave_de_cubo(request: Request) -> str:
        candidata = request.headers.get(NOMBRE_CABECERA)
        if es_clave_valida(candidata, esperada):
            return "key:" + hashlib.sha256(candidata.encode("utf-8")).hexdigest()[:16]
        return "ip:" + get_remote_address(request)

    return Limiter(
        key_func=clave_de_cubo,
        application_limits=[settings.rate_limit],
        storage_uri=settings.rate_limit_storage_uri,
    )
