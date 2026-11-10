"""Tablas de la base pg_catalogo (SQLAlchemy). Solo este servicio las toca."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class ProductoFila(TablaBase):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    precio_cop: Mapped[int] = mapped_column(Integer)
    categoria: Mapped[str] = mapped_column(String(40), index=True)
    region_origen: Mapped[str] = mapped_column(String(60), default="")
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    publicado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
