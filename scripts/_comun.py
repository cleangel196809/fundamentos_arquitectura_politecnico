"""Utilidades compartidas por los scripts (solo biblioteca estándar: no hay que instalar nada)."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PUERTOS = {
    "api-publica": 8000, "catalogo-service": 8001, "inventario-service": 8002, "pedidos-service": 8003,
    "pagos-service": 8004, "notificaciones-service": 8005, "reportes-service": 8006,
    "checkout-bff": 8080, "config-service": 8010, "descubridor-service": 8090,
}


def leer_env() -> dict:
    """Lee el .env de la raíz (las variables del sistema tienen prioridad)."""
    valores = {}
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            nombre, signo, valor = linea.partition("=")
            if signo and not linea.lstrip().startswith("#"):
                valores[nombre.strip()] = valor.strip()
    valores.update({k: v for k, v in os.environ.items() if k.startswith(("PISHOP_", "PUERTO_"))})
    return valores


def url(servicio: str, ruta: str, anfitrion: str = "localhost") -> str:
    return f"http://{anfitrion}:{PUERTOS[servicio]}{ruta}"


def pedir(metodo: str, direccion: str, cuerpo=None, cabeceras=None, espera: float = 8.0):
    """Hace una petición HTTP y devuelve (codigo, json_o_texto, cabeceras en minúscula). Nunca lanza por 4xx/5xx."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(direccion, data=datos, method=metodo,
                                      headers={"Content-Type": "application/json", **(cabeceras or {})})
    try:
        with urllib.request.urlopen(peticion, timeout=espera) as respuesta:
            texto = respuesta.read().decode()
            return respuesta.status, _quizas_json(texto), _minusculas(respuesta.headers)
    except urllib.error.HTTPError as error:
        return error.code, _quizas_json(error.read().decode()), _minusculas(error.headers)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        return 0, str(error), {}


def _minusculas(cabeceras) -> dict:
    return {nombre.lower(): valor for nombre, valor in cabeceras.items()}


def _quizas_json(texto: str):
    try:
        return json.loads(texto)
    except ValueError:
        return texto


def esperar_sistema(segundos_maximos: int = 180) -> bool:
    """Espera a que todos los servicios respondan /health/ready."""
    limite = time.time() + segundos_maximos
    while time.time() < limite:
        pendientes = [s for s in PUERTOS if pedir("GET", url(s, "/health/ready"), espera=2)[0] != 200]
        if not pendientes:
            return True
        print(f"  ... esperando a: {', '.join(pendientes)}")
        time.sleep(5)
    return False
