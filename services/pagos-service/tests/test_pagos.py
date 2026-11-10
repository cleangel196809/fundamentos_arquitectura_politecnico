"""Los cuatro modos de la pasarela, la ACL, la idempotencia y el reembolso."""
import time

import httpx

COBRO = {"pedido_id": "PED-1", "monto_cop": 54000, "medio": "tarjeta"}


def cobrar(cliente, clave="pago-clave-0001"):
    return cliente.post("/v1/pagos", json=COBRO, headers={"Idempotency-Key": clave})


def test_sondas(fabricar):
    cliente = fabricar()
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_modo_ok_aprueba_y_traduce_vocabulario(fabricar):
    cuerpo = cobrar(fabricar("ok")).json()
    assert cuerpo["estado"] == "APROBADO" and cuerpo["codigo_autorizacion"].startswith("AUT-")


def test_modo_rechaza(fabricar):
    assert cobrar(fabricar("rechaza")).json()["estado"] == "RECHAZADO"


def test_modo_falla_es_503(fabricar):
    respuesta = cobrar(fabricar("falla"))
    assert respuesta.status_code == 503 and respuesta.json()["codigo"] == "PASARELA_CAIDA"


def test_modo_lento_responde_504_sin_colgarse(fabricar):
    def pasarela_que_no_contesta(_peticion):
        raise httpx.ReadTimeout("la pasarela no respondió")

    inicio = time.perf_counter()
    respuesta = cobrar(fabricar("lenta", httpx.MockTransport(pasarela_que_no_contesta)))
    assert respuesta.status_code == 504 and time.perf_counter() - inicio < 2


def test_misma_clave_no_cobra_dos_veces(fabricar):
    cliente = fabricar()
    primero, segundo = cobrar(cliente).json(), cobrar(cliente).json()
    assert primero == segundo


def test_sin_clave_400_y_validacion_422(fabricar):
    cliente = fabricar()
    assert cliente.post("/v1/pagos", json=COBRO).status_code == 400
    assert cliente.post("/v1/pagos", json={**COBRO, "monto_cop": -5}, headers={"Idempotency-Key": "abc12345"}).status_code == 422


def test_reembolso_idempotente(fabricar):
    cliente = fabricar()
    pago_id = cobrar(cliente).json()["pago_id"]
    assert cliente.post(f"/v1/pagos/{pago_id}/reembolso").json()["estado"] == "REEMBOLSADO"
    assert cliente.post(f"/v1/pagos/{pago_id}/reembolso").json()["estado"] == "REEMBOLSADO"
    assert cliente.get(f"/v1/pagos/{pago_id}").json()["estado"] == "REEMBOLSADO"
    assert cliente.get("/v1/pagos/PAG-NADA").status_code == 404


def test_cambiar_modo_en_caliente(fabricar):
    cliente = fabricar("ok")
    assert cliente.put("/_simulador/pasarela/modo", json={"modo": "rechaza"}).status_code == 200
    assert cobrar(cliente, "otra-clave-002").json()["estado"] == "RECHAZADO"
