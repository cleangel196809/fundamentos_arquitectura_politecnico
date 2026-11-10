from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.settings import Settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> None:
    """Initialise the async engine & session factory from settings."""
    global _engine, _session_factory

    connect_args = {}
    if "sqlite" in settings.database_url:
        connect_args = {"check_same_thread": False}

    _engine = create_async_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine():
    if _engine is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialised – call init_db() first")
    return _session_factory


async def create_all() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_db() -> AsyncSession:  # FastAPI dependency
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def check_db_ready() -> bool:
    """Return True if the DB is reachable."""
    try:
        from sqlalchemy import text
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
