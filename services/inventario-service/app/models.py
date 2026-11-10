"""Tablas de pg_inventario.

- existencias: cuántas unidades hay de cada SKU y cuántas están apartadas.
- reservas: cada apartado hecho para un pedido (se puede liberar o confirmar).
- respuestas_idempotentes: la respuesta guardada para cada Idempotency-Key,
  así un reintento recibe exactamente lo mismo sin descontar dos veces.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def momento_actual() -> datetime:
    return datetime.now(timezone.utc)


class ExistenciaFila(TablaBase):
    __tablename__ = "existencias"

    sku: Mapped[str] = mapped_column(String(40), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=0)        # unidades físicas en bodega
    reservado: Mapped[int] = mapped_column(Integer, default=0)       # apartadas por pedidos en curso


class ReservaFila(TablaBase):
    __tablename__ = "reservas"

    reserva_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), index=True)
    cantidad: Mapped[int] = mapped_column(Integer)
    pedido_id: Mapped[str] = mapped_column(String(64), index=True)
    estado: Mapped[str] = mapped_column(String(12), default="ACTIVA")   # ACTIVA | LIBERADA | CONFIRMADA
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=momento_actual)


class RespuestaIdempotenteFila(TablaBase):
    __tablename__ = "respuestas_idempotentes"

    clave: Mapped[str] = mapped_column(String(128), primary_key=True)
    codigo_http: Mapped[int] = mapped_column(Integer)
    cuerpo_json: Mapped[str] = mapped_column(Text)
    guardada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=momento_actual)
