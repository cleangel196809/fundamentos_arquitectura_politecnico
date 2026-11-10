"""Configuración externalizada de catalogo-service (Twelve-Factor, factor III).

Todo entra por variables de entorno con prefijo PISHOP_. Los valores de aquí
son solo los "defaults" que permiten correr las pruebas sin nada instalado.
"""
from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "catalogo-service"
    http_port: int = 8001
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    # Base propia. En compose: postgresql+asyncpg://usr_catalogo@postgres:5432/pg_catalogo
    database_url: str = "sqlite+aiosqlite:///./catalogo_local.db"
    database_password: SecretStr = SecretStr("")

    # Registro, descubrimiento y configuración remota (apagados por defecto en local)
    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    consultar_config_remota: bool = False
    registrar_en_consul: bool = False

    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 500          # por encima de esto se registra "respuesta lenta"
    sembrar_datos: bool = True                # carga productos ficticios si la tabla está vacía
    tamano_pagina_defecto: int = Field(default=20, ge=1, le=100)


def get_settings() -> Settings:
    return Settings()
