"""
Modulo de Observabilidad para pedidos-service (Semana 6).
Configura structlog (JSON estructurado a stdout) y el proveedor de trazas OpenTelemetry con exportador OTLP.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, Request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import structlog

# ── 1. Configuracion de Registros Estructurados (structlog) ───────────────────

def configurar_registros() -> None:
    """Configura structlog para emitir JSON puro a stdout con contexto inyectado."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


# ── 2. Proveedor de Trazas OpenTelemetry ──────────────────────────────────────

def configurar_trazas(service_name: str = "pedidos-service") -> trace.Tracer:
    """Configura el TracerProvider con OTLPSpanExporter en modo Batch (asincrono)."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    env = os.getenv("PISHOP_APP_ENV", "dev")

    recurso = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "deployment.environment": env,
    })

    proveedor = TracerProvider(resource=recurso)
    
    # BatchSpanProcessor envia en lotes si hay un endpoint configurado
    if endpoint and endpoint.strip():
        try:
            exportador = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            proveedor.add_span_processor(BatchSpanProcessor(exportador))
        except Exception:
            pass  # En pruebas unitarias opera de forma no bloqueante

    trace.set_tracer_provider(proveedor)
    return trace.get_tracer("pishop.pedidos")


tracer = trace.get_tracer("pishop.pedidos")
log = structlog.get_logger()


# ── 3. Instrumentacion Automatica de FastAPI y HTTPX ─────────────────────────

def instrumentar_aplicacion(app: FastAPI) -> None:
    """Instrumenta FastAPI (excluyendo sondas) y llamadas salientes de HTTPX."""
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health/live,health/ready,health/startup,openapi.json,docs")
    HTTPXClientInstrumentor().instrument()
