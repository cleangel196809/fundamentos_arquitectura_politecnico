"""Datos FICTICIOS para poblar el catálogo (PiShop: PYME agropecuaria colombiana).

Se cargan solo si la tabla está vacía, así reiniciar el contenedor no duplica
nada. Los mismos SKU se usan en inventario-service/app/semilla.py.
"""
from app.models import ProductoFila

# (sku, nombre, precio_cop, categoria, region_origen, publicado)
PRODUCTOS_DE_EJEMPLO = [
    ("CAFE-500G", "Café especial tostado 500 g", 18_000, "cafe", "Huila", True),
    ("CAFE-250G", "Café de origen Nariño 250 g", 11_500, "cafe", "Nariño", True),
    ("CAFE-VERDE-1K", "Café verde para tostar 1 kg", 32_000, "cafe", "Cauca", True),
    ("PANELA-1K", "Panela en bloque 1 kg", 7_000, "dulces", "Santander", True),
    ("PANELA-POLVO", "Panela pulverizada 500 g", 5_200, "dulces", "Cundinamarca", True),
    ("BOCADILLO-VEL", "Bocadillo veleño x 12", 9_800, "dulces", "Santander", True),
    ("AREQUIPE-500", "Arequipe artesanal 500 g", 12_400, "dulces", "Boyacá", True),
    ("MIEL-ABEJAS", "Miel de abejas pura 350 g", 16_900, "dulces", "Tolima", True),
    ("CACAO-NIBS", "Nibs de cacao fino 200 g", 14_500, "cacao", "Arauca", True),
    ("CHOCOLATE-MESA", "Chocolate de mesa 250 g", 6_900, "cacao", "Santander", True),
    ("QUINUA-1K", "Quinua andina 1 kg", 15_800, "granos", "Boyacá", True),
    ("FRIJOL-CARGA", "Fríjol cargamanto 1 kg", 9_600, "granos", "Antioquia", True),
    ("ARROZ-INTEGRAL", "Arroz integral 1 kg", 6_300, "granos", "Tolima", True),
    ("LENTEJA-500", "Lenteja seleccionada 500 g", 4_200, "granos", "Nariño", True),
    ("MAIZ-PIRA", "Maíz pira 500 g", 3_900, "granos", "Córdoba", True),
    ("HUEVOS-CAMPO", "Huevos de campo x 30", 19_500, "lacteos", "Cundinamarca", True),
    ("QUESO-CAMPESINO", "Queso campesino 500 g", 13_200, "lacteos", "Boyacá", True),
    ("QUESO-COSTENO", "Queso costeño 500 g", 14_000, "lacteos", "Córdoba", True),
    ("YOGUR-MORA", "Yogur de mora 1 L", 8_700, "lacteos", "Nariño", True),
    ("AGUACATE-HASS", "Aguacate Hass x 4", 10_900, "frutas", "Caldas", True),
    ("MANGO-TOMMY", "Mango Tommy x 3", 8_100, "frutas", "Tolima", True),
    ("LULO-1K", "Lulo fresco 1 kg", 7_400, "frutas", "Huila", True),
    ("GULUPA-500", "Gulupa 500 g", 6_800, "frutas", "Cundinamarca", True),
    ("PLATANO-HARTON", "Plátano hartón x 5", 5_500, "frutas", "Quindío", True),
    ("FERTILIZANTE-ORG", "Abono orgánico 5 kg", 27_000, "insumos", "Valle del Cauca", True),
    ("SEMILLA-TOMATE", "Semillas de tomate chonto", 4_800, "insumos", "Valle del Cauca", True),
    ("MACHETE-18", "Machete de 18 pulgadas", 24_900, "herramientas", "Antioquia", True),
    ("COSTAL-FIQUE", "Costal de fique", 6_000, "herramientas", "Cauca", True),
    ("TE-COCA-BORRADOR", "Producto en revisión (no publicado)", 9_000, "bebidas", "Cauca", False),
    ("AGUAPANELA-LISTA", "Aguapanela lista para tomar 1 L", 4_500, "bebidas", "Santander", False),
]


def filas_de_ejemplo() -> list[ProductoFila]:
    return [
        ProductoFila(sku=sku, nombre=nombre, precio_cop=precio, categoria=categoria,
                     region_origen=region, descripcion=f"{nombre} — producto de {region}", publicado=visible)
        for sku, nombre, precio, categoria, region, visible in PRODUCTOS_DE_EJEMPLO
    ]
