"""Verificador de sondas (P12 - Danixa Herrera, punto 6).

Revisa en cada servicio los criterios 2 y 3 del reto 4.1 (semana 4):
  Criterio 2: el servicio ARRANCA aunque el config-service este apagado.
  Criterio 3: GET /health/ready responde 503 mientras no se haya aplicado
              una version de configuracion.

Como lo prueba: prende cada servicio en memoria (TestClient de FastAPI, igual que
validar_entrega.py) con el config-service apuntando a un puerto donde no hay
nadie, y en ambiente "qa". (En "dev" la plantilla permite ready=200 sin
configuracion para poder trabajar sin config-service; por eso se usa "qa".)

Uso:
    python herramientas/verificar_sondas.py                          # todos los de services/
    python herramientas/verificar_sondas.py services/pagos-service   # uno solo

Resultado: 0 = todos cumplen, 1 = alguno incumple (y sugiere el texto del issue).
"""
import json            # para pasar resultados entre procesos como texto
import os              # para preparar las variables de entorno
import subprocess      # para prender cada servicio en un proceso aparte
import sys             # para sys.argv y sys.exit
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent   # carpeta principal del repositorio

# Variables con las que se prende cada servicio durante la prueba (configuracion externalizada).
ENTORNO_PRUEBA = {
    "PISHOP_APP_ENV": "qa",                                        # ambiente estricto: ready debe exigir configuracion
    "PISHOP_CONFIG_SERVICE_URL": "http://localhost:9",             # puerto 9: no hay nadie = config-service APAGADO
    "PISHOP_CONSUL_URL": "http://localhost:9",                     # Consul tampoco esta
    "PISHOP_EVENT_BUS": "memory",                                  # bus en memoria (regla 5 del contrato)
    "PISHOP_DATABASE_URL": "sqlite+aiosqlite:///./verificar.db",   # base de prueba SQLite (regla 5)
}

# Mini programa que se ejecuta DENTRO de la carpeta de cada servicio, en un proceso aparte,
# para que un servicio no se mezcle con otro. Imprime una linea RESULTADO={...}.
PRUEBA = r"""
import json
resultado = {"arranco": False, "live": None, "startup": None, "ready": None, "error": None}
try:
    from fastapi.testclient import TestClient     # cliente de pruebas de FastAPI
    from app.main import app                      # importa el servicio
    with TestClient(app) as c:                    # "with" lo PRENDE (dispara el lifespan)
        resultado["arranco"] = True
        resultado["live"] = c.get("/health/live").status_code         # sonda live
        resultado["startup"] = c.get("/health/startup").status_code   # sonda startup
        resultado["ready"] = c.get("/health/ready").status_code       # sonda ready
except Exception as e:                            # si no prende, guardamos por que
    resultado["error"] = f"{type(e).__name__}: {e}"[:200]
print("RESULTADO=" + json.dumps(resultado))
"""


def probar_servicio(carpeta):
    """Prende un servicio con el config-service apagado y devuelve lo que observo."""
    entorno = {**os.environ, **ENTORNO_PRUEBA}                     # entorno normal + las variables de prueba
    proceso = subprocess.run([sys.executable, "-c", PRUEBA],       # corre el mini programa...
                             cwd=carpeta, env=entorno,             # ...dentro de la carpeta del servicio
                             capture_output=True, text=True, timeout=60)
    (carpeta / "verificar.db").unlink(missing_ok=True)             # borra la base de prueba
    for linea in proceso.stdout.splitlines():                      # busca la linea RESULTADO=...
        if linea.startswith("RESULTADO="):
            return json.loads(linea[len("RESULTADO="):])           # la convierte en diccionario
    ultima = (proceso.stderr.strip().splitlines() or ["sin salida"])[-1]   # si no hubo RESULTADO, el ultimo error
    return {"arranco": False, "live": None, "startup": None, "ready": None, "error": ultima[:200]}


def evaluar(r):
    """Aplica los criterios 2 y 3 y devuelve la lista de incumplimientos."""
    problemas = []                                                  # libreta (como "hallazgos")
    # Criterio 2: arranca sin config-service (live 200 y startup 200).
    if not r["arranco"]:
        problemas.append(f"Criterio 2: no arranca con el config-service apagado ({r['error']})")
    elif r["live"] != 200 or r["startup"] != 200:
        problemas.append(f"Criterio 2: arranca pero live={r['live']} startup={r['startup']} (se esperaba 200 y 200)")
    # Criterio 3: sin configuracion aplicada, ready debe ser 503.
    if r["arranco"] and r["ready"] != 503:
        problemas.append(f"Criterio 3: /health/ready respondio {r['ready']} sin configuracion aplicada (se esperaba 503)")
    return problemas


def texto_issue(nombre, problemas):
    """Arma el titulo y el cuerpo sugeridos para el issue de GitHub."""
    cuerpo = "\n".join(f"- {p}" for p in problemas)
    return (f"Titulo: [{nombre}] Incumple criterios del reto 4.1 (sondas)\n"
            f"Cuerpo:\nAl verificar con herramientas/verificar_sondas.py (P12):\n{cuerpo}\n\n"
            f"Como reproducir: python herramientas/verificar_sondas.py services/{nombre}")


def main():
    # 1. Decidir que servicios revisar.
    if len(sys.argv) > 1:                                           # si escribiste una carpeta...
        carpetas = [Path(sys.argv[1]).resolve()]                    # ...solo esa
    else:                                                           # si no, todos los que tengan app/main.py
        carpetas = sorted(p.parent.parent for p in (RAIZ / "services").glob("*/app/main.py"))
    if not carpetas:
        print("No hay servicios implementados en services/ todavia.")
        sys.exit(0)

    # 2. Probar cada uno e imprimir el resultado.
    incumplen = {}                                                  # servicio -> sus problemas
    for carpeta in carpetas:
        nombre = carpeta.name
        r = probar_servicio(carpeta)
        problemas = evaluar(r)
        marca = "ok" if not problemas else "FALLA"
        print(f"[{marca}] {nombre}: live={r['live']} startup={r['startup']} ready={r['ready']}")
        for p in problemas:
            print(f"        {p}")
        if problemas:
            incumplen[nombre] = problemas

    # 3. Informar: todo bien (0) o sugerir los issues (1).
    if not incumplen:
        print("\n[ok] Todos cumplen los criterios 2 y 3 del reto 4.1.")
        sys.exit(0)
    print(f"\n[FALLA] {len(incumplen)} servicio(s) incumplen. Texto sugerido para los issues:\n")
    for nombre, problemas in incumplen.items():
        print(texto_issue(nombre, problemas))
        print("-" * 60)
    sys.exit(1)


if __name__ == "__main__":     # boton de encendido
    main()
