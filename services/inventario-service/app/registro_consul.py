"""Auto-registro en Consul (semana 4: registro y descubrimiento).

Al arrancar, el servicio le dice a Consul "existo, estoy en esta IP y puerto,
y para saber si sigo sano consulta mi /health/ready cada 10 segundos".
Al apagarse se da de baja. Si el proceso muere de golpe (SIGKILL), Consul lo
elimina solo cuando lleva 1 minuto en estado crítico.

Todo es tolerante a fallos: si Consul no está, el servicio igual arranca.
"""
import logging
import socket

import httpx

bitacora = logging.getLogger("registro-consul")


def ip_del_contenedor() -> str:
    """IP del contenedor dentro de la red de Docker (la que Consul puede alcanzar)."""
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return socket.gethostname()


async def registrar(ajustes, id_instancia: str) -> bool:
    if not ajustes.registrar_en_consul:
        return False
    direccion = ip_del_contenedor()
    ficha = {
        "ID": id_instancia,
        "Name": ajustes.service_name,
        "Address": direccion,
        "Port": ajustes.http_port,
        "Meta": {"entorno": ajustes.app_env},
        "Check": {
            "HTTP": f"http://{direccion}:{ajustes.http_port}/health/ready",
            "Interval": "10s",
            "Timeout": "2s",
            "DeregisterCriticalServiceAfter": "1m",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(ajustes.http_timeout_seconds)) as cliente:
            respuesta = await cliente.put(f"{str(ajustes.consul_url).rstrip('/')}/v1/agent/service/register", json=ficha)
        respuesta.raise_for_status()
        bitacora.info("registrado en Consul como %s (%s:%s)", id_instancia, direccion, ajustes.http_port)
        return True
    except httpx.HTTPError as problema:
        bitacora.warning("no se pudo registrar en Consul (%s); se sigue sin registro", problema.__class__.__name__)
        return False


async def dar_de_baja(ajustes, id_instancia: str) -> None:
    if not ajustes.registrar_en_consul:
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(ajustes.http_timeout_seconds)) as cliente:
            await cliente.put(f"{str(ajustes.consul_url).rstrip('/')}/v1/agent/service/deregister/{id_instancia}")
    except httpx.HTTPError:
        pass   # al apagar no vale la pena insistir
