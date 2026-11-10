"""
Modelos de base de datos (SQLAlchemy 2.0) para catalogo-service.
Cada servicio es dueño exclusivo de su base de datos (pg_catalogo o sqlite local).
Separado de schemas.py para garantizar la ACL interna entre persistencia y dominio.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Producto(Base):
    __tablename__ = "productos"

    sku: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(128), nullable=False)
    precio_cop: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publicado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
