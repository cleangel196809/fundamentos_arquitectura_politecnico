"""Re-exporta el cliente reutilizable para permitir `from config_client import ...`."""
from app.config_client import ESTADO, ConfigClient, bucle, refrescar

__all__ = ["ConfigClient", "ESTADO", "bucle", "refrescar"]
