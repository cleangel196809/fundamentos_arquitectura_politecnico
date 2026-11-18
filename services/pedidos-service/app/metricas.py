"""
Instrumentos de metricas de OpenTelemetry para pedidos-service (Semana 6).
Cumple con el patron RED (Rate, Errors, Duration) y cardinalidad acotada.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from opentelemetry import metrics

medidor = metrics.get_meter("pishop.pedidos")

# 1. Contador de negocio (solo crece): Total de pedidos confirmados
pedidos_creados_total = medidor.create_counter(
    "pedidos_creados_total",
    unit="1",
    description="Total de pedidos confirmados creados en el servicio",
)

# 2. Histograma de duracion (unit="s"): Alimenta latencia p50 y p95 del panel RED
pedido_duracion_segundos = medidor.create_histogram(
    "pedido_duracion_segundos",
    unit="s",
    description="Distribucion del tiempo de procesamiento al crear un pedido",
)

# 3. Medidor UpDownCounter (sube y baja): Estado vivo de eventos en cola Outbox
pedidos_pendientes_outbox = medidor.create_up_down_counter(
    "pedidos_pendientes_outbox",
    unit="1",
    description="Cantidad de eventos pendientes de publicacion en la tabla outbox",
)

# 4. Contador de cancelaciones
pedidos_cancelados_total = medidor.create_counter(
    "pedidos_cancelados_total",
    unit="1",
    description="Total de pedidos cancelados (compensaciones)",
)


@contextmanager
def medir_duracion_pedido(canal: str = "web") -> Generator[None, None, None]:
    """Mide la duracion de la creacion de un pedido con atributos de baja cardinalidad."""
    t0 = time.monotonic()
    estado = "exito"
    try:
        yield
    except Exception:
        estado = "error"
        raise
    finally:
        duracion = time.monotonic() - t0
        # NUNCA usar pedido_id, sku ni usuario_id como atributos de metrica (evita explosion de series)
        pedido_duracion_segundos.record(duracion, {"canal": canal, "estado": estado})
