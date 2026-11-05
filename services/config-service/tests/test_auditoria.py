"""Activity 4: exigir X-Autor en PUT para auditoría (y token opcional)."""


def test_put_sin_x_autor_es_rechazado_422(client):
    r = client.put("/config/catalogo-service/dev", json={"data": {"pagina_tamano": 20}, "motivo": "sin autor"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_put_con_x_autor_en_blanco_es_rechazado(client):
    r = client.put(
        "/config/catalogo-service/dev",
        json={"data": {"pagina_tamano": 20}, "motivo": "autor vacio"},
        headers={"X-Autor": "   "},
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "AUTOR_VACIO"


def test_put_con_x_autor_registra_autor_en_auditoria(client):
    r = client.put(
        "/config/inventario-service/prod",
        json={"data": {"reserva_ttl_s": 300}},
        headers={"X-Autor": "fnavarro"},
    )
    assert r.status_code == 201
    assert r.json()["autor"] == "fnavarro"


def test_write_token_opcional_protege_escritura(client, monkeypatch):
    monkeypatch.setenv("PISHOP_WRITE_TOKEN", "token-ops-2026")
    r_sin = client.put(
        "/config/pagos-service/prod",
        json={"data": {"timeout_s": 2.0}, "motivo": "sin token"},
        headers={"X-Autor": "fnavarro"},
    )
    assert r_sin.status_code == 401 and r_sin.json()["codigo"] == "NO_AUTORIZADO"

    r_con = client.put(
        "/config/pagos-service/prod",
        json={"data": {"timeout_s": 2.0}, "motivo": "con token"},
        headers={"X-Autor": "fnavarro", "X-Write-Token": "token-ops-2026"},
    )
    assert r_con.status_code == 201
