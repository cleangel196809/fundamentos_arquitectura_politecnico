"""Configuración externalizada de inventario-service (factor III)."""
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "inventario-service"
    http_port: int = 8002
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    # En compose: postgresql+asyncpg://usr_inventario@postgres:5432/pg_inventario
    database_url: str = "sqlite+aiosqlite:///./inventario_local.db"
    database_password: SecretStr = SecretStr("")

    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    consultar_config_remota: bool = False
    registrar_en_consul: bool = False

    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 500
    sembrar_datos: bool = True


def get_settings() -> Settings:
    return Settings()
