@echo off
REM Apaga PiShop Cloud. Agregue "borrar" para eliminar tambien las bases:  detener.bat borrar
cd /d "%~dp0"
if /i "%1"=="borrar" (
  docker compose down -v
  echo Contenedores y volumenes eliminados: la proxima vez PostgreSQL se crea de cero.
) else (
  docker compose down
  echo Contenedores detenidos. Los datos de PostgreSQL y Redis se conservan.
)
