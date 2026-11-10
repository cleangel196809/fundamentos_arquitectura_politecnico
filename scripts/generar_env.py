#!/usr/bin/env python3
"""Crea el archivo .env con contraseñas ALEATORIAS y fuertes (rol de ciberseguridad).

Uso (desde la raíz del proyecto):
    python scripts/generar_env.py            # crea .env si no existe
    python scripts/generar_env.py --forzar   # lo reemplaza (¡luego: docker compose down -v!)

Por qué: copiar .env.example deja contraseñas de ejemplo ("cambiar-esto") que
cualquiera conoce. Este script usa el módulo `secrets` de Python, pensado para
generar claves criptográficamente seguras. Solo usa la biblioteca estándar.
"""
import argparse
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def clave_nueva(largo_bytes: int = 24) -> str:
    # token_urlsafe solo usa letras, números, "-" y "_": no rompe ni el .env ni las URL.
    return secrets.token_urlsafe(largo_bytes)


def main() -> int:
    opciones = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    opciones.add_argument("--forzar", action="store_true", help="sobrescribe un .env existente")
    argumentos = opciones.parse_args()

    plantilla = RAIZ / ".env.example"
    destino = RAIZ / ".env"
    if destino.exists() and not argumentos.forzar:
        print(f"Ya existe {destino.name}; no se toca. Use --forzar para reemplazarlo.")
        return 1

    lineas_nuevas = []
    for linea in plantilla.read_text(encoding="utf-8").splitlines():
        nombre, signo, valor = linea.partition("=")
        if signo and not linea.lstrip().startswith("#") and valor.startswith("cambiar-esto"):
            linea = f"{nombre}={clave_nueva(32 if 'API_KEY' in nombre else 24)}"
        lineas_nuevas.append(linea)
    destino.write_text("\n".join(lineas_nuevas) + "\n", encoding="utf-8")

    print(f"Listo: {destino} creado con claves aleatorias.")
    print("La clave de la API pública (cabecera X-API-Key) está en la línea PISHOP_API_KEY.")
    if argumentos.forzar:
        print("OJO: si PostgreSQL ya se había creado, ejecute 'docker compose down -v' para aplicar las nuevas claves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
