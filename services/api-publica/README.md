# api-publica (P07) — fachada y seguridad del perímetro

Único servicio de PiShop Cloud visible desde Internet (puerto 8000). **Enruta, no decide**: no contiene lógica de negocio; el BFF agrega y los servicios core resuelven.

| Ruta | Destino interno | Notas |
|---|---|---|
| `GET /v1/catalogo/productos?pagina=&tamano=` | `catalogo-service` `/v1/productos` | solo `publicado=true`; modelo público (sin campos internos) |
| `POST /v1/compras` | `checkout-bff` `/v1/checkout` | reenvía `Idempotency-Key` |
| `GET /v1/compras/{pedido_id}` | `checkout-bff` `/v1/checkout/{pedido_id}/estado` | |
| `GET /health/live \| startup \| ready` | — | sin autenticación y sin límite de tasa |

## Cómo ejecutarlo

```bash
cd services/api-publica
pip install -r requirements.txt
PISHOP_API_KEY=una-clave-local-de-prueba uvicorn app.main:app --port 8000   # dev
python -m pytest -q                                                          # no necesita servicios externos
python ../../herramientas/validar_entrega.py api-publica                     # contrato + sondas
python ../../herramientas/auditar_config.py --servicio api-publica           # auditoría de seguridad
```

Sistema completo con red interna aislada (solo se publica el 8000; requiere Docker Compose ≥ 2.24.4):

```bash
cp .env.example .env        # y cambiar POSTGRES_PASSWORD y PISHOP_API_KEY (≥ 16 caracteres)
docker compose -f docker-compose.yml -f docker-compose.seguro.yml up -d
```

## Configuración (`PISHOP_*`)

| Variable | Por defecto | Descripción |
|---|---|---|
| `PISHOP_API_KEY` | *(vacío)* | Secreto de la API (`SecretStr`). Vacío = **nadie entra** (falla cerrado). En `qa/stg/prod` se rechaza si es vacía, de ejemplo o < 16 caracteres |
| `PISHOP_APP_ENV` | `dev` | `dev\|qa\|stg\|prod` |
| `PISHOP_RATE_LIMIT` | `40/minute` | Límite por clave (requisito del proyecto: máximo 40 por minuto; el contrato original decía 60) |
| `PISHOP_RATE_LIMIT_STORAGE_URI` | `memory://` | Con varias réplicas: `redis://redis:6379/1` |
| `PISHOP_CATALOGO_URL` | `http://localhost:8001` | En compose: `http://catalogo-service:8001` |
| `PISHOP_CHECKOUT_URL` | `http://localhost:8080` | En compose: `http://checkout-bff:8080` |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | `5.0` | Timeout explícito de toda llamada saliente (0 < t ≤ 30) |
| `PISHOP_HTTP_PORT`, `PISHOP_SERVICE_NAME`, `PISHOP_CONFIG_SERVICE_URL`, `PISHOP_CONSUL_URL`, `PISHOP_CONFIG_POLL_SECONDS` | ver `app/settings.py` | Igual que la plantilla |

## Decisiones de seguridad (y por qué)

| Decisión | Razón |
|---|---|
| Secreto como `SecretStr` + `hide_input_in_errors=True` | `SecretStr` muestra `**********` en logs/trazas. Se comprobó que sin `hide_input_in_errors` pydantic **sí imprime el valor** en el error de validación al arrancar |
| `hmac.compare_digest` para la clave | Comparación en tiempo constante: evita adivinar la clave midiendo tiempos |
| Falla cerrado + clave fuerte fuera de `dev` | Un `.env.example` olvidado (`cambiar-esto`) no puede llegar a producción |
| Límite 40/min por clave, **compartido entre rutas** | Requisito del proyecto. El `SlowAPIMiddleware` cuenta también los 401 |
| Claves inválidas → cubo por IP | Probar claves al azar también queda limitado y no se evade rotando valores; la clave válida usa otro cubo |
| Sondas exentas de autenticación y de límite | Docker/Consul las consultan sin clave y con frecuencia |
| Errores `application/problem+json` (RFC 9457, que reemplaza al 7807) | Formato estándar; el 500 no expone traza (se registra en el servidor) y el 422 omite `input` |
| `extra="forbid"` + patrón `^[A-Za-z0-9_.\-]+$` en identificadores | Rechaza campos no declarados (*mass assignment*) y `../`, espacios o comillas en rutas hacia servicios internos |
| Modelo público de producto (ACL) | No se exponen identificadores ni campos internos (semana 3, consecuencia 3) |
| Un `httpx.AsyncClient` por proceso con `Timeout` y `Limits` | Timeout explícito + *Bulkhead*: un servicio lento no agota la fachada. Lento → 504, caído → 503, 5xx interno → 502 |
| Contenedor sin root (`USER pishop`), multi-etapa, `read_only`, `cap_drop: ALL`, `no-new-privileges` | Mínimo privilegio: aunque alguien ejecute código dentro, no puede escribir archivos ni escalar permisos |
| Cabeceras de seguridad (`nosniff`, `DENY`, CSP, `no-store`...) | Recomendación OWASP Secure Headers; se prueban en `test_cabeceras_de_seguridad_en_todas_las_respuestas` |
| `/docs` deshabilitado en `prod` | Menos superficie: un atacante no recibe el mapa de la API |
| Compra fallida → `409 problem+json` con `pedido_id` y motivo | El cliente sabe que se compensó todo y no reintenta a ciegas |
| `docker-compose.seguro.yml` | Publica solo el 8000; Redis, Consul, PostgreSQL y servicios del dominio quedan en la red interna |

