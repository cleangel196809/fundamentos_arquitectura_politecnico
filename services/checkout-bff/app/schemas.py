"""Esquemas Pydantic para el servicio Checkout BFF (P06)."""
from typing import List, Optional
from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    cliente_id: str = Field(..., description="Identificador del cliente")
    sku: str = Field(..., description="Código SKU del producto a comprar")
    cantidad: int = Field(..., gt=0, description="Cantidad a comprar (debe ser mayor a 0)")
    medio_pago: str = Field(..., description="Medio de pago (ej: tarjeta, nequi)")


class PasoResultado(BaseModel):
    paso: str = Field(..., description="Nombre del paso (catalogo, inventario, pedidos, pagos)")
    resultado: str = Field(..., description="Resultado del paso (OK, FALLIDO, COMPENSADO)")
    detalle: Optional[str] = Field(None, description="Detalle del resultado o error")


class CheckoutResponse(BaseModel):
    pedido_id: Optional[str] = Field(None, description="ID del pedido generado")
    estado: str = Field(..., description="Estado de la saga: CONFIRMADO o FALLIDO")
    pasos: List[PasoResultado] = Field(default_factory=list, description="Historial de pasos ejecutados")


class VitrinaItem(BaseModel):
    sku: str
    nombre: str
    precio_cop: float
    stock_disponible: int
    categoria: Optional[str] = None


class VitrinaResponse(BaseModel):
    items: List[VitrinaItem] = Field(default_factory=list)
    total: int = 0

