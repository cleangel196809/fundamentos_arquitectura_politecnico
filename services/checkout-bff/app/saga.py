"""Saga de compra por ORQUESTACIÓN (semana 3).

Pasos, en orden:
  1. validar   -> catalogo-service: el producto existe, está publicado y da el precio
  2. reservar  -> inventario-service: aparta las unidades
  3. registrar -> pedidos-service: crea el pedido (y su evento PedidoCreado)
  4. cobrar    -> pagos-service: cobra; solo APROBADO cuenta como éxito

Si un paso falla, se deshace lo ya hecho en ORDEN INVERSO:
  cobrar falló    -> cancelar pedido, liberar reserva
  registrar falló -> liberar reserva
  reservar falló  -> (nada que deshacer)

Idempotencia de punta a punta: cada llamada lleva una Idempotency-Key derivada
de la del cliente ("<clave>:reserva", "<clave>:pedido", "<clave>:pago"). Si el
cliente reintenta la compra completa, cada servicio devuelve lo que ya hizo y
no se crea un segundo pedido ni se cobra dos veces.

Ningún servicio core orquesta a otro: toda la coordinación vive AQUÍ.
"""
import hashlib
import logging
from dataclasses import dataclass, field

from app.clientes import ClienteInterno, FalloDePaso

bitacora = logging.getLogger("saga-checkout")


@dataclass
class Bitacora:
    """Lo que se le devuelve al cliente: estado final y el rastro de cada paso."""
    pedido_id: str | None = None
    estado: str = "EN_CURSO"
    monto_cop: int = 0
    pasos: list[dict] = field(default_factory=list)
    motivo: str = ""

    def anotar(self, paso: str, resultado: str, detalle: str = "") -> None:
        registro = {"paso": paso, "resultado": resultado}
        if detalle:
            registro["detalle"] = detalle
        self.pasos.append(registro)

    def como_dict(self) -> dict:
        return {"pedido_id": self.pedido_id, "estado": self.estado, "monto_cop": self.monto_cop,
                "pasos": self.pasos, **({"motivo": self.motivo} if self.motivo else {})}


@dataclass
class Destinos:
    catalogo: ClienteInterno
    inventario: ClienteInterno
    pedidos: ClienteInterno
    pagos: ClienteInterno


def referencia_de_compra(clave_cliente: str) -> str:
    """Identificador estable de la compra (no expone la clave original)."""
    return "CHK-" + hashlib.sha256(clave_cliente.encode()).hexdigest()[:16]


async def ejecutar_compra(destinos: Destinos, compra: dict, clave_cliente: str) -> Bitacora:
    rastro = Bitacora()
    referencia = referencia_de_compra(clave_cliente)
    reserva_id: str | None = None

    # -------------------------------------------------------------- 1. validar producto
    try:
        producto = await destinos.catalogo.pedir("GET", f"/v1/productos/{compra['sku']}")
        if not producto.get("publicado"):
            raise FalloDePaso(f"El producto {compra['sku']} no está a la venta", 409)
        rastro.monto_cop = int(producto["precio_cop"]) * int(compra["cantidad"])
        rastro.anotar("validar_producto", "ok")
    except FalloDePaso as error:
        rastro.anotar("validar_producto", "fallo", error.motivo)
        return _fallida(rastro, error.motivo)

    # -------------------------------------------------------------- 2. reservar inventario
    try:
        apartado = await destinos.inventario.pedir(
            "POST", "/v1/reservas", clave_idempotencia=f"{clave_cliente}:reserva",
            json={"sku": compra["sku"], "cantidad": compra["cantidad"], "pedido_id": referencia})
        reserva_id = apartado["reserva_id"]
        rastro.anotar("reservar_inventario", "ok", reserva_id)
    except FalloDePaso as error:
        rastro.anotar("reservar_inventario", "fallo", error.motivo)
        return _fallida(rastro, error.motivo)

    # -------------------------------------------------------------- 3. registrar pedido
    try:
        pedido = await destinos.pedidos.pedir(
            "POST", "/v1/pedidos", clave_idempotencia=f"{clave_cliente}:pedido",
            json={"cliente_id": compra["cliente_id"], "sku": compra["sku"],
                  "cantidad": compra["cantidad"], "monto_cop": rastro.monto_cop})
        rastro.pedido_id = pedido["pedido_id"]
        rastro.anotar("crear_pedido", "ok", rastro.pedido_id)
    except FalloDePaso as error:
        rastro.anotar("crear_pedido", "fallo", error.motivo)
        await _liberar(destinos, rastro, reserva_id)
        return _fallida(rastro, error.motivo)

    # -------------------------------------------------------------- 4. cobrar
    try:
        pago = await destinos.pagos.pedir(
            "POST", "/v1/pagos", clave_idempotencia=f"{clave_cliente}:pago",
            json={"pedido_id": rastro.pedido_id, "monto_cop": rastro.monto_cop, "medio": compra["medio_pago"]})
        if pago.get("estado") != "APROBADO":
            raise FalloDePaso(f"Pago {pago.get('estado', 'desconocido')}", 402)
        rastro.anotar("cobrar", "ok", pago["pago_id"])
    except FalloDePaso as error:
        rastro.anotar("cobrar", "fallo", error.motivo)
        await _cancelar_pedido(destinos, rastro)
        await _liberar(destinos, rastro, reserva_id)
        return _fallida(rastro, error.motivo)

    # -------------------------------------------------------------- cierre feliz
    # Si alguna confirmación falla, la venta YA está cobrada: se deja anotado para revisión,
    # pero no se compensa (devolver el dinero por un fallo administrativo sería peor).
    for paso, destino, ruta in (("confirmar_reserva", destinos.inventario, f"/v1/reservas/{reserva_id}/confirmar"),
                                ("confirmar_pedido", destinos.pedidos, f"/v1/pedidos/{rastro.pedido_id}/confirmar")):
        try:
            await destino.pedir("POST", ruta)
            rastro.anotar(paso, "ok")
        except FalloDePaso as error:
            rastro.anotar(paso, "pendiente", error.motivo)
            bitacora.warning("compra %s cobrada pero %s quedó pendiente: %s", rastro.pedido_id, paso, error.motivo)
    rastro.estado = "CONFIRMADO"
    return rastro


# ------------------------------------------------------------------ compensaciones
async def _liberar(destinos: Destinos, rastro: Bitacora, reserva_id: str | None) -> None:
    if not reserva_id:
        return
    try:
        await destinos.inventario.pedir("POST", f"/v1/reservas/{reserva_id}/liberar")
        rastro.anotar("compensar_liberar_reserva", "ok", reserva_id)
    except FalloDePaso as error:
        rastro.anotar("compensar_liberar_reserva", "fallo", error.motivo)
        bitacora.error("no se pudo liberar la reserva %s: %s", reserva_id, error.motivo)


async def _cancelar_pedido(destinos: Destinos, rastro: Bitacora) -> None:
    try:
        await destinos.pedidos.pedir("POST", f"/v1/pedidos/{rastro.pedido_id}/cancelar")
        rastro.anotar("compensar_cancelar_pedido", "ok", rastro.pedido_id)
    except FalloDePaso as error:
        rastro.anotar("compensar_cancelar_pedido", "fallo", error.motivo)
        bitacora.error("no se pudo cancelar el pedido %s: %s", rastro.pedido_id, error.motivo)


def _fallida(rastro: Bitacora, motivo: str) -> Bitacora:
    rastro.estado = "FALLIDO"
    rastro.motivo = motivo
    return rastro
