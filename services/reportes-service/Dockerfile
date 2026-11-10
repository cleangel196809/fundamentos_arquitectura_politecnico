# ---------- Etapa 1: instalar dependencias (con herramientas de compilación) ----------
FROM python:3.13-slim AS construccion
WORKDIR /construccion
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/dependencias -r requirements.txt

# ---------- Etapa 2: imagen final, liviana y sin privilegios ----------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PISHOP_HTTP_PORT=8006
COPY --from=construccion /dependencias /usr/local
WORKDIR /srv
COPY app ./app
# Mínimo privilegio: el proceso NO corre como root.
RUN useradd --system --no-create-home --uid 10001 pishop
USER pishop
EXPOSE 8006
# Docker (y depends_on: service_healthy) usan la sonda de disponibilidad.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health/ready' % os.environ['PISHOP_HTTP_PORT'], timeout=2)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PISHOP_HTTP_PORT} --no-server-header"]
