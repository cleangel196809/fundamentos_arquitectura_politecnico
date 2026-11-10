#!/usr/bin/env python3
"""
herramientas/test_validar_fronteras.py
======================================
Suite de pruebas automatizadas para la Fitness Function (validar_fronteras.py)
Verifica que:
1. El archivo docker-compose.yml oficial retorne exit code 0 (Aprobado).
2. El archivo de prueba docker-compose.invalido.yml retorne exit code 1 (Fallo por BD compartida).
"""

import sys
import subprocess
from pathlib import Path

# Asegurar codificación UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_test():
    python_exe = sys.executable
    base_dir = Path(__file__).resolve().parent.parent
    script_path = base_dir / "herramientas" / "validar_fronteras.py"
    compose_valido = base_dir / "docker-compose.yml"
    compose_invalido = base_dir / "herramientas" / "test_fixtures" / "docker-compose.invalido.yml"

    print("=" * 70)
    print("SUITE DE PRUEBAS AUTOMATIZADAS — FITNESS FUNCTION ARQUITECTÓNICA")
    print("=" * 70)

    # Caso 1: Archivo Oficial Válido
    print("\n[TEST 1] Evaluando arquitectura oficial (docker-compose.yml)...")
    res_valido = subprocess.run(
        [python_exe, str(script_path), "--compose", str(compose_valido)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if res_valido.returncode == 0:
        print("  ✔ TEST 1 PASÓ: El validador retornó exit code 0 para arquitectura aislada.")
    else:
        print(f"  ❌ TEST 1 FALLÓ: Esperado 0, recibido {res_valido.returncode}")
        print(res_valido.stdout)
        sys.exit(1)

    # Caso 2: Archivo con Violación Arquitectónica (Base de Datos Compartida)
    print("\n[TEST 2] Evaluando escenario con anti-patrón de BD compartida (docker-compose.invalido.yml)...")
    res_invalido = subprocess.run(
        [python_exe, str(script_path), "--compose", str(compose_invalido)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if res_invalido.returncode == 1:
        print("  ✔ TEST 2 PASÓ: El validador detectó exitosamente la violación y retornó exit code 1.")
        print("     Mensaje capturado del fallo:")
        for line in res_invalido.stdout.splitlines():
            if "[VIOLACION]" in line or "FALLO" in line:
                print(f"       -> {line.strip()}")
    else:
        print(f"  ❌ TEST 2 FALLÓ: Esperado exit code 1, pero retornó {res_invalido.returncode}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("RESULTADO DE LA SUITE: 2/2 PRUEBAS PASARON EXITOSAMENTE (100%)")
    print("La Fitness Function arquitectónica opera de manera infalible.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_test()
