# catalogo-service (P01) — puerto 8001

**Tipo:** Core · **Base de datos:** pg_catalogo / usr_catalogo

Dueño de los productos y sus precios. Separa `models.py` (tabla) de `schemas.py` (contrato): la API nunca expone la fila de la base.

## Decisiones

- Siembra 30 productos ficticios (28 publicados) si la tabla está vacía (`app/semilla.py`).
- SKU único: chequeo previo + restricción `UNIQUE` (dos altas simultáneas → 409).
- `tamano` de página por defecto viene del config-service (`pagina_tamano`): recarga en caliente sin reiniciar.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build catalogo-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\catalogo-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py catalogo-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl "http://localhost:8001/v1/productos?pagina=1&tamano=5"
curl http://localhost:8001/v1/productos/CAFE-500G
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
