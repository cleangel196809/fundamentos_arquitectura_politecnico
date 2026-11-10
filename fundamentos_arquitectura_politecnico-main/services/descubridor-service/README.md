# Descubridor Service (Paquete 09) - PiShop

Microservicio de descubrimiento de servicios desarrollado con **FastAPI** e integrado con **Consul** (registro centralizado) para la arquitectura de microservicios de PiShop. Puerto: **8090**.

## 1. Arquitectura

El `descubridor-service` se registra en Consul al arrancar y expone a los demás servicios (por ejemplo el BFF) la lista de servicios, sus instancias sanas y una instancia resuelta con balanceo round-robin.

```text
  +--------------+   GET /v1/servicios/{nombre}/resolver   +--------------------+
  | Cliente/BFF  | --------------------------------------> | descubridor-service|
  +--------------+                                          |   (FastAPI :8090)  |
                                                            +--------------------+
                                                                      |
                                                    /v1/health/service/{nombre}?passing=true
                                                                      v
                                                            +--------------------+
                                                            |   Consul (:8500)   |
                                                            +--------------------+
```

## 2. Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/v1/servicios` | Servicios registrados en Consul |
| GET | `/v1/servicios/{nombre}/instancias` | Instancias en estado `passing` |
| GET | `/v1/servicios/{nombre}/resolver` | Una instancia sana, en round-robin (404 si no hay) |
| GET | `/health/live` | Sonda de vida (no toca dependencias) |
| GET | `/health/startup` | 200 cuando terminó el arranque |
| GET | `/health/ready` | 200 si arrancó y Consul responde; 503 en otro caso |

Documentación interactiva en `http://localhost:8090/docs`. La ruta `/` no existe (responde 404).

## 3. Configuración (variables `PISHOP_*`)

| Variable | Descripción | Local | Docker |
|---|---|---|---|
| `PISHOP_SERVICE_NAME` | Nombre con el que se registra en Consul | `descubridor-service` | `descubridor-service` |
| `PISHOP_HTTP_PORT` | Puerto HTTP | `8090` | `8090` |
| `PISHOP_APP_ENV` | Entorno de ejecución | `dev` | `dev` |
| `PISHOP_CONSUL_URL` | URL de Consul | `http://localhost:8500` | `http://consul:8500` |
| `PISHOP_HTTP_TIMEOUT_SECONDS` | Timeout de las llamadas a Consul | `2.0` | `2.0` |

## 4. Ejecución

Con Docker (recomendado):

```powershell
docker compose up -d --build descubridor-service
```

Local (Python 3.13, con Consul levantado en Docker):

```powershell
pip install -r services/descubridor-service/requirements.txt
$env:PISHOP_CONSUL_URL="http://localhost:8500"
cd services/descubridor-service
uvicorn app.main:app --port 8090
```

Validación del contrato (desde la raíz del repo):

```powershell
python herramientas/validar_entrega.py descubridor-service
```

## 5. Decisiones de diseño

- **FastAPI**: validación con Pydantic y documentación automática en `/docs`.
- **Solo instancias `passing`**: se consulta `/v1/health/service/{nombre}?passing=true`, así nunca se resuelve una instancia caída.
- **Round-robin**: un contador por servicio rota entre las instancias sanas.
- **Errores**: Consul inalcanzable responde 503 (dependencia caída); servicio sin instancias sanas responde 404.
- **Registro automático** en el `lifespan` (`registro.py`: `registrar()` / `dar_de_baja()`), con ID único por instancia para soportar réplicas.
- **Sondas diferenciadas**: `live` no depende de nada; `ready` verifica Consul.
- Ver `docs/descubrimiento.md` (descubrimiento del lado del cliente vs. del servidor).

## 6. Evidencia

