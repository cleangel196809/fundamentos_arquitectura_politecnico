# checkout-bff (P06) — puerto 8080

**Tipo:** Compuesto (BFF, saga) · **Base de datos:** — (sin base propia)

Orquesta la saga de compra: validar producto → reservar → crear pedido → cobrar, con compensaciones en orden inverso (`app/saga.py`).

## Decisiones

- Timeouts por servicio (1 s / 1 s / 1 s / 2,5 s): una compra nunca pasa de 5 s.
- Idempotencia de punta a punta con claves derivadas (`<clave>:reserva`, `:pedido`, `:pago`).
- `/v1/vitrina` con bulkhead (máx. 10 consultas en paralelo) y fallback si inventario no responde.

## Cómo ejecutarlo

```bat
:: Con todo el sistema (desde la raíz del proyecto)
docker compose up -d --build checkout-bff

:: Solo las pruebas (SQLite y bus en memoria: no necesita Docker)
cd services\checkout-bff
pip install -r requirements.txt pytest
python -m pytest -q
python ..\..\herramientas\validar_entrega.py checkout-bff
```

## Configuración

Todas las variables usan el prefijo `PISHOP_` y están documentadas en `app/settings.py` (valores por defecto para pruebas) y en `docker-compose.yml` (valores reales).

## Evidencia

```bat
curl http://localhost:8080/v1/vitrina
```

> Pegue aquí su salida real de `curl` y de `pytest` (la sustentación valida autoría).
