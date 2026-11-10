"""Configuración externalizada (Twelve-Factor). Todo entra por variables PISHOP_*."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore")

    service_name: str = "descubridor-service"   # PISHOP_SERVICE_NAME
    http_port: int = 8090                        # PISHOP_HTTP_PORT
    app_env: str = "dev"                         # PISHOP_APP_ENV
    consul_url: str = "http://consul:8500"       # PISHOP_CONSUL_URL (en local: http://localhost:8500)
    http_timeout_seconds: float = 2.0            # PISHOP_HTTP_TIMEOUT_SECONDS


settings = Settings()
