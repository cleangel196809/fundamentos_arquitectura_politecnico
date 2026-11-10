# Atajos para Linux/Mac (en Windows use iniciar.bat / detener.bat)
up:      ; [ -f .env ] || python3 scripts/generar_env.py; docker compose up -d --build
down:    ; docker compose down
limpiar: ; docker compose down -v
seguro:  ; docker compose -f docker-compose.yml -f docker-compose.seguro.yml up -d --build
test:    ; for d in services/*/; do (cd $$d && python3 -m pytest -q) || exit 1; done
e2e:     ; python3 scripts/prueba_e2e.py
seed:    ; python3 scripts/generar_datos.py
auditar: ; python3 herramientas/auditar_config.py
.PHONY: up down limpiar seguro test e2e seed auditar
