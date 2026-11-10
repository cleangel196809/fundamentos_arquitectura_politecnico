# notificaciones-service (P05) — puerto 8005

**Tipo:** Core (consumidor asíncrono) · **Base de datos:** pg_notif / usr_notif

Escucha `pishop.pedidos` con el grupo `notificaciones` y registra el mensaje (simulado) al cliente por email o SMS.

## Decisiones

- Descarta duplicados por `evento_id` (consulta + columna `UNIQUE`): log `[dup] evento ... se descarta`.
- `/health/ready` = 503 si Redis no responde; `/health/live` no depende de nada.
- Si el servicio cae, la compra no falla: los eventos esperan en el stream (lee primero sus pendientes al volver).

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build notificaciones-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\notificaciones-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py notificaciones-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl "http://localhost:8005/v1/notificaciones?limite=5"
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
