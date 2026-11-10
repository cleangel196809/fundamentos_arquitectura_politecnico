"""Dobles de los cuatro servicios core: el BFF se prueba sin depender de nadie."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.settings import Settings


class NucleoFalso:
    """Imita catalogo, inventario, pedidos y pagos según docs/CONTRATOS.md.

    `falla_en` permite romper un paso concreto: 'catalogo', 'inventario',
    'pedidos', 'pagos_rechazo', 'pagos_caido' o 'stock'.
    """

    def __init__(self, falla_en: str | None = None):
        self.falla_en = falla_en
        self.llamadas: list[str] = []
        self.pedidos_creados = 0

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        host, ruta, metodo = peticion.url.host, peticion.url.path, peticion.method
        self.llamadas.append(f"{metodo} {host}{ruta}")
        if host == "catalogo":
            if self.falla_en == "catalogo":
                raise httpx.ConnectError("catalogo apagado")
            if ruta == "/v1/productos":
                return httpx.Response(200, json={"items": [
                    {"sku": "CAFE-500G", "nombre": "Café", "precio_cop": 18000, "categoria": "cafe", "publicado": True},
                    {"sku": "LULO-1K", "nombre": "Lulo", "precio_cop": 7400, "categoria": "frutas", "publicado": True}],
                    "total": 2, "pagina": 1, "tamano": 100})
            return httpx.Response(200, json={"sku": "CAFE-500G", "precio_cop": 18000, "publicado": True})
        if host == "inventario":
            if self.falla_en == "inventario":
                raise httpx.ReadTimeout("inventario lento")
            if ruta.startswith("/v1/stock/"):
                return httpx.Response(200, json={"disponible": 0 if "LULO" in ruta else 50})
            if ruta == "/v1/reservas":
                if self.falla_en == "stock":
                    return httpx.Response(409, json={"detalle": "Stock insuficiente", "codigo": "STOCK_INSUFICIENTE"})
                return httpx.Response(201, json={"reserva_id": "R-1", "estado": "ACTIVA"})
            return httpx.Response(200, json={"reserva_id": "R-1"})
        if host == "pedidos":
            if ruta == "/v1/pedidos":
                if self.falla_en == "pedidos":
                    return httpx.Response(500, json={"detalle": "error", "codigo": "ERROR_INTERNO"})
                self.pedidos_creados += 1
                return httpx.Response(201, json={"pedido_id": "PED-1", "estado": "CREADO"})
            if ruta == "/v1/pedidos/PED-1":
                return httpx.Response(200, json={"pedido_id": "PED-1", "estado": "CONFIRMADO", "monto_cop": 36000})
            return httpx.Response(200, json={"pedido_id": "PED-1"})
        if host == "pagos":
            if self.falla_en == "pagos_caido":
                return httpx.Response(503, json={"detalle": "La pasarela de pagos no está disponible"})
            estado = "RECHAZADO" if self.falla_en == "pagos_rechazo" else "APROBADO"
            return httpx.Response(201, json={"pago_id": "PAG-1", "estado": estado})
        return httpx.Response(404, json={"detalle": "no existe"})


@pytest.fixture
def armar():
    abiertos = []

    def _armar(falla_en=None):
        nucleo = NucleoFalso(falla_en)
        ajustes = Settings(_env_file=None, catalogo_url="http://catalogo", inventario_url="http://inventario",
                           pedidos_url="http://pedidos", pagos_url="http://pagos")
        navegador = TestClient(crear_app(ajustes, httpx.MockTransport(nucleo)))
        navegador.__enter__()
        abiertos.append(navegador)
        return navegador, nucleo

    yield _armar
    for navegador in abiertos:
        navegador.__exit__(None, None, None)
