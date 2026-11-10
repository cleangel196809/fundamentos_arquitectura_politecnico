"""Almacén versionado de configuración (en memoria, sembrado desde seed.json).

Cada cambio crea una versión nueva y monótona (v1, v2, v3...) con autor,
motivo y fecha. Nunca se edita una versión vieja: el rollback también crea
una versión nueva con los datos de la anterior (así queda en el historial).
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class VersionConfig:
    version: int
    autor: str
    motivo: str
    data: dict
    fecha: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AlmacenConfiguracion:
    def __init__(self):
        self._historiales: dict[str, list[VersionConfig]] = {}

    @staticmethod
    def _llave(aplicacion: str, entorno: str) -> str:
        return f"{aplicacion}:{entorno}"

    def sembrar(self, archivo: Path) -> int:
        if not archivo.exists():
            return 0
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        for llave, inicial in contenido.items():
            self._historiales[llave] = [VersionConfig(version=1, autor=inicial["autor"], motivo=inicial["motivo"], data=inicial["data"])]
        return len(contenido)

    def historial(self, aplicacion: str, entorno: str) -> list[VersionConfig]:
        return self._historiales.get(self._llave(aplicacion, entorno), [])

    def vigente(self, aplicacion: str, entorno: str, version: int | None = None) -> VersionConfig | None:
        versiones = self.historial(aplicacion, entorno)
        if not versiones:
            return None
        if version is None:
            return versiones[-1]
        return next((v for v in versiones if v.version == version), None)

    def publicar(self, aplicacion: str, entorno: str, data: dict, autor: str, motivo: str) -> VersionConfig:
        versiones = self._historiales.setdefault(self._llave(aplicacion, entorno), [])
        nueva = VersionConfig(version=(versiones[-1].version + 1) if versiones else 1, autor=autor, motivo=motivo, data=data)
        versiones.append(nueva)
        return nueva

    @staticmethod
    def resumen(version: VersionConfig) -> dict:
        datos = asdict(version)
        datos.pop("data")
        return datos
