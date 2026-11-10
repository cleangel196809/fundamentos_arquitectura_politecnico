# pedidos-service (P03) — puerto 8003

**Tipo:** Core + Outbox · **Base de datos:** pg_pedidos / usr_pedidos

Pedidos con Transactional Outbox: el pedido y su evento se guardan en la MISMA transacción, sin llamadas de red dentro.

## Decisiones

- Publicador en segundo plano (`app/publicador.py`) → stream `pishop.pedidos` y marca `publicado_en`.
- Garantía al-menos-una-vez, demostrada en `test_al_menos_una_vez_si_muere_entre_publicar_y_marcar`. No es exactamente-una-vez porque Redis y PostgreSQL no comparten transacción: lo complementa la idempotencia de los consumidores.
- `PISHOP_EVENT_BUS=memory` para pruebas.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build pedidos-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\pedidos-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py pedidos-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl http://localhost:8003/v1/outbox/pendientes
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
