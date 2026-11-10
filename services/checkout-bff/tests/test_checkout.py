"""Saga de checkout: éxito, fallo en cada paso con sus compensaciones e idempotencia."""
COMPRA = {"cliente_id": "C-9001", "sku": "CAFE-500G", "cantidad": 2, "medio_pago": "tarjeta"}
CLAVE = {"Idempotency-Key": "compra-prueba-0001"}


def pasos(respuesta):
    return [(p["paso"], p["resultado"]) for p in respuesta.json()["pasos"]]


def test_sondas(armar):
    cliente, _ = armar()
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_compra_feliz(armar):
    cliente, _ = armar()
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "CONFIRMADO" and cuerpo["monto_cop"] == 36000 and cuerpo["pedido_id"] == "PED-1"
    assert [p for p, _ in pasos(respuesta)][:4] == ["validar_producto", "reservar_inventario", "crear_pedido", "cobrar"]


def test_pago_rechazado_compensa_en_orden_inverso(armar):
    cliente, _ = armar("pagos_rechazo")
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert respuesta.status_code == 409 and respuesta.json()["estado"] == "FALLIDO"
    assert pasos(respuesta)[-2:] == [("compensar_cancelar_pedido", "ok"), ("compensar_liberar_reserva", "ok")]


def test_pagos_caido_tambien_compensa(armar):
    cliente, _ = armar("pagos_caido")
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert respuesta.json()["estado"] == "FALLIDO" and "pasarela" in respuesta.json()["motivo"]


def test_fallo_al_crear_pedido_libera_reserva(armar):
    cliente, _ = armar("pedidos")
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert pasos(respuesta)[-1] == ("compensar_liberar_reserva", "ok")


def test_sin_stock_no_compensa_nada(armar):
    cliente, nucleo = armar("stock")
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert respuesta.json()["motivo"] == "Stock insuficiente"
    assert not any("liberar" in llamada for llamada in nucleo.llamadas)


def test_inventario_lento_responde_sin_colgarse(armar):
    cliente, _ = armar("inventario")
    respuesta = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE)
    assert respuesta.json()["motivo"] == "inventario-service no respondió a tiempo"


def test_repetir_checkout_no_crea_otro_pedido(armar):
    cliente, nucleo = armar()
    primera = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE).json()
    segunda = cliente.post("/v1/checkout", json=COMPRA, headers=CLAVE).json()
    assert primera == segunda and nucleo.pedidos_creados == 1


def test_sin_clave_400(armar):
    cliente, _ = armar()
    assert cliente.post("/v1/checkout", json=COMPRA).status_code == 400


def test_vitrina_y_fallback_si_inventario_cae(armar):
    cliente, _ = armar()
    vitrina = {a["sku"]: a for a in cliente.get("/v1/vitrina").json()}
    assert vitrina["CAFE-500G"]["disponible"] == 50 and vitrina["LULO-1K"]["agotado"] is True
    cliente_degradado, _ = armar("inventario")
    articulos = cliente_degradado.get("/v1/vitrina").json()
    assert len(articulos) == 2 and articulos[0]["disponible"] is None


def test_estado(armar):
    cliente, _ = armar()
    assert cliente.get("/v1/checkout/PED-1/estado").json()["estado"] == "CONFIRMADO"
