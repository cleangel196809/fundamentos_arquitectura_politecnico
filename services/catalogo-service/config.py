"""
Configuración centralizada de catalogo-service.
Cumple con Factor III (Twelve-Factor App) y la regla 2 de arquitectura:
Toda la configuración entra por variables PISHOP_* con pydantic-settings;
los secretos son SecretStr.
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    pishop_app_name: str = "catalogo-service"
    pishop_env: str = "dev"
    pishop_port: int = 8001
    pishop_database_url: str = "sqlite+aiosqlite:///./catalogo.db"
    pishop_secret_key: SecretStr = SecretStr("clave-secreta-catalogo-2026")
    pishop_http_timeout_seconds: float = 2.0
    pishop_event_bus: str = "memory"

    model_config = SettingsConfigDict(
        env_prefix="PISHOP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False
    )


settings = Settings()
