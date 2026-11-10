# ADR-003: Esquema de Comunicación Híbrida: REST Síncrono en Ingress y Event-Driven AMQP en el Núcleo

| Campo | Valor |
| :--- | :--- |
| **Identificador** | ADR-003 |
| **Estado** | **Aceptado / En Producción** |
| **Fecha** | Noviembre 2026 |
| **Autor / Rol** | P11 — Arquitecto de Software |
| **Contexto Técnico** | Protocolos y mecanismos de comunicación inter-servicios y clientes externos |

---

## 1. Contexto y Planteamiento del Problema
Un sistema de comercio digital moderno enfrenta dos requerimientos contradictorios:
1. **Inmediatez en la Experiencia de Usuario:** Los clientes esperan respuestas HTTP rápidas e intuitivas al navegar productos y al confirmar su orden de compra (latencia imperceptible $< 200\text{ ms}$).
2. **Resiliencia y Procesamiento Pesado en Segundo Plano:** El procesamiento de pagos, la reserva y sincronización de inventario, el despacho de correos y la generación de reportes analíticos requieren tiempo, interactúan con redes de terceros (bancos, APIs de correo) y sufren fluctuaciones impredecibles de latencia.

Si todos los servicios se comunican de forma síncrona encadenada, la latencia total es la suma acumulada de todos los saltos de red y el fallo de un solo servicio secundario bloquea toda la compra. Por otro lado, un modelo 100% asíncrono para todas las operaciones impediría al usuario saber de inmediato si su pedido fue recibido formalmente.

---

## 2. Decisión Adoptada
Se decide implementar un **Esquema de Comunicación Híbrida**:

1. **Comunicación Síncrona (HTTP/REST) en la Periferia e Ingress:**
   - La interacción del cliente con `api-publica` (8000) y `checkout-bff` (8080) se realiza mediante **HTTP/REST síncrono sobre HTTPS/JSON**.
   - La llamada de checkout (`POST /v1/checkout`) se despacha de forma síncrona a `pedidos-service` (`POST /v1/pedidos`), donde se valida la orden, se almacena en estado preliminar `PENDIENTE_PAGO` y se retorna de inmediato un código **HTTP 202 Accepted** con el identificador del pedido (`pedido_id`) en menos de $200\text{ ms}$.
   - La consulta de vitrina (`GET /v1/vitrina`) y catálogo (`GET /v1/productos`) se resuelve de manera síncrona para entrega inmediata.
2. **Comunicación Asíncrona (Event-Driven AMQP) en el Núcleo y Saga:**
   - Una vez persistido el pedido preliminar, `pedidos-service` emite un evento de dominio (`PedidoCreado`) a través del broker de mensajería **RabbitMQ 3.13 (protocolo AMQP 0-9-1)** utilizando el patrón *Transactional Outbox*.
   - Los servicios downstream (`inventario-service`, `pagos-service`, `notificaciones-service`, `reportes-service`) consumen los eventos desde sus colas dedicadas, desacoplados temporalmente.
   - Las transacciones compensatorias de la Saga (`POST /v1/reservas/{id}/liberar`, `POST /v1/pagos/{id}/reembolso`) y las notificaciones se coordinan asíncronamente a través del bus de eventos con colas de reintento y colas de mensajes no procesables (*Dead Letter Queues - DLQ*).

---

## 3. Alternativas Descartadas

### Alternativa Descartada 1: Arquitectura 100% Síncrona en Cascada (Cascading REST)
- **Descripción:** El cliente llama al Gateway; el Gateway llama al BFF; el BFF llama en cascada síncrona a `pedidos-service`, este llama a `inventario-service`, luego a `pagos-service`, este a la pasarela bancaria y finalmente a `notificaciones-service`, esperando todas las respuestas antes de contestar al cliente.
- **Razón del Descarte:**
  - **Efecto dominó de fallos y fragilidad extrema:** Si `notificaciones-service` está saturado o caído, la compra completa del cliente falla, aun cuando el pago hubiera sido aprobado.
  - **Latencia inaceptable:** La latencia acumulada superaría fácilmente los $1500 - 3000\text{ ms}$, violando el RNF-01 (latencia $P_{95} \le 200\text{ ms}$).
  - **Agotamiento del pool de hilos:** En horas pico, los clientes mantienen conexiones HTTP abiertas esperando a la pasarela externa, agotando los descriptores de sockets del Gateway y provocando caídas masivas del sistema.

### Alternativa Descartada 2: Arquitectura 100% Asíncrona con Kafka para Todas las Operaciones
- **Descripción:** Todo tráfico (incluso la navegación del catálogo de productos y la consulta de estado de pedidos) se modela como eventos en topics de Apache Kafka.
- **Razón del Descarte:**
  - **Sobrecarga de complejidad innecesaria:** Para consultas idempotentes de solo lectura (como `GET /v1/productos` o `/health/live`), una arquitectura basada exclusivamente en tópicos requiere implementar flujos complejos de *request-reply* asíncrono con *correlation IDs* en el navegador.
  - **Costos operativos desproporcionados:** Operar un clúster de Apache Kafka con ZooKeeper o KRaft excede las necesidades y los recursos de desarrollo del proyecto en comparación con la ligereza de RabbitMQ.

---

## 4. Trade-offs y Consecuencias

### Consecuencias Positivas (Beneficios)
- **Excelente Experiencia de Usuario:** El cliente experimenta una respuesta instantánea al enviar su orden de checkout ($< 200\text{ ms}$), sabiendo que su pedido fue recibido y está en proceso.
- **Absorción Eficiente de Picos de Demanda (*Buffering*):** Durante campañas de alta concurrencia, las compras se encolan en RabbitMQ sin saturar ni tumbar los servicios de inventario o la pasarela de pagos.
- **Tolerancia a Caídas de Destino:** Si el microservicio de notificaciones o el de reportes colapsa, los mensajes quedan retenidos de forma segura en las colas persistentes de RabbitMQ y se procesan automáticamente cuando el servicio se recupera.

### Consecuencias Negativas y Mitigaciones
- **Mantenimiento de Infraestructura Adicional:** Se requiere desplegar y monitorear el broker RabbitMQ y gestionar sus colas.
  - *Mitigación:* Se utiliza la imagen oficial `rabbitmq:3.13-management-alpine` con interfaz de administración web en el puerto 15672 y monitoreo automatizado de sondas de salud.
- **Complejidad de Monitoreo Distribuido:** El flujo de una orden transita entre HTTP y eventos AMQP.
  - *Mitigación:* Se propaga un encabezado unificado de trazabilidad (`X-Correlation-ID`) en todas las cabeceras HTTP y propiedades de los mensajes AMQP para correlacionar logs de punta a punta.
