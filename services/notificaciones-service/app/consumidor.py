"""Lógica del consumidor de `pishop.pedidos` (grupo `notificaciones`).

Idempotencia: la entrega es "al menos una vez", así que el MISMO evento puede
llegar dos veces. Se descarta el duplicado por `evento_id` (y como segunda
barrera, la columna es UNIQUE en la base).
"""
import json
import logging
import zlib

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import NotificacionFila

bitacora = logging.getLogger("consumidor-notificaciones")

PLANTILLAS = {
    "PedidoCreado": "Hola {cliente}: recibimos tu pedido {pedido} de {cantidad} x {sku} por ${monto:,} COP.",
    "PedidoCancelado": "Hola {cliente}: tu pedido {pedido} fue cancelado y no se te cobrará nada.",
}


def elegir_canal(cliente_id: str) -> str:
    """Simulación: unos clientes prefieren correo y otros SMS (determinístico)."""
    return "email" if zlib.crc32(cliente_id.encode()) % 2 == 0 else "sms"


async def procesar_evento(fabrica_sesiones, campos: dict) -> str:
    """Devuelve 'enviada', 'duplicado' o 'ignorado'."""
    identificador = campos.get("evento_id", "")
    tipo = campos.get("tipo", "")
    if tipo not in PLANTILLAS or not identificador:
        return "ignorado"
    datos = json.loads(campos.get("payload") or "{}")
    async with fabrica_sesiones() as sesion:
        if await sesion.scalar(select(NotificacionFila.id).where(NotificacionFila.evento_id == identificador)):
            bitacora.info("[dup] evento %s ya procesado: se descarta", identificador)
            return "duplicado"
        texto = PLANTILLAS[tipo].format(cliente=datos.get("cliente_id", "?"), pedido=datos.get("pedido_id", "?"),
                                        cantidad=datos.get("cantidad", 0), sku=datos.get("sku", "?"),
                                        monto=int(datos.get("monto_cop", 0)))
        sesion.add(NotificacionFila(evento_id=identificador, pedido_id=datos.get("pedido_id", ""),
                                    cliente_id=datos.get("cliente_id", ""), tipo_evento=tipo,
                                    canal=elegir_canal(datos.get("cliente_id", "")), mensaje=texto[:300]))
        try:
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            bitacora.info("[dup] evento %s llegó dos veces a la vez: se descarta", identificador)
            return "duplicado"
    bitacora.info("notificación enviada (simulada) por el evento %s", identificador)
    return "enviada"
