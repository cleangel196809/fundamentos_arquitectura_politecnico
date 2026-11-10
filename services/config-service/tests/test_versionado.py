"""Activity 2: versionado con historial (autor, motivo, fecha)."""


def _put(c, data, motivo="cambio de prueba", autor="fnavarro", app="catalogo-service", env="dev"):
    return c.put(f"/config/{app}/{env}", json={"data": data, "motivo": motivo}, headers={"X-Autor": autor})


def test_config_inexistente_da_404_con_formato_del_contrato(client):
    r = client.get("/config/catalogo-service/dev")
    assert r.status_code == 404
    assert r.json()["codigo"] == "CONFIG_NO_ENCONTRADA" and "detalle" in r.json()


def test_put_crea_versiones_monotonas(client):
    assert _put(client, {"pagina_tamano": 20}).json()["version"] == 1
    r = _put(client, {"pagina_tamano": 50}, motivo="ajuste p95")
    assert r.status_code == 201 and r.json()["version"] == 2
    actual = client.get("/config/catalogo-service/dev").json()
    assert actual["version"] == 2 and actual["data"] == {"pagina_tamano": 50}


def test_historial_registra_autor_motivo_y_fecha(client):
    _put(client, {"a": 1}, motivo="inicial", autor="ana")
    _put(client, {"a": 2}, motivo="segundo", autor="beto")
    h = client.get("/config/catalogo-service/dev/versions").json()
    assert [v["version"] for v in h] == [1, 2]
    assert [v["autor"] for v in h] == ["ana", "beto"]
    assert h[1]["motivo"] == "segundo" and h[1]["creado_en"]


def test_entornos_y_apps_son_independientes(client):
    _put(client, {"x": 1}, env="dev")
    _put(client, {"x": 9}, env="prod")
    assert client.get("/config/catalogo-service/prod").json()["version"] == 1
    assert client.get("/config/catalogo-service/dev").json()["data"] == {"x": 1}


def test_validacion_422(client):
    assert client.get("/config/catalogo-service/produccion").status_code == 422
    r = client.put("/config/catalogo-service/dev", json={"data": {"a": 1}, "motivo": "x"}, headers={"X-Autor": "ana"})
    assert r.status_code == 422 and r.json()["codigo"] == "VALIDACION"