## Auditoría antes del PR

- [ ] `python -m pytest -q` en `services/api-publica` (33 pruebas: 401, 429 + `Retry-After`, 422, 500 sin traza, 504/503/502, `SecretStr`, timeouts)
- [ ] `python herramientas/validar_entrega.py api-publica` → `OK`
- [ ] `python herramientas/auditar_config.py` → `SIN HALLAZGOS` (R1 secretos, R2 `SecretStr`, R3 timeouts, R4 compose/Dockerfile, R5 puertos)
- [ ] `python -m pytest herramientas -q` (pruebas del propio auditor)

## Evidencia (reproducible)

Con el servicio levantado y `K="X-API-Key: <su clave>"`:

| Comando | Resultado esperado |
|---|---|
| `curl -i localhost:8000/v1/catalogo/productos` | `401`, `content-type: application/problem+json`, `www-authenticate: ApiKey` |
| `curl -H "$K" localhost:8000/v1/catalogo/productos` | `200`, solo `sku,nombre,precio_cop,categoria` de productos publicados |
| `curl -H "$K" -H "Content-Type: application/json" -d '{"cantidad":-5}' localhost:8000/v1/compras` | `422` con `errors[].loc/msg/type` |
| `curl localhost:8000/health/live` (y `startup`, `ready`) | `200` sin clave |
| 41 `curl -H "$K"` seguidos | el 41.º devuelve `429` con `retry-after` (segundos que faltan) |

> **Pegue aquí su propia captura** (salida real de `curl` y de `pytest`): la sustentación valida autoría.

## Limitaciones conocidas

- Con `memory://` el límite es **por instancia**: con N réplicas el tope real es N×40. Con `redis://` es exacto, pero si Redis cae el límite deja de poder evaluarse.
- Detrás de un proxy (Traefik) `request.client.host` sería la IP del proxy; habría que leer `X-Forwarded-For` de un proxy de confianza.
- El filtro de «solo publicados» se aplica después de paginar: una página puede traer menos de `tamano` elementos y no se devuelve `total`.
- Si el cliente no envía `Idempotency-Key`, se genera una; solo reenviar **la misma** clave protege de compras duplicadas.
- Una sola clave compartida; no hay TLS ni rotación (se resolvería con Traefik/Keycloak, semana 7).
- El contrato del BFF (`pedido_id`, `estado`) y el campo `publicado` del catálogo se asumieron de `docs/CONTRATOS.md`; confirmar con P01 y P06.

## Coordinación con otros paquetes

- **P12:** `docker-compose.yml` ya define `PISHOP_CATALOGO_URL` / `PISHOP_CHECKOUT_URL` para `api-publica`. Para CI: `pip install -r services/api-publica/requirements.txt`, luego `python herramientas/auditar_config.py` y `python -m pytest herramientas -q`. `auditar_config.py` figura como entregable de P12 en `docs/ROLES.md`: acordar quién lo versiona para evitar conflictos.
- **P09 / P08:** el `lifespan` ya se registra en Consul (`app/registro_consul.py`) y consulta el config-service (`app/cliente_config.py`).

## Declaración de uso de IA generativa

- **Herramienta:** Claude (Anthropic).
- **Parte generada con IA:** borrador de `app/`, `tests/`, `herramientas/auditar_config.py` y `docker-compose.seguro.yml`, a partir de la guía *Rol y Estrategia de Ciberseguridad* y de las diapositivas de las semanas 1 a 4.
- **Qué verifiqué yo** *(marque solo lo que realmente hizo)*:
  - [ ] Leí cada archivo y puedo explicar qué hace y por qué (`SecretStr`, `compare_digest`, límite por clave).
  - [ ] Ejecuté pytest, `validar_entrega.py` y `auditar_config.py` en mi máquina.
  - [ ] Probé los `curl` de la tabla de evidencia y pegué mi propia salida.
  - [ ] Confirmé los contratos con P01 y P06.
