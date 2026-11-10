"""Pruebas de ciberseguridad de api-publica (checklist de auditoría antes del PR)."""
import httpx
import pytest
from pydantic import ValidationError

from app.settings import Settings
from tests.conftest import CLAVE

COMPRA = {"cliente_id": "C-9001", "sku": "CAFE-500G", "cantidad": 3, "medio_pago": "PSE"}
LIMITE = 40   # requisito del proyecto: 40 peticiones por minuto por clave
RUTAS_PROTEGIDAS = [("GET", "/v1/catalogo/productos"), ("POST", "/v1/compras"), ("GET", "/v1/compras/P-1")]


# ----------------------------------------------------------- autenticación (401)
@pytest.mark.parametrize("metodo,ruta", RUTAS_PROTEGIDAS)
def test_sin_api_key_devuelve_401(cliente, metodo, ruta):
    r = cliente().request(metodo, ruta, json=COMPRA if metodo == "POST" else None)
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["status"] == 401 and r.headers["www-authenticate"] == "ApiKey"


def test_api_key_invalida_devuelve_401(cliente):
    assert cliente().get("/v1/catalogo/productos", headers={"X-API-Key": "otra-clave"}).status_code == 401


def test_clave_no_configurada_falla_cerrado(cliente):
    """Sin PISHOP_API_KEY nadie entra (ni siquiera enviando una clave vacía)."""
    c = cliente(api_key="")
    assert c.get("/v1/catalogo/productos", headers={"X-API-Key": ""}).status_code == 401
    assert c.get("/v1/catalogo/productos", headers={"X-API-Key": "cualquiera"}).status_code == 401


def test_las_sondas_no_exigen_clave(cliente):
    c = cliente()
    assert [c.get(f"/health/{s}").status_code for s in ("live", "startup", "ready")] == [200, 200, 200]


# ----------------------------------------------------------- límite de tasa (429)
def test_41_peticiones_en_un_minuto_devuelven_429_con_retry_after(cliente, auth):
    c = cliente()
    codigos = [c.get("/v1/catalogo/productos", headers=auth).status_code for _ in range(LIMITE)]
    assert set(codigos) == {200}
    r = c.get("/v1/catalogo/productos", headers=auth)
    assert r.status_code == 429
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert r.headers["content-type"].startswith("application/problem+json")


