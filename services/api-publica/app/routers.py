"""Rutas de la fachada. SOLO enruta: no hay lógica de negocio."""
import httpx
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.errores import ProblemaError
from app.seguridad import exigir_api_key

router = APIRouter(prefix="/v1", dependencies=[Depends(exigir_api_key)])


class CompraIn(BaseModel):
    cliente_id: str
    sku: str
    cantidad: int = Field(gt=0)
    medio_pago: str


async def _llamar(request: Request, metodo: str, url: str, **kw) -> httpx.Response:
    """Llamada saliente con el AsyncClient único (timeout explícito) y errores traducidos."""
    try:
        resp = await request.app.state.http.request(metodo, url, **kw)
    except httpx.TimeoutException as exc:
        raise ProblemaError(504, "Tiempo de espera agotado",
                            "El servicio interno no respondió a tiempo.", "timeout_upstream") from exc
    except httpx.HTTPError as exc:
        raise ProblemaError(502, "Servicio no disponible",
                            "No se pudo contactar el servicio interno.", "upstream_caido") from exc
    if resp.status_code >= 400:
        try:
            detalle = resp.json().get("detalle") or resp.text
        except ValueError:
            detalle = resp.text
        raise ProblemaError(resp.status_code, "Error del servicio interno", str(detalle),
                            "error_upstream")
    return resp


@router.get("/catalogo/productos")
async def listar_productos(request: Request, pagina: int = Query(1, ge=1),
                           tamano: int = Query(20, ge=1, le=100)):
    base = str(request.app.state.settings.catalogo_url).rstrip("/")
    resp = await _llamar(request, "GET", f"{base}/v1/productos",
                         params={"pagina": pagina, "tamano": tamano})
    datos = resp.json()
    datos["items"] = [p for p in datos.get("items", []) if p.get("publicado")]
    return datos


@router.post("/compras")
async def crear_compra(request: Request, compra: CompraIn,
                       idempotency_key: str | None = Header(default=None)):
    base = str(request.app.state.settings.checkout_bff_url).rstrip("/")
    cabeceras = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
    resp = await _llamar(request, "POST", f"{base}/v1/checkout",
                         json=compra.model_dump(), headers=cabeceras)
    return JSONResponse(resp.json(), status_code=resp.status_code)


@router.get("/compras/{pedido_id}")
async def estado_compra(request: Request, pedido_id: str):
    base = str(request.app.state.settings.checkout_bff_url).rstrip("/")
    resp = await _llamar(request, "GET", f"{base}/v1/checkout/{pedido_id}/estado")
    return resp.json()
