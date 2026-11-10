"""
Esquemas de validación y transferencia (Pydantic v2) para catalogo-service.
Garantiza los contratos exactos de docs/CONTRATOS.md.
"""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field


class ProductoBase(BaseModel):
    nombre: Annotated[str, Field(min_length=1, max_length=128, description="Nombre del producto")]
    precio_cop: Annotated[int, Field(gt=0, description="Precio en pesos colombianos, estrictamente mayor a 0")]
    categoria: Annotated[str, Field(min_length=1, max_length=64, description="Categoría agropecuaria")]


class ProductoCrear(ProductoBase):
    sku: Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[A-Z0-9\-]+$", description="SKU único en mayúsculas, números o guiones")]


class ProductoOut(BaseModel):
    sku: str
    nombre: str
    precio_cop: int
    categoria: str
    publicado: bool

    model_config = ConfigDict(from_attributes=True)


class PaginaProductos(BaseModel):
    items: list[ProductoOut]
    total: int
    pagina: int
    tamano: int


class ErrorRespuesta(BaseModel):
    detalle: str
    codigo: str
