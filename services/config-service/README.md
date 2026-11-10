# config-service (P08) — puerto 8010

**Tipo:** Soporte · **Base de datos:** — (en memoria, sembrado desde `app/seed.json`)

Configuración versionada de 9 servicios × 4 entornos (36 combinaciones).

## Decisiones

- `ETag` + `If-None-Match` → 304; `?version=N`; historial con autor, motivo y fecha; rollback que crea una versión nueva.
- `X-Autor` obligatorio en escrituras; `X-Token-Admin` si se define `PISHOP_CONFIG_ADMIN_TOKEN`.
- Los demás servicios lo consultan cada 15 s (`app/cliente_config.py`) y siguen funcionando si cae.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build config-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\config-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py config-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl -i http://localhost:8010/config/catalogo-service/dev
curl -X PUT http://localhost:8010/config/catalogo-service/dev -H "X-Autor: maik" -H "Content-Type: application/json" -d "{\"data\":{\"pagina_tamano\":5},\"motivo\":\"demo\"}"
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
