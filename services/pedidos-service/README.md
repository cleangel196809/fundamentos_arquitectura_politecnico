# pedidos-service — P03 (José Luis Pineda Sanabria)

Microservicio de gestión de pedidos para **PiShop Cloud**, implementando el patrón **Transactional Outbox** para garantía de entrega _at-least-once_ hacia el stream `pishop.pedidos`.

---

## Cómo ejecutar

```bash
# Desarrollo local (SQLite + bus en memoria)
cd services/pedidos-service
pip install -r requirements.txt
uvicorn app.main:app --port 8003 --reload
```

### Docker Compose (PostgreSQL + Redis)

```yaml
pedidos-service:
  build: services/pedidos-service
  ports: ["8003:8003"]
  environment:
    PISHOP_DATABASE_URL: "postgresql+asyncpg://postgres:secret@db:5432/pedidos"
    PISHOP_DATABASE_PASSWORD: "secret"
    PISHOP_EVENT_BUS: "redis"
    PISHOP_REDIS_URL: "redis://redis:6379"
    PISHOP_HTTP_PORT: "8003"
```

### Aislamiento en el Edge (Semana 5)

En la arquitectura con **Edge Server (Traefik v3)**, `pedidos-service` opera como un servicio core dentro de la red interna `pishop-net`. No publica puertos hacia el host de la máquina (`ports` se omite en producción) para bloquear peticiones externas directas. El acceso se realiza exclusivamente a través de `checkout-bff` o `api-publica`. Para más detalles técnicos, consultar [docs/arquitectura/entregable-04-edge.md](../../docs/arquitectura/entregable-04-edge.md).

---

## Variables de configuración `PISHOP_*`

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `PISHOP_SERVICE_NAME` | `pedidos-service` | Nombre del servicio |
| `PISHOP_HTTP_PORT` | `8003` | Puerto HTTP |
| `PISHOP_APP_ENV` | `dev` | Entorno (`dev`, `prod`) |
| `PISHOP_DATABASE_URL` | `sqlite+aiosqlite:///./pedidos.db` | URL de conexión a BD |
| `PISHOP_DATABASE_PASSWORD` | `cambiar-en-entorno` | Contraseña BD (SecretStr) |
| `PISHOP_EVENT_BUS` | `memory` | Bus de eventos: `memory` o `redis` |
| `PISHOP_REDIS_URL` | `redis://localhost:6379` | URL de Redis (si bus=redis) |
| `PISHOP_PUBLISH_INTERVAL_SECONDS` | `5.0` | Intervalo del publisher de outbox |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | `2.0` | Timeout para llamadas HTTP salientes |

---

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/v1/pedidos` | Crear pedido (atómico: pedido + evento outbox) |
| `GET` | `/v1/pedidos/{pedido_id}` | Consultar pedido |
| `POST` | `/v1/pedidos/{pedido_id}/cancelar` | Cancelar pedido |
| `GET` | `/v1/outbox/pendientes` | Eventos outbox no publicados |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/startup` | Startup probe |
| `GET` | `/health/ready` | Readiness probe (verifica BD) |

### Cabecera de idempotencia

```
Idempotency-Key: <uuid-o-string-único>
```

Incluirla en `POST /v1/pedidos` garantiza que llamadas repetidas retornen la misma respuesta sin crear duplicados.

---

## Ejemplos `curl`

```bash
# Crear pedido
curl -X POST http://localhost:8003/v1/pedidos \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: mi-clave-unica-001" \
  -d '{"cliente_id":"cli-001","sku":"LAPTOP-X1","cantidad":1,"monto_cop":3500000}'

# Respuesta: 201
# {"pedido_id":"a1b2c3d4-...","estado":"CREADO"}

# Consultar pedido
curl http://localhost:8003/v1/pedidos/a1b2c3d4-...

# Cancelar pedido
curl -X POST http://localhost:8003/v1/pedidos/a1b2c3d4-.../cancelar

# Ver eventos pendientes
curl http://localhost:8003/v1/outbox/pendientes

# Health
curl http://localhost:8003/health/live
curl http://localhost:8003/health/ready
```

---

## Por qué el Outbox NO da exactamente-una-vez (y qué lo complementa)

### El problema

El Outbox garantiza **at-least-once**: si el servicio falla *después* de publicar el evento en el bus pero *antes* de marcar `publicado_en`, el evento se re-publicará en el siguiente ciclo del publisher.

```
Transacción DB:
  INSERT pedido
  INSERT outbox_event (publicado_en = NULL)   ← atómico ✅

Publisher loop:
  1. Leer eventos WHERE publicado_en IS NULL
  2. XADD pishop.pedidos ...                  ← si crash aquí → re-publica
  3. UPDATE publicado_en = now()
```

Esto significa que un consumidor **puede recibir el mismo evento dos o más veces**.

### Qué lo complementa: consumidores idempotentes

Cada consumidor debe almacenar los `evento_id` ya procesados (p. ej. en una tabla `eventos_procesados`) y descartar duplicados:

```python
if await ya_procesado(evento_id):
    return  # ignorar duplicado
await procesar(evento)
await marcar_procesado(evento_id)
```

La combinación **Outbox (at-least-once) + Consumidor idempotente** logra semántica de procesamiento efectivamente-una-vez (_effectively-once_) sin necesidad de coordinación distribuida costosa.

---

## Diagrama: Patrón Outbox

