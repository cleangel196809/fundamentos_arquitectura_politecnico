"""Contrato de entrada/salida (Pydantic). Es la "capa anticorrupción" interna:
la API nunca expone directamente la fila de la base de datos (models.py)."""
from pydantic import BaseModel, ConfigDict, Field


class ProductoNuevo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=3, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9-]*$", examples=["CAFE-500G"])
    nombre: str = Field(min_length=2, max_length=120)
    precio_cop: int = Field(gt=0, le=100_000_000, description="Precio en pesos colombianos; debe ser mayor que 0")
    categoria: str = Field(min_length=2, max_length=40)
    region_origen: str = Field(default="", max_length=60)
    descripcion: str = Field(default="", max_length=300)


class ProductoDetalle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    nombre: str
    precio_cop: int
    categoria: str
    region_origen: str
    descripcion: str
    publicado: bool


class PaginaDeProductos(BaseModel):
    items: list[ProductoDetalle]
    total: int
    pagina: int
    tamano: int
