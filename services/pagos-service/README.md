# pagos-service (P04) — puerto 8004

**Tipo:** Core + ACL · **Base de datos:** pg_pagos / usr_pagos

Cobros y reembolsos. La pasarela simulada responde en su propio idioma (APPROVED/DECLINED); `app/adaptador_pasarela.py` es la ACL que traduce a APROBADO/RECHAZADO/PENDIENTE.

## Decisiones

- Un `httpx.AsyncClient` por proceso con timeout explícito: pasarela lenta → 504, caída → 503, nunca se cuelga.
- La `Idempotency-Key` es `UNIQUE` en la tabla `pagos`: imposible cobrar dos veces.
- Modos: `ok`, `rechaza`, `lenta`, `falla` (`PISHOP_PASARELA_MODO` o `PUT /_simulador/pasarela/modo`, bloqueado en prod).

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build pagos-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\pagos-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py pagos-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl -X PUT http://localhost:8004/_simulador/pasarela/modo -H "Content-Type: application/json" -d "{\"modo\":\"rechaza\"}"
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
