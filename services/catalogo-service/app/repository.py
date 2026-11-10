"""Acceso a datos del catálogo: el único lugar que habla SQL con pg_catalogo."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ErrorDeNegocio
from app.models import ProductoFila
from app.schemas import ProductoNuevo


class RepositorioCatalogo:
    def __init__(self, sesion: AsyncSession):
        self._sesion = sesion

    async def listar(self, pagina: int, tamano: int, categoria: str | None, solo_publicados: bool):
        filtro = select(ProductoFila)
        if categoria:
            filtro = filtro.where(ProductoFila.categoria == categoria)
        if solo_publicados:
            filtro = filtro.where(ProductoFila.publicado.is_(True))
        cuantos = await self._sesion.scalar(select(func.count()).select_from(filtro.subquery()))
        pagina_actual = await self._sesion.scalars(
            filtro.order_by(ProductoFila.id).offset((pagina - 1) * tamano).limit(tamano)
        )
        return list(pagina_actual), int(cuantos or 0)

    async def buscar_por_sku(self, sku: str) -> ProductoFila | None:
        return await self._sesion.scalar(select(ProductoFila).where(ProductoFila.sku == sku))

    async def crear(self, datos: ProductoNuevo) -> ProductoFila:
        if await self.buscar_por_sku(datos.sku):
            raise ErrorDeNegocio(409, f"Ya existe un producto con SKU {datos.sku}", "SKU_DUPLICADO")
        fila_nueva = ProductoFila(**datos.model_dump(), publicado=False)
        self._sesion.add(fila_nueva)
        try:
            await self._sesion.commit()
        except IntegrityError:
            # Dos peticiones simultáneas con el mismo SKU: la restricción UNIQUE decide.
            await self._sesion.rollback()
            raise ErrorDeNegocio(409, f"Ya existe un producto con SKU {datos.sku}", "SKU_DUPLICADO")
        return fila_nueva

    async def publicar(self, sku: str) -> ProductoFila:
        encontrado = await self.buscar_por_sku(sku)
        if encontrado is None:
            raise ErrorDeNegocio(404, f"No existe el producto {sku}")
        encontrado.publicado = True
        await self._sesion.commit()
        return encontrado

    async def esta_vacio(self) -> bool:
        return not await self._sesion.scalar(select(func.count()).select_from(ProductoFila))
