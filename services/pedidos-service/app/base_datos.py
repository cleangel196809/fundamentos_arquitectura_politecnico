"""Conexión a la base de datos PROPIA del servicio (SQLAlchemy 2, modo asíncrono).

- En docker-compose se usa PostgreSQL 17 con un usuario exclusivo por base.
- En las pruebas se usa SQLite (aiosqlite), así no hace falta ningún servidor.

La contraseña NO viaja dentro de la URL: llega aparte, como SecretStr, y solo
se inserta en el último momento. Así nunca aparece en logs ni en /docs.
"""
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class TablaBase(DeclarativeBase):
    """Clase madre de todas las tablas de este servicio."""


def crear_motor(ajustes) -> AsyncEngine:
    direccion = make_url(ajustes.database_url)
    opciones_pool = {}
    if direccion.get_backend_name() == "postgresql":
        clave_real = ajustes.database_password.get_secret_value()
        if clave_real:
            direccion = direccion.set(password=clave_real)
        # Pool pequeño: 10 servicios x 10 conexiones no deben ahogar a PostgreSQL.
        opciones_pool = {"pool_size": 5, "max_overflow": 5, "pool_timeout": 5, "pool_recycle": 1800}
    return create_async_engine(direccion, pool_pre_ping=True, **opciones_pool)


def crear_fabrica_sesiones(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(motor, expire_on_commit=False)


async def crear_tablas(motor: AsyncEngine) -> None:
    """Crea las tablas que falten (idempotente: si ya existen no hace nada)."""
    async with motor.begin() as conexion:
        await conexion.run_sync(TablaBase.metadata.create_all)


async def base_responde(motor: AsyncEngine) -> bool:
    """Usado por /health/ready: un SELECT 1 rápido. Nunca lanza excepción."""
    try:
        async with motor.connect() as conexion:
            await conexion.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - cualquier fallo significa "no listo"
        return False
