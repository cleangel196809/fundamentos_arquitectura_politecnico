"""Configuración externalizada (Twelve-Factor, factor III).

Ningún valor de entorno, dirección o secreto debe estar escrito en el código
de negocio. Todo entra por variables de entorno con prefijo PISHOP_.
"""
from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore")

    service_name: str = "checkout-bff"
    http_port: int = 8080
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./local.db"   # en compose: postgresql+asyncpg://...
    database_password: SecretStr = SecretStr("cambiar-en-entorno")
    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    catalogo_service_url: HttpUrl = "http://localhost:8001"
    inventario_service_url: HttpUrl = "http://localhost:8002"
    pedidos_service_url: HttpUrl = "http://localhost:8003"
    pagos_service_url: HttpUrl = "http://localhost:8004"
    config_poll_seconds: int = 15
    http_timeout_seconds: float = 2.0     # timeout explícito (semana 3)


def get_settings() -> Settings:
    return Settings()
