#!/usr/bin/env python3
"""Prueba de extremo a extremo de PiShop Cloud (paquete P12).

Recorre el flujo completo contra el sistema levantado con docker compose:
  1. Las 10 sondas /health/ready responden.
  2. Seguridad: sin X-API-Key -> 401.
  3. Compra feliz: 201 CONFIRMADO, el stock baja, llega la notificación y el reporte.
  4. Compra con pago rechazado: 409 FALLIDO y se verifican las compensaciones
     (pedido CANCELADO y stock devuelto).
  5. (opcional, --probar-limite) la petición 41 dentro del minuto recibe 429.

Uso:
    python scripts/prueba_e2e.py
    python scripts/prueba_e2e.py --probar-limite
Código de salida 0 = todo bien.
"""
import argparse
import sys
import time
import uuid

from _comun import PUERTOS, esperar_sistema, leer_env, pedir, url

resultados: list[bool] = []


def verificar(descripcion: str, condicion: bool, extra="") -> bool:
    resultados.append(bool(condicion))
    print(f"  [{'OK' if condicion else 'FALLA'}] {descripcion}" + (f"  -> {extra}" if (extra and not condicion) else ""))
    return condicion


def disponible(sku: str) -> int:
    return pedir("GET", url("inventario-service", f"/v1/stock/{sku}"))[1]["disponible"]


def esperar_hasta(condicion, segundos: float = 15) -> bool:
    """Los efectos asíncronos (outbox -> Redis -> consumidores) tardan un poco."""
    limite = time.time() + segundos
    while time.time() < limite:
        if condicion():
            return True
        time.sleep(0.5)
    return False


def main() -> int:
    opciones = argparse.ArgumentParser()
    opciones.add_argument("--probar-limite", action="store_true", help="agota las 40 peticiones/min (tarda ~1 min)")
    argumentos = opciones.parse_args()
    clave = leer_env().get("PISHOP_API_KEY", "")
    autorizado = {"X-API-Key": clave}
    sku = "CAFE-500G"

    print("1) Sondas de salud")
    listos = verificar("los 10 servicios están listos", esperar_sistema(120))
    for servicio in PUERTOS:
        codigo, _, cabeceras = pedir("GET", url(servicio, "/health/ready"))
        verificar(f"{servicio:<24} /health/ready -> {codigo or 'sin conexión'} ({cabeceras.get('x-tiempo-respuesta-ms', '?')} ms)",
                  codigo == 200)
    if not listos:
        print("\nLos servicios no están respondiendo. Revise con:")
        print("   docker compose ps -a")
        print("   docker compose logs --tail 30 catalogo-service")
        return 1

    print("2) Seguridad del perímetro")
    verificar("sin X-API-Key -> 401", pedir("GET", url("api-publica", "/v1/catalogo/productos"))[0] == 401)
    codigo, catalogo, cabeceras = pedir("GET", url("api-publica", "/v1/catalogo/productos"), cabeceras=autorizado)
    verificar("con X-API-Key -> 200 y solo productos publicados", codigo == 200 and len(catalogo["items"]) > 0, catalogo)
    verificar("cabeceras de seguridad presentes", cabeceras.get("x-content-type-options") == "nosniff")

    print("3) Compra feliz")
    pedir("PUT", url("pagos-service", "/_simulador/pasarela/modo"), {"modo": "ok"})
    antes = disponible(sku)
    compra = {"cliente_id": "C-E2E-001", "sku": sku, "cantidad": 2, "medio_pago": "pse"}
    llave = {"Idempotency-Key": f"e2e-{uuid.uuid4().hex}"}
    codigo, cuerpo, cabeceras = pedir("POST", url("api-publica", "/v1/compras"), compra, {**autorizado, **llave})
    verificar("POST /v1/compras -> 201 CONFIRMADO", codigo == 201 and cuerpo.get("estado") == "CONFIRMADO", cuerpo)
    print(f"      tiempo total de la compra: {cabeceras.get('x-tiempo-respuesta-ms', '?')} ms")
    pedido_id = cuerpo.get("pedido_id", "")
    repetida = pedir("POST", url("api-publica", "/v1/compras"), compra, {**autorizado, **llave})[1]
    verificar("repetir con la misma Idempotency-Key devuelve el mismo pedido", repetida.get("pedido_id") == pedido_id)
    verificar("el stock bajó exactamente 2 unidades", disponible(sku) == antes - 2)
    verificar("GET /v1/compras/{id} -> CONFIRMADO",
              pedir("GET", url("api-publica", f"/v1/compras/{pedido_id}"), cabeceras=autorizado)[1].get("estado") == "CONFIRMADO")
    verificar("notificaciones-service recibió el evento (asíncrono)", esperar_hasta(
        lambda: len(pedir("GET", url("notificaciones-service", f"/v1/notificaciones?pedido_id={pedido_id}"))[1]) == 1))
    verificar("reportes-service contó la venta (CQRS)", esperar_hasta(
        lambda: pedir("GET", url("reportes-service", "/v1/reportes/resumen"))[1]["pedidos_total"] >= 1))

    print("4) Compra con pago rechazado (compensaciones de la saga)")
    pedir("PUT", url("pagos-service", "/_simulador/pasarela/modo"), {"modo": "rechaza"})
    antes = disponible(sku)
    codigo, cuerpo, _ = pedir("POST", url("api-publica", "/v1/compras"), {**compra, "cliente_id": "C-E2E-002"},
                              {**autorizado, "Idempotency-Key": f"e2e-{uuid.uuid4().hex}"})
    pedir("PUT", url("pagos-service", "/_simulador/pasarela/modo"), {"modo": "ok"})
    verificar("POST /v1/compras -> 409 FALLIDO", codigo == 409 and cuerpo.get("estado") == "FALLIDO", cuerpo)
    fallido = cuerpo.get("pedido_id") or ""
    verificar("el pedido quedó CANCELADO",
              pedir("GET", url("pedidos-service", f"/v1/pedidos/{fallido}"))[1].get("estado") == "CANCELADO")
    verificar("el stock se devolvió (reserva liberada)", disponible(sku) == antes)

    if argumentos.probar_limite:
        print("5) Límite de 40 peticiones por minuto")
        print("      esperando 60 s para empezar con la cuota limpia...")
        time.sleep(61)
        codigos = [pedir("GET", url("api-publica", "/v1/catalogo/productos"), cabeceras=autorizado)[0] for _ in range(41)]
        verificar("las primeras 40 pasan", set(codigos[:40]) == {200}, codigos)
        verificar("la 41 recibe 429", codigos[40] == 429, codigos[40])

    exitos = sum(resultados)
    print(f"\nResultado: {exitos}/{len(resultados)} verificaciones correctas")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
