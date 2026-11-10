# ADR-001: Implementación del Patrón Saga Orquestada para Transacciones Distribuidas en el Checkout

| Campo | Valor |
| :--- | :--- |
| **Identificador** | ADR-001 |
| **Estado** | **Aceptado / En Producción** |
| **Fecha** | Noviembre 2026 |
| **Autor / Rol** | P11 — Arquitecto de Software |
| **Contexto Técnico** | Flujo de Checkout distribuido entre `checkout-bff` (8080), `pedidos-service` (8003), `inventario-service` (8002) y `pagos-service` (8004) |

---

## 1. Contexto y Planteamiento del Problema
En la plataforma de comercio digital, completar una orden de compra (*checkout*) involucra múltiples operaciones de negocio que abarcan distintos bounded contexts:
1. Creación preliminar de la orden en `pedidos-service`.
2. Reserva atómica de existencias de SKUs en `inventario-service` (`POST /v1/reservas`).
3. Débito monetario y autorización en `pagos-service` (`POST /v1/pagos` contra pasarela externa).
4. Actualización del estado final de la orden a `CONFIRMADO` o `CANCELADO`.

Dado que cada microservicio cuenta con su propia base de datos relacional independiente (*Database-per-Service*), no es posible utilizar transacciones ACID locales mediante bloques `BEGIN...COMMIT`. Si el cobro falla o el cliente no tiene fondos suficientes tras haberse reservado las existencias, el sistema incurriría en una inconsistencia crítica: el inventario quedaría bloqueado indebidamente y el pedido quedaría en un limbo transaccional.

---

## 2. Decisión Adoptada
Se decide implementar el **Patrón Saga Orquestada** coordinado por el microservicio de pedidos (`pedidos-service [P03]`), complementado con el **Transactional Outbox Pattern** (`GET /v1/outbox/pendientes`):

1. **Orquestador Centralizado de la Saga:** `pedidos-service` actúa como el coordinador transaccional. Mantiene en su base de datos (`pedidos_db`) una máquina de estados explícita (`INICIADO`, `STOCK_RESERVADO`, `PAGO_PROCESANDO`, `COMPLETADO`, `COMPENSANDO`, `CANCELADO`).
2. **Ejecución de Pasos Transaccionales Locales:**
   - **Paso 1:** `pedidos-service` registra la orden preliminar en `pedidos_db` y emite el comando de reserva de stock a `inventario-service`.
   - **Paso 2:** Al recibir la confirmación de la reserva (`reserva_id`), el orquestador solicita el cobro a `pagos-service`.
   - **Paso 3:** Si `pagos-service` aprueba el pago, el orquestador marca el pedido como `COMPLETADO` y notifica a los servicios de soporte.
3. **Transacciones Compensatorias Explícitas (Rollback Semántico):**
   - Si `pagos-service` rechaza el cobro (por saldo insuficiente o error bancario), el orquestador no puede hacer rollback ACID; en su lugar, ejecuta de forma atómica e idempotente la transacción compensatoria: invoca `POST /v1/reservas/{reserva_id}/liberar` en `inventario-service` y marca el pedido como `CANCELADO` mediante `POST /v1/pedidos/{pedido_id}/cancelar`.
   - Si el pedido se cancela con un pago ya ejecutado, se dispara la compensación `POST /v1/pagos/{pago_id}/reembolso`.

---

## 3. Alternativas Descartadas

### Alternativa Descartada 1: Two-Phase Commit (2PC / XA Transaccional Global)
- **Descripción:** Coordinar una transacción distribuida clásica bloqueando las tablas de `pedidos_db`, `inventario_db` y `pagos_db` bajo un protocolo de dos fases (Prepare / Commit).
- **Razón del Descarte:**
  - **Bloqueos destructivos y cuello de botella:** 2PC es un protocolo de bloqueo síncrono. Cualquier retardo en la pasarela externa de pagos mantendría bloqueadas las filas de inventario y pedidos, degradando drásticamente el rendimiento global de la plataforma ($P_{95} > 5000\text{ ms}$).
  - **Punto único de falla:** Si el coordinador de transacciones falla durante la fase de preparación, los recursos quedan en un estado de bloqueo indefinido.
  - **Incompatibilidad con servicios externos:** Las pasarelas de pago externas (Stripe, PSE) no soportan transacciones XA / 2PC.

### Alternativa Descartada 2: Saga Coreografiada Pura (Event-Driven Choreo)
- **Descripción:** Cada servicio escucha eventos y decide autónomamente el siguiente paso sin un orquestador central (e.g., `pedidos` emite evento, `inventario` escucha y emite evento, `pagos` escucha y emite evento).
- **Razón del Descarte:**
  - **Complejidad de observabilidad y depuración (*Spaghetti de Eventos*):** En flujos complejos de comercio con múltiples bifurcaciones y cancelaciones, es sumamente difícil rastrear en qué estado se encuentra un pedido específico sin consultar logs en 4 servicios distintos.
  - **Acoplamiento cíclico de eventos:** La lógica de compensación queda distribuida y fragmentada, aumentando el riesgo de bucles de eventos y dificultando el cumplimiento del indicador de auditoría y reportes.

---

## 4. Trade-offs y Consecuencias

### Consecuencias Positivas (Beneficios)
- **Alta Disponibilidad y Ausencia de Bloqueos:** No se retienen bloqueos de base de datos distribuidos entre microservicios; cada servicio realiza transacciones locales rápidas e independientes.
- **Visibilidad y Trazabilidad Centralizada:** El estado exacto del checkout y de la saga reside en `pedidos-service`, permitiendo consultar el estado en cualquier instante vía `GET /v1/pedidos/{pedido_id}` o desde el BFF `GET /v1/checkout/{pedido_id}/estado`.
- **Resiliencia Operativa:** Si un servicio falla temporalmente, el orquestador reintenta la compensación hasta garantizar la consistencia eventual.

### Consecuencias Negativas y Mitigaciones
- **Consistencia Eventual (Falta de Aislamiento ACID):** Durante una ventana de pocos cientos de milisegundos, el stock reservado no está formalmente pagado.
  - *Mitigación:* Se implementa un tiempo de expiración (TTL de 10 minutos) en las reservas de inventario para liberar stock huérfano automáticamente si la saga se interrumpe catastróficamente.
- **Complejidad Adicional en el Orquestador:** `pedidos-service` debe gestionar la lógica de estados de la saga y las llamadas compensatorias.
  - *Mitigación:* Se encapsula la máquina de estados en una clase especializada (`SagaOrchestrator`) con políticas de reintento idempotentes.
