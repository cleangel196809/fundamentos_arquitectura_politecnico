# Contratos de PiShop Cloud (semanas 1 a 4)

Todos los equipos trabajan en paralelo contra estos contratos. **Nadie espera a otro**: si su servicio necesita a otro que aún no existe, use un doble de prueba (mock) que respete el contrato.

## Reglas de arquitectura (válidas para los 12 paquetes)

1. Cada servicio es dueño exclusivo de su base de datos (`pg_<contexto>`); ningún servicio lee la base de otro (semana 1, antídoto del monolito distribuido).
2. Toda la configuración entra por variables `PISHOP_*` con `pydantic-settings`; los secretos son `SecretStr` (semana 4, factor III).
3. Cada servicio expone `/health/live`, `/health/ready` y `/health/startup` con semántica diferenciada (semana 4).
4. Toda llamada saliente usa `httpx.AsyncClient` con **timeout explícito** (semana 3).
5. Para pruebas, la base debe funcionar con SQLite (`sqlite+aiosqlite`) y el bus de eventos con `PISHOP_EVENT_BUS=memory`; en compose se usa PostgreSQL 17 y Redis 8 (`PISHOP_EVENT_BUS=redis`).
6. Rutas versionadas bajo `/v1`. Errores en JSON `{"detalle": "...", "codigo": "..."}`; validación inválida = `422`; recurso inexistente = `404`.
7. Escrituras que pueden repetirse (reservas, pagos, pedidos desde el BFF) exigen la cabecera `Idempotency-Key`; repetir la misma clave devuelve la **misma respuesta** sin repetir el efecto (semana 3).

## Puertos (fijados en la semana 2)

| Servicio | Puerto | Tipo | Paquete |
|---|---|---|---|
| api-publica | 8000 | API | P07 |
| catalogo-service | 8001 | Core | P01 |
| inventario-service | 8002 | Core | P02 |
| pedidos-service | 8003 | Core | P03 |
| pagos-service | 8004 | Core | P04 |
| notificaciones-service | 8005 | Core | P05 |
| reportes-service | 8006 | Core (CQRS, lectura) | P10 |
| checkout-bff | 8080 | Compuesto | P06 |
| descubridor-service | 8090 | Soporte | P09 |
| config-service | 8010 | Soporte | P08 |
| Consul | 8500 | Infra | P09 |
| Redis | 6379 | Infra | P12 |

## Contrato de eventos (Redis Streams)

Stream `pishop.pedidos`. Campos de cada entrada: `evento_id` (uuid), `tipo` (`PedidoCreado` · `PedidoCancelado`), `payload` (JSON string).

```json
{"pedido_id": "8f3c...", "cliente_id": "C-9001", "sku": "CAFE-500G", "cantidad": 3, "monto_cop": 56000, "ocurrido_en": "2026-11-05T14:00:00Z"}
```

Grupos de consumidores: `notificaciones` (P05) y `reportes` (P10). Entrega *at-least-once*: los consumidores **deben** descartar duplicados por `evento_id`.

## Contratos por servicio

### P01 · catalogo-service (8001)
- `GET /v1/productos?pagina=1&tamano=20` → `{"items":[...],"total":N,"pagina":1,"tamano":20}`; `tamano` máximo 100.
- `POST /v1/productos` `{sku,nombre,precio_cop>0,categoria}` → `201`; SKU duplicado → `409`; precio ≤ 0 → `422`.
- `GET /v1/productos/{sku}` → `200` / `404`.
- `PATCH /v1/productos/{sku}/publicar` → `200` con `publicado=true` / `404`.

### P02 · inventario-service (8002)
- `PUT /v1/stock/{sku}` `{cantidad>=0}` · `GET /v1/stock/{sku}` → `{sku,cantidad,reservado}`.
- `POST /v1/reservas` `{sku,cantidad,pedido_id}` + `Idempotency-Key` → `201 {reserva_id,...}`; stock insuficiente → `409`; misma clave → misma respuesta, **sin descontar dos veces**.
- `POST /v1/reservas/{reserva_id}/liberar` → compensación: devuelve el stock; liberar dos veces no devuelve doble.

