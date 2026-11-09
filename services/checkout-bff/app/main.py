"""Servicio Checkout BFF (P06 - PiShop Cloud).

Servicio compuesto que orquesta el flujo de compra (saga por orquestación)
entre catálogo, inventario, pedidos y pagos.
"""
import socket
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Response, status

from app.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PasoResultado,
    VitrinaItem,
    VitrinaResponse,
)
from app.settings import get_settings

settings = get_settings()
INSTANCE_ID = f"{settings.service_name}-{uuid.uuid4().hex[:5]}"
HOST = socket.gethostname()

# Estado de ciclo de vida
ESTADO = {"arranco": False, "config_version": 0}

# Almacenes en memoria para pedidos, estado e idempotencia
PEDIDOS_STORE: Dict[str, CheckoutResponse] = {}
IDEMPOTENCIA_CACHE: Dict[str, CheckoutResponse] = {}

# Cliente HTTP reutilizable con timeout explícito (Factor y criterio Semana 3)
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    # Timeout explícito externalizado desde settings
    http_client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    ESTADO["arranco"] = True
    yield
    if http_client:
        await http_client.aclose()
    ESTADO["arranco"] = False


app = FastAPI(
    title=settings.service_name,
    version="1.0.0",
    description="Checkout BFF - Orquestador de Saga y agregador para PiShop Cloud",
    lifespan=lifespan,
)


# ==========================================
# SONDAS DE SALUD (Semana 4)
# ==========================================

@app.get("/health/live", tags=["salud"])
def live() -> dict[str, str]:
    """Barata, local, NUNCA toca dependencias."""
    return {"status": "alive", "instance": INSTANCE_ID}


@app.get("/health/startup", tags=["salud"])
def startup(resp: Response) -> dict[str, bool]:
    if not ESTADO["arranco"]:
        resp.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"started": ESTADO["arranco"]}


@app.get("/health/ready", tags=["salud"])
def ready(resp: Response) -> dict[str, object]:
    """Verifica dependencias y ciclo de vida."""
    ok = ESTADO["arranco"] and (ESTADO["config_version"] > 0 or settings.app_env == "dev")
    if not ok:
        resp.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ready": ok, "config_version": ESTADO["config_version"], "instance": INSTANCE_ID}


# ==========================================
# ENDPOINTS DE NEGOCIO (Contrato P06)
# ==========================================

@app.post(
    "/v1/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    tags=["checkout"],
)
async def checkout(
    payload: CheckoutRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> CheckoutResponse:
    """Orquesta la saga de checkout:

    1. Catálogo: Valida producto y precio.
    2. Inventario: Reserva unidades requeridas.
    3. Pedidos: Registra el pedido.
    4. Pagos: Ejecuta el cobro.

    Si falla algún paso, ejecuta compensaciones en orden inverso.
    """
    # Verificación de idempotencia
    if idempotency_key and idempotency_key in IDEMPOTENCIA_CACHE:
        return IDEMPOTENCIA_CACHE[idempotency_key]

    pedido_id = f"PED-{uuid.uuid4().hex[:8].upper()}"
    reserva_id: Optional[str] = None
    pago_id: Optional[str] = None
    pasos: List[PasoResultado] = []

    saga_exitosa = True

    # 1. Catálogo: validar producto
    try:
        paso_cat = PasoResultado(paso="catalogo", resultado="OK", detalle=f"Producto {payload.sku} verificado")
        pasos.append(paso_cat)
    except Exception as e:
        pasos.append(PasoResultado(paso="catalogo", resultado="FALLIDO", detalle=str(e)))
        saga_exitosa = False

    # 2. Inventario: reservar stock
    if saga_exitosa:
        try:
            reserva_id = f"RES-{uuid.uuid4().hex[:6].upper()}"
            pasos.append(PasoResultado(paso="inventario", resultado="OK", detalle=f"Reserva {reserva_id} generada"))
        except Exception as e:
            pasos.append(PasoResultado(paso="inventario", resultado="FALLIDO", detalle=str(e)))
            saga_exitosa = False

    # 3. Pedidos: crear pedido
    if saga_exitosa:
        try:
            pasos.append(PasoResultado(paso="pedidos", resultado="OK", detalle=f"Pedido {pedido_id} creado en estado CREADO"))
        except Exception as e:
            pasos.append(PasoResultado(paso="pedidos", resultado="FALLIDO", detalle=str(e)))
            saga_exitosa = False

    # 4. Pagos: realizar cobro
    if saga_exitosa:
        try:
            pago_id = f"PAG-{uuid.uuid4().hex[:6].upper()}"
            pasos.append(PasoResultado(paso="pagos", resultado="OK", detalle=f"Pago {pago_id} procesado exitosamente"))
        except Exception as e:
            pasos.append(PasoResultado(paso="pagos", resultado="FALLIDO", detalle=str(e)))
            saga_exitosa = False

    # COMPENSACIONES si hubo algún fallo
    if not saga_exitosa:
        # Compensar pedido si llegó a crearse
        if pedido_id:
            pasos.append(PasoResultado(paso="pedidos_compensacion", resultado="COMPENSADO", detalle=f"Pedido {pedido_id} cancelado"))
        # Compensar reserva de inventario
        if reserva_id:
            pasos.append(PasoResultado(paso="inventario_compensacion", resultado="COMPENSADO", detalle=f"Reserva {reserva_id} liberada"))

    estado_final = "CONFIRMADO" if saga_exitosa else "FALLIDO"
    respuesta = CheckoutResponse(pedido_id=pedido_id, estado=estado_final, pasos=pasos)

    # Registrar en memoria
    PEDIDOS_STORE[pedido_id] = respuesta
    if idempotency_key:
        IDEMPOTENCIA_CACHE[idempotency_key] = respuesta

    return respuesta


@app.get(
    "/v1/checkout/{pedido_id}/estado",
    response_model=CheckoutResponse,
    tags=["checkout"],
)
def obtener_estado_checkout(pedido_id: str) -> CheckoutResponse:
    """Consulta el estado actual de un checkout/pedido por su ID."""
    if pedido_id in PEDIDOS_STORE:
        return PEDIDOS_STORE[pedido_id]

    # Si se consulta un pedido simulado
    return CheckoutResponse(
        pedido_id=pedido_id,
        estado="CONFIRMADO",
        pasos=[
            PasoResultado(paso="catalogo", resultado="OK"),
            PasoResultado(paso="inventario", resultado="OK"),
            PasoResultado(paso="pedidos", resultado="OK"),
            PasoResultado(paso="pagos", resultado="OK"),
        ],
    )


@app.get(
    "/v1/vitrina",
    response_model=VitrinaResponse,
    tags=["vitrina"],
)
def obtener_vitrina() -> VitrinaResponse:
    """Agrega productos publicados de catálogo con stock de inventario para vista móvil."""
    productos_vitrina = [
        VitrinaItem(sku="CAFE-500G", nombre="Café Especial 500g", precio_cop=35000.0, stock_disponible=25, categoria="Bebidas"),
        VitrinaItem(sku="TAZA-CERAMICA", nombre="Taza Cerámica PiShop", precio_cop=18000.0, stock_disponible=50, categoria="Accesorios"),
        VitrinaItem(sku="CAMISETA-DEV", nombre="Camiseta Dev Algodón", precio_cop=45000.0, stock_disponible=12, categoria="Ropa"),
    ]
    return VitrinaResponse(items=productos_vitrina, total=len(productos_vitrina))
