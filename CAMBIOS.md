# Cambios respecto al repositorio original

| Carpeta / archivo | Cambio | Importancia |
|---|---|---|
| `services/` (estaba vacía) | **10 servicios completos**: catalogo, inventario, pedidos, pagos, notificaciones, reportes, checkout-bff, api-publica, config, descubridor. Cada uno con `app/`, `tests/`, `Dockerfile` multi-etapa, `requirements.txt` y `README.md` | ★★★ |
| `docker-compose.yml` | Reescrito: 13 contenedores, contraseña por base, healthchecks, `depends_on` por salud, redes `interna`/`borde`, volúmenes, límites de recursos, endurecimiento, puertos internos en `127.0.0.1`, Redis 6380 y PostgreSQL 5433 en el anfitrión | ★★★ |
| `infra/initdb/` | `01-bases.sql` documentado + **nuevo** `02-usuarios.sh` (un usuario dueño por cada una de las 6 bases) | ★★★ |
| `.env.example` | 6 contraseñas de base, límite 40/min, puertos del anfitrión | ★★ |
| `scripts/` (nueva) | `generar_env.py`, `generar_datos.py`, `prueba_e2e.py`, `_comun.py` | ★★ |
| `services/api-publica/` | Límite 40/min, cabeceras de seguridad, `/docs` apagado en prod, 409 para compra fallida, registro en Consul, cliente de config, timeout 5 s | ★★ |
| `docker-compose.seguro.yml` | Ahora también cierra PostgreSQL | ★ |
| `herramientas/` | Se agregan `auditar_config.py` y sus pruebas (rol de ciberseguridad) | ★ |
| `.github/workflows/ci.yml` | Instala cada servicio, ruff, pytest, validador, auditoría, bandit y `docker compose build` | ★ |
| `docs/` | `CIBERSEGURIDAD.md`, `descubrimiento.md`, `declaracion-uso-ia.md` | ★ |
| `README.md`, `iniciar.bat`, `detener.bat`, `Makefile`, `.gitattributes`, `.gitignore` | Guía de operación y atajos | ★ |

Sin cambios: `contracts/endpoints.json`, `docs/ENUNCIADO.md`, `docs/CONTRATOS.md`, `docs/ROLES.md`, `plantilla-servicio/`, `ruleta/`, `herramientas/validar_entrega.py`.
