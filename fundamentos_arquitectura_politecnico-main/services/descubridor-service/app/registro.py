"""Registro/baja en Consul, reutilizable desde el lifespan de cualquier servicio."""
import socket

import httpx

from app.settings import settings

# ID único por instancia: permite varias réplicas del mismo servicio.
SERVICE_ID = f"{settings.service_name}-{socket.gethostname()}"


async def registrar() -> None:
    payload = {
        "ID": SERVICE_ID,
        "Name": settings.service_name,
        "Address": socket.gethostname(),
        "Port": settings.http_port,
        "Check": {
            "HTTP": f"http://{socket.gethostname()}:{settings.http_port}/health/live",
            "Interval": "10s",
            "Timeout": "3s",
            "DeregisterCriticalServiceAfter": "30s",
        },
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        try:
            await client.put(f"{settings.consul_url}/v1/agent/service/register", json=payload)
        except Exception as e:  # Consul caído no debe tumbar el arranque
            print(f"Error registrando en Consul: {e}")


async def dar_de_baja() -> None:
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        try:
            await client.put(f"{settings.consul_url}/v1/agent/service/deregister/{SERVICE_ID}")
        except Exception as e:
            print(f"Error dando de baja en Consul: {e}")
