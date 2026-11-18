"""
Shared pytest fixtures.

Uses SQLite (in-file for async compatibility) + MemoryBus.
All PISHOP_* env vars are overridden via os.environ before importing app modules.
"""

from __future__ import annotations

import os
import pytest
import pytest_asyncio

# Point to SQLite test DB and memory bus BEFORE importing any app module
os.environ.setdefault("PISHOP_DATABASE_URL", "sqlite+aiosqlite:///./test_pedidos.db")
os.environ.setdefault("PISHOP_EVENT_BUS", "memory")
os.environ["PISHOP_DATABASE_URL"] = "sqlite+aiosqlite:///./test_pedidos.db"
os.environ["PISHOP_EVENT_BUS"] = "memory"

from httpx import ASGITransport, AsyncClient  # noqa: E402

import app.database as db_module  # noqa: E402
from app.bus import clear_memory_events  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import get_settings  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    settings = get_settings()
    db_module.init_db(settings)
    await db_module.create_all()
    clear_memory_events()
    yield
    await db_module.drop_all()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
