# Ciberseguridad en PiShop Cloud — qué se hizo y qué se agregó como plus

Rol: seguridad transversal (atributo **Seguridad** de ISO/IEC 25010). Referencia: guía *Rol y Estrategia de Ciberseguridad — PiShop Cloud*.

## 1. Lo que pide la guía (checklist) — cumplido

| Ítem de la guía | Implementación | Cómo se comprueba |
|---|---|---|
| Gobernanza de secretos (factor III) | Toda credencial entra por `PISHOP_*`; los secretos son `SecretStr` y `hide_input_in_errors=True` | `python herramientas/auditar_config.py` (R1, R2) |
| Autenticación `X-API-Key` → 401 | `services/api-publica/app/seguridad.py`, comparación en tiempo constante (`hmac.compare_digest`) | `tests/test_seguridad.py` |
| Rate limiting → 429 + `Retry-After` | **40 peticiones/min por clave** (requisito del proyecto) | prueba `test_41_peticiones...` y `scripts/prueba_e2e.py --probar-limite` |
| Sanitización (Pydantic v2) → 422 | `extra="forbid"`, rangos, patrones `^[A-Za-z0-9_.\-]+$` en identificadores | pruebas 422 de cada servicio |
| Errores sin exponer detalles | API: `application/problem+json` (RFC 9457); internos: `{"detalle","codigo"}`; nunca la traza | `test_error_inesperado_devuelve_500_sin_exponer_detalles` |
| Timeouts explícitos en httpx | Todos los clientes con `httpx.Timeout(...)`; un cliente por proceso (bulkhead) | auditoría R3 |
| Aislamiento de red | Solo el 8000 abierto a la red; el resto en `127.0.0.1`; perfil `docker-compose.seguro.yml` cierra todo | auditoría R5 |

## 2. PLUS agregados (para explicar en la sustentación)

1. **Un usuario de PostgreSQL por base (mínimo privilegio).** `infra/initdb/02-usuarios.sh` crea `usr_catalogo`, `usr_pagos`, etc. Cada uno es dueño solo de su base y se le quita el permiso `CONNECT` al público. *Probado:* `usr_catalogo` intentando entrar a `pg_pagos` recibe `User does not have CONNECT privilege`. Si roban la clave de un servicio, no se llevan las otras 5 bases.
2. **La contraseña nunca va dentro de la URL de conexión.** `PISHOP_DATABASE_URL` no lleva clave; `PISHOP_DATABASE_PASSWORD` llega aparte como `SecretStr` y se inserta en el último momento (`app/base_datos.py`). Así no aparece en logs ni en mensajes de error.
3. **Generador de `.env` con claves aleatorias** (`scripts/generar_env.py`, módulo `secrets`). Evita que lleguen a producción claves de ejemplo como `cambiar-esto`.
4. **Contenedores endurecidos** (en `docker-compose.yml`, plantilla `x-endurecimiento`): usuario sin root (`uid 10001`), sistema de archivos de solo lectura (`read_only`), `cap_drop: ALL`, `no-new-privileges`, límites de CPU y memoria (un servicio atacado no tumba a los demás) y Dockerfile **multi-etapa** (la imagen final no lleva compiladores).
5. **Puertos internos solo en `127.0.0.1`.** Se pueden probar desde su PC, pero un compañero en la misma Wi-Fi no puede entrar a PostgreSQL ni a pagos.
6. **Cabeceras de seguridad HTTP** en la API pública (OWASP Secure Headers): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`, `Referrer-Policy`, `Cache-Control: no-store`, `Permissions-Policy`. Además uvicorn corre con `--no-server-header` (no se revela el software del servidor).
7. **`/docs` deshabilitado en producción** (`PISHOP_APP_ENV=prod`): un atacante no recibe el mapa de la API.
8. **Idempotencia como control antifraude:** la misma `Idempotency-Key` nunca cobra dos veces (`pagos-service`, clave `UNIQUE` en la base) ni descuenta dos veces el stock.
9. **Condición de carrera cerrada en inventario:** `UPDATE ... WHERE cantidad - reservado >= n` atómico; probado con 10 compradores simultáneos por 2 unidades (exactamente 2 ganan).
10. **Config-service con token de administración opcional** (`PISHOP_CONFIG_ADMIN_TOKEN` → cabecera `X-Token-Admin`) y auditoría obligatoria (`X-Autor`) en cada cambio.
11. **Trazabilidad:** cabecera `X-Correlacion-Id` que viaja de la API al BFF y a los core: permite seguir una compra sospechosa en todos los logs.
12. **Simulador de pasarela bloqueado en producción** (`PUT /_simulador/pasarela/modo` devuelve 404 si `APP_ENV=prod`).
13. **CI con controles de seguridad:** el pipeline ejecuta la auditoría (`auditar_config.py` + sus pruebas) y **bandit** (análisis estático de seguridad de Python). Hoy: `bandit -ll` sin hallazgos.

## 3. Riesgos que quedan (dígalos si le preguntan — demuestra criterio)

- No hay **TLS/HTTPS**: el tráfico va en claro. Se resuelve con Traefik como edge (semana 5) y certificados.
- Una sola API key compartida; lo ideal es **OAuth 2.1 / OIDC con JWT** (Keycloak, semana 7) con *scopes* por endpoint.
- Los secretos viven en un archivo `.env`; en producción irían a un gestor (Vault, AWS Secrets Manager) con rotación.
- Con varias réplicas de la API, el límite en memoria es por réplica; con `PISHOP_RATE_LIMIT_STORAGE_URI=redis://redis:6379/1` sería global.
- Detrás de un proxy, el límite por IP debería leer `X-Forwarded-For` solo de un proxy de confianza.

## 4. Comandos de evidencia

```bat
python herramientas\auditar_config.py
python -m pytest -q herramientas\test_auditar_config.py
cd services\api-publica && python -m pytest -q && cd ..\..
python scripts\prueba_e2e.py --probar-limite
docker exec -it pishop-cloud-postgres-1 psql -U usr_catalogo -d pg_pagos
   (debe fallar: el usuario de catálogo no puede entrar a la base de pagos)
```
