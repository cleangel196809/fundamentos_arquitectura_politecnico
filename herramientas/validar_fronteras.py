#!/usr/bin/env python3
"""
herramientas/validar_fronteras.py
=================================
Fitness Function Arquitectónica — Gobernanza de Persistencia (Docs-as-Code)
Rol: P11 — Arquitecto de Software
Proyecto: PiShop Cloud (fundamentos_arquitectura_politecnico)

Propósito:
    Comprueba de forma automatizada que se cumpla estrictamente el patrón
    arquitectónico "Database-per-Service" (persistencia aislada por servicio).

Criterio de Evaluación:
    - Falla con código de salida 1 (sys.exit(1)) si dos o más servicios
      comparten la misma base de datos (mismo nombre de BD o archivo de persistencia).
    - Termina con código de salida 0 (sys.exit(0)) si todos los servicios con
      persistencia mantienen almacenes de datos exclusivos y desacoplados.
"""

import sys
import os
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Tuple, Optional

# Asegurar codificación UTF-8 en terminales Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def parse_database_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Parsea una cadena de conexión y retorna (dbname, host, port)."""
    try:
        cleaned_url = re.sub(r"\$\{[^:]+:-([^}]+)\}", r"\1", url)
        cleaned_url = re.sub(r"\$[A-Za-z0-9_]+", "", cleaned_url)
        
        # SQLite
        if "sqlite" in cleaned_url:
            match_sqlite = re.search(r"sqlite.*?///(?:\./)?(.*)", cleaned_url)
            if match_sqlite:
                return match_sqlite.group(1), "localhost", 0

        parsed = urlparse(cleaned_url)
        dbname = parsed.path.lstrip("/") if parsed.path else None
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        return dbname, host, port
    except Exception:
        return None, None, None


def analizar_desde_initdb(root_dir: Path) -> Dict[str, str]:
    """Lee infra/initdb/01-bases.sql para mapear las bases oficiales del proyecto."""
    sql_file = root_dir / "infra" / "initdb" / "01-bases.sql"
    if not sql_file.exists():
        return {}

    db_map = {}
    lines = sql_file.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        match = re.search(r"CREATE\s+DATABASE\s+([a-zA-Z0-9_]+);", line, re.I)
        if match:
            dbname = match.group(1)
            # Deducir el servicio a partir del prefijo pg_ (ej. pg_pagos -> pagos-service)
            srv_candidate = dbname.replace("pg_", "") + "-service"
            db_map[srv_candidate] = f"postgres:5432/{dbname}"

    return db_map


