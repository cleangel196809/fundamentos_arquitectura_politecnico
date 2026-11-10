#!/usr/bin/env python3
"""Validador de entregas del Parcial 1 (PiShop Cloud).

Uso:
    python herramientas/validar_entrega.py catalogo-service          # importa services/<nombre>/app/main.py
    python herramientas/validar_entrega.py catalogo-service --url http://localhost:8001   # contra un servicio ya levantado
    python herramientas/validar_entrega.py --todos

Comprueba (cada ítem es un criterio del enunciado):
  1. Que la ruta+método de CADA endpoint del contrato exista en /openapi.json
  2. Que las tres sondas /health/live, /health/ready y /health/startup respondan
  3. Que no haya configuración embebida en el código (criterio 1 del reto 4.1)
Código de salida 0 = todo cumple; 1 = hay incumplimientos.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONTRATO = json.loads((RAIZ / "contracts" / "endpoints.json").read_text(encoding="utf-8"))
PATRON_EMBEBIDO = re.compile(r"""(password\s*=\s*["'][^"']+["']|secret\s*=\s*["'][^"']+["']|api_key\s*=\s*["'][^"']+["']|https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})""", re.I)


def _cliente_local(nombre: str):
    from fastapi.testclient import TestClient
    carpeta = RAIZ / "services" / nombre
    if not (carpeta / "app" / "main.py").exists():
        raise SystemExit(f"[x] No existe {carpeta}/app/main.py")
    for m in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
        del sys.modules[m]
    sys.path.insert(0, str(carpeta))
    try:
        app = importlib.import_module("app.main").app
    finally:
        sys.path.pop(0)
    return TestClient(app), True


def _cliente_remoto(url: str):
    import httpx
    return httpx.Client(base_url=url, timeout=3.0), False


def auditar_config(nombre: str) -> list[str]:
    hallazgos = []
    src = RAIZ / "services" / nombre / "app"
    for py in src.rglob("*.py"):
        if py.name == "settings.py":
            continue   # los defaults válidos viven en settings.py
        for n, linea in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if PATRON_EMBEBIDO.search(linea):
                hallazgos.append(f"{py.relative_to(RAIZ)}:{n}: {linea.strip()[:80]}")
    return hallazgos


def validar(nombre: str, url: str | None) -> bool:
    spec = CONTRATO["servicios"][nombre]
    cliente, local = _cliente_remoto(url) if url else _cliente_local(nombre)
    ok = True
    print(f"\n== {nombre} (rol {spec['rol']}, puerto {spec['puerto']}) ==")
    paths = cliente.get("/openapi.json").json().get("paths", {})
    for metodo, ruta in spec["endpoints"]:
        existe = ruta in paths and metodo.lower() in paths[ruta]
        print(f"  [{'ok' if existe else 'FALTA'}] {metodo:6} {ruta}")
        ok &= existe
    def sondear():
        nonlocal ok
        for s in CONTRATO["sondas"]:
            try:
                code = cliente.get(s).status_code
            except Exception as e:  # noqa: BLE001
                code = f"error {e.__class__.__name__}"
            bien = code in (200, 503)   # 503 es válido en ready/startup mientras no esté listo
            print(f"  [{'ok' if bien else 'FALTA'}] sonda {s} -> {code}")
            ok &= bien
    if local:
        with cliente:   # dispara el lifespan
            sondear()
    else:
        sondear()
    if local:
        hall = auditar_config(nombre)
        print(f"  [{'ok' if not hall else 'FALTA'}] sin configuración embebida ({len(hall)} hallazgos)")
        for h in hall:
            print("      ", h)
        ok &= not hall
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("servicio", nargs="?")
    ap.add_argument("--url")
    ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()
    nombres = list(CONTRATO["servicios"]) if a.todos else [a.servicio]
    if not nombres or nombres == [None]:
        ap.error("indique un servicio o --todos")
    resultados = {}
    for n in nombres:
        if n not in CONTRATO["servicios"]:
            ap.error(f"servicio desconocido: {n}")
        carpeta = RAIZ / "services" / n
        if a.todos and not (carpeta / "app" / "main.py").exists():
            print(f"\n== {n} == (sin implementar aún)")
            resultados[n] = False
            continue
        resultados[n] = validar(n, a.url)
    print("\nResumen:", {k: ("OK" if v else "INCOMPLETO") for k, v in resultados.items()})
    sys.exit(0 if all(resultados.values()) else 1)


if __name__ == "__main__":
    main()
