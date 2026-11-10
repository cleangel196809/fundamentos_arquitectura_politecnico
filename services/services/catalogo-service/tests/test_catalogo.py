"""
Batería de pruebas automatizadas (pytest + pytest-asyncio + httpx).
Cumple con el criterio C y las acciones del paquete P01:
Al menos 6 pruebas requeridas: 200, 201, 404, 409, 422, paginación.
"""
import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from models import Base
from database import get_db, seed_db
from health import marcar_startup_listo
from main import app

# Configuración con StaticPool para SQLite en memoria
test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
test_async_session = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db():
    async with test_async_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="function", autouse=True)
async def preparar_base_datos():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with test_async_session() as session:
        await seed_db(session)
    marcar_startup_listo()
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def cliente():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_01_listar_productos_paginacion(cliente: httpx.AsyncClient):
    """Prueba Paginación: GET /v1/productos?pagina=1&tamano=5 debe retornar 5 elementos y total 10."""
    response = await cliente.get("/v1/productos?pagina=1&tamano=5")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["pagina"] == 1
    assert data["tamano"] == 5
    assert len(data["items"]) == 5
    assert data["total"] == 10


@pytest.mark.asyncio
async def test_02_obtener_producto_por_sku_200(cliente: httpx.AsyncClient):
    """Prueba 200: GET /v1/productos/{sku} retorna 200 con el producto esperado."""
    response = await cliente.get("/v1/productos/CAFE-500G")
    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "CAFE-500G"
    assert data["precio_cop"] == 28000
    assert data["categoria"] == "Café"
    assert data["publicado"] is True


@pytest.mark.asyncio
async def test_03_crear_producto_201(cliente: httpx.AsyncClient):
    """Prueba 201: POST /v1/productos con datos válidos crea el producto con publicado=False."""
    nuevo_prod = {
        "sku": "QUESO-CAMP-500",
        "nombre": "Queso Campesino Fresco 500g",
        "precio_cop": 13500,
        "categoria": "Lácteos"
    }
    response = await cliente.post("/v1/productos", json=nuevo_prod)
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "QUESO-CAMP-500"
    assert data["nombre"] == "Queso Campesino Fresco 500g"
    assert data["precio_cop"] == 13500
    assert data["publicado"] is False


@pytest.mark.asyncio
async def test_04_obtener_producto_inexistente_404(cliente: httpx.AsyncClient):
    """Prueba 404: GET /v1/productos/{sku} con SKU inexistente retorna 404 y formato estándar."""
    response = await cliente.get("/v1/productos/SKU-NO-EXISTE-XYZ")
    assert response.status_code == 404
    data = response.json()
    assert "detalle" in data
    assert data["codigo"] == "PRODUCTO_NO_ENCONTRADO"


@pytest.mark.asyncio
async def test_05_crear_producto_sku_duplicado_409(cliente: httpx.AsyncClient):
    """Prueba 409: POST /v1/productos con SKU existente retorna 409 Conflict."""
    duplicado = {
        "sku": "CAFE-500G",
        "nombre": "Otro Café Duplicado",
        "precio_cop": 30000,
        "categoria": "Café"
    }
    response = await cliente.post("/v1/productos", json=duplicado)
    assert response.status_code == 409
    data = response.json()
    assert "detalle" in data
    assert data["codigo"] == "SKU_DUPLICADO"


@pytest.mark.asyncio
async def test_06_crear_producto_precio_invalido_422(cliente: httpx.AsyncClient):
    """Prueba 422: POST /v1/productos con precio <= 0 retorna 422 Unprocessable Entity."""
    invalido = {
        "sku": "YUCA-FRESCA-KG",
        "nombre": "Yuca Fresca",
        "precio_cop": 0,
        "categoria": "Tubérculos"
    }
    response = await cliente.post("/v1/productos", json=invalido)
    assert response.status_code == 422
    data = response.json()
    assert "detalle" in data
    assert "codigo" in data


@pytest.mark.asyncio
async def test_07_publicar_producto_patch_200(cliente: httpx.AsyncClient):
    """Prueba PATCH /v1/productos/{sku}/publicar actualiza publicado=True."""
    response_patch = await cliente.patch("/v1/productos/PANELA-BLOQUE/publicar")
    assert response_patch.status_code == 200
    assert response_patch.json()["publicado"] is True

    # Verificar persistencia
    response_verif = await cliente.get("/v1/productos/PANELA-BLOQUE")
    assert response_verif.json()["publicado"] is True


@pytest.mark.asyncio
async def test_08_publicar_producto_inexistente_404(cliente: httpx.AsyncClient):
    """Prueba PATCH /v1/productos/{sku}/publicar con SKU inexistente retorna 404."""
    response = await cliente.patch("/v1/productos/INEXISTENTE-123/publicar")
    assert response.status_code == 404
    data = response.json()
    assert data["codigo"] == "PRODUCTO_NO_ENCONTRADO"


@pytest.mark.asyncio
async def test_09_sondas_salud_live_ready_startup(cliente: httpx.AsyncClient):
    """Prueba las tres sondas Kubernetes: /health/live, /health/ready, /health/startup."""
    resp_live = await cliente.get("/health/live")
    assert resp_live.status_code == 200
    assert resp_live.json()["status"] == "ALIVE"

    resp_ready = await cliente.get("/health/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "READY"

    resp_startup = await cliente.get("/health/startup")
    assert resp_startup.status_code == 200
    assert resp_startup.json()["status"] == "STARTED"
