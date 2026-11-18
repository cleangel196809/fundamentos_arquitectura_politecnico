"""
Pedidos router – /v1/pedidos
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import IdempotencyRecord, OutboxEvent, Pedido
from app.schemas import CrearPedidoRequest, CrearPedidoResponse, PedidoResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/pedidos", tags=["pedidos"])


def _pedido_to_response(p: Pedido) -> PedidoResponse:
    return PedidoResponse(
        pedido_id=p.id,
        cliente_id=p.cliente_id,
        sku=p.sku,
        cantidad=p.cantidad,
        monto_cop=p.monto_cop,
        estado=p.estado,
        creado_en=p.creado_en,
    )


def _build_outbox_payload(pedido: Pedido) -> str:
    ocurrido_en = pedido.creado_en if hasattr(pedido, "creado_en") else datetime.now(timezone.utc)
    return json.dumps(
        {
            "pedido_id": pedido.id,
            "cliente_id": pedido.cliente_id,
            "sku": pedido.sku,
            "cantidad": pedido.cantidad,
            "monto_cop": pedido.monto_cop,
            "ocurrido_en": (
                ocurrido_en.isoformat()
                if isinstance(ocurrido_en, datetime)
                else str(ocurrido_en)
            ),
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CrearPedidoResponse)
async def crear_pedido(
    body: CrearPedidoRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
) -> CrearPedidoResponse:
    # ── Idempotency check ────────────────────────────────────────────────────
    if idempotency_key:
        result = await db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.id == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            response.status_code = existing.status_code
            return CrearPedidoResponse(**json.loads(existing.response_body))

    # ── Create pedido + outbox event in ONE transaction ──────────────────────
    pedido = Pedido(
        cliente_id=body.cliente_id,
        sku=body.sku,
        cantidad=body.cantidad,
        monto_cop=body.monto_cop,
    )
    db.add(pedido)
    await db.flush()  # populate pedido.id

    outbox = OutboxEvent(
        pedido_id=pedido.id,
        tipo="PedidoCreado",
        payload=_build_outbox_payload(pedido),
    )
    db.add(outbox)

    resp_body = CrearPedidoResponse(pedido_id=pedido.id, estado=pedido.estado)

    if idempotency_key:
        idem = IdempotencyRecord(
            id=idempotency_key,
            response_body=resp_body.model_dump_json(),
            status_code=201,
        )
        db.add(idem)

    await db.commit()
    return resp_body


@router.get("/{pedido_id}", response_model=PedidoResponse)
async def obtener_pedido(
    pedido_id: str,
    db: AsyncSession = Depends(get_db),
) -> PedidoResponse:
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(
            status_code=404,
            detail={"detalle": "Pedido no encontrado", "codigo": "PEDIDO_NOT_FOUND"},
        )
    return _pedido_to_response(pedido)


@router.post("/{pedido_id}/cancelar", response_model=PedidoResponse)
async def cancelar_pedido(
    pedido_id: str,
    db: AsyncSession = Depends(get_db),
) -> PedidoResponse:
    result = await db.execute(select(Pedido).where(Pedido.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(
            status_code=404,
            detail={"detalle": "Pedido no encontrado", "codigo": "PEDIDO_NOT_FOUND"},
        )

    if pedido.estado == "CANCELADO":
        return _pedido_to_response(pedido)

    # ── Update estado + insert outbox in ONE transaction ─────────────────────
    pedido.estado = "CANCELADO"
    db.add(pedido)

    outbox = OutboxEvent(
        pedido_id=pedido.id,
        tipo="PedidoCancelado",
        payload=_build_outbox_payload(pedido),
    )
    db.add(outbox)

    await db.commit()
    await db.refresh(pedido)
    return _pedido_to_response(pedido)
