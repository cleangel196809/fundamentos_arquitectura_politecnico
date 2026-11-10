#!/bin/sh
# =============================================================================
# Paso 2 de la inicialización: un USUARIO distinto por base (mínimo privilegio).
#
# Por qué: si alguien roba la contraseña de pagos-service, con ella NO puede
# entrar a la base de pedidos ni a la de catálogo. El superusuario "postgres"
# solo se usa aquí, para crear bases y usuarios; ningún servicio lo conoce.
#
# Las contraseñas llegan como variables de entorno desde el archivo .env
# (docker-compose.yml se las pasa al contenedor de postgres). Nunca se
# escriben en este archivo.
#
# Ojo: este script solo corre cuando el volumen de datos está vacío. Si cambia
# una contraseña en .env, hay que borrar el volumen:  docker compose down -v
# =============================================================================
set -e

crear_dueno_de_base() {
  nombre_base="$1"
  nombre_usuario="$2"
  clave_usuario="$3"

  if [ -z "$clave_usuario" ]; then
    echo "[initdb] FALTA la contraseña de $nombre_usuario en el .env" >&2
    exit 1
  fi

  # Las variables de psql (:"nombre" e :'valor') citan correctamente los
  # identificadores y los textos, así una contraseña con comillas no rompe el SQL.
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
       -v usuario="$nombre_usuario" -v clave="$clave_usuario" -v base="$nombre_base" <<'SQL'
CREATE ROLE :"usuario" LOGIN PASSWORD :'clave' CONNECTION LIMIT 20;
ALTER DATABASE :"base" OWNER TO :"usuario";
REVOKE ALL ON DATABASE :"base" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"base" TO :"usuario";
SQL
  echo "[initdb] base $nombre_base lista, dueño: $nombre_usuario"
}

crear_dueno_de_base pg_catalogo   usr_catalogo   "$PG_CLAVE_CATALOGO"
crear_dueno_de_base pg_inventario usr_inventario "$PG_CLAVE_INVENTARIO"
crear_dueno_de_base pg_pedidos    usr_pedidos    "$PG_CLAVE_PEDIDOS"
crear_dueno_de_base pg_pagos      usr_pagos      "$PG_CLAVE_PAGOS"
crear_dueno_de_base pg_notif      usr_notif      "$PG_CLAVE_NOTIF"
crear_dueno_de_base pg_reportes   usr_reportes   "$PG_CLAVE_REPORTES"
