"""Contrato de entrada/salida de pedidos-service."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PedidoSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cliente_id: str = Field(min_length=1, max_length=64)
    sku: str = Field(min_length=1, max_length=40)
    cantidad: int = Field(gt=0, le=10_000)
    monto_cop: int = Field(gt=0)


class PedidoVista(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pedido_id: str
    cliente_id: str
    sku: str
    cantidad: int
    monto_cop: int
    estado: str
    creado_en: datetime


class EventoPendiente(BaseModel):
    evento_id: str
    tipo: str
    contenido: dict
    registrado_en: datetime
