"""ETag/304, versionado con auditoría, historial y rollback."""
CAMBIO = {"data": {"pagina_tamano": 35}, "motivo": "más productos por página"}


def test_sondas(cliente):
    for ruta in ("/health/live", "/health/startup", "/health/ready"):
        assert cliente.get(ruta).status_code == 200


def test_semilla_y_etag_304(cliente):
    primera = cliente.get("/config/catalogo-service/prod")
    assert primera.json()["data"]["pagina_tamano"] == 50 and primera.headers["ETag"] == '"v1"'
    assert cliente.get("/config/catalogo-service/prod", headers={"If-None-Match": '"v1"'}).status_code == 304


def test_put_exige_autor_y_crea_version(cliente):
    assert cliente.put("/config/catalogo-service/dev", json=CAMBIO).status_code == 400
    nueva = cliente.put("/config/catalogo-service/dev", json=CAMBIO, headers={"X-Autor": "maik"})
    assert nueva.json()["version"] == 2
    historial = cliente.get("/config/catalogo-service/dev/versions").json()
    assert [v["autor"] for v in historial] == ["semilla", "maik"]


def test_version_historica_y_rollback(cliente):
    cliente.put("/config/catalogo-service/dev", json=CAMBIO, headers={"X-Autor": "maik"})
    assert cliente.get("/config/catalogo-service/dev?version=1").json()["data"]["pagina_tamano"] == 20
    revertida = cliente.post("/config/catalogo-service/dev/rollback/1", headers={"X-Autor": "maik"}).json()
    assert revertida["version"] == 3 and revertida["data"]["pagina_tamano"] == 20


def test_404_y_nombres_invalidos(cliente):
    assert cliente.get("/config/no-existe/dev").status_code == 404
    assert cliente.get("/config/catalogo-service/produccion").status_code == 422


def test_token_admin_protege_la_escritura(cliente_protegido):
    sin_token = cliente_protegido.put("/config/pagos-service/dev", json=CAMBIO, headers={"X-Autor": "x"})
    assert sin_token.status_code == 401
    con_token = cliente_protegido.put("/config/pagos-service/dev", json=CAMBIO,
                                      headers={"X-Autor": "x", "X-Token-Admin": "token-admin-de-prueba-123"})
    assert con_token.status_code == 200
