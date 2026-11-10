"""Tablas de pg_reportes: el MODELO DE LECTURA (CQRS).

Nadie escribe aquí directamente: las filas se derivan de los eventos que
publica pedidos-service. Por eso se pueden borrar y reconstruir en cualquier
momento a partir del stream.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def reloj_utc() -> datetime:
    return datetime.now(timezone.utc)


class EventoAplicadoFila(TablaBase):
    """Registro de eventos ya sumados: evita contar dos veces el mismo evento."""
    __tablename__ = "eventos_aplicados"

    evento_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(30))
    aplicado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=reloj_utc)


class VentaPorSkuFila(TablaBase):
    __tablename__ = "ventas_por_sku"

    sku: Mapped[str] = mapped_column(String(40), primary_key=True)
    pedidos: Mapped[int] = mapped_column(Integer, default=0)
    unidades: Mapped[int] = mapped_column(Integer, default=0)
    monto_cop: Mapped[int] = mapped_column(Integer, default=0)
