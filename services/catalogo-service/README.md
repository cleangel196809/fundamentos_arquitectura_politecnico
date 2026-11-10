# P01 · catalogo-service (Puerto 8001)

**Estudiante:** Diego Alejandro Rodríguez Moncada  
**Rol asignado:** Catálogo (Core)  
**Curso:** Fundamentos de Arquitectura (1419) · Ciclo VIII · Politécnico Internacional I.E.S.  
**Docente:** Edgar Humberto Angel Millán  
**Indicador syllabus:** 1.1 Criterios de arquitectura objetivo y responsabilidades  
**Fecha de entrega:** Martes 10 de noviembre de 2026, 13:00  

---

## 1. Responsabilidad y contexto de negocio

`catalogo-service` es un servicio **Core** dentro de la arquitectura de **PiShop Cloud**. Es el **dueño exclusivo** de los datos de productos agropecuarios, precios y estado de publicación. Ningún otro servicio del ecosistema puede leer o escribir directamente en su base de datos (`pg_catalogo` o SQLite local), garantizando el desacoplamiento y evitando el antipatrón del *monolito distribuido*.

### Características principales:
* Expone su interfaz pública REST versionada bajo `/v1/productos`.
* Implementa paginación eficiente con límite máximo de 100 items por página.
* Validación estricta de SKU único y precio mayor a 0 con Pydantic v2.
* Publicación explícita de productos (`PATCH /v1/productos/{sku}/publicar`).
* Carga automática de una semilla inicial de 10 productos agropecuarios colombianos.
* Formato de error estandarizado: `{"detalle": "...", "codigo": "..."}`.

---

## 2. Justificación arquitectónica y decisiones (Semanas 1 a 4)

### Semana 1: Atributos de calidad (ISO/IEC 25010) y Trade-offs
* **Eficiencia de desempeño (Escenario medible):** Durante la temporada de cosecha, `catalogo-service` debe sostener ráfagas de lectura intensiva de hasta 1.200 req/s con un percentil $p95 \le 250\text{ ms}$ y tasa de error $< 0,1\,\%$.
* **Trade-off CAP / PACELC (Disponibilidad vs Consistencia):** Según CAP y PACELC, `catalogo-service` se clasifica como **AP (y PA/EL)**. En caso de una partición de red o degradación parcial, es preferible servir datos de productos con una ventana de consistencia eventual o caché ligera que bloquear las consultas de los compradores. La consistencia estricta se reserva para pagos e inventario.
* **Aislamiento de fallos:** Al extraerse del monolito PHP original de 9 años, la sobrecarga del módulo de reportes (que causó la caída del Black Friday) ya no puede agotar la memoria ni las conexiones del catálogo.

### Semana 2: Domain-Driven Design (DDD) y ACL Interna
* **Bounded Context:** Delimitado al contexto de *Catálogo y Productos*.
* **Tríada de servicios:** Clasificado como **Servicio Core** (lógica de negocio fundamental y persistencia autoritativa). Es consumido internamente por `checkout-bff` (P06) y externamente por `api-publica` (P07).
* **Anti-Corruption Layer (ACL) interna:** Separación rigurosa entre `models.py` (SQLAlchemy 2.0 para la persistencia) y `schemas.py` (Pydantic v2 para contratos HTTP y validación). Cualquier cambio en el esquema relacional interno no rompe el contrato público de la API.

### Semana 3: Cubo de escalabilidad de Abbott & Fisher
* **Eje Y (Descomposición funcional):** Catálogo se extrae como microservicio independiente porque su perfil de carga es radicalmente asimétrico (95 % lecturas, 5 % escrituras).
* **Eje X (Clonación horizontal):** El servicio es 100 % *stateless* (sin estado en memoria, sin sesiones de usuario locales). En alta temporada puede clonarse en 4 réplicas idénticas detrás de un balanceador round-robin.

### Semana 4: Externalización (Twelve-Factor App) y Sondas Kubernetes
* **Factor III (Configuración externalizada):** Toda la configuración se inyecta mediante variables de entorno `PISHOP_*` gestionadas con `pydantic-settings`. Los secretos sensibles usan el tipo `SecretStr` para evitar fugas en logs.
* **Sondas de salud con semántica diferenciada (Regla 3):**
  * `/health/live`: Liveness probe. Verifica que el proceso Python/Uvicorn está activo. No prueba dependencias externas.
  * `/health/ready`: Readiness probe. Verifica que el servicio está en capacidad de recibir tráfico ejecutando `SELECT 1` sobre la base de datos. Si la BD cae, retorna `503 Service Unavailable`.
  * `/health/startup`: Startup probe. Verifica que la inicialización (creación de tablas y siembra de 10 productos) concluyó satisfactoriamente.

---

## 3. Tabla de configuración (`PISHOP_*`)

