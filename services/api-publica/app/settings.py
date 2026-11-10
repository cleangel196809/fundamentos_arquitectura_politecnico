"""Configuración externalizada de api-publica (Twelve-Factor, factor III).

Nada sensible vive en el código: todo entra por variables PISHOP_*.
El secreto de la API es SecretStr, así que un print/log/traza muestra '**********'
y no el valor real (solo se obtiene con .get_secret_value()).
"""
from pydantic import Field, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de ejemplo que nunca deben aceptarse fuera de desarrollo.
CLAVES_DE_EJEMPLO = {"", "cambiar-esto", "cambiar-en-entorno"}
LARGO_MINIMO_CLAVE = 16


class Settings(BaseSettings):
    # hide_input_in_errors: si la validación falla, pydantic NO imprime los valores de entrada
    # (por defecto los incluye en el mensaje y filtraría la clave a los logs de arranque).
    model_config = SettingsConfigDict(
        env_prefix="PISHOP_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    service_name: str = "api-publica"
    http_port: int = 8000
    app_env: str = Field(default="dev", pattern="^(dev|qa|stg|prod)$")

    # --- Seguridad del perímetro (P07) -------------------------------------
    # Vacío = "falla cerrado": ninguna petición pasa la autenticación.
    api_key: SecretStr = Field(default=SecretStr(""), description="Secreto de la API pública (X-API-Key)")
    rate_limit: str = "40/minute"                 # requisito del proyecto: máximo 40 peticiones/min por clave
    rate_limit_storage_uri: str = "memory://"     # en varias réplicas: redis://redis:6379/1

    # --- Servicios internos a los que enruta --------------------------------
    catalogo_url: HttpUrl = "http://localhost:8001"
    checkout_url: HttpUrl = "http://localhost:8080"
    config_service_url: HttpUrl = "http://localhost:8010"
    consul_url: HttpUrl = "http://localhost:8500"
    config_poll_seconds: int = 15
    registrar_en_consul: bool = False
    consultar_config_remota: bool = False

    # Timeout explícito para toda llamada saliente (semana 3, Bulkhead)
    # El BFF puede tardar hasta ~4 s en el peor caso (pago lento + compensaciones):
    # se le da 5 s como máximo y nunca más (presupuesto total de respuesta).
    http_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    umbral_respuesta_ms: float = 1500

    @model_validator(mode="after")
    def _exigir_clave_fuerte_fuera_de_dev(self) -> "Settings":
        clave = self.api_key.get_secret_value()
        if self.app_env != "dev" and (clave in CLAVES_DE_EJEMPLO or len(clave) < LARGO_MINIMO_CLAVE):
            # El mensaje NO incluye el valor de la clave.
            raise ValueError(
                f"PISHOP_API_KEY ausente, de ejemplo o menor a {LARGO_MINIMO_CLAVE} caracteres "
                f"en el entorno '{self.app_env}'"
            )
        return self


def get_settings() -> Settings:
    return Settings()
