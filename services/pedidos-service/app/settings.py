from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PISHOP_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "pedidos-service"
    http_port: int = 8003
    app_env: str = "dev"

    # Database
    database_url: str = "sqlite+aiosqlite:///./pedidos.db"
    database_password: SecretStr = SecretStr("cambiar-en-entorno")

    # Event bus
    event_bus: str = "memory"           # "memory" or "redis"
    redis_url: str = "redis://localhost:6379"

    # Publisher
    publish_interval_seconds: float = 5.0

    # External services
    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"

    # HTTP client
    http_timeout_seconds: float = 2.0


def get_settings() -> Settings:
    return Settings()