def test_el_limite_es_por_clave_y_compartido_entre_rutas(cliente, auth):
    c = cliente()
    for _ in range(LIMITE // 2):
        c.get("/v1/catalogo/productos", headers=auth)
    for _ in range(LIMITE // 2):
        c.get("/v1/compras/P-1", headers=auth)
    assert c.get("/v1/catalogo/productos", headers=auth).status_code == 429


def test_adivinar_claves_tambien_se_limita_y_no_bloquea_a_la_clave_valida(cliente, auth):
    c = cliente()
    for i in range(LIMITE):
        assert c.get("/v1/catalogo/productos", headers={"X-API-Key": f"intento-{i}"}).status_code == 401
    assert c.get("/v1/catalogo/productos", headers={"X-API-Key": "intento-nuevo"}).status_code == 429
    assert c.get("/v1/catalogo/productos", headers=auth).status_code == 200   # cubo distinto


def test_las_sondas_no_consumen_cuota(cliente):
    c = cliente()
    assert {c.get("/health/live").status_code for _ in range(150)} == {200}


# ----------------------------------------------------------- validación (422) y errores
@pytest.mark.parametrize("cuerpo", [
    {},                                          # faltan campos
    {**COMPRA, "cantidad": -1},                  # rango no positivo
    {**COMPRA, "cantidad": "tres"},              # tipo inválido
    {**COMPRA, "sku": "../etc/passwd"},          # caracteres no permitidos
    {**COMPRA, "es_admin": True},                # campo no declarado (mass assignment)
])
def test_cuerpo_invalido_devuelve_422_sin_fallo_catastrofico(cliente, auth, cuerpo):
    r = cliente().post("/v1/compras", json=cuerpo, headers=auth)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert all(set(e) == {"loc", "msg", "type"} for e in r.json()["errors"])   # sin 'input'
    assert "Traceback" not in r.text


def test_json_malformado_devuelve_422(cliente, auth):
    r = cliente().post("/v1/compras", content=b'{"cliente_id": ', headers={**auth, "Content-Type": "application/json"})
    assert r.status_code == 422


def test_identificador_de_ruta_con_caracteres_peligrosos_se_rechaza(cliente, auth):
    assert cliente().get("/v1/compras/a%24b", headers=auth).status_code == 422


def test_error_inesperado_devuelve_500_sin_exponer_detalles(cliente, auth):
    def explota(request):
        raise RuntimeError("fallo interno con password=hunter2")
    r = cliente(handler=explota).get("/v1/catalogo/productos", headers=auth)
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "hunter2" not in r.text and "RuntimeError" not in r.text and "Traceback" not in r.text
    assert r.json()["instance"] == "/v1/catalogo/productos"


# ----------------------------------------------------------- enrutamiento y fallos aguas abajo
def test_catalogo_solo_publicados_y_sin_campos_internos(cliente, auth):
    r = cliente().get("/v1/catalogo/productos", headers=auth)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [p["sku"] for p in items] == ["CAFE-500G", "PANELA-1K"]
    assert all(set(p) == {"sku", "nombre", "precio_cop", "categoria"} for p in items)


def test_compra_se_enruta_al_checkout_y_reenvia_idempotency_key(cliente, auth):
    vistas = []

    def espia(request: httpx.Request):
        vistas.append(request)
        return httpx.Response(201, json={"pedido_id": "P-9", "estado": "CONFIRMADO", "pasos": []})

    c = cliente(handler=espia)
    r = c.post("/v1/compras", json=COMPRA, headers={**auth, "Idempotency-Key": "clave-idem-0001"})
    assert r.status_code == 201 and r.json() == {"pedido_id": "P-9", "estado": "CONFIRMADO"}
    assert vistas[0].headers["idempotency-key"] == "clave-idem-0001" and vistas[0].url.path == "/v1/checkout"
    c.post("/v1/compras", json=COMPRA, headers=auth)   # sin clave: se genera una
    assert len(vistas[1].headers["idempotency-key"]) >= 8


def test_consultar_compra(cliente, auth):
    r = cliente().get("/v1/compras/P-1", headers=auth)
    assert r.status_code == 200 and r.json() == {"pedido_id": "P-1", "estado": "CONFIRMADO"}
    assert cliente().get("/v1/compras/NO-EXISTE", headers=auth).status_code == 404


@pytest.mark.parametrize("fallo,esperado", [
    (httpx.ReadTimeout("lento"), 504),
    (httpx.ConnectError("caido"), 503),
])
def test_servicio_interno_lento_o_caido(cliente, auth, fallo, esperado):
    def falla(request):
        raise fallo
    r = cliente(handler=falla).get("/v1/catalogo/productos", headers=auth)
    assert r.status_code == esperado and r.headers["content-type"].startswith("application/problem+json")


def test_respuesta_5xx_interna_se_traduce_a_502(cliente, auth):
    r = cliente(handler=lambda req: httpx.Response(500, text="stack trace interno")).get("/v1/catalogo/productos", headers=auth)
    assert r.status_code == 502 and "stack trace" not in r.text


def test_el_cliente_httpx_tiene_timeout_explicito(cliente):
    c = cliente(http_timeout_seconds=1.5)
    t = c.app.state.http.timeout
    assert (t.connect, t.read, t.write, t.pool) == (1.5, 1.5, 1.5, 1.5)


# ----------------------------------------------------------- gobernanza de secretos
def test_secretstr_no_imprime_el_valor_real():
    s = Settings(_env_file=None, api_key=CLAVE)
    assert CLAVE not in repr(s) and CLAVE not in str(s) and "**********" in repr(s)
    assert s.api_key.get_secret_value() == CLAVE


@pytest.mark.parametrize("clave", ["", "cambiar-esto", "corta"])
def test_fuera_de_dev_se_rechazan_claves_ausentes_de_ejemplo_o_debiles(clave):
    with pytest.raises(ValidationError) as e:
        Settings(_env_file=None, app_env="prod", api_key=clave)
    if clave:
        assert clave not in str(e.value)   # el error de validación no filtra el valor


def test_en_prod_acepta_una_clave_fuerte():
    assert Settings(_env_file=None, app_env="prod", api_key="x" * 32).app_env == "prod"


# ----------------------------------------------------------- extras de seguridad
def test_cabeceras_de_seguridad_en_todas_las_respuestas(cliente, auth):
    c = cliente()
    for r in (c.get("/v1/catalogo/productos", headers=auth), c.get("/v1/catalogo/productos")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert float(r.headers["x-tiempo-respuesta-ms"]) >= 0


def test_en_prod_no_se_publica_la_documentacion(cliente):
    assert cliente(app_env="prod", api_key="x" * 32).get("/docs").status_code in (401, 404)


def test_compra_fallida_devuelve_409_problem_json(cliente, auth):
    def saga_fallida(request):
        return httpx.Response(409, json={"pedido_id": "P-5", "estado": "FALLIDO", "motivo": "Pago RECHAZADO", "pasos": []})
    r = cliente(handler=saga_fallida).post("/v1/compras", json=COMPRA, headers=auth)
    assert r.status_code == 409 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["pedido_id"] == "P-5" and r.json()["detail"] == "Pago RECHAZADO"
