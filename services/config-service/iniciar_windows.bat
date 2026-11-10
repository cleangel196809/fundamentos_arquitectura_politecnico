@echo off
rem Doble clic: prepara el entorno, arranca config-service (P08) y abre Swagger.
chcp 65001 >nul
cd /d "%~dp0"
title config-service P08 - puerto 8010 (cierre esta ventana para apagarlo)
where python >nul 2>nul || (echo [x] No se encontro Python. Instale Python 3.11+ marcando "Add to PATH". & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" echo Creando entorno virtual .venv ...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
echo Instalando dependencias (la primera vez tarda 1-2 minutos)...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || (echo [x] Fallo la instalacion. Revise internet. & pause & exit /b 1)
rem Configuracion por variables de entorno (factor III). Token SOLO de prueba para dev.
if not defined PISHOP_APP_ENV set "PISHOP_APP_ENV=dev"
if not defined PISHOP_API_TOKEN set "PISHOP_API_TOKEN=pishop-dev-2026"
rem Abre el navegador en Swagger unos segundos despues de arrancar
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start "" http://127.0.0.1:8010/docs"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
pause