def analizar_desde_services(root_dir: Path) -> Dict[str, str]:
    """Inspecciona los archivos settings.py de cada servicio en services/*/app/settings.py."""
    services_dir = root_dir / "services"
    if not services_dir.exists():
        return {}

    srv_map = {}
    for srv_path in services_dir.iterdir():
        if not srv_path.is_dir():
            continue
        settings_file = srv_path / "app" / "settings.py"
        if settings_file.exists():
            content = settings_file.read_text(encoding="utf-8", errors="replace")
            # Buscar database_url
            match = re.search(r'database_url:\s*str\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                db_url = match.group(1)
                dbname, host, port = parse_database_url(db_url)
                if dbname:
                    srv_map[srv_path.name] = f"{host}:{port}/{dbname}" if port else f"file:{dbname}"

    return srv_map


def extract_services_from_compose(compose_path: Path) -> Dict[str, Dict]:
    """Parsea docker-compose.yml extrayendo servicios y variables de entorno."""
    if not compose_path.exists():
        return {}

    with open(compose_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    services: Dict[str, Dict] = {}
    current_service = None
    in_services_block = False
    in_environment_block = False
    service_indent = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if indent == 0:
            if stripped == "services:":
                in_services_block = True
                current_service = None
                in_environment_block = False
                continue
            else:
                in_services_block = False
                current_service = None
                in_environment_block = False
                continue

        if in_services_block:
            if service_indent is None and stripped.endswith(":"):
                service_indent = indent

            if indent == service_indent and stripped.endswith(":"):
                current_service = stripped[:-1].strip()
                services[current_service] = {"env": {}}
                in_environment_block = False
                continue

            if current_service and indent > service_indent:
                if stripped == "environment:" or stripped.startswith("environment:"):
                    in_environment_block = True
                    # Inline dict: environment: {KEY: VAL, ...}
                    inline_match = re.search(r"environment:\s*\{(.*)\}", stripped)
                    if inline_match:
                        pairs = inline_match.group(1).split(",")
                        for p in pairs:
                            if ":" in p:
                                k, v = p.split(":", 1)
                                services[current_service]["env"][k.strip()] = v.strip().strip("'\"")
                        in_environment_block = False
                    continue

                if in_environment_block and stripped.endswith(":") and not stripped.startswith("-"):
                    in_environment_block = False
                    continue

                if in_environment_block:
                    match_env_list = re.match(r"^\s+-\s*([A-Za-z0-9_]+)=(.*)$", line)
                    if match_env_list:
                        k = match_env_list.group(1).strip()
                        v = match_env_list.group(2).strip().strip("'\"")
                        services[current_service]["env"][k] = v
                        continue

                    match_env_dict = re.match(r"^\s+([A-Za-z0-9_]+):\s*(.*)$", line)
                    if match_env_dict:
                        k = match_env_dict.group(1).strip()
                        v = match_env_dict.group(2).strip().strip("'\"")
                        services[current_service]["env"][k] = v
                        continue

    return services


def analizar_persistencia(services: Dict[str, Dict], root_dir: Path) -> Dict[str, Dict]:
    """Identifica las bases de datos de los servicios unificando compose, settings e initdb."""
    service_db_map = {}

    # 1. Variables en Docker Compose
    for service_name, data in services.items():
        if service_name.endswith("-db") or service_name in ["postgres", "redis", "consul", "rabbitmq"]:
            continue

        env = data.get("env", {})
        for var_name in ["DATABASE_URL", "DB_URL", "PISHOP_DATABASE_URL", "SPRING_DATASOURCE_URL"]:
            if var_name in env:
                parsed_name, parsed_host, parsed_port = parse_database_url(env[var_name])
                if parsed_name:
                    db_key = f"{parsed_host}:{parsed_port}/{parsed_name}" if parsed_port else f"file:{parsed_name}"
                    service_db_map[service_name] = {
                        "db_key": db_key,
                        "origen": "docker-compose.yml"
                    }
                    break

        if service_name not in service_db_map:
            cand_name = env.get("POSTGRES_DB") or env.get("DB_NAME")
            if cand_name:
                cand_host = env.get("POSTGRES_HOST") or env.get("DB_HOST") or "postgres"
                cand_port = env.get("POSTGRES_PORT") or 5432
                service_db_map[service_name] = {
                    "db_key": f"{cand_host}:{cand_port}/{cand_name}",
                    "origen": "docker-compose.yml (env)"
                }

    # 2. Análisis desde settings.py si no estaban en compose
    from_settings = analizar_desde_services(root_dir)
    for srv, db_key in from_settings.items():
        if srv not in service_db_map:
            service_db_map[srv] = {
                "db_key": db_key,
                "origen": "settings.py"
            }

    # 3. Análisis desde infra/initdb/01-bases.sql para los servicios definidos
    from_initdb = analizar_desde_initdb(root_dir)
    for srv, db_key in from_initdb.items():
        if srv not in service_db_map:
            service_db_map[srv] = {
                "db_key": db_key,
                "origen": "01-bases.sql"
            }

    return service_db_map


def verificar_fronteras_arquitectonicas(compose_file: Path, verbose: bool = False) -> int:
    """Función de aptitud: valida que ningún par de servicios comparta base de datos."""
    root_dir = compose_file.parent

    print("\n" + "=" * 80)
    print("  FITNESS FUNCTION: VALIDACION DE FRONTERAS DE PERSISTENCIA ARQUITECTONICA")
    print("  Rol Evaluador: P11 - Arquitecto de Software (Docs-as-Code)")
    print(f"  Archivo Analizado: {compose_file.name}")
    print("=" * 80)

    services = extract_services_from_compose(compose_file)
    service_db_map = analizar_persistencia(services, root_dir)

    if verbose:
        print(f"\n[DIAGNOSTICO] Microservicios con persistencia detectada ({len(service_db_map)}):")
        for srv, info in sorted(service_db_map.items()):
            print(f"  * {srv:<24} -> Conexion: {info['db_key']:<30} [Fuente: {info['origen']}]")

    db_to_services: Dict[str, List[str]] = {}
    for service_name, info in service_db_map.items():
        key = info["db_key"]
        db_to_services.setdefault(key, []).append(service_name)

    violaciones = {db: srvs for db, srvs in db_to_services.items() if len(srvs) > 1}

    if violaciones:
        print("\n" + "!" * 80)
        print("  [FALLO DE COMPUERTA ARQUITECTONICA]: VIOLACION DEL PATRON DATABASE-PER-SERVICE")
        print("!" * 80)
        print("\nSe han detectado servicios que COMPARTEN indebidamente la misma base de datos:\n")
        
        for db, srvs in violaciones.items():
            print(f"  [VIOLACION] Base de Datos Compartida: [{db}]")
            print(f"              Servicios Infractores ({len(srvs)}): {', '.join(srvs)}")
            print("              Impacto Arquitectonico: Acoplamiento de persistencia, riesgo de bloqueos")
            print("              transaccionales y violacion de las fronteras de Bounded Context (DDD).\n")

        print("-" * 80)
        print("  RECOMENDACION ARQUITECTONICA (P11):")
        print("  Separe la base de datos de cada servicio infractor. Cada microservicio debe")
        print("  declarar su propio esquema e instancia de persistencia independiente.")
        print("-" * 80)
        print("\n>>> RESULTADO: FALLO (Codigo de salida: 1)\n")
        return 1

    print("\n" + "*" * 80)
    print("  [EXITO]: TODAS LAS FRONTERAS DE PERSISTENCIA ESTAN CORRECTAMENTE AISLADAS")
    print("*" * 80)
    print(f"\nTotal de servicios evaluados con persistencia aislada: {len(service_db_map)}")
    for srv, info in sorted(service_db_map.items()):
        print(f"  [OK] {srv:<24} -> {info['db_key']:<30} (Persistencia Exclusiva)")

    print("\nRegla Cumplida: 'Database-per-Service' (ISO/IEC 25010 - Modularidad y Aislamiento).")
    print(">>> RESULTADO: APROBADO (Codigo de salida: 0)\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Fitness Function para validar aislamiento de bases de datos entre microservicios."
    )
    parser.add_argument(
        "--compose",
        type=str,
        default="docker-compose.yml",
        help="Ruta al archivo docker-compose.yml a validar (por defecto: docker-compose.yml)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Muestra informacion detallada de diagnostico"
    )

    args = parser.parse_args()
    compose_path = Path(args.compose)

    if not compose_path.is_absolute():
        compose_path = Path.cwd() / compose_path

    exit_code = verificar_fronteras_arquitectonicas(compose_path, verbose=args.verbose)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
