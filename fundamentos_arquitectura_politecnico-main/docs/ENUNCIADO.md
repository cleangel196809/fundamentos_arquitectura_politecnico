# Parcial 1 — Primer corte (15 % de la nota final)

**Curso:** Fundamentos de Arquitectura (1419) · Ciclo VIII · Politécnico Internacional I.E.S.
**Docente:** Edgar Humberto Angel Millán
**Caso:** PiShop Cloud · **Contenidos:** semanas 1 a 4
**Modalidad:** individual dentro de un sistema común (12 paquetes de trabajo)
**Entrega:** martes **10 de noviembre de 2026, 13:00** (hora de Bogotá)

## 1. Propósito

Construir entre los 12 estudiantes el sistema PiShop Cloud: cada uno desarrolla las APIs (o el artefacto) de **un** paquete asignado por ruleta, respetando los contratos de `docs/CONTRATOS.md`. El resultado integrado debe levantarse con `docker compose up -d`.

## 2. Contenidos evaluados

| Semana | Contenido que debe evidenciarse |
|---|---|
| 1 | Atributos de calidad ISO/IEC 25010, trade-offs, C4 y UML, cuándo no usar microservicios, monolito distribuido |
| 2 | Partición vertical/horizontal, DDD y bounded contexts, tríada core/compuesto/API, BFF, ACL |
| 3 | Cubo de escalabilidad, síncrono vs asíncrono, saga, Outbox, CQRS, idempotencia, disponibilidad compuesta, timeouts |
| 4 | Configuración externalizada (factor III), config-service con ETag, registro y descubrimiento, sondas live/ready/startup |

## 3. Flujo de trabajo en GitHub

1. Hacer **fork** del repositorio público y clonarlo.
2. Crear la rama `pXX-nombre` (por ejemplo `p03-pedidos`) y trabajar **solo** en su carpeta.
3. Commits convencionales: `feat(s3): publicador outbox`, `test(s2): paginacion`, `docs(s4): descubrimiento`.
4. Verificar con `python herramientas/validar_entrega.py <su-servicio>`.
5. Abrir un **Pull Request** hacia `main` con el título `[PXX] <nombre completo> — <paquete>`.
6. El último commit del PR debe tener fecha **anterior al 10/11/2026 13:00**. Después de esa hora se aplica el descuento de 20 % por día (política del curso).

## 4. Cronograma sugerido

| Fecha | Hito |
|---|---|
| Lun 02/11 | Sorteo por ruleta y lectura de contratos |
| Mar 03/11 | Fork, rama, plantilla copiada, contrato entendido; dudas al docente |
| Jue 05/11 | Endpoints del contrato respondiendo (aunque sea con datos simulados) |
| Sáb 07/11 | Pruebas `pytest`, idempotencia/resiliencia propias del paquete, README |
| Lun 09/11 | Integración con compañeros (P12 coordina), PR abierto |
| Mar 10/11 13:00 | **Cierre de entregas** |
| Mar 10/11 | Sustentación individual de 5 minutos |

## 5. Entregable mínimo de cada estudiante

- Su carpeta con el código (o documentos) del paquete, dentro de `services/` o `docs/` según el rol.
- `README.md` del paquete: cómo ejecutarlo, tabla de configuración `PISHOP_*`, decisiones y **evidencia** (salida de `curl`, `pytest` o capturas).
- Pruebas `pytest` que pasen sin servicios externos (SQLite y bus en memoria).
- Declaración de uso de IA generativa, si la utilizó (qué parte y qué verificó).

## 6. Rúbrica (100 puntos = 5,0)

| Criterio | Peso | Qué se evalúa |
|---|---|---|
| A. Cumplimiento del contrato | 40 | Todos los endpoints del contrato existen y se comportan como se describe (`validar_entrega.py` + casos de `CONTRATOS.md`) |
| B. Calidad arquitectónica | 20 | Base propia, configuración externalizada con `SecretStr`, tres sondas con semántica correcta, timeouts explícitos, idempotencia o compensación según el rol |
| C. Pruebas y evidencia | 15 | Pruebas `pytest` significativas y evidencia reproducible en el README |
| D. Integración | 10 | El sistema levanta con `docker compose up -d` y pasa el flujo de compra (nota compartida por el grupo) |
| E. Git y entrega a tiempo | 5 | PR correcto, commits convencionales, entrega antes de las 13:00 |
| F. Sustentación individual | 10 | Explica sus decisiones y modifica algo en vivo; valida autoría |

**Aprobación institucional:** 3,0. Un paquete que no arranca limita el criterio A a la mitad.

### Relación con los indicadores del syllabus

- **1.1** criterios de arquitectura objetivo y responsabilidades: P01, P04, P07, P11.
- **1.2** escalamiento en la nube: P02, P03, P05, P08, P09, P10, P12.
- **1.3** interpretación de requerimientos del cliente: P06, P11.
- **1.4** modelamiento UML: P11 y los diagramas del README de cada paquete.

## 7. Honestidad académica

El trabajo es individual dentro de su paquete. Copiar el código de un compañero o permitir la copia es falta académica. El uso de asistentes de IA debe **declararse**; la sustentación oral y el historial de commits sirven para verificar la autoría. Una autoría no verificable en la sustentación reduce los criterios A y F.