| Variable | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `PISHOP_APP_NAME` | `str` | `catalogo-service` | Nombre lógico del microservicio |
| `PISHOP_ENV` | `str` | `dev` | Entorno de ejecución (`dev`, `qa`, `stg`, `prod`) |
| `PISHOP_PORT` | `int` | `8001` | Puerto TCP donde escucha el servicio |
| `PISHOP_DATABASE_URL` | `str` | `sqlite+aiosqlite:///./catalogo.db` | URL de conexión asíncrona a la base de datos |
| `PISHOP_SECRET_KEY` | `SecretStr` | `clave-secreta-catalogo-2026` | Clave criptográfica para firmas internas |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | `float` | `2.0` | Timeout explícito para llamadas salientes con `httpx` |
| `PISHOP_EVENT_BUS` | `str` | `memory` | Bus de eventos (`memory` en local, `redis` en compose) |

---

## 4. Contrato de Endpoints (`/v1/productos`)

| Método | Endpoint | Respuesta Exitosa | Respuestas de Error | Descripción |
|---|---|---|---|---|
| `GET` | `/v1/productos?pagina=1&tamano=20` | `200 OK` (Paginación) | `422` (Parámetros inválidos) | Lista productos con total y paginación. Tamaño máx: 100 |
| `POST` | `/v1/productos` | `201 Created` | `409` (SKU duplicado), `422` (Precio $\le$ 0) | Registra un nuevo producto (por defecto `publicado=false`) |
| `GET` | `/v1/productos/{sku}` | `200 OK` | `404` (No encontrado) | Consulta la ficha de un producto por SKU |
| `PATCH` | `/v1/productos/{sku}/publicar` | `200 OK` (`publicado=true`) | `404` (No encontrado) | Publica un producto para que sea visible en la tienda |
| `POST` | `/v1/productos/semilla/reiniciar` | `200 OK` | `500` | Reinicia la base de datos con los 10 productos semilla |
| `GET` | `/health/live` | `200 OK` | - | Sonda liveness de Kubernetes |
| `GET` | `/health/ready` | `200 OK` | `503` | Sonda readiness (comprueba BD) |
| `GET` | `/health/startup` | `200 OK` | `503` | Sonda startup (comprueba inicialización) |

---

## 5. Semilla inicial de productos (10 productos)

1. `CAFE-500G`: Café Especial Suave 500g ($ 28.000 COP) — *Publicado*
2. `CAFE-1000G`: Café Especial en Grano 1kg ($ 52.000 COP) — *Publicado*
3. `PANELA-1K`: Panela Orgánica Pulverizada 1kg ($ 7.500 COP) — *Publicado*
4. `PANELA-BLOQUE`: Panela Tradicional en Bloque 2kg ($ 12.000 COP) — *No publicado*
5. `MIEL-750`: Miel Pura de Abejas 750ml ($ 35.000 COP) — *Publicado*
6. `CACAO-500G`: Cacao Fino de Aroma en Polvo 500g ($ 24.000 COP) — *Publicado*
7. `AGUACATE-HASS-KG`: Aguacate Hass Exportación (kg) ($ 9.500 COP) — *Publicado*
8. `PLATANO-HARTON-RAC`: Plátano Hartón Racimo 15kg ($ 42.000 COP) — *No publicado*
9. `FRIJOL-BOLA-ROJA-KG`: Fríjol Bola Roja Selección 1kg ($ 14.500 COP) — *Publicado*
10. `MAIZ-AMARILLO-25K`: Maíz Amarillo Bulto 25kg ($ 68.000 COP) — *Publicado*

---

## 6. Cómo ejecutar el servicio localmente

### Prerrequisitos:
* Python 3.13+ instalado.
* Dependencias requeridas:
  ```powershell
  pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy greenlet aiosqlite httpx pytest pytest-asyncio
  ```

### Iniciar el servidor:
```powershell
# Desde la carpeta services/catalogo-service/
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
La documentación interactiva OpenAPI estará disponible de inmediato en:
* Swagger UI: `http://localhost:8001/docs`
* ReDoc: `http://localhost:8001/redoc`

---

## 7. Evidencia reproducible de pruebas y `curl`

### 7.1. Batería de pruebas automatizadas (`pytest`)
Se ejecutaron 9 pruebas unitarias e integración en memoria cubriendo todos los casos exigidos:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.8, pytest-9.2.0, pluggy-1.7.0
rootdir: pishop-cloud\services\catalogo-service
configfile: pytest.ini
plugins: anyio-4.16.0, asyncio-1.4.1.post1
asyncio: mode=Mode.AUTO

