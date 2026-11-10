"""
Repositorio para el acceso a datos del catálogo.
Encapsula las consultas SQLAlchemy separando la persistencia de las rutas HTTP.
"""
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from models import Producto
from schemas import ProductoCrear
from database import PRODUCTOS_SEMILLA


class CatalogoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def obtener_por_sku(self, sku: str) -> Producto | None:
        stmt = select(Producto).where(Producto.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def listar_productos(self, pagina: int = 1, tamano: int = 20) -> tuple[list[Producto], int]:
        # Conteo total
        count_stmt = select(func.count()).select_from(Producto)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Paginación (offset = (pagina - 1) * tamano)
        offset = (pagina - 1) * tamano
        stmt = (
            select(Producto)
            .order_by(Producto.creado_en.asc(), Producto.sku.asc())
            .offset(offset)
            .limit(tamano)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def crear_producto(self, datos: ProductoCrear) -> Producto:
        producto = Producto(
            sku=datos.sku,
            nombre=datos.nombre,
            precio_cop=datos.precio_cop,
            categoria=datos.categoria,
            publicado=False
        )
        self.session.add(producto)
        await self.session.commit()
        await self.session.refresh(producto)
        return producto

    async def publicar_producto(self, sku: str) -> Producto | None:
        producto = await self.obtener_por_sku(sku)
        if not producto:
            return None
        producto.publicado = True
        await self.session.commit()
        await self.session.refresh(producto)
        return producto

    async def reiniciar_semilla(self) -> int:
        await self.session.execute(delete(Producto))
        for item in PRODUCTOS_SEMILLA:
            self.session.add(Producto(**item))
        await self.session.commit()
        return len(PRODUCTOS_SEMILLA)
