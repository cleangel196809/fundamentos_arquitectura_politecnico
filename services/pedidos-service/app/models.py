import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cliente_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(255), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    monto_cop: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(50), default="CREADO", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    outbox_events: Mapped[list["OutboxEvent"]] = relationship("OutboxEvent", back_populates="pedido")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pedido_id: Mapped[str] = mapped_column(String(36), ForeignKey("pedidos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)  # PedidoCreado | PedidoCancelado
    payload: Mapped[str] = mapped_column(Text, nullable=False)     # JSON string
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    pedido: Mapped["Pedido"] = relationship("Pedido", back_populates="outbox_events")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)   # the idempotency key
    response_body: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
