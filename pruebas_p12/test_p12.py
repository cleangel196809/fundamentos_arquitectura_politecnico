"""Pruebas pytest del paquete P12 (Danixa Herrera).

Prueban mis herramientas sin servicios externos: no necesitan Docker,
ni red, ni base de datos. Solo Python y pytest.

Uso (desde la carpeta principal del repositorio):
    python -m pytest pruebas_p12 -v
"""
import importlib.util    # para cargar un archivo .py a partir de su ruta
from pathlib import Path # para armar rutas de archivos

import pytest            # la herramienta de pruebas

RAIZ = Path(__file__).resolve().parent.parent   # carpeta principal del repositorio


def cargar(ruta_relativa):
    """Carga un archivo .py del repositorio para poder usar sus funciones."""
    ruta = RAIZ / ruta_relativa                                   # ruta completa del archivo
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)  # "receta" para cargarlo
    modulo = importlib.util.module_from_spec(spec)                # modulo vacio
    spec.loader.exec_module(modulo)                               # ejecuta el archivo (sin correr main)
    return modulo


disponibilidad = cargar("retos/semana03/disponibilidad.py")   # punto 1
auditor = cargar("herramientas/auditar_config.py")            # punto 5
verificador = cargar("herramientas/verificar_sondas.py")      # punto 6


# ----------------------------------------------------------- punto 1: disponibilidad

def test_serie_multiplica():
    # En serie se multiplican: 0.9 x 0.9 = 0.81
    assert disponibilidad.serie([0.9, 0.9]) == pytest.approx(0.81)


def test_paralelo_con_dos_copias():
    # Con 2 copias de 0.9: falla 0.1 x 0.1 = 0.01, funciona 0.99
    assert disponibilidad.paralelo(0.9, 2) == pytest.approx(0.99)


def test_paralelo_con_una_copia_no_cambia():
    # Con 1 sola copia queda igual
    assert disponibilidad.paralelo(0.997, 1) == pytest.approx(0.997)


def test_horas_caida():
    # 99 % disponible = 1 % de 8760 h = 87.6 h caido al ano
    assert disponibilidad.horas_caida(0.99) == pytest.approx(87.6)


def test_ruta_critica_del_reto():
    # Valores del reto 3.1: 98.7065 % y 113.31 h al ano
    a = disponibilidad.serie(disponibilidad.RUTA_CRITICA.values())
    assert a == pytest.approx(0.987065, abs=1e-6)
    assert disponibilidad.horas_caida(a) == pytest.approx(113.31, abs=0.01)


def test_cada_mitigacion_mejora():
    # Las tres mejoras deben subir la disponibilidad
    antes = disponibilidad.serie(disponibilidad.RUTA_CRITICA.values())
    for nombre, mejora in disponibilidad.MITIGACIONES:
        despues = disponibilidad.serie(mejora(disponibilidad.RUTA_CRITICA).values())
        assert despues > antes, nombre


def test_m3_saca_pagos_de_la_ruta_sin_danar_original():
    # M3 quita pagos y pasarela, pero el diccionario original sigue completo
    nueva = disponibilidad.m3_cobro_asincrono(disponibilidad.RUTA_CRITICA)
    assert "pagos-service" not in nueva
    assert "pasarela externa" not in nueva
    assert "pagos-service" in disponibilidad.RUTA_CRITICA


# ----------------------------------------------------------- punto 5: auditor

def test_auditor_detecta_password(tmp_path):
    # tmp_path es una carpeta temporal que pytest crea y borra solo
    archivo = tmp_path / "main.py"
    archivo.write_text('password = "1234"\n', encoding="utf-8")
    hallazgos = auditor.revisar_archivo(archivo)
    assert len(hallazgos) == 1
    assert hallazgos[0][2] == "password escrito"


def test_auditor_detecta_ip_fija(tmp_path):
    archivo = tmp_path / "main.py"
    archivo.write_text('URL = "http://192.168.0.10:8001"\n', encoding="utf-8")
    assert auditor.revisar_archivo(archivo)[0][2] == "direccion IP fija"


def test_auditor_acepta_codigo_limpio(tmp_path):
    # Leer la clave del entorno o llamar por nombre esta permitido
    archivo = tmp_path / "main.py"
    archivo.write_text('url = "http://pagos-service:8004"\nclave = settings.api_key\n', encoding="utf-8")
    assert auditor.revisar_archivo(archivo) == []


def test_auditor_salta_settings_y_pruebas(tmp_path):
    # settings.py (defaults) y archivos fuera de app/ no se revisan
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "settings.py").write_text('password = "solo-default"\n', encoding="utf-8")
    (tmp_path / "tests" / "test_x.py").write_text('password = "de-prueba"\n', encoding="utf-8")
    assert auditor.revisar_carpeta(tmp_path) == []


# ----------------------------------------------------------- punto 6: verificador

def resultado(arranco=True, live=200, startup=200, ready=503, error=None):
    """Arma un resultado falso, como el que devuelve probar_servicio."""
    return {"arranco": arranco, "live": live, "startup": startup, "ready": ready, "error": error}


def test_verificador_servicio_correcto():
    # Arranca y ready=503 sin configuracion: cumple todo
    assert verificador.evaluar(resultado()) == []


def test_verificador_criterio_3_ready_200():
    # Caso de pagos-service (issue #5): ready 200 sin configuracion
    problemas = verificador.evaluar(resultado(ready=200))
    assert len(problemas) == 1
    assert problemas[0].startswith("Criterio 3")


def test_verificador_criterio_2_no_arranca():
    # Si no arranca, solo se reporta el criterio 2
    problemas = verificador.evaluar(resultado(arranco=False, live=None, startup=None, ready=None, error="ConnectError"))
    assert len(problemas) == 1
    assert problemas[0].startswith("Criterio 2")
