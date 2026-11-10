#!/usr/bin/env python3
"""Auditoría de ciberseguridad de PiShop Cloud (fitness function).

Uso:
    python herramientas/auditar_config.py                       # código + compose seguro
    python herramientas/auditar_config.py --servicio api-publica
    python herramientas/auditar_config.py --compose docker-compose.yml

Reglas (cada una corresponde a un ítem del checklist del rol de ciberseguridad):
  R1  Cero cadenas sensibles: sin password|secret|api_key|token ni IP/credenciales
      escritas a mano en services/*/app (Twelve-Factor, factor III).
  R2  Los campos sensibles de Settings deben ser SecretStr.
  R3  Todo cliente httpx (AsyncClient/Client/atajos) declara timeout explícito.
  R4  Dockerfile y docker-compose sin secretos literales (solo ${VARIABLE}).
  R5  Puertos aislados: el compose efectivo solo publica api-publica (8000) o traefik.

Código de salida: 0 = sin hallazgos; 1 = hay incumplimientos.
El informe NUNCA imprime el valor de un secreto: los literales se enmascaran.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PALABRAS = r"(?:password|passwd|secret|api_?key|token)"

# R1 ---------------------------------------------------------------------------
# nombre sensible (con anotación de tipo opcional) asignado/comparado con un literal
SECRETO_LITERAL = re.compile(
    rf"""\b\w*{PALABRAS}\w*["']?(?:\s*:\s*[\w.\[\]| ]+?)?\s*(?:==|!=|=|:)\s*["'][^"']{{3,}}["']""", re.I)
IP_LITERAL = re.compile(r"""(?:\b[a-z][a-z0-9+.-]*://|["'])\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?""", re.I)
CREDENCIALES_EN_URL = re.compile(r"""\b[a-z][a-z0-9+.-]*://[^/\s:@"']+:[^/\s@"']+@""", re.I)

# R4 ---------------------------------------------------------------------------
ENV_DOCKERFILE = re.compile(rf"""^\s*(?:ENV|ARG)\s+\w*{PALABRAS}\w*[=\s]+(?!\$)\S+""", re.I)
INTERPOLACION = re.compile(r"\$\{[^}]*\}")   # ${VAR} o ${VAR:?mensaje}: se reemplaza por \x00 antes de evaluar
SECRETO_COMPOSE = re.compile(rf"""\b\w*{PALABRAS}\w*\s*[:=]\s*(?!["']?\x00)[^\s,}}\]]+""", re.I)

# R3 ---------------------------------------------------------------------------
ATAJOS_HTTPX = {"get", "post", "put", "patch", "delete", "head", "options", "request", "stream"}
CLIENTES_HTTPX = {"AsyncClient", "Client"}

# R5 ---------------------------------------------------------------------------
PUBLICABLES = {"api-publica": {8000}, "traefik": {80, 443}}
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@dataclass
class Hallazgo:
    regla: str
    lugar: str
    detalle: str


def _enmascarar(linea: str) -> str:
    """Oculta el contenido de los literales para no filtrar el secreto en el informe."""
    return re.sub(r"""(["'])[^"']*\1""", '"***"', linea.strip())[:90]


def _rel(ruta: Path, raiz: Path) -> str:
    try:
        return str(ruta.relative_to(raiz))
    except ValueError:
        return str(ruta)


# ----------------------------------------------------------------------------- R1
def auditar_cadenas(py: Path, raiz: Path) -> list[Hallazgo]:
    hallazgos = []
    for n, linea in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
        motivos = []
        if py.name != "settings.py" and SECRETO_LITERAL.search(linea):   # los defaults viven en settings.py
            motivos.append("secreto escrito en el código")
        if IP_LITERAL.search(linea):
            motivos.append("dirección IP escrita a mano")
        if CREDENCIALES_EN_URL.search(linea):
            motivos.append("credenciales dentro de una URL")
        for m in motivos:
            hallazgos.append(Hallazgo("R1", f"{_rel(py, raiz)}:{n}", f"{m}: {_enmascarar(linea)}"))
    return hallazgos


