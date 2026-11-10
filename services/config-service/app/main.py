"""config-service (P08) — fuente única de verdad de la configuración.

Rutas del contrato:
  GET  /config/{app_name}/{env}                       versión vigente (ETag; If-None-Match -> 304)
       ?version=N                                     una versión histórica
  PUT  /config/{app_name}/{env}                       publica una versión nueva (exige X-Autor)
  GET  /config/{app_name}/{env}/versions              historial: autor, motivo, fecha
  POST /config/{app_name}/{env}/rollback/{version}    vuelve a una versión anterior

Los demás servicios lo consultan cada 15 s (app/cliente_config.py). Si este
servicio cae, ellos siguen con su última configuración conocida.
"""
import hmac
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app import registro_consul
from app.almacen import AlmacenConfiguracion
from app.errores import ErrorDeNegocio, instalar_manejadores
from app.medicion import MedidorDeTiempos
from app.settings import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
bitacora = logging.getLogger("config-service")
NOMBRE_VALIDO = r"^[a-z0-9][a-z0-9-]{1,48}$"
ENTORNO_VALIDO = r"^(dev|qa|stg|prod)$"


class CambioDeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: dict
    motivo: str = Field(min_length=3, max_length=200)


def crear_app(ajustes: Settings | None = None) -> FastAPI:
    ajustes = ajustes or get_settings()
    instancia = f"{ajustes.service_name}-{uuid.uuid4().hex[:5]}"
    almacen = AlmacenConfiguracion()
    progreso = {"arranco": False}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        cargadas = almacen.sembrar(ajustes.archivo_semilla)
        bitacora.info("config-service sembrado con %s combinaciones servicio:entorno", cargadas)
        await registro_consul.registrar(ajustes, instancia)
        progreso["arranco"] = True
        yield
        progreso["arranco"] = False
        await registro_consul.dar_de_baja(ajustes, instancia)

    app = FastAPI(title=ajustes.service_name, version="1.0.0", lifespan=lifespan,
                  description="Servidor central de configuración versionada.")
    app.add_middleware(MedidorDeTiempos, umbral_ms=ajustes.umbral_respuesta_ms)
    instalar_manejadores(app)

    def exigir_permiso_de_escritura(token_recibido: str | None) -> None:
        esperado = ajustes.admin_token.get_secret_value()
        if esperado and not (token_recibido and hmac.compare_digest(token_recibido, esperado)):
            raise ErrorDeNegocio(401, "Falta o es inválida la cabecera X-Token-Admin", "NO_AUTORIZADO")

    # ------------------------------------------------------------------ sondas
    @app.get("/health/live", tags=["salud"])
    def vivo() -> dict:
        return {"status": "alive", "instance": instancia}

    @app.get("/health/startup", tags=["salud"])
    def arranque(respuesta: Response) -> dict:
        if not progreso["arranco"]:
            respuesta.status_code = 503
        return {"started": progreso["arranco"]}

    @app.get("/health/ready", tags=["salud"])
    def listo(respuesta: Response) -> dict:
        # El config-service ES la fuente de configuración: no espera una versión de nadie.
        if not progreso["arranco"]:
            respuesta.status_code = 503
        return {"ready": progreso["arranco"], "config_version": 1 if progreso["arranco"] else 0, "instance": instancia}

    # ------------------------------------------------------------------ configuración
    @app.get("/config/{app_name}/{env}", tags=["config"])
    def leer(respuesta: Response,
             app_name: str = Path(pattern=NOMBRE_VALIDO), env: str = Path(pattern=ENTORNO_VALIDO),
             version: int | None = Query(None, ge=1),
             if_none_match: str | None = Header(default=None, max_length=40)):
        elegida = almacen.vigente(app_name, env, version)
        if elegida is None:
            raise ErrorDeNegocio(404, f"No hay configuración para {app_name} en {env}")
        etiqueta = f'"v{elegida.version}"'
        if version is None and if_none_match == etiqueta:
            return Response(status_code=304, headers={"ETag": etiqueta})
        respuesta.headers["ETag"] = etiqueta
        return {"app": app_name, "env": env, "version": elegida.version, "data": elegida.data}

    @app.put("/config/{app_name}/{env}", tags=["config"])
    def publicar(cambio: CambioDeConfig, respuesta: Response,
                 app_name: str = Path(pattern=NOMBRE_VALIDO), env: str = Path(pattern=ENTORNO_VALIDO),
                 x_autor: str | None = Header(default=None, max_length=60),
                 x_token_admin: str | None = Header(default=None, max_length=200)):
        exigir_permiso_de_escritura(x_token_admin)
        if not x_autor or not x_autor.strip():
            raise ErrorDeNegocio(400, "La cabecera X-Autor es obligatoria (auditoría)", "FALTA_AUTOR")
        nueva = almacen.publicar(app_name, env, cambio.data, x_autor.strip(), cambio.motivo)
        bitacora.info("config %s:%s -> v%s por %s (%s)", app_name, env, nueva.version, nueva.autor, nueva.motivo)
        respuesta.headers["ETag"] = f'"v{nueva.version}"'
        return {"app": app_name, "env": env, "version": nueva.version, "data": nueva.data}

    @app.get("/config/{app_name}/{env}/versions", tags=["config"])
    def versiones(app_name: str = Path(pattern=NOMBRE_VALIDO), env: str = Path(pattern=ENTORNO_VALIDO)):
        lista = almacen.historial(app_name, env)
        if not lista:
            raise ErrorDeNegocio(404, f"No hay configuración para {app_name} en {env}")
        return [almacen.resumen(v) for v in lista]

    @app.post("/config/{app_name}/{env}/rollback/{version}", tags=["config"])
    def revertir(app_name: str = Path(pattern=NOMBRE_VALIDO), env: str = Path(pattern=ENTORNO_VALIDO),
                 version: int = Path(ge=1),
                 x_autor: str | None = Header(default=None, max_length=60),
                 x_token_admin: str | None = Header(default=None, max_length=200)):
        exigir_permiso_de_escritura(x_token_admin)
        anterior = almacen.vigente(app_name, env, version)
        if anterior is None:
            raise ErrorDeNegocio(404, f"No existe la versión {version} de {app_name}:{env}")
        nueva = almacen.publicar(app_name, env, dict(anterior.data), (x_autor or "rollback").strip(),
                                 f"rollback a v{version}")
        return {"app": app_name, "env": env, "version": nueva.version, "data": nueva.data}

    return app


app = crear_app()
