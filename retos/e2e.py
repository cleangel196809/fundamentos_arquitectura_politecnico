"""Prueba de extremo a extremo (e2e) de PiShop Cloud (P12 - Danixa Herrera).

Hace dos compras de verdad contra el sistema prendido y revisa el resultado:
  1. Compra feliz: pago aprobado -> pedido CONFIRMADO y el stock baja.
  2. Pago rechazado: pedido FALLIDO, el pedido queda CANCELADO y el stock
     vuelve a como estaba (compensaciones de la saga).
Ademas revisa la idempotencia: repetir la compra con la misma clave no crea otro pedido.

Uso:
    python retos/e2e.py              # contra el sistema real (docker compose up -d)
    python retos/e2e.py --dobles     # contra el doble de prueba (retos/dobles/)

Python 3.13, sin dependencias externas. Resultado: 0 = todo bien, 1 = algo fallo.
"""
import json              # para convertir entre texto JSON y diccionarios de Python
import os                # para leer variables de entorno (la API key)
import subprocess        # para ejecutar comandos de terminal (docker compose)
import sys               # para leer lo que se escribe al correrlo y para sys.exit
import urllib.error      # para reconocer errores HTTP (404, 409, 503...)
import urllib.request    # para hacer peticiones HTTP sin instalar nada
import uuid              # para generar claves unicas (Idempotency-Key)

# ------------------------------------------------------------------ configuracion

USAR_DOBLES = "--dobles" in sys.argv                          # True si escribiste --dobles al correrlo
API_KEY = os.environ.get("PISHOP_API_KEY", "cambiar-esto")    # la llave sale del entorno; si no hay, usa la de ejemplo
SKU = "E2E-CAFE-500G"                                         # codigo del producto de prueba

# Direcciones de los servicios (puertos fijados en docs/CONTRATOS.md).
if USAR_DOBLES:                                                         # con el doble...
    API = CATALOGO = INVENTARIO = PEDIDOS = "http://localhost:8000"    # ...uno solo atiende todo en el 8000
else:                                                                   # con el sistema real...
    API = "http://localhost:8000"          # api-publica (puerta de entrada)
    CATALOGO = "http://localhost:8001"     # catalogo-service
    INVENTARIO = "http://localhost:8002"   # inventario-service
    PEDIDOS = "http://localhost:8003"      # pedidos-service

ERRORES = []   # libreta donde se anotan las revisiones que fallan (como "hallazgos")


# ------------------------------------------------------------------ herramientas

def llamar(metodo, url, cuerpo=None, cabeceras=None):
    """Le habla a un servicio y devuelve (codigo, respuesta)."""
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None   # el cuerpo se manda como texto JSON
    peticion = urllib.request.Request(url, data=datos, method=metodo)    # arma la peticion (GET, POST, PUT...)
    peticion.add_header("Content-Type", "application/json")              # avisa que mandamos JSON
    for nombre, valor in (cabeceras or {}).items():                      # agrega cada cabecera extra
        peticion.add_header(nombre, valor)
    try:
        with urllib.request.urlopen(peticion, timeout=10) as r:          # envia; timeout explicito de 10 s (semana 3)
            return r.status, json.loads(r.read() or "null")              # devuelve el codigo (200, 201) y la respuesta
    except urllib.error.HTTPError as e:                                  # si respondio con error (4xx o 5xx)...
        return e.code, json.loads(e.read() or "null")                    # ...igual devuelve el codigo y la respuesta
    except urllib.error.URLError:                                        # si NADIE contesto...
        print(f"\n[FALLA] {url} no responde: prendiste el sistema (o el doble)?")
        sys.exit(1)                                                      # ...termina con error


def revisar(descripcion, condicion):
    """Imprime [ok] si la condicion se cumple; si no, [FALLA] y la anota."""
    print(f"  [{'ok' if condicion else 'FALLA'}] {descripcion}")
    if not condicion:                  # si la condicion es falsa...
        ERRORES.append(descripcion)    # ...se anota en la libreta


def cambiar_modo_pasarela(modo):
    """Pone la pasarela simulada en modo "ok" o "rechaza"."""
    if USAR_DOBLES:                                          # con el doble...
        llamar("POST", f"{API}/_simulador/modo/{modo}")      # ...basta con avisarle el modo
        return
    # Sistema real: se reinicia pagos-service con el modo nuevo (configuracion externalizada).
    entorno = {**os.environ, "PISHOP_PASARELA_MODO": modo}   # copia el entorno y cambia solo el modo
    subprocess.run(["docker", "compose", "up", "-d", "--wait", "pagos-service"],   # reinicia pagos y espera a que este sano
                   env=entorno, check=True)


def ver_stock():
    """Pregunta al inventario cuanto stock hay del producto de prueba."""
    return llamar("GET", f"{INVENTARIO}/v1/stock/{SKU}")[1]      # [1] = solo la respuesta, sin el codigo