# --------------------------------------------------------------------- R2 y R3 (AST)
def auditar_ast(py: Path, raiz: Path) -> list[Hallazgo]:
    try:
        arbol = ast.parse(py.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [Hallazgo("R3", f"{_rel(py, raiz)}:{e.lineno}", "no se pudo analizar el archivo (error de sintaxis)")]
    hallazgos = []
    for nodo in ast.walk(arbol):
        # R2: en clases *Settings, nombres sensibles => SecretStr
        if isinstance(nodo, ast.ClassDef) and any(ast.unparse(b).endswith("BaseSettings") for b in nodo.bases):
            for it in nodo.body:
                if (isinstance(it, ast.AnnAssign) and isinstance(it.target, ast.Name)
                        and re.search(PALABRAS, it.target.id, re.I) and "SecretStr" not in ast.unparse(it.annotation)):
                    hallazgos.append(Hallazgo("R2", f"{_rel(py, raiz)}:{it.lineno}",
                                              f"el campo sensible '{it.target.id}' debe ser SecretStr"))
        # R3: clientes httpx con timeout explícito (y distinto de None)
        if isinstance(nodo, ast.Call):
            f = nodo.func
            nombre = None
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "httpx":
                nombre = f.attr if f.attr in CLIENTES_HTTPX | ATAJOS_HTTPX else None
            elif isinstance(f, ast.Name) and f.id == "AsyncClient":
                nombre = f.id
            if nombre is None or any(k.arg is None for k in nodo.keywords):   # **opciones: no se puede saber
                continue
            timeout = next((k.value for k in nodo.keywords if k.arg == "timeout"), None)
            if timeout is None or (isinstance(timeout, ast.Constant) and timeout.value is None):
                hallazgos.append(Hallazgo("R3", f"{_rel(py, raiz)}:{nodo.lineno}",
                                          f"httpx.{nombre}(...) sin timeout explícito (use httpx.Timeout(2.0))"))
    return hallazgos


# ----------------------------------------------------------------------------- R4
def auditar_texto_infra(archivo: Path, raiz: Path, es_compose: bool) -> list[Hallazgo]:
    patron = SECRETO_COMPOSE if es_compose else ENV_DOCKERFILE
    hallazgos = []
    for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
        if linea.lstrip().startswith("#"):
            continue
        evaluada = INTERPOLACION.sub("\x00", linea) if es_compose else linea
        if patron.search(evaluada):
            hallazgos.append(Hallazgo("R4", f"{_rel(archivo, raiz)}:{n}",
                                      f"secreto literal (use ${{VARIABLE}} desde .env): {_enmascarar(linea)}"))
    return hallazgos


# ----------------------------------------------------------------------------- R5
def _puerto(entrada: str) -> tuple[str | None, int] | None:
    partes = entrada.strip().strip("\"',").split("/")[0].split(":")
    try:
        if len(partes) in (1, 2):
            return None, int(partes[0].split("-")[0])
        if len(partes) == 3:
            return partes[0], int(partes[1].split("-")[0])
    except ValueError:
        pass
    return None


def leer_puertos(texto: str) -> dict[str, tuple[bool, list[tuple[str | None, int]]]]:
    """{servicio: (reemplaza, [(ip_enlace, puerto_host)])}. Entiende '!reset' y '!override'."""
    res: dict = {}
    servicio, en_services, bloque = None, False, False
    for cruda in texto.splitlines():
        linea = re.sub(r"\s+#.*$", "", cruda).rstrip()
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        sangria, txt = len(linea) - len(linea.lstrip()), linea.strip()
        if sangria == 0:
            en_services, servicio, bloque = txt == "services:", None, False
        elif not en_services:
            continue
        elif sangria == 2:
            m = re.fullmatch(r"([\w.-]+):", txt)
            if m:
                servicio, bloque = m.group(1), False
                res.setdefault(servicio, (False, []))
        elif servicio is None:
            continue
        elif sangria == 4:
            bloque = False
            m = re.match(r"ports:\s*(.*)$", txt)
            if m:
                resto = m.group(1)
                if resto.startswith(("!reset", "!override")):
                    res[servicio] = (True, res[servicio][1])
                    resto = re.sub(r"^!(?:reset|override)\s*", "", resto)
                if resto.startswith("["):
                    res[servicio][1].extend(p for p in map(_puerto, resto.strip("[]").split(",")) if p)
                elif resto == "":
                    bloque = True
        elif bloque:
            m = re.match(r"-\s*(.+)$", txt)
            p = _puerto(m.group(1)) if m else None
            pub = re.search(r"""published:\s*["']?(\d+)""", txt)
            if p:
                res[servicio][1].append(p)
            elif pub:
                res[servicio][1].append((None, int(pub.group(1))))
    return res


def auditar_puertos(composes: list[Path], raiz: Path) -> list[Hallazgo]:
    efectivos: dict[str, list[tuple[str | None, int]]] = {}
    for c in composes:   # el orden importa: el override se aplica sobre la base
        for srv, (reemplaza, lista) in leer_puertos(c.read_text(encoding="utf-8")).items():
            efectivos[srv] = list(lista) if reemplaza else efectivos.get(srv, []) + lista
    hallazgos = []
    for srv, lista in sorted(efectivos.items()):
        for ip, puerto in lista:
            if ip in LOOPBACK or puerto in PUBLICABLES.get(srv, set()):
                continue
            hallazgos.append(Hallazgo("R5", ", ".join(_rel(c, raiz) for c in composes),
                                      f"{srv} publica el puerto {puerto} hacia el exterior (debe quedar en la red interna)"))
    return hallazgos


# ----------------------------------------------------------------------------- main
TITULOS = {
    "R1": "R1  Cero cadenas sensibles en el código",
    "R2": "R2  Campos sensibles de Settings como SecretStr",
    "R3": "R3  Timeouts explícitos en clientes httpx",
    "R4": "R4  Sin secretos literales en Dockerfile / compose",
    "R5": "R5  Puertos internos aislados en docker-compose",
}


def auditar(raiz: Path, servicio: str | None = None, compose: list[str] | None = None) -> list[Hallazgo]:
    carpetas = [raiz / "services" / servicio] if servicio else sorted((raiz / "services").glob("*/"))
    hallazgos: list[Hallazgo] = []
    for carpeta in carpetas:
        for py in sorted((carpeta / "app").rglob("*.py")):
            hallazgos += auditar_cadenas(py, raiz) + auditar_ast(py, raiz)
        for df in sorted(carpeta.glob("Dockerfile*")):
            hallazgos += auditar_texto_infra(df, raiz, es_compose=False)
    if compose:
        archivos = [raiz / c for c in compose]
    else:
        archivos = [raiz / "docker-compose.yml"]
        if (raiz / "docker-compose.seguro.yml").exists():
            archivos.append(raiz / "docker-compose.seguro.yml")
    archivos = [a for a in archivos if a.exists()]
    for a in archivos:
        hallazgos += auditar_texto_infra(a, raiz, es_compose=True)
    if archivos:
        hallazgos += auditar_puertos(archivos, raiz)
    return hallazgos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Auditoría de ciberseguridad de PiShop Cloud")
    ap.add_argument("--servicio", help="limita la auditoría de código a services/<nombre>")
    ap.add_argument("--compose", action="append", help="archivo compose (repetible; el último se aplica encima)")
    ap.add_argument("--raiz", type=Path, default=RAIZ, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    hallazgos = auditar(a.raiz, a.servicio, a.compose)
    for regla, titulo in TITULOS.items():
        propios = [h for h in hallazgos if h.regla == regla]
        print(f"[{'ok' if not propios else 'FALTA'}] {titulo} ({len(propios)} hallazgos)")
        for h in propios:
            print(f"        {h.lugar}: {h.detalle}")
    print("\nResultado:", "SIN HALLAZGOS" if not hallazgos else f"{len(hallazgos)} HALLAZGO(S)")
    return 0 if not hallazgos else 1


if __name__ == "__main__":
    sys.exit(main())
