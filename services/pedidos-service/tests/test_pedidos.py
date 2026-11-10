"""Pedidos + Outbox: transacción única, cancelación y entrega al-menos-una-vez."""
import pytest

from app.publicador import publicar_lote

PEDIDO = {"cliente_id": "C-9001", "sku": "CAFE-500G", "cantidad": 3, "monto_cop": 54000}


def publicar(cliente, antes_de_marcar=None):
    app = cliente.app
    return cliente.portal.call(publicar_lote, app.state.fabrica_sesiones, app.state.bus, antes_de_marcar)


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_crear_guarda_pedido_y_evento_juntos(cliente):
    creado = cliente.post("/v1/pedidos", json=PEDIDO)
    assert creado.status_code == 201 and creado.json()["estado"] == "CREADO"
    pendientes = cliente.get("/v1/outbox/pendientes").json()
    assert len(pendientes) == 1 and pendientes[0]["tipo"] == "PedidoCreado"
    assert pendientes[0]["contenido"]["pedido_id"] == creado.json()["pedido_id"]


def test_idempotency_key_no_crea_dos_pedidos(cliente):
    a = cliente.post("/v1/pedidos", json=PEDIDO, headers={"Idempotency-Key": "checkout-777"}).json()
    b = cliente.post("/v1/pedidos", json=PEDIDO, headers={"Idempotency-Key": "checkout-777"}).json()
    assert a["pedido_id"] == b["pedido_id"]
    assert len(cliente.get("/v1/outbox/pendientes").json()) == 1


def test_publicador_vacia_la_outbox(cliente):
    cliente.post("/v1/pedidos", json=PEDIDO)
    assert publicar(cliente) == 1
    assert cliente.get("/v1/outbox/pendientes").json() == []
    assert cliente.app.state.bus.publicados[0]["tipo"] == "PedidoCreado"


def test_al_menos_una_vez_si_muere_entre_publicar_y_marcar(cliente):
    cliente.post("/v1/pedidos", json=PEDIDO)

    def caida_simulada(_evento):
        raise RuntimeError("el proceso murió antes de marcar publicado_en")

    with pytest.raises(RuntimeError):
        publicar(cliente, caida_simulada)
    publicar(cliente)                                   # el proceso "revive"
    enviados = cliente.app.state.bus.publicados
    assert len(enviados) == 2 and enviados[0]["evento_id"] == enviados[1]["evento_id"]   # duplicado esperado


def test_cancelar_genera_evento_una_sola_vez(cliente):
    pedido_id = cliente.post("/v1/pedidos", json=PEDIDO).json()["pedido_id"]
    assert cliente.post(f"/v1/pedidos/{pedido_id}/cancelar").json()["estado"] == "CANCELADO"
    cliente.post(f"/v1/pedidos/{pedido_id}/cancelar")
    tipos = [e["tipo"] for e in cliente.get("/v1/outbox/pendientes").json()]
    assert tipos == ["PedidoCreado", "PedidoCancelado"]


def test_confirmar_y_404(cliente):
    pedido_id = cliente.post("/v1/pedidos", json=PEDIDO).json()["pedido_id"]
    assert cliente.post(f"/v1/pedidos/{pedido_id}/confirmar").json()["estado"] == "CONFIRMADO"
    assert cliente.post(f"/v1/pedidos/{pedido_id}/cancelar").status_code == 409
    assert cliente.get("/v1/pedidos/PED-NO-EXISTE").status_code == 404


def test_validacion_422(cliente):
    assert cliente.post("/v1/pedidos", json={**PEDIDO, "cantidad": 0}).status_code == 422
