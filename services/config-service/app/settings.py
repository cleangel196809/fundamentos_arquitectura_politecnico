"""Configuración externalizada del propio config-service (factor III)."""
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "config-service"
    http_port: int = 8010
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    archivo_semilla: Path = Path(__file__).with_name("seed.json")
    # Si se define, cambiar configuración (PUT / rollback) exige la cabecera X-Token-Admin.
    admin_token: SecretStr = SecretStr("")

    consul_url: HttpUrl = "http://localhost:8500"
    registrar_en_consul: bool = False
    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 300


def get_settings() -> Settings:
    return Settings()
