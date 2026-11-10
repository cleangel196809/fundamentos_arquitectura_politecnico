"""Configuración externalizada de descubridor-service (factor III)."""
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "descubridor-service"
    http_port: int = 8090
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    consul_url: HttpUrl = "http://localhost:8500"
    registrar_en_consul: bool = False
    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 300


def get_settings() -> Settings:
    return Settings()
