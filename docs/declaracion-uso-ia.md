
# Declaración de uso de asistentes de IA

> Complete y firme antes de entregar. Marque solo lo que realmente hizo.

1. **Herramientas:** Claude (Anthropic), versión Opus.
2. **Partes donde se usó:** estructura de los 10 servicios en `services/`, `docker-compose.yml`, `infra/initdb/`, `scripts/`, pruebas `pytest`, y redacción de `README.md`, `docs/CIBERSEGURIDAD.md` y `docs/descubrimiento.md`.
3. **Porcentaje aproximado del código con asistencia de IA:** ____ %
4. **Qué hice para verificar y comprender:**
   - [ ] Leí cada servicio y puedo explicar su `main.py`, sus tablas (`models.py`) y sus pruebas.
   - [ ] Ejecuté `docker compose up -d --build` en mi equipo y vi los 13 contenedores `healthy`.
   - [ ] Ejecuté `python scripts\prueba_e2e.py` y guardé la salida como evidencia.
   - [ ] Ejecuté `python herramientas\validar_entrega.py --todos` y `python herramientas\auditar_config.py`.
   - [ ] Entré a PostgreSQL (puerto 5433) y revisé las 6 bases.
   - [ ] Modifiqué algo en vivo (por ejemplo, el límite de 40/min o el modo de la pasarela) para practicar la sustentación.
5. *"Declaramos que comprendemos la totalidad del código y la documentación entregados y que estamos en capacidad de explicar, justificar y modificar cualquier parte de ellos."*

Firma: ______________________   Fecha: ____________
