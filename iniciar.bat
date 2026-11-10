@echo off
REM =====================================================================
REM  PiShop Cloud - arranque en Windows (doble clic o desde cmd)
REM  1) crea el .env con claves aleatorias si no existe
REM  2) construye y levanta todo con docker compose
REM =====================================================================
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo [x] Docker no responde. Abra Docker Desktop y espere a que diga "Engine running".
  pause
  exit /b 1
)

if not exist ".env" (
  echo [*] No hay .env: generando uno con claves aleatorias...
  python scripts\generar_env.py
  if errorlevel 1 copy .env.example .env >nul
)

echo [*] Construyendo y levantando PiShop Cloud (la primera vez tarda varios minutos)...
docker compose up -d --build
if errorlevel 1 (
  echo [x] Fallo docker compose. Revise el mensaje de arriba.
  pause
  exit /b 1
)

echo.
echo [*] Estado de los contenedores:
docker compose ps
echo.
echo  API publica ....... http://localhost:8000/docs
echo  Consul ............ http://localhost:8500
echo  Prueba completa ... python scripts\prueba_e2e.py
echo  Datos ficticios ... python scripts\generar_datos.py
pause
