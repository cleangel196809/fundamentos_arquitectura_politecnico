# PiShop Cloud — sistema completo (Parcial 1)

Fundamentos de Arquitectura (1419) · Politécnico Internacional I.E.S. · Docente: Edgar Humberto Angel Millán

PiShop Cloud es la tienda en línea de una PYME agropecuaria colombiana, partida en **10 microservicios FastAPI** que se levantan con un solo comando. Cada servicio core tiene **su propia base PostgreSQL 17** (6 bases, 6 usuarios distintos), los eventos viajan por **Redis 8 Streams**, los servicios se registran en **Consul** y toda la configuración entra por variables de entorno.

**Entrega: martes 10 de noviembre de 2026, 13:00 (hora de Bogotá).**

---

## 1. Requisitos previos

| Herramienta | Versión | Para qué |
|---|---|---|
| Docker Desktop (Windows) | con Compose v2 ≥ 2.24 | levantar todo el sistema |
| Python | 3.13 (sirve 3.11+) | scripts de datos, pruebas y validadores |

Los scripts de `scripts/` **solo usan la biblioteca estándar**: no hay que instalar nada para ejecutarlos.

## 2. Arranque paso a paso (Windows, `cmd`)

```bat
cd C:\Users\<usuario>\Downloads\fundamentos_arquitectura_politecnico-main

:: 1) Crear el .env con contraseñas aleatorias (o: copy .env.example .env)
python scripts\generar_env.py

:: 2) Construir y levantar los 13 contenedores (la primera vez tarda 3-6 min)
docker compose up -d --build

:: 3) Ver que todo esté "healthy"
docker compose ps

:: 4) Prueba de punta a punta (compra feliz + pago rechazado con compensaciones)
python scripts\prueba_e2e.py

:: 5) Llenar las bases con compras ficticias (respeta el límite de 40/min)
python scripts\generar_datos.py --con-rechazos
```

Atajo: doble clic en **`iniciar.bat`** (hace los pasos 1 a 3). Para apagar: **`detener.bat`** (o `detener.bat borrar` para borrar también las bases).

## 3. Puertos y direcciones

| Servicio | Puerto | Tipo | Base de datos (usuario) | Abierto a |
|---|---|---|---|---|
| api-publica | **8000** | API (fachada) | — | **la red** (única puerta de entrada) |
| catalogo-service | 8001 | Core | `pg_catalogo` (`usr_catalogo`) | solo este PC |
| inventario-service | 8002 | Core | `pg_inventario` (`usr_inventario`) | solo este PC |
| pedidos-service | 8003 | Core + Outbox | `pg_pedidos` (`usr_pedidos`) | solo este PC |
| pagos-service | 8004 | Core + ACL | `pg_pagos` (`usr_pagos`) | solo este PC |
| notificaciones-service | 8005 | Core (consumidor) | `pg_notif` (`usr_notif`) | solo este PC |
| reportes-service | 8006 | Core (CQRS) | `pg_reportes` (`usr_reportes`) | solo este PC |
| checkout-bff | 8080 | Compuesto (saga) | — | solo este PC |
| config-service | 8010 | Soporte | — (versionado en memoria) | solo este PC |
| descubridor-service | 8090 | Soporte | — (consulta Consul) | solo este PC |
| Consul (UI) | 8500 | Infra | — | solo este PC |
| PostgreSQL 17 | **5433** → 5432 | Infra | 6 bases | solo este PC |
| Redis 8 | **6380** → 6379 | Infra | stream `pishop.pedidos` | solo este PC |

"Solo este PC" = publicado en `127.0.0.1`: usted puede probar con `curl`, el navegador o DataGrip, pero nadie más en la red Wi-Fi lo alcanza. PostgreSQL y Redis usan 5433 y 6380 en el anfitrión para no chocar con instalaciones locales (se cambian en `.env`).

- Documentación interactiva de cada servicio: `http://localhost:<puerto>/docs`
- Consul: `http://localhost:8500`
- Para cerrar TODO excepto el 8000: `docker compose -f docker-compose.yml -f docker-compose.seguro.yml up -d`

## 4. Flujo principal (con `curl` en cmd)

```bat
set K=X-API-Key: <copie aquí PISHOP_API_KEY de su .env>

curl -H "%K%" http://localhost:8000/v1/catalogo/productos
curl -X POST http://localhost:8000/v1/compras -H "%K%" -H "Content-Type: application/json" -H "Idempotency-Key: compra-demo-0001" -d "{\"cliente_id\":\"C-9001\",\"sku\":\"CAFE-500G\",\"cantidad\":2,\"medio_pago\":\"pse\"}"
curl -H "%K%" http://localhost:8000/v1/compras/<pedido_id>
curl http://localhost:8006/v1/reportes/resumen
curl "http://localhost:8005/v1/notificaciones?pedido_id=<pedido_id>"
```

Cambiar la pasarela simulada (demo de resiliencia): `curl -X PUT http://localhost:8004/_simulador/pasarela/modo -H "Content-Type: application/json" -d "{\"modo\":\"lenta\"}"` (modos: `ok`, `rechaza`, `lenta`, `falla`).

## 5. Requisitos del proyecto y dónde se cumplen

