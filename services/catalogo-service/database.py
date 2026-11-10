"""
Capa de persistencia asíncrona para catalogo-service.
Soporta SQLite con aiosqlite en local/pruebas y PostgreSQL 17 en producción.
"""
from typing import AsyncGenerator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings
from models import Base, Producto

engine = create_async_engine(
    settings.pishop_database_url,
    echo=False,
    future=True
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


PRODUCTOS_SEMILLA = [
    {"sku": "CAFE-500G", "nombre": "Café Especial Suave 500g", "precio_cop": 28000, "categoria": "Café", "publicado": True},
    {"sku": "CAFE-1000G", "nombre": "Café Especial en Grano 1kg", "precio_cop": 52000, "categoria": "Café", "publicado": True},
    {"sku": "PANELA-1K", "nombre": "Panela Orgánica Pulverizada 1kg", "precio_cop": 7500, "categoria": "Endulzantes", "publicado": True},
    {"sku": "PANELA-BLOQUE", "nombre": "Panela Tradicional en Bloque 2kg", "precio_cop": 12000, "categoria": "Endulzantes", "publicado": False},
    {"sku": "MIEL-750", "nombre": "Miel Pura de Abejas 750ml", "precio_cop": 35000, "categoria": "Apicultura", "publicado": True},
    {"sku": "CACAO-500G", "nombre": "Cacao Fino de Aroma en Polvo 500g", "precio_cop": 24000, "categoria": "Cacao", "publicado": True},
    {"sku": "AGUACATE-HASS-KG", "nombre": "Aguacate Hass Exportación (kg)", "precio_cop": 9500, "categoria": "Frutas", "publicado": True},
    {"sku": "PLATANO-HARTON-RAC", "nombre": "Plátano Hartón Racimo 15kg", "precio_cop": 42000, "categoria": "Plátano", "publicado": False},
    {"sku": "FRIJOL-BOLA-ROJA-KG", "nombre": "Fríjol Bola Roja Selección 1kg", "precio_cop": 14500, "categoria": "Granos", "publicado": True},
    {"sku": "MAIZ-AMARILLO-25K", "nombre": "Maíz Amarillo Bulto 25kg", "precio_cop": 68000, "categoria": "Granos", "publicado": True},
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_db(session: AsyncSession) -> int:
    """Carga los 10 productos de semilla si la tabla está vacía."""
    stmt = select(Producto)
    existentes = (await session.execute(stmt)).scalars().all()
    if existentes:
        return len(existentes)

    for p_data in PRODUCTOS_SEMILLA:
        producto = Producto(**p_data)
        session.add(producto)
    await session.commit()
    return len(PRODUCTOS_SEMILLA)
