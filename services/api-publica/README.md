# api-publica (P07) — fachada pública de PiShop Cloud

Autor: <Andres Felipe Rivera Sogamoso> · Paquete P07 · Fundamentos de Arquitectura (1419)

Fachada (API gateway) que autentica con `X-API-Key`, limita la tasa por clave y **enruta**
a `catalogo-service` y `checkout-bff`. No contiene lógica de negocio.

## Endpoints
| Método | Ruta | Destino |
|---|---|---|
| GET | `/v1/catalogo/productos` | catalogo-service `GET /v1/productos` (solo `publicado=true`) |
| POST | `/v1/compras` | checkout-bff `POST /v1/checkout` (reenvía `Idempotency-Key`) |
| GET | `/v1/compras/{pedido_id}` | checkout-bff `GET /v1/checkout/{pedido_id}/estado` |
| GET | `/health/live`, `/health/ready`, `/health/startup` | sondas |

## Cómo ejecutarlo
```bash
pip install -r requirements.txt
PISHOP_API_KEY=mi-clave uvicorn app.main:app --port 8000
pytest
```

## Configuración (`PISHOP_*`)
| Variable | Por defecto | Descripción |
|---|---|---|
| `PISHOP_API_KEY` | `cambiar-en-entorno` | Secreto (`SecretStr`) que se exige en `X-API-Key` |
| `PISHOP_RATE_LIMIT_PER_MINUTE` | `60` | Peticiones por minuto por clave |
| `PISHOP_CHECKOUT_BFF_URL` | `http://localhost:8080` | URL del checkout-bff |
| `PISHOP_CATALOGO_URL` | `http://localhost:8001` | URL del catalogo-service |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | `2.0` | Timeout explícito de llamadas salientes |
| `PISHOP_APP_ENV` | `dev` | Entorno |

## Decisiones
- **Sin lógica de negocio**: solo autentica, limita, enruta y traduce errores.
- **Límite de tasa en memoria** (ventana deslizante): simple y suficiente para el parcial; no se comparte entre réplicas (en producción iría en Redis).
- **Timeouts y errores**: un `AsyncClient` por proceso; timeout → 504, servicio caído → 502; los 4xx del upstream se propagan.
- **Errores** en `application/problem+json` (RFC 9457) con campo extra `codigo`.
- **Idempotencia**: la fachada reenvía `Idempotency-Key`; la garantía la da el checkout-bff.

## Evidencia
C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main>cd services/api-publica

C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\api-publica>pip install -r requirements.txt
Requirement already satisfied: fastapi>=0.115 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 1)) (0.135.2)
Requirement already satisfied: uvicorn>=0.30 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 2)) (0.42.0)
Requirement already satisfied: pydantic>=2.8 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 3)) (2.12.5)
Collecting pydantic-settings>=2.4 (from -r requirements.txt (line 4))
  Downloading pydantic_settings-2.16.2-py3-none-any.whl.metadata (4.0 kB)
Requirement already satisfied: httpx>=0.27 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 5)) (0.28.1)
Requirement already satisfied: sqlalchemy>=2.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 6)) (2.0.48)
Collecting aiosqlite>=0.20 (from -r requirements.txt (line 7))
  Downloading aiosqlite-0.22.1-py3-none-any.whl.metadata (4.3 kB)
Collecting asyncpg>=0.29 (from -r requirements.txt (line 8))
  Downloading asyncpg-0.32.0-cp311-cp311-win_amd64.whl.metadata (4.5 kB)
