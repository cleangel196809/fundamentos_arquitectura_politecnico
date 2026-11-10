"""Consumidor idempotente: el mismo evento dos veces produce UNA notificación."""

EVENTO = {"evento_id": "11111111-aaaa-bbbb-cccc-000000000001", "tipo": "PedidoCreado",
          "payload": {"pedido_id": "PED-1", "cliente_id": "C-9001", "sku": "CAFE-500G", "cantidad": 3, "monto_cop": 54000}}


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_evento_duplicado_se_descarta(cliente):
    assert cliente.post("/v1/notificaciones/prueba", json=EVENTO).json()["resultado"] == "enviada"
    assert cliente.post("/v1/notificaciones/prueba", json=EVENTO).json()["resultado"] == "duplicado"
    enviadas = cliente.get("/v1/notificaciones?pedido_id=PED-1").json()
    assert len(enviadas) == 1 and "54,000" in enviadas[0]["mensaje"]


def test_cancelacion_genera_su_propio_mensaje(cliente):
    cliente.post("/v1/notificaciones/prueba", json=EVENTO)
    cancelado = {**EVENTO, "evento_id": "11111111-aaaa-bbbb-cccc-000000000002", "tipo": "PedidoCancelado"}
    cliente.post("/v1/notificaciones/prueba", json=cancelado)
    tipos = sorted(n["tipo_evento"] for n in cliente.get("/v1/notificaciones").json())
    assert tipos == ["PedidoCancelado", "PedidoCreado"]


def test_tipo_desconocido_es_422(cliente):
    assert cliente.post("/v1/notificaciones/prueba", json={**EVENTO, "tipo": "Otro"}).status_code == 422
