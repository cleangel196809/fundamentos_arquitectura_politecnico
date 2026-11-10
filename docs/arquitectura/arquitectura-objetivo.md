# Arquitectura Objetivo — Plataforma Distribuida de Comercio y Pagos

| Metadato | Detalle |
| :--- | :--- |
| **Rol / Autor** | **P11 — Arquitecto de Software (Documentación como Código)** |
| **Proyecto** | `fundamentos_arquitectura_politecnico` |
| **Indicador Evaluado** | **Indicador 1.3: Contexto de Negocio y Requerimientos Arquitectónicos** |
| **Versión** | 1.0.0 (Aprobada) |
| **Fecha de Publicación** | Noviembre 2026 |

---

## 1. Contexto del Negocio

### 1.1 Visión General
El proyecto **fundamentos_arquitectura_politecnico** responde a la necesidad de diseñar, estructurar y documentar una plataforma moderna de comercio digital distribuida, de alto rendimiento y resiliente. En los ecosistemas modernos de retail y compras en línea, los sistemas centralizados monolíticos colapsan ante picos de demanda masiva (eventos de alta concurrencia, promociones relámpago, etc.) debido a la contención en una única base de datos, el acoplamiento temporal y la cascada de fallas.

La **Arquitectura Objetivo** adopta un paradigma de **Microservicios Guiados por el Dominio (Domain-Driven Design - DDD)** y **Arquitectura Dirigida por Eventos (EDA)**, donde cada subdominio del negocio está modelado como un servicio independiente con su propia persistencia (*Database-per-Service*). El rol del **P11 (Arquitecto)** garantiza la gobernanza técnica a través de la **Documentación como Código (Docs-as-Code)** y funciones de aptitud automáticas (*fitness functions*) ejecutadas en integración continua.

### 1.2 Mapa de Roles y Servicios del Sistema

| Rol | Servicio | Puerto | Responsabilidad Primaria | Persistencia / Tipo |
| :--- | :--- | :--- | :--- | :--- |
| **P01** | `catalogo-service` | `8001` | Catálogo de productos, categorización y publicación de SKUs | `catalogo_db` (PostgreSQL) |
| **P02** | `inventario-service`| `8002` | Control de stock físico y gestión de reservas atómicas | `inventario_db` (PostgreSQL) |
| **P03** | `pedidos-service` | `8003` | Ciclo de vida de órdenes, orquestador de Saga y patrón Outbox | `pedidos_db` (PostgreSQL) |
| **P04** | `pagos-service` | `8004` | Transacciones de pago, cobros externos simulados y Capa ACL | `pagos_db` (PostgreSQL) |
| **P05** | `notificaciones-service` | `8005` | Despacho multicanal asíncrono de eventos de orden | `notificaciones_db` (PostgreSQL) |
| **P06** | `checkout-bff` | `8080` | Backend for Frontend para orquestar la experiencia de checkout | Stateless (In-Memory Cache) |
| **P07** | `api-publica` | `8000` | Ingress público para navegación de catálogo y compras | Gateway / Reverse Proxy |
| **P08** | `config-service` | `8010` | Centralización y versionado de variables de entorno y configs | `config_db` (PostgreSQL) |
| **P09** | `descubridor-service` | `8090` | Service Registry & Discovery dinámico para resolución de red | In-Memory Registry |
| **P10** | `reportes-service` | `8006` | Consolidación analítica y proyecciones de ventas (CQRS) | `reportes_db` (PostgreSQL) |
| **P11** | **Arquitecto (Docs-as-Code)** | `N/A` | **Diseño arquitectónico, gobernanza C4, ADRs y Fitness Functions** | Repositorio / CI Pipeline |

### 1.3 Contrato de Sondas de Salud Obligatorias
Cada microservicio implementa de forma obligatoria las tres sondas estándar de observabilidad y ciclo de vida de contenedores (Kubernetes/Docker Ready):
1. **`/health/live` (Liveness Probe):** Verifica que el proceso del servicio esté activo y respondiendo solicitudes HTTP.
2. **`/health/ready` (Readiness Probe):** Verifica que las dependencias críticas (base de datos dedicada, conexión con RabbitMQ) estén operativas antes de recibir tráfico de red.
3. **`/health/startup` (Startup Probe):** Protege servicios de inicialización lenta durante migraciones de esquema o carga inicial.

---

## 2. Requerimientos del Sistema (Indicador 1.3)

### 2.1 Requerimientos Funcionales (RF)