Requirement already satisfied: redis>=5.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 9)) (8.0.1)
Requirement already satisfied: pytest>=8.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from -r requirements.txt (line 10)) (9.1.1)
Requirement already satisfied: starlette>=0.46.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from fastapi>=0.115->-r requirements.txt (line 1)) (1.0.0)
Requirement already satisfied: typing-extensions>=4.8.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from fastapi>=0.115->-r requirements.txt (line 1)) (4.15.0)
Requirement already satisfied: typing-inspection>=0.4.2 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from fastapi>=0.115->-r requirements.txt (line 1)) (0.4.2)
Requirement already satisfied: annotated-doc>=0.0.2 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from fastapi>=0.115->-r requirements.txt (line 1)) (0.0.4)
Requirement already satisfied: click>=7.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from uvicorn>=0.30->-r requirements.txt (line 2)) (8.3.1)
Requirement already satisfied: h11>=0.8 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from uvicorn>=0.30->-r requirements.txt (line 2)) (0.16.0)
Requirement already satisfied: annotated-types>=0.6.0 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pydantic>=2.8->-r requirements.txt (line 3)) (0.7.0)
Requirement already satisfied: pydantic-core==2.41.5 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pydantic>=2.8->-r requirements.txt (line 3)) (2.41.5)
Requirement already satisfied: python-dotenv>=1.2.2 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pydantic-settings>=2.4->-r requirements.txt (line 4)) (1.2.2)
Requirement already satisfied: anyio in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from httpx>=0.27->-r requirements.txt (line 5)) (4.13.0)
Requirement already satisfied: certifi in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from httpx>=0.27->-r requirements.txt (line 5)) (2026.2.25)
Requirement already satisfied: httpcore==1.* in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from httpx>=0.27->-r requirements.txt (line 5)) (1.0.9)
Requirement already satisfied: idna in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from httpx>=0.27->-r requirements.txt (line 5)) (3.11)
Requirement already satisfied: greenlet>=1 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from sqlalchemy>=2.0->-r requirements.txt (line 6)) (3.3.2)
Requirement already satisfied: colorama>=0.4 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pytest>=8.0->-r requirements.txt (line 10)) (0.4.6)
Requirement already satisfied: iniconfig>=1.0.1 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pytest>=8.0->-r requirements.txt (line 10)) (2.3.0)
Requirement already satisfied: packaging>=22 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pytest>=8.0->-r requirements.txt (line 10)) (26.0)
Requirement already satisfied: pluggy<2,>=1.5 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pytest>=8.0->-r requirements.txt (line 10)) (1.6.0)
Requirement already satisfied: pygments>=2.7.2 in C:\Users\felip\AppData\Local\Programs\Python\Python311\Lib\site-packages (from pytest>=8.0->-r requirements.txt (line 10)) (2.20.0)
Downloading pydantic_settings-2.16.2-py3-none-any.whl (81 kB)
Downloading aiosqlite-0.22.1-py3-none-any.whl (17 kB)
Downloading asyncpg-0.32.0-cp311-cp311-win_amd64.whl (610 kB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 610.5/610.5 kB 3.2 MB/s  0:00:00
Installing collected packages: asyncpg, aiosqlite, pydantic-settings
Successfully installed aiosqlite-0.22.1 asyncpg-0.32.0 pydantic-settings-2.16.2

[notice] A new release of pip is available: 26.0.1 -> 26.3
[notice] To update, run: python.exe -m pip install --upgrade pip

C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\api-publica>pytest
======================================= test session starts ========================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\api-publica
plugins: anyio-4.13.0, Faker-40.28.1, cov-7.1.0, django-4.12.0, mock-3.15.1
collected 10 items                                                                                  

tests\test_fachada.py .........                                                               [ 90%]
tests\test_health.py .                                                                        [100%]

======================================== 10 passed in 4.28s ========================================

C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main\services\api-publica>cd ../..

C:\Users\felip\Downloads\fundamentos_arquitectura_politecnico-main\fundamentos_arquitectura_politecnico-main>python herramientas/validar_entrega.py api-publica

== api-publica (rol P07, puerto 8000) ==
  [ok] GET    /v1/catalogo/productos
  [ok] POST   /v1/compras
  [ok] GET    /v1/compras/{pedido_id}
  [ok] sonda /health/live -> 200
  [ok] sonda /health/ready -> 200
  [ok] sonda /health/startup -> 200
  [ok] sin configuración embebida (0 hallazgos)

Resumen: {'api-publica': 'OK'}

## Uso de IA generativa
* use Claude para verificar con pytest, el validador y leyendo el código
* use Claude para ayudarme a corregir errores de los archivos .py de la carpeta app
* Use claude para que verificara que la estructura estubiera bien
* use Claude para que me ayudara a organizar y arreglar el archivo README.md
