"""Configuración externalizada de pedidos-service (factor III)."""
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "pedidos-service"
    http_port: int = 8003
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    # En compose: postgresql+asyncpg://usr_pedidos@postgres:5432/pg_pedidos
    database_url: str = "sqlite+aiosqlite:///./pedidos_local.db"
    database_password: SecretStr = SecretStr("")

    # Bus de eventos: "memory" en pruebas, "redis" en docker-compose
    event_bus: str = Field(default="memory", pattern="^(memory|redis)$")
    redis_url: str = "redis://localhost:6379/0"
    outbox_intervalo_segundos: float = Field(default=1.0, gt=0)   # cada cuánto revisa la outbox
    publicador_activo: bool = True

    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    consultar_config_remota: bool = False
    registrar_en_consul: bool = False

    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 500


def get_settings() -> Settings:
    return Settings()
