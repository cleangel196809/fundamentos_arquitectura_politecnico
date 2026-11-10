#!/usr/bin/env python3
"""Genera datos FICTICIOS haciendo compras reales a través de la API pública.

Así se llenan de verdad las 6 bases: pedidos, pagos, inventario, y por los
eventos asíncronos también notificaciones y reportes.

Uso (con el sistema levantado):
    python scripts/generar_datos.py                  # 25 compras
    python scripts/generar_datos.py --compras 60     # más compras (tarda más)
    python scripts/generar_datos.py --con-rechazos   # algunas con pago rechazado

Respeta el límite de 40 peticiones por minuto de la API: hace una compra cada
1.6 segundos (unas 37 por minuto). Si se pasa, espera lo que indique
Retry-After y continúa.
"""
import argparse
import random
import sys
import time
import uuid

from _comun import esperar_sistema, leer_env, pedir, url

NOMBRES = ["Valentina", "Santiago", "Camila", "Andrés", "Daniela", "Juan Pablo", "Mariana", "Sebastián",
           "Luisa", "Felipe", "Laura", "Mateo", "Isabella", "Nicolás", "Sara", "Tomás", "Gabriela", "Samuel"]
APELLIDOS = ["Gómez", "Rodríguez", "Martínez", "López", "Hernández", "Díaz", "Moreno", "Rojas",
             "Vargas", "Castro", "Ortiz", "Ramírez", "Torres", "Quintero", "Suárez", "Cárdenas"]
CIUDADES = ["BOG", "MED", "CAL", "BAQ", "BUC", "PEI", "MAN", "IBA", "TUN", "PAS"]
MEDIOS = ["tarjeta", "pse", "nequi", "daviplata", "efecty"]


def cliente_ficticio(generador: random.Random) -> str:
    """Identificador legible y sin datos reales: C-BOG-ValentinaGomez-042."""
    sin_tildes = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")   # la API solo acepta letras sin tilde
    nombre = generador.choice(NOMBRES).replace(" ", "").translate(sin_tildes)
    apellido = generador.choice(APELLIDOS).translate(sin_tildes)
    return f"C-{generador.choice(CIUDADES)}-{nombre}{apellido}-{generador.randint(1, 999):03d}"


def main() -> int:
    opciones = argparse.ArgumentParser(description="Genera compras ficticias en PiShop Cloud")
    opciones.add_argument("--compras", type=int, default=25)
    opciones.add_argument("--con-rechazos", action="store_true", help="1 de cada 6 compras con pago rechazado")
    opciones.add_argument("--semilla", type=int, default=2026, help="misma semilla = mismos datos")
    argumentos = opciones.parse_args()

    entorno = leer_env()
    clave_api = entorno.get("PISHOP_API_KEY", "")
    if not clave_api:
        print("No encontré PISHOP_API_KEY en el .env")
        return 1
    print("Verificando que el sistema esté arriba...")
    if not esperar_sistema(60):
        print("El sistema no está listo. ¿Ejecutó 'docker compose up -d --build'?")
        return 1

    codigo, vitrina, _ = pedir("GET", url("checkout-bff", "/v1/vitrina"))
    productos = [p["sku"] for p in vitrina if p.get("disponible")] if codigo == 200 else []
    if not productos:
        print("No hay productos con stock en la vitrina.")
        return 1

    azar = random.Random(argumentos.semilla)
    clientes = [cliente_ficticio(azar) for _ in range(12)]
    totales = {"CONFIRMADO": 0, "FALLIDO": 0, "otros": 0}

    for numero in range(1, argumentos.compras + 1):
        rechazar = argumentos.con_rechazos and numero % 6 == 0
        if rechazar:
            pedir("PUT", url("pagos-service", "/_simulador/pasarela/modo"), {"modo": "rechaza"})
        compra = {"cliente_id": azar.choice(clientes), "sku": azar.choice(productos),
                  "cantidad": azar.choice([1, 1, 1, 2, 2, 3, 5]), "medio_pago": azar.choice(MEDIOS)}
        cabeceras = {"X-API-Key": clave_api, "Idempotency-Key": f"datos-{uuid.uuid4().hex}"}
        codigo, cuerpo, encabezados = pedir("POST", url("api-publica", "/v1/compras"), compra, cabeceras)
        if codigo == 429:
            pausa = int(encabezados.get("retry-after", "10"))
            print(f"  límite de 40/min alcanzado; espero {pausa} s")
            time.sleep(pausa)
            codigo, cuerpo, _ = pedir("POST", url("api-publica", "/v1/compras"), compra, cabeceras)
        if rechazar:
            pedir("PUT", url("pagos-service", "/_simulador/pasarela/modo"), {"modo": "ok"})

        estado = cuerpo.get("estado", "otros") if isinstance(cuerpo, dict) else "otros"
        totales[estado if estado in totales else "otros"] += 1
        detalle = cuerpo.get("detail", "") if isinstance(cuerpo, dict) else ""
        print(f"[{numero:03d}] {compra['cliente_id']:<34} {compra['cantidad']} x {compra['sku']:<16} -> {codigo} {estado} {detalle}")
        time.sleep(1.6)

    print("\nResumen de compras:", totales)
    time.sleep(3)   # consistencia eventual: dar tiempo a la outbox y a los consumidores
    print("Reporte (reportes-service):", pedir("GET", url("reportes-service", "/v1/reportes/resumen"))[1])
    notificaciones = pedir("GET", url("notificaciones-service", "/v1/notificaciones?limite=500"))[1]
    print("Notificaciones enviadas:", len(notificaciones) if isinstance(notificaciones, list) else notificaciones)
    return 0


if __name__ == "__main__":
    sys.exit(main())
