"""Casos de uso de pedidos sobre pg_pedidos.

Regla de oro del Outbox: el pedido y su evento se guardan en UNA sola
transacción y SIN llamadas de red dentro de ella. Si la base confirma, ambos
existen; si falla, no existe ninguno. Publicar al bus es trabajo de otro
proceso (app/publicador.py).
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ErrorDeNegocio
from app.models import OutboxFila, PedidoFila, RespuestaRepetibleFila
from app.schemas import PedidoSolicitud


def contenido_del_evento(pedido: PedidoFila) -> dict:
    """Payload acordado en docs/CONTRATOS.md (contrato de eventos)."""
    return {"pedido_id": pedido.pedido_id, "cliente_id": pedido.cliente_id, "sku": pedido.sku,
            "cantidad": pedido.cantidad, "monto_cop": pedido.monto_cop,
            "ocurrido_en": datetime.now(timezone.utc).isoformat()}


class RepositorioPedidos:
    def __init__(self, sesion: AsyncSession):
        self._sesion = sesion

    def _anotar_evento(self, tipo: str, pedido: PedidoFila) -> None:
        self._sesion.add(OutboxFila(evento_id=str(uuid.uuid4()), tipo=tipo,
                                    contenido_json=json.dumps(contenido_del_evento(pedido))))

    async def crear(self, solicitud: PedidoSolicitud, clave: str | None) -> PedidoFila:
        if clave:
            anterior = await self._sesion.get(RespuestaRepetibleFila, clave)
            if anterior:
                return await self.obtener(anterior.pedido_id)
        pedido_nuevo = PedidoFila(pedido_id=f"PED-{uuid.uuid4().hex[:12]}", estado="CREADO", **solicitud.model_dump())
        self._sesion.add(pedido_nuevo)
        self._anotar_evento("PedidoCreado", pedido_nuevo)                 # misma transacción
        if clave:
            self._sesion.add(RespuestaRepetibleFila(clave=clave, pedido_id=pedido_nuevo.pedido_id))
        try:
            await self._sesion.commit()
        except IntegrityError:
            await self._sesion.rollback()
            ganador = await self._sesion.get(RespuestaRepetibleFila, clave) if clave else None
            if ganador:
                return await self.obtener(ganador.pedido_id)
            raise
        return pedido_nuevo

    async def obtener(self, pedido_id: str) -> PedidoFila:
        pedido = await self._sesion.get(PedidoFila, pedido_id)
        if pedido is None:
            raise ErrorDeNegocio(404, f"No existe el pedido {pedido_id}")
        return pedido

    async def cancelar(self, pedido_id: str) -> PedidoFila:
        """Compensación de la saga. Cancelar dos veces no genera dos eventos."""
        pedido = await self.obtener(pedido_id)
        if pedido.estado == "CANCELADO":
            return pedido
        if pedido.estado == "CONFIRMADO":
            raise ErrorDeNegocio(409, "Un pedido confirmado no se puede cancelar", "PEDIDO_CONFIRMADO")
        pedido.estado = "CANCELADO"
        self._anotar_evento("PedidoCancelado", pedido)
        await self._sesion.commit()
        return pedido

    async def confirmar(self, pedido_id: str) -> PedidoFila:
        pedido = await self.obtener(pedido_id)
        if pedido.estado == "CANCELADO":
            raise ErrorDeNegocio(409, "Un pedido cancelado no se puede confirmar", "PEDIDO_CANCELADO")
        pedido.estado = "CONFIRMADO"
        await self._sesion.commit()
        return pedido

    async def eventos_sin_publicar(self, limite: int = 100) -> list[OutboxFila]:
        resultado = await self._sesion.scalars(
            select(OutboxFila).where(OutboxFila.publicado_en.is_(None)).order_by(OutboxFila.registrado_en).limit(limite)
        )
        return list(resultado)
