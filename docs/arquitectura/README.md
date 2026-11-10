# P11 — Arquitecto de Software: Documentación como Código

| Metadato | Detalle |
| :--- | :--- |
| **Asignatura** | Fundamentos de Arquitectura (1419) — Parcial 1 (Primer Corte) |
| **Institución** | Politécnico Internacional I.E.S. |
| **Docente** | Edgar Humberto Angel Millán |
| **Paquete Asignado** | **P11 — Arquitecto (Documentación como Código)** |
| **Estudiante** | vanesarzr1801-alt |
| **Rama Git** | `p11-arquitectura` |
| **Semanas Evaluadas** | Semana 1 y Semana 2 |
| **Indicadores Syllabus** | **1.1** (Arquitectura objetivo y responsabilidades), **1.3** (Interpretación de requerimientos), **1.4** (Modelamiento UML) |

---

## 1. Resumen Ejecutivo del Paquete P11

El paquete **P11 (Arquitecto de Software)** establece las directrices estructurales, los límites de contexto (*Bounded Contexts*) y los mecanismos de gobernanza técnica para la plataforma distribuida de comercio electrónico **PiShop Cloud**.

Siguiendo el enfoque de **Documentación como Código (Docs-as-Code)**, todos los artefactos arquitectónicos están versionados como código fuente reproducible (Markdown, PlantUML y Mermaid), acompañados de una **Fitness Function Arquitectónica** ejecutable que actúa como compuerta de calidad automatizada para prevenir la degradación hacia un monolito distribuido.

---

## 2. Mapa Integral de Entregables P11

Todos los entregables requeridos por el enunciado del Parcial 1 y la especificación de roles (`docs/ROLES.md`) están organizados en `docs/arquitectura/` y `herramientas/`:

| # | Requerimiento / Criterio | Entregable Versionado | Formato / Lenguaje |
| :---: | :--- | :--- | :--- |
| **1** | Contexto de negocio y requerimientos RF/RNF (Indicador 1.3) | [`docs/arquitectura/arquitectura-objetivo.md`](arquitectura-objetivo.md) | Markdown |
| **2** | Modelo C4 Nivel 1 (Contexto) y Nivel 2 (Contenedores) | [`docs/arquitectura/c4/`](c4/README.md)<br>• [`c4-nivel1-contexto.puml`](c4/c4-nivel1-contexto.puml) / [`.svg`](c4/c4-nivel1-contexto.svg)<br>• [`c4-nivel2-contenedores.puml`](c4/c4-nivel2-contenedores.puml) / [`.svg`](c4/c4-nivel2-contenedores.svg) | PlantUML (C4-PlantUML) + SVG renderizados |
| **3** | Subdominios DDD y Context Map con al menos 3 patrones y ACL | [`docs/arquitectura/subdominios-y-context-map.md`](subdominios-y-context-map.md) | Markdown + Mermaid (Context Map con 4 patrones) |
| **4** | Matriz ISO/IEC 25010 priorizada y 3 ADRs | [`docs/arquitectura/atributos-calidad-iso25010.md`](atributos-calidad-iso25010.md)<br>• [`ADR-001: Saga Orquestada Checkout`](adrs/ADR-001-patron-saga-orquestada-checkout.md)<br>• [`ADR-002: Persistencia Aislada Database-per-Service`](adrs/ADR-002-persistencia-aislada-database-per-service.md)<br>• [`ADR-003: Comunicación Híbrida Gateway + Broker`](adrs/ADR-003-comunicacion-hibrida-gateway-broker.md) | Markdown con plantilla estándar (Contexto, Decisión, Descartadas, Consecuencias) |
| **5** | Diagramas UML Checkout (Síncrono vs Asíncrono), Saga y Despliegue | [`docs/arquitectura/diagramas/`](diagramas/)<br>• [`secuencia-checkout.md`](diagramas/secuencia-checkout.md) / [`.puml`](diagramas/secuencia-checkout.puml)<br>• [`saga-checkout.md`](diagramas/saga-checkout.md)<br>• [`despliegue.md`](diagramas/despliegue.md) / [`.puml`](diagramas/despliegue.puml) | PlantUML y Mermaid |
| **6** | Matriz de Modos de Comunicación y Resiliencia ante Caídas | [`docs/arquitectura/matriz-comunicacion.md`](matriz-comunicacion.md) | Markdown (10 pares de servicios evaluados) |
| **7** | *Fitness Function* Arquitectónica automatizada | [`herramientas/validar_fronteras.py`](../../herramientas/validar_fronteras.py)<br>[`herramientas/test_validar_fronteras.py`](../../herramientas/test_validar_fronteras.py) | Python 3 + Fixtures de prueba |

---

## 3. Fitness Function: Gobernanza de Persistencia (Docs-as-Code)