### 1. Comando docker compose
```text
C:\Users\Usuario\Documents\fundamentos_arquitectura_politecnico-main>docker compose up -d --build descubridor-service
[+] Building 1.4s (13/13) FINISHED
 => [internal] load local bake definitions                                                                  0.0s
 => => reading from stdin 779B                                                                                0.0s
 => [internal] load build definition from Dockerfile                                                          0.0s
 => => transferring dockerfile: 246B                                                                          0.0s
 => [internal] load metadata for docker.io/library/python:3.11-slim                                           0.8s
 => [auth] library/python:pull token for registry-1.docker.io                                                 0.0s
 => [internal] load .dockerignore                                                                           0.0s
 => => transferring context: 2B                                                                               0.0s
 => [1/5] FROM docker.io/library/python:3.11-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b1  0.0s
 => => resolve docker.io/library/python:3.11-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b1  0.0s
 => [internal] load build context                                                                           0.0s
 => => transferring context: 3.52kB                                                                           0.0s
 => CACHED [2/5] WORKDIR /app                                                                                 0.0s
 => CACHED [3/5] COPY requirements.txt .                                                                      0.0s
 => CACHED [4/5] RUN pip install --no-cache-dir -r requirements.txt                                           0.0s
 => [5/5] COPY . .                                                                                            0.0s
 => exporting to image                                                                                        0.2s
 => => exporting layers                                                                                       0.1s
 => => exporting manifest sha256:98c99e0c87f199e889c4d97b4e4a635435cde44657de2ace15475001eea96c54             0.0s
 => => exporting config sha256:963f06a1da3f16814a6242e96f00bac4f845fc366c372e32228f4e213e4b4e3c                0.0s
 => => exporting attestation manifest sha256:55c17016f4057d536e55043c8281bcdd811446b74c1e5fa4d56077ccbbe9fd56  0.0s
 => => exporting manifest list sha256:e7e5f798794c3d55dac27df9b6f7c6d91c89e9118b2d34af3cb8ba590c24d46f        0.0s
 => => naming to docker.io/library/fundamentos_arquitectura_politecnico-main-descubridor-service:latest         0.0s
 => => unpacking to docker.io/library/fundamentos_arquitectura_politecnico-main-descubridor-service:latest    0.0s
 => resolving provenance for metadata file                                                                  0.0s
[+] up 4/4
 ✔ Image fundamentos_arquitectura_politecnico-main-descubridor-service       Built        1.7s
 ✔ Container fundamentos_arquitectura_politecnico-main-redis-1             Healthy        1.3s
 ✔ Container fundamentos_arquitectura_politecnico-main-consul-1            Healthy        1.3s
 ✔ Container fundamentos_arquitectura_politecnico-main-descubridor-service-1 Started       1.6s
```

### 2. Endpoint de servicios
```powershell
Invoke-RestMethod -Uri "http://localhost:8090/v1/servicios"
```
<pegar aquí la salida real>

### 3. Resolver (round-robin)
```powershell
Invoke-RestMethod -Uri "http://localhost:8090/v1/servicios/descubridor-service/resolver"
```
<pegar aquí la salida real>

### 4. Contenedores activos
```text
CONTAINER ID   IMAGE                                                 COMMAND                  CREATED         STATUS                  PORTS                                           NAMES
01215e2948b3   fundamentos_arquitectura_politecnico-main-descubridor-service   "uvicorn app.main:ap…"   10 minutes ago  Up 10 minutes           0.0.0.0:8090->8090/tcp, [::]:8090->8090/tcp   fundamentos_arquitectura_politecnico-main-descubridor-service-1
74f0253a47e2   redis:8-alpine                                        "docker-entrypoint.s…"   22 minutes ago  Up 22 minutes (healthy) 0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp   fundamentos_arquitectura_politecnico-main-redis-1
622f4cbbf908   hashicorp/consul:1.21                                 "docker-entrypoint.s…"   22 minutes ago  Up 22 minutes (healthy) 0.0.0.0:8500->8500/tcp, [::]:8500->8500/tcp   fundamentos_arquitectura_politecnico-main-consul-1
```

### 5. Validación
```powershell
python herramientas/validar_entrega.py descubridor-service
```
<pegar aquí la salida real>

### 6. Consul UI
<captura de http://localhost:8500 mostrando descubridor-service en passing>

## 7. Declaración de uso de la IA

Áreas de Asistencia de la IA:
1. Soporte Arquitectónico y Estructural: Guía en el diseño de los endpoints orientados a la integración con Consul (/v1/servicios, /v1/servicios/{nombre}/instancias, /v1/servicios/{nombre}/resolver) y las sondas de ciclo de vida (/health/live, /health/ready, /health/startup).

2. Depuración y Resolución de Errores: Asistencia en la identificación y corrección de excepciones de entorno y conectividad (NameError y variables de entorno en Windows/PowerShell), del manejo de errores (404/503), del registro en el `lifespan`, del round-robin y de los nombres de las variables `PISHOP_*` en `settings.py`.

3. Documentación Técnica: Apoyo en la estructuración y redacción del archivo README.md (diagrama de comunicación, tabla de configuración PISHOP_* y decisiones de diseño).

¿Qué se verificó?

-Conexiones con los puertos y respuesta de los mismos con el comando docker compose.

-Funcionamiento del descubridor de servicios mediante pruebas locales con datos ficticios.

-Prueba del funcionamiento del sistema en web.

-Pruebas y validaciones con todo en OK sin novedades.
