"""CQRS: proyección idempotente, cancelaciones y reconstrucción."""


def evento(numero, tipo="PedidoCreado", sku="CAFE-500G", cantidad=2, monto=36000):
    return {"evento_id": f"evt-{numero:04d}", "tipo": tipo,
            "payload": {"pedido_id": f"PED-{numero}", "cliente_id": "C-1", "sku": sku, "cantidad": cantidad, "monto_cop": monto}}


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_reprocesar_no_altera_totales(cliente):
    for _ in range(3):
        cliente.post("/v1/reportes/eventos/prueba", json=evento(1))
    assert cliente.get("/v1/reportes/resumen").json() == {"pedidos_total": 1, "unidades_total": 2, "monto_total_cop": 36000}


def test_cancelacion_descuenta(cliente):
    cliente.post("/v1/reportes/eventos/prueba", json=evento(1))
    cliente.post("/v1/reportes/eventos/prueba", json=evento(2, sku="PANELA-1K", cantidad=5, monto=35000))
    cancelado = evento(1, tipo="PedidoCancelado")
    cancelado["evento_id"] = "evt-cancel-1"
    cliente.post("/v1/reportes/eventos/prueba", json=cancelado)
    assert cliente.get("/v1/reportes/resumen").json() == {"pedidos_total": 1, "unidades_total": 5, "monto_total_cop": 35000}
    por_sku = {v["sku"]: v for v in cliente.get("/v1/reportes/ventas-por-sku").json()}
    assert por_sku["CAFE-500G"]["pedidos"] == 0 and por_sku["PANELA-1K"]["unidades"] == 5


def test_reconstruir_da_el_mismo_resultado(cliente):
    for n in range(1, 6):
        cliente.post("/v1/reportes/eventos/prueba", json=evento(n))
    antes = cliente.get("/v1/reportes/resumen").json()
    informe = cliente.post("/v1/reportes/reconstruir").json()
    assert informe["eventos_leidos"] == 5 and informe["aplicado"] == 5
    assert cliente.get("/v1/reportes/resumen").json() == antes
