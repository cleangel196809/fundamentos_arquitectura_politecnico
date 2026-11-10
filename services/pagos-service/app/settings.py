"""Configuración externalizada de pagos-service (factor III)."""
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "pagos-service"
    http_port: int = 8004
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    # En compose: postgresql+asyncpg://usr_pagos@postgres:5432/pg_pagos
    database_url: str = "sqlite+aiosqlite:///./pagos_local.db"
    database_password: SecretStr = SecretStr("")

    # Pasarela de pagos SIMULADA (vive en este mismo servicio, en /_simulador)
    pasarela_url: HttpUrl = "http://localhost:8004/_simulador/pasarela/cobrar"
    pasarela_modo: str = Field(default="ok", pattern="^(ok|rechaza|lenta|falla)$")
    pasarela_demora_lenta_segundos: float = 5.0    # en modo "lenta" tarda más que el timeout

    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    consultar_config_remota: bool = False
    registrar_en_consul: bool = False

    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 500


def get_settings() -> Settings:
    return Settings()
