"""Configuración externalizada del config-service (Twelve-Factor, factor III).

Ningún valor de entorno, dirección o secreto debe estar escrito en el código
de negocio. Todo entra por variables de entorno con prefijo PISHOP_.
"""
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", frozen=True)

    service_name: str = "config-service"
    http_port: int = Field(default=8010, ge=1024, le=65535)
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")
    # Base propia del config-service (regla 1). En pruebas: sqlite+aiosqlite:///:memory:
    database_url: str = "sqlite+aiosqlite:///./config.db"
    # Ruta de la semilla; vacío = usar seed.json junto al servicio. Si no existe, arranca vacío.
    seed_path: str = ""
    # Token de la API: si está definido, todo /config/* exige "Authorization: Bearer <token>".
    # Nunca se escribe en el código: llega por la variable de entorno PISHOP_API_TOKEN.
    # Si no se define, la API queda pública (modo de prueba, Swagger sin candados).
    api_token: SecretStr = SecretStr("")
    # Host con el que se anuncian las direcciones al arrancar (enlaces para abrir con Ctrl + clic).
    public_host: str = "127.0.0.1"
    # Token opcional ADICIONAL para escribir (PUT/rollback). Vacío = basta el token de la API + X-Autor.
    write_token: SecretStr = SecretStr("")
    http_timeout_seconds: float = Field(default=2.0, gt=0, le=10)


def get_settings() -> Settings:
    return Settings()
