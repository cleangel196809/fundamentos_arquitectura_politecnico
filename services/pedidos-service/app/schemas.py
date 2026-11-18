from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class CrearPedidoRequest(BaseModel):
    cliente_id: str = Field(..., min_length=1)
    sku: str = Field(..., min_length=1)
    cantidad: int = Field(..., gt=0)
    monto_cop: int = Field(..., gt=0)


# ── Response schemas ─────────────────────────────────────────────────────────

class PedidoResponse(BaseModel):
    pedido_id: str
    cliente_id: str
    sku: str
    cantidad: int
    monto_cop: int
    estado: str
    creado_en: datetime

    model_config = {"from_attributes": True}


class CrearPedidoResponse(BaseModel):
    pedido_id: str
    estado: str


class OutboxEventResponse(BaseModel):
    evento_id: str
    pedido_id: str
    tipo: str
    payload: str
    creado_en: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detalle: str
    codigo: str
