# P12: Confiabilidad, integración y CI

Autora: Danixa Alexandra Herrera Nimisica · Paquete P12 · Parcial 1 PiShop Cloud

Mi paquete no es un servicio. Son las herramientas que comprueban que el sistema completo sea confiable: cuánto se cae, si se puede prender completo, si una compra funciona de punta a punta, si el código no trae claves escritas y si cada servicio responde bien sus sondas.

## Los 6 entregables

| # | Entregable | Archivo | Commit |
|---|---|---|---|
| 1 | Disponibilidad compuesta (reto 3.1) | `retos/semana03/disponibilidad.py` | `d61d10a` |
| 2 | Sistema completo con un comando | `docker-compose.yml` | `5a81164`, `792d8fa` |
| 3 | Prueba de extremo a extremo | `retos/e2e.py` + `retos/dobles/pishop_doble.py` | `9bf87be` |
| 4 | Integración continua | `.github/workflows/ci.yml` | `e34bbf3` |
| 5 | Auditor de configuración (criterio 1 del reto 4.1) | `herramientas/auditar_config.py` | `4991967` |
| 6 | Verificador de sondas (criterios 2 y 3 del reto 4.1) | `herramientas/verificar_sondas.py` | `1cc43f4` |

Todo se corre desde la carpeta principal del repositorio con Python 3.13 o más nuevo.

## Cómo ejecutar cada parte

```
# 1. Disponibilidad (no necesita instalar nada)
python retos/semana03/disponibilidad.py

# 2. Prender todo el sistema (necesita Docker Desktop y un .env)
copy .env.example .env
docker compose config -q          # revisa que el archivo esté bien escrito
docker compose up -d --wait       # prende los 13 contenedores

# 3. Prueba e2e
python -m uvicorn retos.dobles.pishop_doble:app --port 8000   # en otra terminal
python retos/e2e.py --dobles      # contra el doble de prueba
python retos/e2e.py               # contra el sistema real (con docker compose arriba)

# 5. Auditor de configuración
python herramientas/auditar_config.py

# 6. Verificador de sondas (instalar antes el requirements.txt del servicio)
python herramientas/verificar_sondas.py                         # todos los servicios
python herramientas/verificar_sondas.py services/pagos-service  # uno solo
```

El punto 4 (CI) corre solo en GitHub cada vez que alguien hace push o abre un Pull Request.

## Configuración `PISHOP_*` que usa mi paquete

| Variable | Dónde | Para qué |
|---|---|---|
| `PISHOP_DATABASE_URL` | docker-compose | Cada servicio con datos apunta a su propia base en PostgreSQL |
| `PISHOP_REDIS_URL` | docker-compose | Bus de eventos (Redis 8) |
| `PISHOP_CONSUL_URL` | docker-compose | Registro de servicios (Consul) |
| `PISHOP_CONFIG_SERVICE_URL` | docker-compose y verificador | Dónde está el config-service. El verificador lo apunta a `localhost:9`, donde no hay nada, para simularlo apagado |
| `PISHOP_APP_ENV` | verificador | Se usa `qa`, porque en `dev` la plantilla permite ready=200 sin configuración |
| `PISHOP_CATALOGO_SERVICE_URL`, `PISHOP_INVENTARIO_SERVICE_URL`, `PISHOP_PEDIDOS_SERVICE_URL`, `PISHOP_PAGOS_SERVICE_URL` | docker-compose (checkout-bff) | Direcciones por nombre, según el `settings.py` de P06 |
| `PISHOP_CHECKOUT_BFF_URL`, `PISHOP_CATALOGO_URL` | docker-compose (api-publica) | Según el `settings.py` de P07 |
| `PISHOP_PASARELA_MODO` | docker-compose y e2e | Modo de la pasarela simulada (`ok`, `rechazo`...). El e2e lo cambia para probar el pago rechazado |
| `PISHOP_API_KEY` | e2e | Llave para llamar a la API pública. Sale del entorno, nunca del código |

## Decisiones

