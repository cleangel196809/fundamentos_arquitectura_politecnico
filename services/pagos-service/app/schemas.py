"""Contrato de entrada/salida de pagos-service."""
from pydantic import BaseModel, ConfigDict, Field


class CobroSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_id: str = Field(min_length=1, max_length=64)
    monto_cop: int = Field(gt=0)
    medio: str = Field(min_length=2, max_length=32, examples=["tarjeta", "pse", "nequi"])


class PagoVista(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pago_id: str
    pedido_id: str
    monto_cop: int
    medio: str
    estado: str
    codigo_autorizacion: str


class ModoPasarela(BaseModel):
    modo: str = Field(pattern="^(ok|rechaza|lenta|falla)$")
