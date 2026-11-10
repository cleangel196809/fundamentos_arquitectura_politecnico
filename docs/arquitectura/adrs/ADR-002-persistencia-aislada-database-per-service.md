# ADR-002: Adopción del Patrón Database-per-Service para Aislamiento de Persistencia

| Campo | Valor |
| :--- | :--- |
| **Identificador** | ADR-002 |
| **Estado** | **Aceptado / En Producción** |
| **Fecha** | Noviembre 2026 |
| **Autor / Rol** | P11 — Arquitecto de Software |
| **Contexto Técnico** | Persistencia de datos para los servicios P01 a P10 y regla de aptitud arquitectónica (*fitness function*) |

---

## 1. Contexto y Planteamiento del Problema
En el desarrollo de arquitecturas empresariales, uno de los anti-patrones más destructivos es el **"Monolito de Base de Datos"** (múltiples microservicios conectados a una misma base de datos relacional compartida). Cuando los servicios comparten tablas o instancias de base de datos:
1. Se crean dependencias ocultas a nivel de esquema relacional; modificar una columna o una clave foránea en la tabla de pagos rompe inadvertidamente el servicio de pedidos o el de reportes.
2. Se generan cuellos de botella de concurrencia y bloqueos mutuos (*deadlocks*) entre transacciones de dominios completamente ajenos.
3. Se viola el principio de bounded context de DDD, ya que los límites lógicos se diluyen en consultas SQL directas con sentencias `JOIN`.
4. El escalamiento y la seguridad no pueden aislarse: un compromiso de seguridad en el catálogo expondría las tablas de transacciones financieras.

---

## 2. Decisión Adoptada
Se decide adoptar de manera estricta e irrevocable el **Patrón Database-per-Service (Base de Datos por Servicio)**:

1. **Instancias y Esquemas Completamente Aislados:**
   - `catalogo-service` posee en exclusiva `catalogo_db` (PostgreSQL 16).
   - `inventario-service` posee en exclusiva `inventario_db` (PostgreSQL 16).
   - `pedidos-service` posee en exclusiva `pedidos_db` (PostgreSQL 16).
   - `pagos-service` posee en exclusiva `pagos_db` (PostgreSQL 16).
   - `notificaciones-service` posee en exclusiva `notificaciones_db` (PostgreSQL 16).
   - `reportes-service` posee en exclusiva `reportes_db` (PostgreSQL 16).
   - `config-service` posee en exclusiva `config_db` (PostgreSQL 16).
2. **Prohibición de Acceso Directo Cruzado:**
   - Ningún servicio puede conectarse, leer o escribir en la base de datos de otro servicio.
   - Toda interacción y consumo de datos entre dominios debe realizarse a través de APIs REST expuestas o mediante la publicación y suscripción de eventos asíncronos en RabbitMQ.
3. **Gobernanza Automatizada (*Fitness Function*):**
   - Se incorpora en el pipeline de integración continua el script `herramientas/validar_fronteras.py`, el cual analiza los archivos de configuración (`docker-compose.yml`, variables de entorno, cadenas de conexión).
   - Si dos servicios comparten la misma base de datos, el script **falla inmediatamente con código de salida `1`**, impidiendo la integración del código defectuoso.

---

## 3. Alternativas Descartadas

### Alternativa Descartada 1: Base de Datos Única Compartida (Shared Database Pattern)
- **Descripción:** Un único clúster PostgreSQL centralizado donde todos los servicios leen y escriben en tablas comunes (`public.pedidos`, `public.pagos`, `public.stock`).
- **Razón del Descarte:**
  - Acoplamiento severo en tiempo de despliegue: los equipos no pueden realizar migraciones de base de datos de forma autónoma.
  - Imposibilidad de garantizar el indicador de disponibilidad (99.9%): la saturación de conexiones causada por una consulta analítica pesada de reportes degradaría las transacciones de cobro en tiempo real.
  - Violación directa del rol del arquitecto y de las buenas prácticas de microservicios.

### Alternativa Descartada 2: Instancia Única de Base de Datos con Esquemas Separados y Permisos
- **Descripción:** Una sola instancia PostgreSQL con esquemas aislados (`schema_pedidos`, `schema_pagos`) y usuarios con permisos restringidos.
- **Razón del Descarte:**
  - Aunque mejora el aislamiento lógico, persiste el acoplamiento físico a nivel de recursos de cómputo (CPU, I/O de disco, memoria y saturación del pool de conexiones del motor PostgreSQL).
  - Riesgo latente de que un desarrollador ejecute un grant permisivo y cruce esquemas con sentencias `SELECT ... FROM schema_pedidos.pedidos JOIN schema_pagos.transacciones`, corrompiendo la arquitectura.

---

## 4. Trade-offs y Consecuencias

### Consecuencias Positivas (Beneficios)
- **Autonomía Total de Despliegue y Migración:** Cada equipo puede modificar esquemas, ejecutar migraciones (Alembic / Flyway) o alterar índices sin coordinar ventanas de mantenimiento con otros equipos.
- **Escalabilidad Elástica e Independiente:** Es posible dimensionar y optimizar la base de datos de inventario con alta capacidad de lectura, y la de pagos con almacenamiento SSD de alta resistencia a escrituras transaccionales.
- **Aislamiento de Fallos y Seguridad Reforzada:** Un bloqueo o corrupción en `reportes_db` tiene impacto cero en la persistencia transaccional de `pedidos_db` o `pagos_db`.

### Consecuencias Negativas y Mitigaciones
- **Pérdida de `JOINs` SQL Relacionales Directos:** No es posible consultar en una sola sentencia SQL los datos de un pedido, su cliente y su estado de cobro.
  - *Mitigación:* Se implementa el patrón **CQRS** en `reportes-service` (8006), el cual proyecta y desnormaliza los datos que necesita consumiendo eventos del bus de mensajería.
- **Mayor Costo y Sobrecarga Operativa de Infraestructura:** Se administran múltiples contenedores o instancias de PostgreSQL.
  - *Mitigación:* En desarrollo y pruebas se orquestan mediante `docker-compose.yml` con volúmenes persistentes aislados; en producción se utilizan clústeres gestionados (Cloud SQL / RDS).
