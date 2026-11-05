"""Activity 3: ETag, If-None-Match -> 304, consulta ?version=N y rollback."""


def _put(c, data, motivo="cambio", autor="fnavarro", app="catalogo-service", env="prod"):
    return c.put(f"/config/{app}/{env}", json={"data": data, "motivo": motivo}, headers={"X-Autor": autor})


def test_etag_y_if_none_match_devuelve_304(client):
    _put(client, {"timeout_inventario_s": 3.0, "pagina_tamano": 20}, motivo="inicial")
    r1 = client.get("/config/catalogo-service/prod")
    assert r1.status_code == 200
    assert r1.headers.get("ETag") == '"v1"'

    r2 = client.get("/config/catalogo-service/prod", headers={"If-None-Match": '"v1"'})
    assert r2.status_code == 304
    assert r2.text == ""

    # Al publicar v2, el ETag anterior '"v1"' ya no coincide y entrega 200 con '"v2"'
    _put(client, {"timeout_inventario_s": 1.5, "pagina_tamano": 50}, motivo="ajuste p95")
    r3 = client.get("/config/catalogo-service/prod", headers={"If-None-Match": '"v1"'})
    assert r3.status_code == 200
    assert r3.headers.get("ETag") == '"v2"'
    assert r3.json()["version"] == 2


def test_consultar_version_historica_especifica(client):
    _put(client, {"pagina_tamano": 20}, motivo="v1 inicial")
    _put(client, {"pagina_tamano": 50}, motivo="v2 ajuste")

    v1 = client.get("/config/catalogo-service/prod?version=1")
    assert v1.status_code == 200
    assert v1.json()["version"] == 1 and v1.json()["data"] == {"pagina_tamano": 20}
    assert v1.headers.get("ETag") == '"v1"'

    inexistente = client.get("/config/catalogo-service/prod?version=99")
    assert inexistente.status_code == 404
    assert inexistente.json()["codigo"] == "VERSION_NO_ENCONTRADA"


def test_rollback_crea_nueva_version_inmutable(client):
    _put(client, {"pagina_tamano": 20, "flag_promos": False}, motivo="v1 estable")
    _put(client, {"pagina_tamano": 100, "flag_promos": True}, motivo="v2 experimento")

    rb = client.post("/config/catalogo-service/prod/rollback/1", headers={"X-Autor": "fnavarro"})
    assert rb.status_code == 201
    cuerpo = rb.json()
    assert cuerpo["version"] == 3
    assert cuerpo["data"] == {"pagina_tamano": 20, "flag_promos": False}
    assert "rollback a v1" in cuerpo["motivo"]

    # El historial conserva v1, v2 y v3 (inmutabilidad de auditoría)
    hist = client.get("/config/catalogo-service/prod/versions").json()
    assert [v["version"] for v in hist] == [1, 2, 3]

    # Rollback a versión inexistente -> 404
    rb_404 = client.post("/config/catalogo-service/prod/rollback/99", headers={"X-Autor": "fnavarro"})
    assert rb_404.status_code == 404
