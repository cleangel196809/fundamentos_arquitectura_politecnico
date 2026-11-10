"""Proyección idempotente de ventas (CQRS).

Cada evento se aplica en UNA transacción que hace dos cosas:
  1) anota su evento_id en `eventos_aplicados` (clave primaria), y
  2) suma o resta en `ventas_por_sku`.
Si el evento ya estaba anotado, no se toca nada: reprocesar no altera totales.
"""
import json
import logging

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.models import EventoAplicadoFila, VentaPorSkuFila

bitacora = logging.getLogger("proyeccion-ventas")
SIGNO_POR_TIPO = {"PedidoCreado": +1, "PedidoCancelado": -1}


async def aplicar_evento(fabrica_sesiones, campos: dict) -> str:
    """Devuelve 'aplicado', 'duplicado' o 'ignorado'."""
    codigo_evento = campos.get("evento_id", "")
    tipo = campos.get("tipo", "")
    signo = SIGNO_POR_TIPO.get(tipo)
    if signo is None or not codigo_evento:
        return "ignorado"
    venta = json.loads(campos.get("payload") or "{}")
    sku = str(venta.get("sku", "SIN-SKU"))
    async with fabrica_sesiones() as sesion:
        if await sesion.get(EventoAplicadoFila, codigo_evento):
            return "duplicado"
        sesion.add(EventoAplicadoFila(evento_id=codigo_evento, tipo=tipo))
        acumulado = await sesion.get(VentaPorSkuFila, sku)
        if acumulado is None:
            acumulado = VentaPorSkuFila(sku=sku, pedidos=0, unidades=0, monto_cop=0)
            sesion.add(acumulado)
        acumulado.pedidos += signo
        acumulado.unidades += signo * int(venta.get("cantidad", 0))
        acumulado.monto_cop += signo * int(venta.get("monto_cop", 0))
        try:
            await sesion.commit()
        except IntegrityError:
            await sesion.rollback()
            return "duplicado"
    return "aplicado"


async def borrar_proyeccion(fabrica_sesiones) -> None:
    async with fabrica_sesiones() as sesion:
        await sesion.execute(delete(VentaPorSkuFila))
        await sesion.execute(delete(EventoAplicadoFila))
        await sesion.commit()
