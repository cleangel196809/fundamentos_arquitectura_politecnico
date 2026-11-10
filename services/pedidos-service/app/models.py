"""Tablas de pg_pedidos: pedidos + outbox (patrón Transactional Outbox)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def hora_utc() -> datetime:
    return datetime.now(timezone.utc)


class PedidoFila(TablaBase):
    __tablename__ = "pedidos"

    pedido_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    cliente_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    cantidad: Mapped[int] = mapped_column(Integer)
    monto_cop: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(12), default="CREADO")   # CREADO | CONFIRMADO | CANCELADO
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=hora_utc)


class OutboxFila(TablaBase):
    """Evento pendiente de publicar. Se escribe en la MISMA transacción que el pedido."""
    __tablename__ = "outbox"

    evento_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))               # PedidoCreado | PedidoCancelado
    contenido_json: Mapped[str] = mapped_column(Text)
    registrado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=hora_utc)
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class RespuestaRepetibleFila(TablaBase):
    """Respuesta guardada por Idempotency-Key (el BFF puede reintentar la creación)."""
    __tablename__ = "respuestas_idempotentes"

    clave: Mapped[str] = mapped_column(String(128), primary_key=True)
    pedido_id: Mapped[str] = mapped_column(String(40))
