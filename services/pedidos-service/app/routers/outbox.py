"""
Outbox router – /v1/outbox
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OutboxEvent
from app.schemas import OutboxEventResponse

router = APIRouter(prefix="/v1/outbox", tags=["outbox"])


@router.get("/pendientes", response_model=list[OutboxEventResponse])
async def pendientes(db: AsyncSession = Depends(get_db)) -> list[OutboxEventResponse]:
    result = await db.execute(
        select(OutboxEvent)
        .where(OutboxEvent.publicado_en.is_(None))
        .order_by(OutboxEvent.creado_en)
    )
    events = result.scalars().all()
    return [
        OutboxEventResponse(
            evento_id=e.id,
            pedido_id=e.pedido_id,
            tipo=e.tipo,
            payload=e.payload,
            creado_en=e.creado_en,
        )
        for e in events
    ]
