"""Repositorio versionado de configuración (base propia del config-service).

Cada publicación crea una fila nueva e inmutable: versión monótona creciente por
(app, entorno), con autor, motivo y fecha. Nunca se actualiza ni se borra una
versión: el historial es la auditoría (semana 4, "Versionado de configuración").
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VersionConfig:
    id: int
    app: str
    env: str
    version: int
    data_json: str
    autor: str
    motivo: str
    creado_en: str

    def a_dict(self, con_data: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {
            "app": self.app,
            "env": self.env,
            "version": self.version,
            "autor": self.autor,
            "motivo": self.motivo,
            "creado_en": self.creado_en,
        }
        if con_data:
            d["data"] = json.loads(self.data_json)
        return d


def _resolver_ruta_sqlite(database_url: str) -> str:
    """Convierte URLs como sqlite+aiosqlite:///./config.db o :memory: a ruta sqlite3."""
    if ":memory:" in database_url or not database_url:
        return ":memory:"
    for pref in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(pref):
            ruta = database_url[len(pref) :]
            return ruta or ":memory:"
    return database_url


class Repositorio:
    """Almacén SQLite versionado e inmutable (sin bloqueos de hilos en pruebas)."""

    def __init__(self, database_url: str) -> None:
        self.ruta = _resolver_ruta_sqlite(database_url)
        if self.ruta != ":memory:":
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(self.ruta, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Conexión de base de datos cerrada")
        return self._conn

    async def crear_esquema(self) -> None:
        with self._lock:
            self._c().executescript(
                """
                CREATE TABLE IF NOT EXISTS config_versiones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app TEXT NOT NULL,
                    env TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    autor TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    creado_en TEXT NOT NULL,
                    UNIQUE (app, env, version)
                );
                CREATE INDEX IF NOT EXISTS ix_config_app_env
                    ON config_versiones (app, env, version);
                """
            )
            self._c().commit()

    async def cerrar(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    async def ping(self) -> bool:
        try:
            with self._lock:
                self._c().execute("SELECT 1").fetchone()
            return True
        except Exception:  # noqa: BLE001 - readiness: cualquier fallo = no listo
            return False

    @staticmethod
    def _fila(r: sqlite3.Row | None) -> VersionConfig | None:
        if r is None:
            return None
        return VersionConfig(
            id=r["id"],
            app=r["app"],
            env=r["env"],
            version=r["version"],
            data_json=r["data_json"],
            autor=r["autor"],
            motivo=r["motivo"],
            creado_en=r["creado_en"],
        )

    async def actual(self, app: str, env: str) -> VersionConfig | None:
        with self._lock:
            r = (
                self._c()
                .execute(
                    "SELECT * FROM config_versiones WHERE app = ? AND env = ? ORDER BY version DESC LIMIT 1",
                    (app, env),
                )
                .fetchone()
            )
            return self._fila(r)

    async def obtener(self, app: str, env: str, version: int) -> VersionConfig | None:
        with self._lock:
            r = (
                self._c()
                .execute(
                    "SELECT * FROM config_versiones WHERE app = ? AND env = ? AND version = ?",
                    (app, env, version),
                )
                .fetchone()
            )
            return self._fila(r)

    async def historial(self, app: str, env: str) -> list[VersionConfig]:
        with self._lock:
            filas = (
                self._c()
                .execute(
                    "SELECT * FROM config_versiones WHERE app = ? AND env = ? ORDER BY version ASC",
                    (app, env),
                )
                .fetchall()
            )
            return [self._fila(r) for r in filas if r is not None]

    async def publicar(
        self, app: str, env: str, data: dict[str, Any], autor: str, motivo: str
    ) -> VersionConfig:
        """Inserta la versión N+1 en una sola transacción."""
        with self._lock:
            c = self._c()
            row = c.execute(
                "SELECT COALESCE(MAX(version), 0) AS m FROM config_versiones WHERE app = ? AND env = ?",
                (app, env),
            ).fetchone()
            nueva_version = int(row["m"]) + 1
            ahora = datetime.now(timezone.utc).isoformat()
            data_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
            cur = c.execute(
                """
                INSERT INTO config_versiones (app, env, version, data_json, autor, motivo, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (app, env, nueva_version, data_str, autor, motivo, ahora),
            )
            c.commit()
            return VersionConfig(
                id=int(cur.lastrowid or 0),
                app=app,
                env=env,
                version=nueva_version,
                data_json=data_str,
                autor=autor,
                motivo=motivo,
                creado_en=ahora,
            )

    async def cuenta(self) -> int:
        with self._lock:
            row = self._c().execute("SELECT COUNT(*) AS c FROM config_versiones").fetchone()
            return int(row["c"]) if row else 0
