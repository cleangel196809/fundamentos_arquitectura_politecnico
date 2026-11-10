"""Existencias FICTICIAS iniciales (mismos SKU que el catálogo).

Las cantidades son variadas a propósito: hay productos con mucho stock, otros
casi agotados (para probar el 409) y uno en cero.
"""
from app.models import ExistenciaFila

UNIDADES_INICIALES = {
    "CAFE-500G": 120, "CAFE-250G": 80, "CAFE-VERDE-1K": 35, "PANELA-1K": 200, "PANELA-POLVO": 90,
    "BOCADILLO-VEL": 60, "AREQUIPE-500": 45, "MIEL-ABEJAS": 30, "CACAO-NIBS": 25, "CHOCOLATE-MESA": 150,
    "QUINUA-1K": 40, "FRIJOL-CARGA": 110, "ARROZ-INTEGRAL": 140, "LENTEJA-500": 95, "MAIZ-PIRA": 70,
    "HUEVOS-CAMPO": 55, "QUESO-CAMPESINO": 38, "QUESO-COSTENO": 33, "YOGUR-MORA": 48, "AGUACATE-HASS": 64,
    "MANGO-TOMMY": 52, "LULO-1K": 3, "GULUPA-500": 2, "PLATANO-HARTON": 85, "FERTILIZANTE-ORG": 20,
    "SEMILLA-TOMATE": 300, "MACHETE-18": 15, "COSTAL-FIQUE": 0, "TE-COCA-BORRADOR": 10, "AGUAPANELA-LISTA": 12,
}


def existencias_de_ejemplo() -> list[ExistenciaFila]:
    return [ExistenciaFila(sku=sku, cantidad=unidades, reservado=0) for sku, unidades in UNIDADES_INICIALES.items()]
