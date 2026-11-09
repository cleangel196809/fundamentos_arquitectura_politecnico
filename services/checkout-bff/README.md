# checkout-bff (P06) — servicio compuesto y orquestador de saga de PiShop Cloud

Autor: Johan Sebastian Rubiano Guzmán · Paquete P06 · Fundamentos de Arquitectura (1419)

Servicio compuesto (Backend For Frontend - BFF) que implementa el patrón **Saga por Orquestación** para coordinar el flujo de compras entre los servicios de `catalogo-service`, `inventario-service`, `pedidos-service` y `pagos-service`. Además, actúa como agregador de datos para la vista móvil (`/v1/vitrina`).

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/v1/checkout` | Orquesta la saga de compra (valida catálogo → reserva inventario → crea pedido → cobra). Soporta `Idempotency-Key` |
| GET | `/v1/checkout/{pedido_id}/estado` | Consulta el estado del checkout y el historial de pasos ejecutados |
| GET | `/v1/vitrina` | Agregador BFF: combina productos publicados de catálogo con su stock disponible |
| GET | `/health/live` | Sonda de vida (local, barata, sin dependencias) |
| GET | `/health/ready` | Sonda de preparación (verifica dependencias y versión de configuración) |
| GET | `/health/startup` | Sonda de inicio (indica si el ciclo de vida del servicio ya arrancó) |

## Cómo ejecutarlo
```bash
cd services/checkout-bff
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8080
python -m pytest
```

O utilizando Docker Compose desde la raíz del proyecto:
```bash
docker compose up -d consul redis postgres checkout-bff
```

## Configuración (`PISHOP_*`)
| Variable | Por defecto | Descripción |
|---|---|---|
| `PISHOP_SERVICE_NAME` | `checkout-bff` | Nombre del microservicio para registro |
| `PISHOP_HTTP_PORT` | `8080` | Puerto en el que escucha el servicio |
| `PISHOP_APP_ENV` | `dev` | Entorno de ejecución (`dev`, `qa`, `stg`, `prod`) |
| `PISHOP_DATABASE_URL` | `sqlite+aiosqlite:///./local.db` | URL de base de datos local (en compose PostgreSQL) |
| `PISHOP_DATABASE_PASSWORD` | `cambiar-en-entorno` | Contraseña de base de datos (`SecretStr`) |
| `PISHOP_CATALOGO_SERVICE_URL` | `http://localhost:8001` | URL del servicio de Catálogo (P01) |
| `PISHOP_INVENTARIO_SERVICE_URL` | `http://localhost:8002` | URL del servicio de Inventario (P02) |
| `PISHOP_PEDIDOS_SERVICE_URL` | `http://localhost:8003` | URL del servicio de Pedidos (P03) |
| `PISHOP_PAGOS_SERVICE_URL` | `http://localhost:8004` | URL del servicio de Pagos (P04) |
| `PISHOP_CONFIG_SERVICE_URL` | `http://localhost:8010` | URL del Config Service (P08) |
| `PISHOP_CONSUL_URL` | `http://localhost:8500` | URL de Consul para descubrimiento |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | `2.0` | Timeout explícito para llamadas salientes |

## Decisiones
- **Saga por Orquestación**: El BFF asume la responsabilidad central de coordinar los pasos de la compra; ningún microservicio core llama directamente a otro, evitando acoplamientos innecesarios.
- **Compensaciones en orden inverso**: Si un paso posterior de la saga falla (por ejemplo, pago rechazado o error de red), el orquestador ejecuta las compensaciones en orden inverso (cancela el pedido y libera la reserva en inventario) respondiendo con estado `FALLIDO` y el detalle de cada paso.
- **Idempotencia (`Idempotency-Key`)**: Implementación de caché de idempotencia en memoria para reintentos de `POST /v1/checkout`. Repetir la misma petición con la misma clave devuelve exactamente el mismo resultado sin duplicar pedidos ni cobros.
- **Timeouts explícitos**: Uso de un único `httpx.AsyncClient` por proceso configurado con timeout explícito (`2.0s`) para evitar colgar hilos o peticiones en caso de lentitud de servicios downstream.
- **Agregador BFF (`/v1/vitrina`)**: Reduce el número de viajes de red (roundtrips) desde dispositivos móviles entregando en una sola llamada los campos esenciales de catálogo y stock.

## Evidencia

```cmd
C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main>cd services/checkout-bff

C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\checkout-bff>pip install -r requirements.txt
Requirement already satisfied: fastapi>=0.115 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 1)) (0.162.0)
Requirement already satisfied: uvicorn>=0.30 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 2)) (0.54.0)
Requirement already satisfied: pydantic>=2.8 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 3)) (2.14.3)
Requirement already satisfied: pydantic-settings>=2.4 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 4)) (2.16.2)
Requirement already satisfied: httpx>=0.27 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 5)) (0.28.1)
Requirement already satisfied: sqlalchemy>=2.0 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 6)) (2.1.8)
Requirement already satisfied: aiosqlite>=0.20 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 7)) (0.22.1)
Requirement already satisfied: asyncpg>=0.29 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 8)) (0.32.0)
Requirement already satisfied: redis>=5.0 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 9)) (8.1.0)
Requirement already satisfied: pytest>=8.0 in c:\users\yessi\appdata\local\packages\pythonsoftwarefoundation.python.3.11_qbz5n2kfra8p0\localcache\local-packages\python311\site-packages (from -r requirements.txt (line 10)) (9.2.0)

C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\checkout-bff>python -m pytest
======================================= test session starts ========================================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\checkout-bff
plugins: anyio-4.16.0
collected 5 items                                                                                   

tests\test_checkout.py ....                                                                   [ 80%]
tests\test_health.py .                                                                        [100%]

======================================== 5 passed in 4.35s =========================================

C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\checkout-bff>cd ../..

C:\Users\yessi\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main>python herramientas/validar_entrega.py checkout-bff

== checkout-bff (rol P06, puerto 8080) ==
  [ok] POST   /v1/checkout
  [ok] GET    /v1/checkout/{pedido_id}/estado
  [ok] GET    /v1/vitrina
  [ok] sonda /health/live -> 200
  [ok] sonda /health/ready -> 200
  [ok] sonda /health/startup -> 200
  [ok] sin configuración embebida (0 hallazgos)

Resumen: {'checkout-bff': 'OK'}
```

## Uso de IA generativa
* Utilicé IA para la configuración inicial de los contenedores Docker y la resolución del bloqueo de puertos en Windows.
* Utilicé IA para diseñar e implementar la estructura de la saga orquestada (`POST /v1/checkout`), compensaciones y manejo de idempotencia en `app/main.py`.
* Utilicé IA para estructurar los modelos Pydantic en `app/schemas.py` y actualizar las variables en `app/settings.py`.
* Utilicé IA para crear las pruebas unitarias en `tests/test_checkout.py` y validar la entrega contra `herramientas/validar_entrega.py`.
* Verifiqué manualmente la ejecución de las pruebas unitarias y el paso exitoso del validador.

