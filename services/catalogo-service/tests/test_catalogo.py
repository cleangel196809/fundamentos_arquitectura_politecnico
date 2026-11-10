"""Casos del contrato de catalogo-service: 200, 201, 404, 409, 422 y paginación."""


def test_las_tres_sondas_responden(cliente):
    assert cliente.get("/health/live").status_code == 200
    assert cliente.get("/health/startup").status_code == 200
    listo = cliente.get("/health/ready")
    assert listo.status_code == 200 and listo.json()["base_datos"] is True


def test_semilla_carga_productos_ficticios(cliente):
    cuerpo = cliente.get("/v1/productos?tamano=100").json()
    assert cuerpo["total"] == 30
    assert any(p["sku"] == "CAFE-500G" for p in cuerpo["items"])


def test_paginacion_respeta_tamano(cliente):
    primera = cliente.get("/v1/productos?pagina=1&tamano=5").json()
    segunda = cliente.get("/v1/productos?pagina=2&tamano=5").json()
    assert len(primera["items"]) == 5 and primera["tamano"] == 5
    assert primera["items"][0]["sku"] != segunda["items"][0]["sku"]
    assert cliente.get("/v1/productos?tamano=101").status_code == 422


def test_crear_y_duplicar_sku(cliente):
    nuevo = {"sku": "PANELA-2K", "nombre": "Panela 2 kg", "precio_cop": 13000, "categoria": "dulces"}
    creado = cliente.post("/v1/productos", json=nuevo)
    assert creado.status_code == 201 and creado.json()["publicado"] is False
    repetido = cliente.post("/v1/productos", json=nuevo)
    assert repetido.status_code == 409 and repetido.json()["codigo"] == "SKU_DUPLICADO"


def test_precio_cero_o_negativo_es_422(cliente):
    malo = {"sku": "GRATIS-1", "nombre": "Regalo", "precio_cop": 0, "categoria": "x1"}
    respuesta = cliente.post("/v1/productos", json=malo)
    assert respuesta.status_code == 422 and respuesta.json()["codigo"] == "VALIDACION"


def test_detalle_y_404(cliente):
    assert cliente.get("/v1/productos/CAFE-500G").json()["precio_cop"] == 18000
    no_existe = cliente.get("/v1/productos/NO-EXISTE")
    assert no_existe.status_code == 404 and no_existe.json()["codigo"] == "NO_ENCONTRADO"


def test_publicar(cliente):
    assert cliente.get("/v1/productos/TE-COCA-BORRADOR").json()["publicado"] is False
    publicado = cliente.patch("/v1/productos/TE-COCA-BORRADOR/publicar")
    assert publicado.status_code == 200 and publicado.json()["publicado"] is True
    assert cliente.patch("/v1/productos/NADA/publicar").status_code == 404


def test_cabeceras_de_medicion(cliente):
    respuesta = cliente.get("/v1/productos", headers={"X-Correlacion-Id": "prueba-123"})
    assert float(respuesta.headers["X-Tiempo-Respuesta-ms"]) >= 0
    assert respuesta.headers["X-Correlacion-Id"] == "prueba-123"