def comprar(clave=None):
    """Hace una compra de 2 unidades por la api-publica."""
    cabeceras = {"X-API-Key": API_KEY,                          # la llave que exige la api-publica
                 "Idempotency-Key": clave or str(uuid.uuid4())} # clave unica; si se repite, no se repite la compra
    cuerpo = {"cliente_id": "C-E2E", "sku": SKU, "cantidad": 2, "medio_pago": "tarjeta"}   # datos del contrato
    return llamar("POST", f"{API}/v1/compras", cuerpo, cabeceras)


# ------------------------------------------------------------------ las pruebas

def preparar():
    """Deja un producto publicado con 10 unidades."""
    print("Preparando datos: producto publicado con 10 unidades")
    producto = {"sku": SKU, "nombre": "Cafe e2e 500 g", "precio_cop": 18000, "categoria": "cafe"}
    codigo, _ = llamar("POST", f"{CATALOGO}/v1/productos", producto)         # crea el producto
    revisar("producto creado (o ya existia)", codigo in (201, 409))          # 201 = creado; 409 = ya existia
    llamar("PATCH", f"{CATALOGO}/v1/productos/{SKU}/publicar")               # lo publica
    codigo, _ = llamar("PUT", f"{INVENTARIO}/v1/stock/{SKU}", {"cantidad": 10})   # le pone 10 unidades
    revisar("stock inicial puesto en 10", codigo == 200)


def compra_feliz():
    """Compra con pago aprobado: todo debe salir bien."""
    print("\n1) Compra feliz (pasarela en modo ok)")
    cambiar_modo_pasarela("ok")                     # la pasarela aprueba
    antes = ver_stock()                             # foto del stock ANTES
    clave = str(uuid.uuid4())                       # clave unica para esta compra
    codigo, r = comprar(clave)                      # compra; r = respuesta del checkout
    revisar(f"la compra responde 200/201 (respondio {codigo})", codigo in (200, 201))
    revisar(f"estado CONFIRMADO (llego {r.get('estado')})", r.get("estado") == "CONFIRMADO")
    revisar("el stock cambio (se reservaron 2 unidades)", ver_stock() != antes)   # el stock ya no es el de antes
    pedido = llamar("GET", f"{PEDIDOS}/v1/pedidos/{r.get('pedido_id')}")[1] or {} # busca el pedido creado
    revisar(f"el pedido existe y no esta cancelado (estado {pedido.get('estado')})",
            pedido.get("estado") not in (None, "CANCELADO"))
    # Idempotencia (semana 3): misma clave -> misma respuesta, sin otro pedido ni otra reserva.
    stock_despues = ver_stock()                     # foto del stock despues de la compra
    _, repetida = comprar(clave)                    # repite la compra con LA MISMA clave
    revisar("repetir con la misma Idempotency-Key devuelve el mismo pedido",
            repetida.get("pedido_id") == r.get("pedido_id"))
    revisar("repetir no vuelve a descontar stock", ver_stock() == stock_despues)


def compra_rechazada():
    """Compra con pago rechazado: la saga debe deshacer todo (compensaciones)."""
    print("\n2) Compra con pago rechazado (pasarela en modo rechaza)")
    cambiar_modo_pasarela("rechaza")                # la pasarela rechaza
    antes = ver_stock()                             # foto del stock ANTES
    codigo, r = comprar()                           # compra con clave nueva
    revisar(f"estado FALLIDO (llego {r.get('estado')})", r.get("estado") == "FALLIDO")
    print("     pasos:", [f"{p['paso']}={p['resultado']}" for p in r.get("pasos", [])])   # muestra los pasos de la saga
    revisar("compensacion: el stock volvio a como estaba", ver_stock() == antes)       # se libero la reserva
    pedido = llamar("GET", f"{PEDIDOS}/v1/pedidos/{r.get('pedido_id')}")[1] or {}
    revisar(f"compensacion: el pedido quedo CANCELADO (estado {pedido.get('estado')})",
            pedido.get("estado") == "CANCELADO")                                        # se cancelo el pedido
    cambiar_modo_pasarela("ok")                     # deja la pasarela como estaba


def main():
    print(f"Prueba e2e de PiShop Cloud contra {'el DOBLE' if USAR_DOBLES else 'el sistema real'}\n")
    preparar()                                      # 0. datos de prueba
    compra_feliz()                                  # 1. compra que sale bien
    compra_rechazada()                              # 2. compra que se deshace
    if ERRORES:                                     # si la libreta tiene algo...
        print(f"\n[FALLA] {len(ERRORES)} revision(es) fallaron")
        sys.exit(1)                                 # ...termina con 1 (rojo)
    print("\n[ok] Compra feliz y compensaciones verificadas")
    sys.exit(0)                                     # todo bien: 0 (verde)


if __name__ == "__main__":     # boton de encendido: al correr el archivo, ejecuta main()
    main()
