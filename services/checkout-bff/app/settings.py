"""Configuración externalizada de checkout-bff (factor III).

Las direcciones de los servicios core son NOMBRES lógicos (DNS de Docker),
nunca IP. Cada servicio tiene su propio timeout: el presupuesto total de una
compra queda por debajo de 5 segundos aunque todo vaya lento.
"""
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True)

    service_name: str = "checkout-bff"
    http_port: int = 8080
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    catalogo_url: HttpUrl = "http://localhost:8001"
    inventario_url: HttpUrl = "http://localhost:8002"
    pedidos_url: HttpUrl = "http://localhost:8003"
    pagos_url: HttpUrl = "http://localhost:8004"

    # Timeouts por servicio (segundos). Pagos es mayor porque adentro espera a la pasarela.
    timeout_catalogo: float = Field(default=1.0, gt=0, le=10)
    timeout_inventario: float = Field(default=1.0, gt=0, le=10)
    timeout_pedidos: float = Field(default=1.0, gt=0, le=10)
    timeout_pagos: float = Field(default=2.5, gt=0, le=10)
    max_consultas_paralelas: int = Field(default=10, ge=1, le=50)    # bulkhead de la vitrina

    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    consultar_config_remota: bool = False
    registrar_en_consul: bool = False

    http_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    umbral_respuesta_ms: float = 1500


def get_settings() -> Settings:
    return Settings()