### 3.1 Propósito
La herramienta `herramientas/validar_fronteras.py` audita de forma estática y dinámica que se cumpla estrictamente el patrón **Database-per-Service**:
- Inspecciona `docker-compose.yml`, los archivos `app/settings.py` de cada microservicio y los scripts de inicialización `infra/initdb/`.
- **Falla con código de salida 1 (`sys.exit(1)`)** si detecta que dos o más servicios intentan compartir la misma base de datos, puerto o archivo de persistencia (anti-patrón de Monolito Distribuido).
- **Termina con código de salida 0 (`sys.exit(0)`)** cuando todas las bases de datos están desacopladas y aisladas por servicio.

### 3.2 Comandos de Ejecución

```bash
# 1. Validar la arquitectura oficial del repositorio
python herramientas/validar_fronteras.py

# 2. Validar un archivo docker-compose específico
python herramientas/validar_fronteras.py --compose docker-compose.yml

# 3. Ejecutar la suite completa de pruebas automatizadas (100% estándar, compatible con pytest)
python herramientas/test_validar_fronteras.py
# o con pytest:
pytest herramientas/test_validar_fronteras.py
```

### 3.3 Evidencia de Ejecución de las Pruebas

```
======================================================================
SUITE DE PRUEBAS AUTOMATIZADAS — FITNESS FUNCTION ARQUITECTÓNICA
======================================================================

[TEST 1] Evaluando arquitectura oficial (docker-compose.yml)...
  ✔ TEST 1 PASÓ: El validador retornó exit code 0 para arquitectura aislada.

[TEST 2] Evaluando escenario con anti-patrón de BD compartida (docker-compose.invalido.yml)...
  ✔ TEST 2 PASÓ: El validador detectó exitosamente la violación y retornó exit code 1.
     Mensaje capturado del fallo:
       -> [FALLO DE COMPUERTA ARQUITECTONICA]: VIOLACION DEL PATRON DATABASE-PER-SERVICE
       -> [VIOLACION] Base de Datos Compartida: [shared-db:5432/monolito_db]
       -> >>> RESULTADO: FALLO (Codigo de salida: 1)

======================================================================
RESULTADO DE LA SUITE: 2/2 PRUEBAS PASARON EXITOSAMENTE (100%)
La Fitness Function arquitectónica opera de manera infalible.
======================================================================
```

---

## 4. Resumen de Decisiones Arquitectónicas (ADRs)

1. **ADR-001 — Saga Orquestada para el Checkout Transaccional (`P06`):**
   - *Decisión:* Orquestación centralizada en `checkout-bff` y `pedidos-service` en lugar de coreografía reactiva.
   - *Justificación:* Facilita la trazabilidad paso a paso, simplifica las compensaciones de stock y reembolsos, y evita el riesgo de dependencias cíclicas en el bus de eventos.

2. **ADR-002 — Persistencia Aislada (*Database-per-Service*):**
   - *Decisión:* Cada servicio es propietario único de su esquema y base de datos física (`catalogo_db`, `inventario_db`, `pedidos_db`, `pagos_db`, etc.).
   - *Justificación:* Previene el acoplamiento a nivel de datos y elimina bloqueos de contención inter-dominio. Protegido en CI por `validar_fronteras.py`.

3. **ADR-003 — Topología de Comunicación Híbrida (Gateway + Broker):**
   - *Decisión:* Ingress y consultas críticas por HTTP/REST sincrónico de baja latencia; propagación de estado (`PedidoCreado`, `PagoAprobado`) por mensajería asíncrona desacoplada con RabbitMQ.
   - *Justificación:* Garantiza escalabilidad horizontal en los consumidores (`notificaciones-service`, `reportes-service`) y alta disponibilidad en compras.

---

## 5. Declaración de Uso de Inteligencia Artificial Generativa

En cumplimiento con el numeral 7 del `docs/ENUNCIADO.md` y las políticas de integridad académica del curso:

- **Asistencia recibida:** Se empleó un modelo de IA generativa para la estructuración y estandarización del código PlantUML (macros C4-PlantUML), la conversión a formato vectorial SVG interactivo (`render_c4.py`), y la redacción formal de los esquemas de ADR según la plantilla Michael Nygard.
- **Verificación y validación humana:**
  - Se contrastaron cada uno de los puertos (`8000` a `8090`) y servicios contra la especificación contractual oficial de `contracts/endpoints.json` y `docs/CONTRATOS.md`.
  - Se codificó y probó manualmente la suite de pruebas unitarias y de integración de la fitness function (`herramientas/validar_fronteras.py` y `herramientas/test_validar_fronteras.py`), certificando el retorno de código `0` en arquitectura conforme y `1` ante la presencia de anti-patrones.
  - Se garantizó que ningún archivo ni variable sensible (`.env`, secretos, contraseñas) forme parte del control de versiones.