```
┌─────────────────────────────────────────┐
│          pedidos-service                │
│                                         │
│  POST /v1/pedidos                       │
│       │                                 │
│       ▼                                 │
│  ┌─────────────────────────────────┐    │
│  │  Transacción única              │    │
│  │  ① INSERT INTO pedidos          │    │
│  │  ② INSERT INTO outbox_events    │    │
│  │     (publicado_en = NULL)       │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  OutboxPublisher (background)    │   │
│  │  loop cada N segundos:           │   │
│  │  ③ SELECT * WHERE pub_en IS NULL │   │
│  │  ④ XADD pishop.pedidos fields   │   │  ──► Redis Stream / MemoryBus
│  │  ⑤ UPDATE publicado_en = now()  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘

         ▲ at-least-once: si crash entre ④ y ⑤
           → re-publica en el siguiente ciclo

Consumidores deben ser IDEMPOTENTES usando evento_id.
```

---

## Ejecutar tests

```bash
cd services/pedidos-service
pytest tests/ -v
```

Todos los tests usan SQLite (`sqlite+aiosqlite`) + bus en memoria sin servicios externos.

---

## Observabilidad y Métricas RED (Semana 6)

El servicio incorpora los tres pilares de observabilidad mediante **OpenTelemetry**, **structlog** y la pila Grafana (Tempo, Loki, Prometheus).

### 1. Registros Estructurados (Logs en JSON)
Todos los logs se emiten a `stdout` en formato JSON con niveles estándar (`INFO`, `WARNING`, `ERROR`).
Cada registro incluye automáticamente el identificador de correlación `request_id` (propagado o generado desde `X-Request-Id`) y el `trace_id` de OpenTelemetry:

```json
{"event": "pedido_creado_exitosamente", "level": "info", "pedido_id": "a1b2c3d4-...", "request_id": "req-9912", "service": "pedidos-service", "timestamp": "2026-11-18T18:30:00Z", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"}
```
*Conforme a la Ley 1581 de 2012 de protección de datos personales, no se registran datos personales sensibles, tokens ni datos financieros.*

### 2. Trazas Distribuidas (OTLP y W3C Trace Context)
- Propagación automática de cabeceras `traceparent` (W3C Trace Context) en llamadas entrantes y salientes con `opentelemetry-instrumentation-fastapi` y `opentelemetry-instrumentation-httpx`.
- Tramo manual de negocio: `tracer.start_as_current_span("crear_pedido")` y `cancelar_pedido` miden el tiempo de la transacción local de base de datos y registran excepciones.
- Exportación en segundo plano vía gRPC OTLP con `BatchSpanProcessor` hacia `otel-collector:4317` (y de allí a Grafana Tempo).

### 3. Métricas Propias del Dominio (OpenTelemetry Metrics SDK)
- **Contador (`Counter`):** `pedidos_creados_total` (unit="1", etiquetas: `canal`, `estado`).
- **Histograma (`Histogram`):** `pedido_duracion_segundos` (unit="s", distribución de latencia para percentiles p50 y p95).
- **Medidor (`UpDownCounter`):** `pedidos_pendientes_outbox` (unit="1", seguimiento en tiempo real de eventos no publicados en la tabla `outbox_events`).

### 4. Definición de SLI, SLO y Presupuesto de Error

| Concepto | Definición para `pedidos-service` | Métrica / Fórmula |
|---|---|---|
| **SLI (Service Level Indicator)** | Proporción de peticiones exitosas de creación de pedido atendidas en menos de 300 ms | $\frac{\text{Peticiones HTTP 201 con latencia} \le 300\text{ms}}{\text{Total de peticiones válidas}} \times 100$ |
| **SLO (Service Level Objective)** | 99.5 % de disponibilidad y rendimiento conforme en una ventana móvil de 30 días | **99.5 %** |
| **Presupuesto de Error (Error Budget)** | Margen de fallo admisible antes de congelar despliegues | **0.5 %** del tráfico mensual ($\approx 3.65$ horas de degradación/mes) |

### 5. Pila de Observabilidad y Tablero RED
- Se incluye `compose.obs.yaml` para desplegar la pila:
  ```bash
  docker compose -f compose.obs.yaml up -d
  ```
- Grafana accesible en `http://localhost:3000` con el tablero importable `tablero-red.json` con los 4 paneles RED:
  1. **Rate:** `sum(rate(pedidos_creados_total[1m]))`
  2. **Errors:** Tasa de cancelación / errores
  3. **Duration p50:** `histogram_quantile(0.50, ...)`
  4. **Duration p95:** `histogram_quantile(0.95, ...)` (Monitoreo de cumplimiento del SLO)

---

## Declaración de uso de IA generativa

- **Herramienta utilizada**: Asistente de IA (Antigravity / LLM).
- **Partes generadas**: Estructura inicial del boilerplate FastAPI, esquemas Pydantic y casos de prueba base con pytest.
- **Verificación humana realizada**:
  1. Revisión y ajuste de las transacciones atómicas con SQLAlchemy 2.0 AsyncSession (`app/routers/pedidos.py`) para evitar llamadas de red internas y garantizar que tanto el pedido como el evento en la tabla `outbox` se confirmen atómicamente.
  2. Implementación y validación del mecanismo de reintento *at-least-once* en el publicador en segundo plano (`app/publisher.py`), comprobando que `publicado_en` se marque únicamente después de confirmar el envío al bus.
  3. Ejecución exitosa de los 19 tests unitarios/integración con `pytest` y validación completa con la herramienta del curso `python herramientas/validar_entrega.py pedidos-service` con resultado 100% OK.

