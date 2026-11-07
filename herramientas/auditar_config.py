"""Auditor de configuracion embebida (P12, criterio 1 del reto 4.1).

Busca en el codigo de los servicios contrasenas, secretos, llaves de API o
direcciones IP escritas directamente. Todo eso debe entrar por variables de
entorno PISHOP_* (factor III de Twelve-Factor), nunca escrito en el codigo.

Uso:
    python herramientas/auditar_config.py              # revisa services/ y plantilla-servicio/
    python herramientas/auditar_config.py services/pagos-service   # revisa una sola carpeta

Resultado: 0 = limpio, 1 = hay hallazgos (asi el CI puede fallar).
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent   # carpeta principal del repositorio

# Lo que esta prohibido encontrar en el codigo (criterio 1 del reto 4.1).
REGLAS = {
    "password escrito": r"""password\s*=\s*["'][^"']+["']""",
    "secret escrito": r"""secret\s*=\s*["'][^"']+["']""",
    "api_key escrita": r"""api_key\s*=\s*["'][^"']+["']""",
    "direccion IP fija": r"""https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}""",
}

# settings.py es el unico lugar donde se permiten valores por defecto.
ARCHIVOS_PERMITIDOS = {"settings.py"}


def revisar_archivo(archivo):
    """Lee un archivo linea por linea y devuelve los problemas que encuentra."""
    hallazgos = []
    lineas = archivo.read_text(encoding="utf-8", errors="ignore").splitlines()
    for numero, linea in enumerate(lineas, start=1):
        for nombre_regla, patron in REGLAS.items():
            if re.search(patron, linea, re.IGNORECASE):
                hallazgos.append((archivo, numero, nombre_regla, linea.strip()))
    return hallazgos


def revisar_carpeta(carpeta):
    """Revisa todos los .py de la carpeta app/ de cada servicio."""
    hallazgos = []
    for archivo in sorted(carpeta.rglob("*.py")):   # todos los .py, incluso en subcarpetas
        if "app" not in archivo.parts:              # no esta en app/ (ej. pruebas): saltar
            continue
        if archivo.name in ARCHIVOS_PERMITIDOS:     # es settings.py: saltar
            continue
        hallazgos += revisar_archivo(archivo)       # revisar y sumar sus problemas
    return hallazgos


def main():
    # 1. Decidir que carpetas revisar.
    if len(sys.argv) > 1:                       # si escribiste una carpeta al correrlo
        carpetas = [Path(sys.argv[1])]          # revisa solo esa
    else:                                       # si no escribiste nada
        carpetas = [RAIZ / "services", RAIZ / "plantilla-servicio"]

    # 2. Revisar cada carpeta y juntar todos los problemas en una sola lista.
    hallazgos = []
    for carpeta in carpetas:
        print(f"Revisando {carpeta} ...")
        hallazgos += revisar_carpeta(carpeta)

    # 3. Informar el resultado.
    if not hallazgos:                           # la lista quedo vacia: todo limpio
        print("[ok] Sin configuracion embebida: criterio 1 del reto 4.1 cumplido.")
        sys.exit(0)                             # 0 = todo bien

    print(f"[FALLA] {len(hallazgos)} hallazgo(s):")
    for archivo, numero, nombre_regla, linea in hallazgos:
        print(f"  {archivo}:{numero}  ({nombre_regla})  {linea}")
    sys.exit(1)                                 # 1 = hay problemas


if __name__ == "__main__":
    main()
