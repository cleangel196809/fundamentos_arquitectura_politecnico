# descubridor-service (P09) — puerto 8090

**Tipo:** Soporte · **Base de datos:** — (consulta Consul)

Lista servicios registrados en Consul, sus instancias sanas y resuelve una URL con round-robin. Ver `docs/descubrimiento.md`.

## Decisiones

- Solo instancias `passing`.
- 503 claro si Consul no responde o no hay instancias sanas.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build descubridor-service

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\descubridor-service
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py descubridor-service
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl http://localhost:8090/v1/servicios
curl http://localhost:8090/v1/servicios/catalogo-service/resolver
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