| ID | Nombre | Descripción Funcional | Componentes Involucrados |
| :--- | :--- | :--- | :--- |
| **RF-01** | **Vitrina y Consulta de Catálogo** | El cliente puede navegar por los productos disponibles filtrados por SKU y categorías sin bloqueo de transacciones. | `api-publica` (8000), `checkout-bff` (8080), `catalogo-service` (8001) |
| **RF-02** | **Inicio Rápido de Checkout (Síncrono)** | El usuario envía la orden de compra mediante `POST /v1/checkout`. El sistema valida la solicitud, crea el pedido en estado preliminar `PENDIENTE_PAGO` y retorna una confirmación inmediata con HTTP 202 en $< 200\text{ ms}$. | `checkout-bff` (8080), `pedidos-service` (8003) |
| **RF-03** | **Reserva Transaccional de Stock** | Durante el checkout se reserva el stock de cada SKU vía `POST /v1/reservas`. Si el inventario es insuficiente, se cancela la operación de forma atómica. | `inventario-service` (8002) |
| **RF-04** | **Cobro y Liquidación con Pasarela Externa** | Se ejecuta el débito bancario vía `POST /v1/pagos` contra `/_simulador/pasarela/cobrar`. Si la pasarela aprueba, se confirma el pago; si rechaza, se inicia compensación. | `pagos-service` (8004) |
| **RF-05** | **Compensación Automática (Saga Rollback)** | Si el cobro falla o el pedido es cancelado vía `POST /v1/pedidos/{id}/cancelar`, el sistema libera automáticamente la reserva mediante `POST /v1/reservas/{reserva_id}/liberar` o reembolsa con `POST /v1/pagos/{pago_id}/reembolso`. | `pedidos-service` (8003), `inventario-service` (8002), `pagos-service` (8004) |
| **RF-06** | **Notificación Asíncrona al Cliente** | Envío de confirmaciones por correo o mensaje sin bloquear el hilo principal de procesamiento transaccional. | `notificaciones-service` (8005) |
| **RF-07** | **Reportes Analíticos CQRS Desacoplados** | Emisión de resúmenes de venta y ventas por SKU vía `GET /v1/reportes/resumen` sin realizar lecturas pesadas sobre la base transaccional de pedidos. | `reportes-service` (8006) |

### 2.2 Requerimientos No Funcionales (RNF) — ISO/IEC 25010

| ID | Atributo ISO 25010 | Requerimiento No Funcional | Métrica / Criterio de Éxito |
| :--- | :--- | :--- | :--- |
| **RNF-01** | **Eficiencia de Desempeño (Latencia)** | La respuesta inicial de recepción de checkout en `POST /v1/checkout` debe ser inmediata para garantizar excelente UX. | Latencia percentil $P_{95} \le 200\text{ ms}$. |
| **RNF-02** | **Fiabilidad (Disponibilidad y Tolerancia a Fallos)** | El fallo de servicios secundarios (notificaciones o reportes) no debe interrumpir el flujo de compra. | Uptime del cluster $\ge 99.9\%$. Dead-Letter Queues (DLQ) para reintentos. |
| **RNF-03** | **Seguridad (Aislamiento de Persistencia)** | Principio estricto de *Database-per-Service*. Ningún servicio puede consultar directamente la base de datos de otro. | Cero violaciones detectadas por `herramientas/validar_fronteras.py` (código de salida 0). |
| **RNF-04** | **Mantenibilidad (Contratos Abiertos y Estandarizados)** | Cada microservicio debe exponer su especificación contractual en `/openapi.json` con sus rutas, tipos de datos y sondas de salud. | 100% de cumplimiento contractual validado contra `contratos/contrato_servicios.json`. |
| **RNF-05** | **Portabilidad y Despliegue Automatizado** | Toda la arquitectura debe ser ejecutable localmente mediante contenedores Docker y orquestación unificada. | `docker-compose up -d` despliega el 100% del ecosistema funcional sin dependencias manuales. |

---

## 3. Restricciones Técnicas y Principios de Diseño

1. **Aislamiento Estricto de Persistencia:** Cada servicio posee sus propias credenciales, base de datos y esquema relacional. Se prohíben *cross-database queries* o *foreign keys* físicas inter-servicio.
2. **Gobernanza Automatizada (Fitness Function):** El script `herramientas/validar_fronteras.py` actúa como compuerta de calidad arquitectónica en el pipeline, abortando la integración si dos servicios comparten base de datos.
3. **Desacoplamiento Temporal mediante Sagas:** El checkout no utiliza transacciones de bloqueo distribuido (Two-Phase Commit / 2PC) para evitar contención, adoptando el patrón Saga con transacciones compensatorias.
4. **Capa Anti-Corrupción (ACL) en Pagos:** El microservicio de pagos (`P04`) aísla su modelo de dominio de los contratos volátiles y esquemas externos de la pasarela mediante un adaptador ACL explícito.

---

## 4. Estructura de la Documentación como Código

| Componente | Descripción | Enlace al Artefacto |
| :--- | :--- | :--- |
| **C4 Modelo Nivel 1 y 2** | Diagramas de Contexto y Contenedores en PlantUML + SVG Renderizado | [`docs/arquitectura/c4/`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/c4/README.md) |
| **DDD & Context Map** | Tabla de Subdominios (Core, Soporte, Genérico), Context Map Mermaid y ACL Justificada | [`subdominios-y-context-map.md`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/subdominios-y-context-map.md) |
| **ISO/IEC 25010 y ADRs** | Matriz de Atributos de Calidad y 3 Architecture Decision Records (ADR) | [`atributos-calidad-iso25010.md`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/atributos-calidad-iso25010.md) |
| **Diagramas de Secuencia** | Secuencia de Checkout Síncrono vs Asíncrono, Saga Mermaid y Despliegue | [`docs/arquitectura/diagramas/`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/diagramas/) |
| **Matriz de Comunicación** | Modos síncronos/asíncronos, protocolos y tolerancia ante caídas de destino | [`matriz-comunicacion.md`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/docs/arquitectura/matriz-comunicacion.md) |
| **Fitness Function** | Script ejecutable en Python para verificar fronteras de persistencia | [`herramientas/validar_fronteras.py`](file:///c:/Users/LENOVO/Documents/SimuladorTrafico/herramientas/validar_fronteras.py) |
