"""Reto 3.1 - La matematica de la fragilidad de PiShop Cloud (P12).

Calcula la disponibilidad compuesta de la ruta critica del checkout,
la caida estimada en horas/ano y el efecto de tres mitigaciones.

Uso:  python retos/semana03/disponibilidad.py
Python 3.13, sin dependencias externas.
"""
from math import prod

HORAS_ANO = 365 * 24  # 8760 horas

# Disponibilidades medidas de la ruta critica (valores del reto 3.1, semana 3).
RUTA_CRITICA = {
    "api-publica": 0.9995,
    "checkout-bff": 0.9990,
    "catalogo-service": 0.9990,
    "inventario-service": 0.9985,
    "pedidos-service": 0.9990,
    "pagos-service": 0.9970,
    "pasarela externa": 0.9950,
}


def serie(disponibilidades):
    """Todos deben funcionar: se multiplican.  A = A1 x A2 x ... x An"""
    return prod(disponibilidades)


def paralelo(a, n):
    """Basta con que funcione uno de n: A = 1 - (1 - a)^n"""
    return 1 - (1 - a) ** n


def horas_caida(a):
    """Horas al ano en que el sistema NO esta disponible."""
    return (1 - a) * HORAS_ANO


# ---------------------------------------------------------------- mitigaciones

def m1_replicas_eje_x(ruta):
    """M1 - Eje X del cubo (clonacion horizontal): 2 replicas en paralelo de
    cada servicio propio. La pasarela externa no es nuestra: no se replica."""
    nueva = dict(ruta)                   # copia para no danar el original
    for nombre, a in ruta.items():       # recorre los 7 servicios uno por uno
        if nombre != "pasarela externa":  # != significa "diferente de"
            nueva[nombre] = paralelo(a, 2)  # 2 copias de ese servicio
    return nueva


def m2_segunda_pasarela(ruta):
    """M2 - Redundancia en paralelo del proveedor: si la pasarela principal
    falla, el adaptador ACL de pagos-service usa una segunda pasarela."""
    nueva = dict(ruta)                   # copia para no danar el original
    nueva["pasarela externa"] = paralelo(ruta["pasarela externa"], 2)  # 2 pasarelas
    return nueva


def m3_cobro_asincrono(ruta):
    """M3 - Paso a asincrono (saga + Outbox): el checkout confirma el pedido
    como PENDIENTE_PAGO y el cobro (pagos-service + pasarela) se hace despues
    a partir del evento PedidoCreado. Esos dos ya no estan en la ruta sincrona.
    Riesgo de negocio asumido: se acepta el pedido antes de saber si el pago
    pasa; si la pasarela rechaza, hay que cancelar el pedido, liberar el stock
    reservado (compensacion) y avisar al cliente."""
    nueva = dict(ruta)                   # copia para no danar el original
    del nueva["pagos-service"]           # sale de la ruta sincrona
    del nueva["pasarela externa"]        # sale de la ruta sincrona
    return nueva


MITIGACIONES = [
    ("M1 Replicas x2 (eje X del cubo)", m1_replicas_eje_x),
    ("M2 Segunda pasarela (redundancia)", m2_segunda_pasarela),
    ("M3 Cobro asincrono (saga + Outbox)", m3_cobro_asincrono),
]


def fila(nombre, ruta):
    a = serie(list(ruta.values()))
    return nombre, a, horas_caida(a)


def main():
    print("Ruta critica del checkout de PiShop Cloud (en serie):")
    for nombre, a in RUTA_CRITICA.items():
        print(f"  {nombre:<20} {a:.4f}")

    filas = [fila("Antes (sin mitigar)", RUTA_CRITICA)]
    for nombre, mitigar in MITIGACIONES:
        filas.append(fila(nombre, mitigar(RUTA_CRITICA)))

    # Las tres juntas: primero replicas y segunda pasarela, luego cobro asincrono.
    todas = m3_cobro_asincrono(m2_segunda_pasarela(m1_replicas_eje_x(RUTA_CRITICA)))
    filas.append(fila("M1 + M2 + M3 juntas", todas))

    antes = filas[0][2]
    print()
    print(f"{'Escenario':<38} {'Disponib.':>10} {'Caida h/ano':>12} {'Mejora':>8}")
    print("-" * 71)
    for nombre, a, horas in filas:
        mejora = f"-{antes - horas:.1f} h" if horas < antes else "-"
        print(f"{nombre:<38} {a * 100:>9.4f}% {horas:>12.2f} {mejora:>8}")


if __name__ == "__main__":
    main()
