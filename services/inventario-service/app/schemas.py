"""Contrato de entrada/salida de inventario-service."""
from pydantic import BaseModel, ConfigDict, Field


class StockAjuste(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cantidad: int = Field(ge=0, le=10_000_000)


class StockVista(BaseModel):
    sku: str
    cantidad: int
    reservado: int
    disponible: int


class ReservaSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=40)
    cantidad: int = Field(gt=0, le=10_000)
    pedido_id: str = Field(min_length=1, max_length=64)


class ReservaVista(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reserva_id: str
    sku: str
    cantidad: int
    pedido_id: str
    estado: str
