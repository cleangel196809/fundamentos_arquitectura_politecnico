# Diagrama de la Saga Transaccional Distribuida (Mermaid)

| Metadato | Detalle |
| :--- | :--- |
| **Rol / Autor** | P11 — Arquitecto de Software |
| **Proyecto** | `fundamentos_arquitectura_politecnico` |
| **Patrón** | Saga Orquestada con Transacciones Compensatorias (Semantic Rollback) |
| **Herramienta** | Mermaid State & Flowchart Diagram |

---

## 1. Contexto de la Saga en el Checkout

En una arquitectura de microservicios con persistencia aislada (*Database-per-Service*), una transacción que abarca múltiples servicios no puede resolverse con un commit ACID centralizado. El **Patrón Saga** modela la transacción distribuida como una secuencia de transacciones locales coordinadas.

Si alguna transacción local fracasa (por ejemplo, fondos insuficientes en la tarjeta o falta de existencias físicas), el orquestador ejecuta una serie de **transacciones compensatorias** en orden inverso para deshacer semánticamente los cambios efectuados previamente.

---

## 2. Diagrama de Estados y Flujo de la Saga en Mermaid

```mermaid
flowchart TD
    %% Estilos de los Nodos
    classDef startEnd fill:#cfe2ff,stroke:#084298,stroke-width:2px,font-weight:bold;
    classDef success fill:#d1e7dd,stroke:#0f5132,stroke-width:2px,color:#0f5132;
    classDef failure fill:#f8d7da,stroke:#842029,stroke-width:2px,color:#842029;
    classDef step fill:#fff3cd,stroke:#664d03,stroke-width:1.5px,color:#664d03;
    classDef comp fill:#f5c2c7,stroke:#842029,stroke-width:2px,stroke-dasharray: 5 5,color:#842029;

    Inicio([Inicia Checkout\nPOST /v1/checkout]):::startEnd --> Paso1

    %% Paso 1: Pedidos
    subgraph S1 ["Paso 1: Microservicio de Pedidos (P03)"]
        Paso1["Crear Pedido Preliminar\nPOST /v1/pedidos\nEstado: PENDIENTE_PAGO"]:::step
    end

    Paso1 --> Paso2

    %% Paso 2: Inventario
    subgraph S2 ["Paso 2: Microservicio de Inventario (P02)"]
        Paso2{"¿Hay existencias de SKU?\nPOST /v1/reservas"}:::step
        ReservaOK["Stock Reservado Exitosamente\nreserva_id generado"]:::success
        ReservaFail["Stock Insuficiente\nError 409 Conflict"]:::failure
    end

    Paso2 -- Sí --> ReservaOK
    Paso2 -- No --> ReservaFail

    %% Paso 3: Pagos
    subgraph S3 ["Paso 3: Microservicio de Pagos (P04)"]
        Paso3{"Autorización de Cobro\nPOST /v1/pagos\n(vía Capa ACL Pasarela)"}:::step
        PagoOK["Cobro Autorizado\ntransaccion_id emitido"]:::success
        PagoFail["Cobro Rechazado\n(Fondos insuficientes / Error)"]:::failure
    end

    ReservaOK --> Paso3
    Paso3 -- Aprobado --> PagoOK
    Paso3 -- Rechazado --> PagoFail

    %% Happy Path: Confirmación
    subgraph S4 ["Cierre Exitoso: Happy Path"]
        Confirmar["Actualizar Pedido\nEstado: CONFIRMADO"]:::success
        Notificar["Despacho Notificación\nPOST /v1/notificaciones"]:::success
        FinExito([Fin de la Saga:\nPedido Completado]):::startEnd
    end

    PagoOK --> Confirmar --> Notificar --> FinExito

    %% Transacciones Compensatorias
    subgraph SC ["Transacciones Compensatorias (Rollback Semántico)"]
        CompLiberarStock["Compensación 1:\nLiberar Reserva de Stock\nPOST /v1/reservas/{id}/liberar"]:::comp
        CompCancelarPedido["Compensación 2:\nCancelar Pedido\nPOST /v1/pedidos/{id}/cancelar"]:::comp
        FinCancelado([Fin de la Saga:\nTransacción Revertida]):::failure
    end

    %% Flujos de Fallo y Compensación
    ReservaFail --> CompCancelarPedido
    PagoFail --> CompLiberarStock
    CompLiberarStock --> CompCancelarPedido
    CompCancelarPedido --> FinCancelado
```

---

## 3. Matriz de Acciones Transaccionales y Compensatorias

| Paso de la Saga | Microservicio | Acción Transaccional Directa | Endpoint de Acción | Transacción Compensatoria (Rollback) | Endpoint de Compensación |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | `pedidos-service` (8003) | Registrar orden preliminar en estado `PENDIENTE_PAGO`. | `POST /v1/pedidos` | Cancelar orden y marcar estado `CANCELADO`. | `POST /v1/pedidos/{id}/cancelar` |
| **2** | `inventario-service` (8002) | Reservar existencias físicas de los SKUs solicitados. | `POST /v1/reservas` | Liberar la reserva y restaurar las existencias. | `POST /v1/reservas/{reserva_id}/liberar` |
| **3** | `pagos-service` (8004) | Procesar cobro bancario vía Capa Anti-Corrupción (ACL). | `POST /v1/pagos` | Reembolsar cargo financiero acreditado. | `POST /v1/pagos/{pago_id}/reembolso` |
| **4** | `notificaciones-service` (8005) | Enviar correo/SMS de confirmación final. | `POST /v1/notificaciones/prueba` | Enviar alerta de cancelación o fallo de compra al cliente. | N/A (Operación idempotente terminal) |

---

## 4. Garantías de Concurrencia e Idempotencia
1. **Idempotencia de Compensaciones:** Todos los endpoints de compensación (`/liberar`, `/cancelar`, `/reembolso`) son estrictamente **idempotentes**. Si un evento de compensación es entregado dos veces debido a reintentos en RabbitMQ, el resultado en la persistencia es idéntico y seguro.
2. **Expiración de Reservas (TTL):** Toda reserva de stock en `inventario-service` cuenta con un tiempo de vida (*Time-to-Live*) de 10 minutos. Si el orquestador sufre una desconexión crítica antes de completar o compensar la saga, un cron interno en `inventario-service` libera automáticamente el stock retenido.