| Requisito | Cómo se cumple | Dónde |
|---|---|---|
| Máximo **40 procesos (peticiones) por minuto** | Límite por clave en la API pública; la 41.ª recibe `429` + `Retry-After` | `PISHOP_RATE_LIMIT=40/minute`, `services/api-publica/app/seguridad.py` |
| **6 bases en PostgreSQL** | Una base y un usuario por servicio core; un usuario no puede entrar a la base de otro | `infra/initdb/01-bases.sql`, `infra/initdb/02-usuarios.sh` |
| **Datos ficticios** | 30 productos y sus existencias al arrancar + compras ficticias por la API | `*/app/semilla.py`, `scripts/generar_datos.py` |
| **Docker Compose** | 13 contenedores, healthchecks, `depends_on` con condición, volúmenes, redes, límites de recursos | `docker-compose.yml` |
| **Abarcar los puertos** 8000–8006, 8080 (+ 8010, 8090, 8500, Redis) | Todos publicados; los internos solo en `127.0.0.1` | sección 3 |
| **Tiempo máximo de respuesta** | Ver la nota de abajo | `X-Tiempo-Respuesta-ms`, timeouts |

### Nota sobre los "5 nanosegundos"

Una respuesta HTTP **no puede** tardar 5 nanosegundos: en ese tiempo la luz recorre 1,5 metros y una sola lectura de memoria RAM ya tarda más. Lo que se mide en la práctica son **milisegundos**. Lo implementado:

- Cada respuesta trae la cabecera **`X-Tiempo-Respuesta-ms`** con lo que tardó (con precisión de microsegundos, medida con `perf_counter_ns`).
- Si una petición supera el umbral (`PISHOP_UMBRAL_RESPUESTA_MS`: 500 ms en los core, 1500 ms en el BFF y la API) queda una advertencia `respuesta lenta` en el log.
- **Presupuesto máximo de 5 segundos** por compra: timeouts de 1 s a catálogo/inventario/pedidos, 2,5 s a pagos y 5 s de la API al BFF. Con la pasarela en modo `lenta`, la compra responde `409 FALLIDO` en unos 2 segundos, ya compensada, en vez de quedarse colgada.
- Medido en local: sondas ~1–2 ms, compra completa (4 servicios + 2 confirmaciones) ~45 ms.

Si el docente se refería a otra cifra (5 ms o 5 s), solo hay que cambiar las variables de timeout/umbral en `docker-compose.yml`.

## 6. Pruebas

```bat
:: Pruebas unitarias de un servicio (SQLite + bus en memoria: no necesitan Docker)
cd services\catalogo-service
pip install -r requirements.txt pytest
python -m pytest -q

:: Contratos de los 10 servicios y auditoría de seguridad (desde la raíz)
python herramientas\validar_entrega.py --todos
python herramientas\auditar_config.py
```

Resultado actual: **96 pruebas pytest** (8+8+8+9+4+4+11+33+6+5), validador **10/10 OK**, auditoría **SIN HALLAZGOS**, e2e **23/23**.

## 7. Variables de entorno (`.env`)

| Variable | Ejemplo | Explicación |
|---|---|---|
| `POSTGRES_PASSWORD` | (aleatoria) | Superusuario: solo crea bases y usuarios |
| `PG_CLAVE_CATALOGO` … `PG_CLAVE_REPORTES` | (aleatorias) | Contraseña de cada usuario de base |
| `PISHOP_API_KEY` | (aleatoria, 43 caracteres) | Clave de la cabecera `X-API-Key` |
| `PISHOP_RATE_LIMIT` | `40/minute` | Límite de peticiones por clave |
| `PISHOP_APP_ENV` | `dev` | `dev\|qa\|stg\|prod` (fuera de dev exige clave ≥ 16 caracteres) |
| `PUERTO_POSTGRES_HOST` / `PUERTO_REDIS_HOST` | `5433` / `6380` | Puertos en su PC |
| `PISHOP_CONFIG_ADMIN_TOKEN` | (vacío) | Si se llena, cambiar configuración exige `X-Token-Admin` |

## 8. Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `port is already allocated` | Otro programa usa ese puerto. Cambie `PUERTO_POSTGRES_HOST`/`PUERTO_REDIS_HOST` en `.env`, o cierre el programa |
| Un servicio queda `unhealthy` | `docker compose logs <servicio>` |
| `password authentication failed` tras cambiar el `.env` | Las bases se crearon con las claves anteriores: `docker compose down -v` y vuelva a subir |
| `02-usuarios.sh: not found` o `\r` en el log de postgres | El archivo quedó con fin de línea Windows (CRLF). Ábralo en VS Code y cambie a `LF` abajo a la derecha |
| La compra responde 429 | Pasó las 40 peticiones del minuto; espere los segundos de `Retry-After` |

## 9. Estructura

```
docker-compose.yml          sistema completo (13 contenedores)
docker-compose.seguro.yml   perfil que cierra todos los puertos menos el 8000
.env.example                variables (copiar a .env o usar scripts/generar_env.py)
infra/initdb/               creación de las 6 bases y sus 6 usuarios
services/<servicio>/        10 servicios: app/, tests/, Dockerfile multi-etapa, requirements.txt
scripts/                    generar_env.py, generar_datos.py, prueba_e2e.py
herramientas/               validar_entrega.py, auditar_config.py (+ sus pruebas)
docs/                       enunciado, contratos, roles, CIBERSEGURIDAD.md, descubrimiento.md
iniciar.bat / detener.bat   atajos para Windows
```

## 10. Uso de IA generativa

Ver `docs/declaracion-uso-ia.md`. Debe completarse y firmarse antes de entregar.
