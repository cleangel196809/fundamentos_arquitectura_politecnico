"""
Rutas HTTP versionadas bajo /v1 para catalogo-service.
Cumple estrictamente los contratos de docs/CONTRATOS.md:
- GET /v1/productos?pagina=1&tamano=20 (tamano max 100)
- POST /v1/productos (201 / 409 sku duplicado / 422 precio <= 0)
- GET /v1/productos/{sku} (200 / 404)
- PATCH /v1/productos/{sku}/publicar (200 con publicado=true / 404)
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from repository import CatalogoRepository
from schemas import (
    ErrorRespuesta,
    PaginaProductos,
    ProductoCrear,
    ProductoOut,
)

productos_router = APIRouter(prefix="/v1/productos", tags=["productos"])


@productos_router.get(
    "",
    response_model=PaginaProductos,
    status_code=status.HTTP_200_OK,
    summary="Listar productos paginados"
)
async def listar_productos(
    pagina: Annotated[int, Query(ge=1, description="Número de página (inicia en 1)")] = 1,
    tamano: Annotated[int, Query(ge=1, le=100, description="Tamaño de la página (máximo 100)")] = 20,
    db: AsyncSession = Depends(get_db)
) -> PaginaProductos:
    repo = CatalogoRepository(db)
    items, total = await repo.listar_productos(pagina=pagina, tamano=tamano)
    return PaginaProductos(
        items=[ProductoOut.model_validate(p) for p in items],
        total=total,
        pagina=pagina,
        tamano=tamano
    )


@productos_router.post(
    "",
    response_model=ProductoOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorRespuesta, "description": "SKU duplicado"},
        422: {"model": ErrorRespuesta, "description": "Validación fallida"}
    },
    summary="Crear un nuevo producto"
)
async def crear_producto(
    datos: ProductoCrear,
    db: AsyncSession = Depends(get_db)
) -> ProductoOut:
    if datos.precio_cop <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detalle": "El precio debe ser estrictamente mayor a 0", "codigo": "PRECIO_INVALIDO"}
        )

    repo = CatalogoRepository(db)
    existente = await repo.obtener_por_sku(datos.sku)
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detalle": f"El producto con SKU '{datos.sku}' ya existe", "codigo": "SKU_DUPLICADO"}
        )

    nuevo = await repo.crear_producto(datos)
    return ProductoOut.model_validate(nuevo)


@productos_router.get(
    "/{sku}",
    response_model=ProductoOut,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorRespuesta, "description": "Recurso inexistente"}},
    summary="Obtener un producto por su SKU"
)
async def obtener_producto(
    sku: str,
    db: AsyncSession = Depends(get_db)
) -> ProductoOut:
    repo = CatalogoRepository(db)
    producto = await repo.obtener_por_sku(sku)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detalle": f"Producto con SKU '{sku}' no existe", "codigo": "PRODUCTO_NO_ENCONTRADO"}
        )
    return ProductoOut.model_validate(producto)


@productos_router.patch(
    "/{sku}/publicar",
    response_model=ProductoOut,
    status_code=status.HTTP_200_OK,
    responses={404: {"model": ErrorRespuesta, "description": "Recurso inexistente"}},
    summary="Publicar un producto para visibilidad en tienda"
)
async def publicar_producto(
    sku: str,
    db: AsyncSession = Depends(get_db)
) -> ProductoOut:
    repo = CatalogoRepository(db)
    producto = await repo.publicar_producto(sku)
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detalle": f"Producto con SKU '{sku}' no existe", "codigo": "PRODUCTO_NO_ENCONTRADO"}
        )
    return ProductoOut.model_validate(producto)


@productos_router.post(
    "/semilla/reiniciar",
    status_code=status.HTTP_200_OK,
    summary="Reiniciar semilla de 10 productos"
)
async def reiniciar_semilla(
    db: AsyncSession = Depends(get_db)
) -> dict[str, str | int]:
    repo = CatalogoRepository(db)
    total = await repo.reiniciar_semilla()
    return {"mensaje": "Semilla reiniciada con éxito", "total_productos": total}
