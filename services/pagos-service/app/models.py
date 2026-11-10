"""Tabla de pg_pagos. La Idempotency-Key se guarda en el propio pago (UNIQUE)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def instante_utc() -> datetime:
    return datetime.now(timezone.utc)


class PagoFila(TablaBase):
    __tablename__ = "pagos"

    pago_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    clave_idempotencia: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    pedido_id: Mapped[str] = mapped_column(String(64), index=True)
    monto_cop: Mapped[int] = mapped_column(Integer)
    medio: Mapped[str] = mapped_column(String(32))
    estado: Mapped[str] = mapped_column(String(12), default="PENDIENTE")   # APROBADO | RECHAZADO | PENDIENTE | REEMBOLSADO
    codigo_autorizacion: Mapped[str] = mapped_column(String(40), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=instante_utc)
    reembolsado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
