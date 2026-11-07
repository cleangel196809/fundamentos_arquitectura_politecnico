"""Configuración externalizada (Twelve-Factor, factor III).

Todo entra por variables de entorno con prefijo PISHOP_.
"""
from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore")

    service_name: str = "api-publica"
    http_port: int = 8000
    app_env: str = "dev"
    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    http_timeout_seconds: float = 2.0     # timeout explícito (semana 3)

    # --- específicos de la fachada ---
    api_key: SecretStr = SecretStr("cambiar-en-entorno")
    checkout_bff_url: HttpUrl = "http://localhost:8080"
    catalogo_url: HttpUrl = "http://localhost:8001"
    rate_limit_per_minute: int = 60


def get_settings() -> Settings:
    return Settings()
