# reportes-service (P10) — puerto 8006

**Tipo:** Core (CQRS, lectura) · **Base de datos:** pg_reportes / usr_reportes

Modelo de lectura: totales de ventas derivados de los eventos. Consistencia eventual (1–2 s después de la compra).

## Decisiones

- Proyección idempotente: `eventos_aplicados` + `ventas_por_sku` en una sola transacción.
- `PedidoCancelado` descuenta.
- `POST /v1/reportes/reconstruir` borra y rehace todo desde el stream: el resultado es idéntico.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build reportes-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\reportes-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py reportes-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl http://localhost:8006/v1/reportes/resumen
curl -X POST http://localhost:8006/v1/reportes/reconstruir
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
