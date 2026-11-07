"""Doble de prueba de PiShop Cloud (P12 - Danixa Herrera).

Un servicio "de mentira" que imita, en UN solo proceso y en memoria, los
contratos de catalogo, inventario, pedidos, pagos, checkout-bff y api-publica
(docs/CONTRATOS.md). Sirve para correr retos/e2e.py sin esperar a los
companeros: "Nadie espera a otro: use un doble que respete el contrato".

Uso (desde la carpeta principal del proyecto):
    python -m uvicorn retos.dobles.pishop_doble:app --port 8000
    python retos/e2e.py --dobles          (en otra terminal)
"""
import uuid                                       # para generar identificadores unicos

from fastapi import FastAPI, Header, HTTPException   # FastAPI: el mismo framework de los servicios del curso

app = FastAPI(title="pishop-doble")               # crea la aplicacion web

API_KEY = "cambiar-esto"          # la misma llave del .env.example (solo para pruebas, no es secreta)

# "Bases de datos" en memoria: diccionarios que se borran al apagar el doble.
PRODUCTOS = {}    # catalogo:   sku -> producto
STOCK = {}        # inventario: sku -> {cantidad, reservado}
RESERVAS = {}     # inventario: reserva_id -> reserva
PEDIDOS = {}      # pedidos:    pedido_id -> pedido
CHECKOUTS = {}    # api/bff:    Idempotency-Key -> respuesta ya dada
SIMULADOR = {"modo": "ok"}        # modo de la pasarela: "ok" aprueba, "rechaza" rechaza


# ---------------------------------------------------------- simulador de pasarela
@app.post("/_simulador/modo/{modo}")              # e2e.py llama aqui para cambiar el modo
def cambiar_modo(modo: str):
    SIMULADOR["modo"] = modo
    return SIMULADOR


# ---------------------------------------------------------- catalogo (P01)
@app.post("/v1/productos", status_code=201)       # crear producto -> 201
def crear_producto(p: dict):
    if p["sku"] in PRODUCTOS:                     # SKU repetido...
        raise HTTPException(409, "SKU duplicado") # ...-> 409, como dice el contrato
    PRODUCTOS[p["sku"]] = {**p, "publicado": False}
    return PRODUCTOS[p["sku"]]


@app.patch("/v1/productos/{sku}/publicar")        # publicar producto
def publicar(sku: str):
    PRODUCTOS[sku]["publicado"] = True
    return PRODUCTOS[sku]


# ---------------------------------------------------------- inventario (P02)
@app.put("/v1/stock/{sku}")                       # fijar el stock de un producto
def poner_stock(sku: str, datos: dict):
    STOCK[sku] = {"sku": sku, "cantidad": datos["cantidad"], "reservado": 0}
    return STOCK[sku]


@app.get("/v1/stock/{sku}")                       # consultar el stock
def ver_stock(sku: str):
    return STOCK[sku]


def reservar(sku, cantidad):
    """Paso 2 de la saga: aparta unidades del stock."""
    if STOCK[sku]["cantidad"] < cantidad:         # no alcanza...
        raise HTTPException(409, "stock insuficiente")
    STOCK[sku]["cantidad"] -= cantidad            # descuenta
    reserva_id = str(uuid.uuid4())
    RESERVAS[reserva_id] = {"sku": sku, "cantidad": cantidad, "liberada": False}
    return reserva_id


def liberar(reserva_id):
    """Compensacion de reservar: devuelve el stock. Idempotente: liberar dos veces no devuelve doble."""
    r = RESERVAS[reserva_id]
    if not r["liberada"]:                         # solo si no se habia liberado antes
        STOCK[r["sku"]]["cantidad"] += r["cantidad"]
        r["liberada"] = True


# ---------------------------------------------------------- pedidos (P03)
@app.get("/v1/pedidos/{pedido_id}")               # consultar un pedido
def ver_pedido(pedido_id: str):
    return PEDIDOS[pedido_id]


# ---------------------------------------------------------- checkout-bff (P06): la SAGA
def checkout(cliente_id, sku, cantidad, medio_pago):
    """Orquesta los 4 pasos; si el cobro falla, compensa en orden inverso."""
    pasos = []                                                           # registro de lo que paso
    producto = PRODUCTOS.get(sku)                                        # 1. validar producto
    pasos.append({"paso": "validar_producto", "resultado": "ok" if producto else "fallo"})
    reserva_id = reservar(sku, cantidad)                                 # 2. reservar inventario
    pasos.append({"paso": "reservar_inventario", "resultado": "ok"})
    pedido_id = str(uuid.uuid4())                                        # 3. crear pedido
    PEDIDOS[pedido_id] = {"pedido_id": pedido_id, "estado": "CREADO"}
    pasos.append({"paso": "crear_pedido", "resultado": "ok"})
    aprobado = SIMULADOR["modo"] == "ok"                                 # 4. cobrar (pasarela simulada)
    pasos.append({"paso": "cobrar", "resultado": "APROBADO" if aprobado else "RECHAZADO"})
    if aprobado:                                                         # todo bien -> CONFIRMADO
        return {"pedido_id": pedido_id, "estado": "CONFIRMADO", "pasos": pasos}
    # Fallo el cobro: compensaciones en orden INVERSO (primero lo ultimo que se hizo).
    PEDIDOS[pedido_id]["estado"] = "CANCELADO"                           # deshace el paso 3
    pasos.append({"paso": "cancelar_pedido", "resultado": "compensado"})
    liberar(reserva_id)                                                  # deshace el paso 2
    pasos.append({"paso": "liberar_reserva", "resultado": "compensado"})
    return {"pedido_id": pedido_id, "estado": "FALLIDO", "pasos": pasos}


# ---------------------------------------------------------- api-publica (P07)
@app.post("/v1/compras", status_code=201)         # la puerta de entrada de las compras
def comprar(datos: dict, x_api_key: str = Header(None), idempotency_key: str = Header(None)):
    if x_api_key != API_KEY:                      # sin la llave correcta...
        raise HTTPException(401, "falta X-API-Key")   # ...-> 401, como dice el contrato
    if idempotency_key in CHECKOUTS:              # misma clave = misma respuesta, sin repetir la compra
        return CHECKOUTS[idempotency_key]
    respuesta = checkout(datos["cliente_id"], datos["sku"], datos["cantidad"], datos["medio_pago"])
    CHECKOUTS[idempotency_key] = respuesta        # guarda la respuesta para esa clave
    return respuesta