### P03 · pedidos-service (8003)
- `POST /v1/pedidos` `{cliente_id,sku,cantidad,monto_cop}` → `201 {pedido_id,estado:"CREADO"}`. **En una sola transacción** inserta el pedido y la fila `outbox` (`PedidoCreado`).
- `GET /v1/pedidos/{pedido_id}` · `POST /v1/pedidos/{pedido_id}/cancelar` (estado `CANCELADO` + evento `PedidoCancelado`).
- `GET /v1/outbox/pendientes` → eventos aún sin publicar. Un publicador en segundo plano los envía a `pishop.pedidos` y los marca `publicado_en`.

### P04 · pagos-service (8004)
- `POST /v1/pagos` `{pedido_id,monto_cop,medio}` + `Idempotency-Key` → `201 {pago_id,estado}`; estados de dominio `APROBADO` · `RECHAZADO` · `PENDIENTE`.
- **ACL**: un adaptador traduce la respuesta de la pasarela (`APPROVED`/`DECLINED`/`TIMEOUT`) a los estados de dominio; el dominio nunca ve el vocabulario externo.
- `POST /_simulador/pasarela/cobrar` es la pasarela simulada; su modo se fija con `PISHOP_PASARELA_MODO=ok|rechaza|lenta|falla`.
- `GET /v1/pagos/{pago_id}` · `POST /v1/pagos/{pago_id}/reembolso` (compensación, idempotente).
- Pasarela lenta o caída → `504`/`503` en menos de `http_timeout_seconds`, nunca colgar.

### P05 · notificaciones-service (8005)
- Consumidor del grupo `notificaciones` sobre `pishop.pedidos`; por cada `PedidoCreado` registra una notificación (simulada) y **descarta duplicados** por `evento_id`.
- `GET /v1/notificaciones?pedido_id=` · `POST /v1/notificaciones/prueba` (inyecta un evento de prueba sin Redis).
- `/health/ready` es `503` si el bus está configurado y no responde.

### P06 · checkout-bff (8080) — servicio compuesto
- `POST /v1/checkout` `{cliente_id,sku,cantidad,medio_pago}` + `Idempotency-Key`. Orquesta la **saga**: (1) validar producto en catálogo, (2) reservar inventario, (3) crear pedido, (4) cobrar.
- Si un paso falla ejecuta las **compensaciones** en orden inverso (liberar reserva, cancelar pedido, reembolsar) y responde `{pedido_id, estado:"FALLIDO"|"CONFIRMADO", pasos:[{paso,resultado}]}`.
- `GET /v1/checkout/{pedido_id}/estado` · `GET /v1/vitrina` (productos publicados + stock, solo campos para móvil).
- Ningún core orquesta a otro: la orquestación vive **aquí**.

### P07 · api-publica (8000) — fachada
- `GET /v1/catalogo/productos` (solo publicados) · `POST /v1/compras` (→ checkout-bff) · `GET /v1/compras/{pedido_id}`.
- Exige cabecera `X-API-Key` (secreto por settings): sin ella `401`. Límite de 60 peticiones/min por clave → `429` con `Retry-After`.
- Errores en `application/problem+json` (RFC 9457). No contiene lógica de negocio.

### P08 · config-service (8010)
- `GET /config/{app}/{env}` con `ETag` y `If-None-Match` → `304` si no cambió; `?version=N` devuelve una versión histórica.
- `PUT /config/{app}/{env}` (requiere `X-Autor`, deja historial: autor, motivo, fecha) · `GET .../versions` · `POST .../rollback/{version}`.
- Debe poder correr con configuración vacía y sembrada desde un archivo `seed.json`.

### P09 · descubridor-service (8090) + Consul (8500)
- Consul en compose y un módulo `registro.py` reutilizable (`registrar()` / `dar_de_baja()` para el `lifespan` de cualquier servicio).
- `GET /v1/servicios` · `GET /v1/servicios/{nombre}/instancias` (solo instancias `passing`) · `GET /v1/servicios/{nombre}/resolver` (balanceo round-robin entre instancias sanas).
- Documento corto: ¿descubrimiento del lado del cliente o del servidor? Justificación para PiShop.

### P10 · reportes-service (8006) — CQRS (modelo de lectura)
- Consume `pishop.pedidos` (grupo `reportes`) y mantiene una proyección idempotente.
- `GET /v1/reportes/resumen` `{pedidos_total, unidades_total, monto_total_cop}` · `GET /v1/reportes/ventas-por-sku` · `POST /v1/reportes/reconstruir` (borra y rehace la proyección desde el stream).
- No escribe en ninguna base de otro servicio.

### P11 y P12 (sin API propia)
Ver `docs/ROLES.md`.
