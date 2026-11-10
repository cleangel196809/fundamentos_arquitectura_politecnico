"""Casos del contrato de inventario-service: idempotencia, 409, compensación y carrera."""
from concurrent.futures import ThreadPoolExecutor


def apartar(cliente, sku, cantidad, clave, pedido="P-1"):
    return cliente.post("/v1/reservas", json={"sku": sku, "cantidad": cantidad, "pedido_id": pedido},
                        headers={"Idempotency-Key": clave})


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_stock_sembrado_y_ajuste(cliente):
    assert cliente.get("/v1/stock/CAFE-500G").json() == {"sku": "CAFE-500G", "cantidad": 120, "reservado": 0, "disponible": 120}
    assert cliente.put("/v1/stock/NUEVO-SKU", json={"cantidad": 7}).json()["cantidad"] == 7
    assert cliente.put("/v1/stock/NUEVO-SKU", json={"cantidad": -1}).status_code == 422
    assert cliente.get("/v1/stock/NO-HAY").status_code == 404


def test_misma_clave_misma_respuesta_sin_descontar_dos_veces(cliente):
    primera = apartar(cliente, "PANELA-1K", 5, "clave-unica-001")
    segunda = apartar(cliente, "PANELA-1K", 5, "clave-unica-001")
    assert primera.status_code == segunda.status_code == 201
    assert primera.json() == segunda.json()
    assert cliente.get("/v1/stock/PANELA-1K").json()["reservado"] == 5


def test_sin_clave_es_400(cliente):
    respuesta = cliente.post("/v1/reservas", json={"sku": "PANELA-1K", "cantidad": 1, "pedido_id": "P"})
    assert respuesta.status_code == 400


def test_stock_insuficiente_es_409(cliente):
    respuesta = apartar(cliente, "GULUPA-500", 3, "clave-gulupa-01")
    assert respuesta.status_code == 409 and respuesta.json()["codigo"] == "STOCK_INSUFICIENTE"


def test_liberar_dos_veces_no_devuelve_doble(cliente):
    reserva = apartar(cliente, "LULO-1K", 2, "clave-lulo-0001").json()
    cliente.post(f"/v1/reservas/{reserva['reserva_id']}/liberar")
    otra_vez = cliente.post(f"/v1/reservas/{reserva['reserva_id']}/liberar")
    assert otra_vez.json()["estado"] == "LIBERADA"
    assert cliente.get("/v1/stock/LULO-1K").json() == {"sku": "LULO-1K", "cantidad": 3, "reservado": 0, "disponible": 3}


def test_confirmar_descuenta_de_bodega(cliente):
    reserva = apartar(cliente, "MACHETE-18", 4, "clave-machete-1").json()
    assert cliente.post(f"/v1/reservas/{reserva['reserva_id']}/confirmar").json()["estado"] == "CONFIRMADA"
    assert cliente.get("/v1/stock/MACHETE-18").json() == {"sku": "MACHETE-18", "cantidad": 11, "reservado": 0, "disponible": 11}
    assert cliente.post(f"/v1/reservas/{reserva['reserva_id']}/liberar").status_code == 409


def test_carrera_por_la_ultima_unidad(cliente):
    """10 compradores a la vez por 2 unidades: exactamente 2 ganan, el resto recibe 409."""
    with ThreadPoolExecutor(max_workers=10) as hilos:
        resultados = list(hilos.map(lambda n: apartar(cliente, "GULUPA-500", 1, f"clave-carrera-{n:03d}").status_code, range(10)))
    assert resultados.count(201) == 2 and resultados.count(409) == 8
    assert cliente.get("/v1/stock/GULUPA-500").json()["disponible"] == 0