tests/test_catalogo.py::test_01_listar_productos_paginacion PASSED       [ 11%]
tests/test_catalogo.py::test_02_obtener_producto_por_sku_200 PASSED      [ 22%]
tests/test_catalogo.py::test_03_crear_producto_201 PASSED                [ 33%]
tests/test_catalogo.py::test_04_obtener_producto_inexistente_404 PASSED  [ 44%]
tests/test_catalogo.py::test_05_crear_producto_sku_duplicado_409 PASSED  [ 55%]
tests/test_catalogo.py::test_06_crear_producto_precio_invalido_422 PASSED [ 66%]
tests/test_catalogo.py::test_07_publicar_producto_patch_200 PASSED       [ 77%]
tests/test_catalogo.py::test_08_publicar_producto_inexistente_404 PASSED [ 88%]
tests/test_catalogo.py::test_09_sondas_salud_live_ready_startup PASSED   [100%]

======================== 9 passed in 3.84s ========================
```

### 7.2. Evidencia de llamadas con `curl`

#### 1. Listar productos paginados (200 OK):
```bash
curl -s "http://localhost:8001/v1/productos?pagina=1&tamano=2"
```
**Respuesta:**
```json
{
  "items": [
    {
      "sku": "CAFE-500G",
      "nombre": "Café Especial Suave 500g",
      "precio_cop": 28000,
      "categoria": "Café",
      "publicado": true
    },
    {
      "sku": "CAFE-1000G",
      "nombre": "Café Especial en Grano 1kg",
      "precio_cop": 52000,
      "categoria": "Café",
      "publicado": true
    }
  ],
  "total": 10,
  "pagina": 1,
  "tamano": 2
}
```

#### 2. Crear un nuevo producto (201 Created):
```bash
curl -s -X POST "http://localhost:8001/v1/productos" \
  -H "Content-Type: application/json" \
  -d '{"sku":"QUESO-CAMP-500","nombre":"Queso Campesino 500g","precio_cop":13500,"categoria":"Lácteos"}'
```
**Respuesta:**
```json
{
  "sku": "QUESO-CAMP-500",
  "nombre": "Queso Campesino 500g",
  "precio_cop": 13500,
  "categoria": "Lácteos",
  "publicado": false
}
```

#### 3. Error por SKU duplicado (409 Conflict):
```bash
curl -s -X POST "http://localhost:8001/v1/productos" \
  -H "Content-Type: application/json" \
  -d '{"sku":"CAFE-500G","nombre":"Café Repetido","precio_cop":30000,"categoria":"Café"}'
```
**Respuesta:**
```json
{
  "detalle": "El producto con SKU 'CAFE-500G' ya existe",
  "codigo": "SKU_DUPLICADO"
}
```

#### 4. Error por precio inválido $\le 0$ (422 Unprocessable Content):
```bash
curl -s -X POST "http://localhost:8001/v1/productos" \
  -H "Content-Type: application/json" \
  -d '{"sku":"YUCA-1K","nombre":"Yuca","precio_cop":0,"categoria":"Tubérculos"}'
```
**Respuesta:**
```json
{
  "detalle": "El precio debe ser estrictamente mayor a 0",
  "codigo": "PRECIO_INVALIDO"
}
```

#### 5. Consultar producto inexistente (404 Not Found):
```bash
curl -s "http://localhost:8001/v1/productos/SKU-FANTASMA"
```
**Respuesta:**
```json
{
  "detalle": "Producto con SKU 'SKU-FANTASMA' no existe",
  "codigo": "PRODUCTO_NO_ENCONTRADO"
}
```

#### 6. Publicar producto (PATCH 200 OK):
```bash
curl -s -X PATCH "http://localhost:8001/v1/productos/PANELA-BLOQUE/publicar"
```
**Respuesta:**
```json
{
  "sku": "PANELA-BLOQUE",
  "nombre": "Panela Tradicional en Bloque 2kg",
  "precio_cop": 12000,
  "categoria": "Endulzantes",
  "publicado": true
}
```

#### 7. Sonda de alistamiento (`/health/ready`):
```bash
curl -s "http://localhost:8001/health/ready"
```
**Respuesta:**
```json
{
  "status": "READY",
  "servicio": "catalogo-service",
  "database": "CONNECTED"
}
```

---

## 8. Declaración de uso de IA Generativa

En cumplimiento del numeral 5 de la rúbrica del Parcial 1:
* **Asistente utilizado:** Antigravity (Google DeepMind).
* **Partes en las que se utilizó:**
  * Generación del andamiaje inicial del router FastAPI, esquemas Pydantic v2 y configuración con `pydantic-settings`.
  * Generación de la batería de pruebas en `test_catalogo.py`.
* **Verificación humana realizada por Diego Alejandro Rodríguez Moncada:**
  * Se comprobó manualmente que los códigos de estado HTTP cumplieran exactamente `docs/CONTRATOS.md` (`200`, `201`, `404`, `409`, `422`).
  * Se validó que las sondas Kubernetes (`live`, `ready`, `startup`) respetaran la semántica diferenciada exigida en la Semana 4.
  * Se ejecutó el script de verificación del docente `herramientas/validar_entrega.py catalogo-service` asegurando 100 % de éxito.
