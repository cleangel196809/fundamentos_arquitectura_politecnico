"""ACL — Capa Anticorrupción frente a la pasarela de pagos (semana 2).

La pasarela habla su propio idioma (APPROVED / DECLINED / TIMEOUT, campos en
inglés). El dominio de PiShop solo conoce APROBADO / RECHAZADO / PENDIENTE.
Este adaptador es el ÚNICO lugar que conoce ambos vocabularios: si mañana se
cambia de pasarela, solo se toca este archivo.
"""
from dataclasses import dataclass

import httpx

TRADUCCION_ESTADOS = {"APPROVED": "APROBADO", "DECLINED": "RECHAZADO", "TIMEOUT": "PENDIENTE"}


@dataclass
class ResultadoCobro:
    estado: str                    # vocabulario del dominio
    codigo_autorizacion: str = ""


class PasarelaNoResponde(Exception):
    """La pasarela tardó más que el timeout (se traduce a HTTP 504)."""


class PasarelaCaida(Exception):
    """La pasarela no está disponible o falló internamente (HTTP 503)."""


async def cobrar(cliente_http: httpx.AsyncClient, url_pasarela: str, referencia: str, monto: int) -> ResultadoCobro:
    try:
        respuesta = await cliente_http.post(url_pasarela, json={"reference": referencia, "amount": monto, "currency": "COP"})
    except httpx.TimeoutException as demora:
        raise PasarelaNoResponde() from demora
    except httpx.RequestError as corte:
        raise PasarelaCaida() from corte
    if respuesta.status_code >= 500:
        raise PasarelaCaida()
    datos_externos = respuesta.json()
    estado_dominio = TRADUCCION_ESTADOS.get(datos_externos.get("status", ""), "PENDIENTE")
    return ResultadoCobro(estado=estado_dominio, codigo_autorizacion=str(datos_externos.get("auth_code") or ""))
