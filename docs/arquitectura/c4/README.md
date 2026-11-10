# Modelo C4 — Diagramas de Contexto y Contenedores

| Metadato | Detalle |
| :--- | :--- |
| **Rol / Autor** | P11 — Arquitecto de Software |
| **Proyecto** | `fundamentos_arquitectura_politecnico` |
| **Entregable** | C4 Nivel 1 y Nivel 2 en PlantUML (código versionado + imágenes renderizadas) |
| **Herramientas** | PlantUML, C4-PlantUML Library, SVG Rendering Engine |

---

## 1. Nivel 1: Diagrama de Contexto del Sistema

El diagrama de contexto define los límites del sistema distribuido de comercio electrónico, sus usuarios primarios y las integraciones con plataformas externas indispensables para la operación del negocio.

### Código Fuente Versionado
- Archivo PlantUML: [`c4-nivel1-contexto.puml`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/c4/c4-nivel1-contexto.puml)

### Imagen Renderizada
![C4 Nivel 1 - Contexto](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/c4/c4-nivel1-contexto.svg)

### Elementos Principales:
- **Cliente / Comprador:** Usuario final que interactúa con la vitrina de productos, añade artículos al carrito e inicia el flujo de checkout.
- **Operador de Finanzas y Analítica:** Personal interno encargado de monitorear transacciones, auditar pagos y supervisar métricas comerciales.
- **Plataforma Distribuida (Sistema Central):** Agrupa los microservicios transaccionales y de soporte (Roles P01 a P10).
- **Pasarela de Pagos Externa (Stripe / PSE / Simulador):** Entidad encargada del procesamiento financiero y autorización de cobros.
- **Proveedor de Notificaciones:** Infraestructura de comunicación multicanal (Email / SMS transaccional).
- **ERP Contable / DIAN Legado:** Sistema institucional para registro contable y fiscal.

---

## 2. Nivel 2: Diagrama de Contenedores

El diagrama de contenedores describe la arquitectura interna de la plataforma, detallando las responsabilidades de cada contenedor de software, los puertos fijados en el contrato, sus almacenes de datos dedicados (*Database-per-Service*) y los protocolos de red utilizados.

### Código Fuente Versionado
- Archivo PlantUML: [`c4-nivel2-contenedores.puml`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/c4/c4-nivel2-contenedores.puml)

### Imagen Renderizada
![C4 Nivel 2 - Contenedores](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/c4/c4-nivel2-contenedores.svg)

### Detalle de Contenedores y Asignación de Roles / Puertos:

| Contenedor | Rol | Puerto | Tecnología | Responsabilidad y Persistencia |
| :--- | :--- | :--- | :--- | :--- |
| **`api-publica`** | P07 | `8000` | FastAPI / Python | Gateway de entrada para compras y catálogo público. |
| **`checkout-bff`** | P06 | `8080` | FastAPI / Python | Backend for Frontend para orquestar la experiencia de checkout y vitrina. |
| **`catalogo-service`** | P01 | `8001` | FastAPI + PostgreSQL | Gestión y publicación de SKUs. Persistencia aislada en `catalogo_db`. |
| **`inventario-service`**| P02 | `8002` | FastAPI + PostgreSQL | Control de stock físico y reservas de SKUs. Persistencia aislada en `inventario_db`. |
| **`pedidos-service`** | P03 | `8003` | FastAPI + PostgreSQL | Ciclo de vida de órdenes, orquestador de Saga y Outbox. Persistencia en `pedidos_db`. |
| **`pagos-service`** | P04 | `8004` | FastAPI + PostgreSQL | Liquidación de cobros, Capa Anti-Corrupción (ACL) e idempotencia. Persistencia en `pagos_db`. |
| **`notificaciones-service`** | P05 | `8005` | FastAPI + PostgreSQL | Envío asíncrono de correos y alertas. Persistencia en `notificaciones_db`. |
| **`reportes-service`** | P10 | `8006` | FastAPI + PostgreSQL | Analítica CQRS y proyecciones de ventas. Persistencia en `reportes_db`. |
| **`config-service`** | P08 | `8010` | FastAPI + PostgreSQL | Servicio centralizado de configuración con rollback. Persistencia en `config_db`. |
| **`descubridor-service`**| P09 | `8090` | FastAPI / In-Memory | Registro dinámico de instancias y resolución de red inter-servicios. |
| **`rabbitmq`** | Infra | `5672` / `15672` | RabbitMQ (AMQP 0-9-1) | Bus de eventos asíncronos para la coordinación de la Saga y desacoplamiento temporal. |

---

## 3. Conformidad con Sondas de Salud
Cada uno de los contenedores implementa de forma obligatoria los endpoints de observabilidad:
- `/health/live` (Liveness)
- `/health/ready` (Readiness con validación de persistencia y broker)
- `/health/startup` (Startup probe)
