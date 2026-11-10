# Diagrama de Secuencia del Checkout: Fase Síncrona vs. Asíncrona

| Metadato | Detalle |
| :--- | :--- |
| **Rol / Autor** | P11 — Arquitecto de Software |
| **Proyecto** | `fundamentos_arquitectura_politecnico` |
| **Objetivo** | Modelar el flujo transaccional de checkout diferenciando con precisión milimétrica la interacción síncrona en el borde de la ejecución asíncrona distribuida en el núcleo |

---

## 1. Justificación Arquitectónica de la Separación Síncrono / Asíncrono

Para cumplir con el **RNF-01 (Latencia $P_{95} \le 200\text{ ms}$)** y el **RNF-02 (Disponibilidad $\ge 99.9\%$)**, el proceso de checkout no puede esperar síncronamente por la confirmación de la pasarela bancaria externa ni por el envío de correos electrónicos. 

Se divide el flujo en dos fases claramente delimitadas:
1. **Fase Síncrona (Inmediata / Borde):** Captura la intención de compra del cliente, valida la estructura del payload, genera el `pedido_id` en estado preliminar `PENDIENTE_PAGO` y retorna una respuesta HTTP 202 Accepted en menos de 200 ms.
2. **Fase Asíncrona (Segundo Plano / Núcleo):** Coordina la reserva de stock, el cobro financiero a través de la Capa ACL y el envío de notificaciones mediante eventos asíncronos en RabbitMQ bajo el patrón Saga.

---

## 2. Diagrama de Secuencia UML (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as 👤 Cliente / App
    participant BFF as 🌐 Checkout BFF<br/>(P06: 8080)
    participant Pedidos as 📦 Pedidos Service<br/>(P03: 8003)
    participant PedidosDB as 🗄️ pedidos_db<br/>(PostgreSQL)
    participant Broker as 📬 RabbitMQ Broker<br/>(AMQP 5672)
    participant Inventario as 🏷️ Inventario Service<br/>(P02: 8002)
    participant Pagos as 💳 Pagos Service<br/>(P04: 8004)
    participant Pasarela as 🏦 Pasarela Externa<br/>(Simulador Cobro)
    participant Notif as 🔔 Notificaciones<br/>(P05: 8005)

    %% ========================================================
    %% FASE 1: SÍNCRONA
    %% ========================================================
    rect rgb(235, 245, 255)
    note over Cliente, Broker: FASE 1: INTERACCIÓN SÍNCRONA (Latencia < 200 ms - HTTP REST)
    Cliente->>+BFF: POST /v1/checkout {cliente_id, sku, cantidad, tarjeta_token}
    BFF->>+Pedidos: POST /v1/pedidos {cliente_id, sku, cantidad}
    
    Pedidos->>Pedidos: Validar formato y calcular montos
    Pedidos->>+PedidosDB: INSERT INTO pedidos (id, estado='PENDIENTE_PAGO')
    PedidosDB-->>-Pedidos: OK (pedido_id: "PED-789")
    
    Pedidos->>Broker: Publicar evento 'PedidoIniciado' (vía Outbox)
    Pedidos-->>-BFF: 201 Created / 202 Accepted {pedido_id: "PED-789", estado: "PENDIENTE_PAGO"}
    BFF-->>-Cliente: 202 Accepted {pedido_id: "PED-789", estado: "PENDIENTE_PAGO", poll_url: "/v1/checkout/PED-789/estado"}
    end

    %% ========================================================
    %% FASE 2: ASÍNCRONA
    %% ========================================================
    rect rgb(240, 255, 240)
    note over Broker, Notif: FASE 2: ORQUESTACIÓN ASÍNCRONA DE LA SAGA (Event-Driven AMQP)
    
    %% Paso A: Reserva de Stock
    Broker->>+Inventario: Evento: PedidoIniciado (pedido_id, sku, cantidad)
    Inventario->>Inventario: Ejecutar POST /v1/reservas (atómico)
    alt Stock Disponible
        Inventario->>Broker: Publicar evento 'StockReservado' {pedido_id, reserva_id: "RES-101"}
    else Stock Insuficiente
        Inventario->>Broker: Publicar evento 'StockFallido' {pedido_id, razon: "SIN_EXISTENCIAS"}
        Broker->>Pedidos: Evento 'StockFallido' -> Marcar Pedido CANCELADO
    end
    deactivate Inventario

    %% Paso B: Cobro de Pago
    Broker->>+Pagos: Evento: StockReservado (pedido_id, monto, tarjeta_token)
    Pagos->>Pagos: Validar llave de idempotencia (Idempotency-Key)
    Pagos->>+Pasarela: POST /_simulador/pasarela/cobrar (vía Capa ACL)
    Pasarela-->>-Pagos: 200 OK {transaccion_id: "TX-999", autorizacion: "APROBADA"}
    
    Pagos->>Pagos: INSERT INTO transacciones_pago en pagos_db
    Pagos->>Broker: Publicar evento 'PagoAprobado' {pedido_id, transaccion_id: "TX-999"}
    deactivate Pagos

    %% Paso C: Confirmación de Pedido
    Broker->>+Pedidos: Evento: PagoAprobado
    Pedidos->>+PedidosDB: UPDATE pedidos SET estado='CONFIRMADO' WHERE id='PED-789'
    PedidosDB-->>-Pedidos: OK
    Pedidos->>Broker: Publicar evento 'PedidoConfirmado' {pedido_id, estado: "CONFIRMADO"}
    deactivate Pedidos

    %% Paso D: Notificación Asíncrona
    Broker->>+Notif: Evento: PedidoConfirmado
    Notif->>Notif: Despachar correo/SMS de confirmación de compra
    deactivate Notif
    end

    %% ========================================================
    %% CONSULTA DEL CLIENTE (Polling o SSE)
    %% ========================================================
    rect rgb(255, 250, 235)
    note over Cliente, BFF: ACTUALIZACIÓN DE ESTADO HACIA EL CLIENTE
    Cliente->>+BFF: GET /v1/checkout/PED-789/estado
    BFF->>+Pedidos: GET /v1/pedidos/PED-789
    Pedidos-->>-BFF: {pedido_id: "PED-789", estado: "CONFIRMADO", transaccion_id: "TX-999"}
    BFF-->>-Cliente: 200 OK {estado: "CONFIRMADO", factura_generada: true}
    end
```

---

## 3. Código Fuente Versionado en PlantUML

Para compatibilidad con compiladores estándar de PlantUML, el diagrama se encuentra versionado en [`docs/arquitectura/diagramas/secuencia-checkout.puml`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/diagramas/secuencia-checkout.puml).
