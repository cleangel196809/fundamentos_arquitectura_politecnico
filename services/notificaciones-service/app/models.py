"""Tabla de pg_notif. `evento_id` es UNIQUE: la base misma impide duplicados."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.base_datos import TablaBase


def marca_de_tiempo() -> datetime:
    return datetime.now(timezone.utc)


class NotificacionFila(TablaBase):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evento_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    pedido_id: Mapped[str] = mapped_column(String(40), index=True)
    cliente_id: Mapped[str] = mapped_column(String(64))
    tipo_evento: Mapped[str] = mapped_column(String(30))
    canal: Mapped[str] = mapped_column(String(10))           # email | sms (simulado)
    mensaje: Mapped[str] = mapped_column(String(300))
    enviada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=marca_de_tiempo)