- **Disponibilidad:** la ruta crítica es una cadena en serie de 7 piezas (98,7065 %, 113,31 h caído al año). Mi propuesta tiene tres mejoras: copias de cada servicio (eje X del cubo), una segunda pasarela y cobrar de forma asíncrona con saga y Outbox. Detalle en [`retos/semana03/README.md`](../../retos/semana03/README.md).
- **Compose:** uso bloques reutilizables (`x-servicio`, `x-sonda`) para no repetir lo mismo 10 veces. Cada servicio espera a que su base esté sana y se revisa con su propia sonda `/health/ready`. Los servicios se llaman por nombre, nunca por IP.
- **E2E con doble de prueba:** como no todos los servicios estaban listos, hice un doble (`pishop_doble.py`) que imita catálogo, inventario, pedidos, pagos y checkout en un solo puerto. La misma prueba sirve contra el sistema real.
- **CI:** las pruebas de cada servicio corren en un ciclo que **no se detiene** en el primer error, para ver todos los que fallan de una vez. `validar_entrega.py --todos` es solo informativo (`|| true`), porque mientras haya paquetes sin entregar siempre fallaría.
- **Verificador:** cada servicio se prueba en un proceso aparte con `TestClient`, para que las librerías de uno no se mezclen con las de otro.
- **Conflicto en `ci.yml`:** en `main` se cambió el CI a Python 3.10 y quedó `pip install httpx<0.28` sin comillas. En bash, que es la terminal del CI, el `<` se lee como "leer de un archivo" y el paso falla. Me quedo con mi versión (Python 3.13, igual que la plantilla), que ya corre el pytest de cada servicio con su propio `requirements.txt`.

## Evidencia

**Punto 1:** `python retos/semana03/disponibilidad.py` muestra la tabla antes/después (98,7065 % → 99,9995 % con las tres mejoras).

**Punto 3:** `python retos/e2e.py --dobles` pasó todas las revisiones: compra feliz CONFIRMADO, el stock baja, la idempotencia no crea un segundo pedido, el pago rechazado da FALLIDO, el stock se devuelve y el pedido queda CANCELADO.

**Punto 5:** el auditor da `[ok]` en la plantilla y en los PR #1 a #4.

**Punto 6:** revisé los servicios de los Pull Requests abiertos el 06/11/2026, cada uno en una copia aparte del repositorio (`git fetch origin pull/N/head:prN`):

| Servicio (PR) | live | startup | ready | Criterio 2 | Criterio 3 | Acción |
|---|---|---|---|---|---|---|
| plantilla-servicio | 200 | 200 | 503 | ✅ | ✅ | — |
| pagos-service (#1) | 200 | 200 | 200 | ✅ | ❌ | Issue [#5](https://github.com/cleangel196809/fundamentos_arquitectura_politecnico/issues/5) |
| config-service (#2) | 200 | 200 | 200 | ✅ | No aplica | — |
| api-publica (#3) | 200 | 200 | 503 | ✅ | ✅ | — |
| checkout-bff (#4) | 200 | 200 | 503 | ✅ | ✅ | — |

- **pagos-service:** `/health/ready` responde 200 sin configuración porque el estado inicia con `config_version: 1` fijo. Reportado en el issue #5.
- **config-service:** no aplica, porque es la fuente de la configuración. No depende de que otro le envíe configuración, así que puede estar listo desde el arranque.

## Uso de IA generativa

Usé Claude (Anthropic) como apoyo en todo el paquete: para entender los temas (disponibilidad, configuración externalizada, sondas, sagas, CI), 

Lo que verifiqué yo:
- Hice a mano los cálculos de serie, paralelo y horas de caída, y los comparé con la salida del script.
- Corrí el auditor con una contraseña de prueba para ver que la detectara, y la quité después.
- Revisé el compose con `docker compose config -q`.
- Corrí el e2e contra el doble y todas las revisiones pasaron.
- Corrí el verificador sobre la plantilla y sobre los 4 servicios de mis compañeros.
- Abrí yo misma el issue con el resultado.
