# inventario-service (P02) — puerto 8002

**Tipo:** Core · **Base de datos:** pg_inventario / usr_inventario

Existencias y reservas. Una reserva aparta unidades para un pedido; luego se libera (compensación) o se confirma (venta).

## Decisiones

- `Idempotency-Key` obligatoria: la respuesta queda guardada en `respuestas_idempotentes`; la misma clave devuelve lo mismo sin descontar dos veces.
- Condición de carrera resuelta con `UPDATE ... WHERE cantidad - reservado >= n` atómico (prueba con 10 hilos por 2 unidades).
- Escalado: eje Y ya aplicado; si crece, eje Z particionando por SKU (SKU distintos no compiten entre sí).

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build inventario-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\inventario-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py inventario-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl http://localhost:8002/v1/stock/CAFE-500G
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
