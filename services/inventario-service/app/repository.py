"""Reglas de inventario sobre pg_inventario.

Clave del diseño — evitar la condición de carrera: dos compras simultáneas por
la ÚLTIMA unidad. En lugar de "leer, restar y guardar" (que deja una ventana
entre la lectura y la escritura), se hace un UPDATE condicional atómico:

    UPDATE existencias SET reservado = reservado + :n
    WHERE sku = :sku AND cantidad - reservado >= :n

La base de datos garantiza que solo una de las dos peticiones cumple la
condición; la otra afecta 0 filas y recibe 409.
"""
import json
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ErrorDeNegocio
from app.models import ExistenciaFila, ReservaFila, RespuestaIdempotenteFila
from app.schemas import ReservaSolicitud, ReservaVista, StockVista


def a_vista(existencia: ExistenciaFila) -> StockVista:
    return StockVista(sku=existencia.sku, cantidad=existencia.cantidad, reservado=existencia.reservado,
                      disponible=existencia.cantidad - existencia.reservado)


class RepositorioInventario:
    def __init__(self, sesion: AsyncSession):
        self._sesion = sesion

    # ------------------------------------------------------------- existencias
    async def consultar(self, sku: str) -> StockVista:
        existencia = await self._sesion.get(ExistenciaFila, sku)
        if existencia is None:
            raise ErrorDeNegocio(404, f"No hay registro de inventario para {sku}")
        return a_vista(existencia)

    async def fijar_cantidad(self, sku: str, unidades: int) -> StockVista:
        existencia = await self._sesion.get(ExistenciaFila, sku)
        if existencia is None:
            existencia = ExistenciaFila(sku=sku, cantidad=unidades, reservado=0)
            self._sesion.add(existencia)
        elif unidades < existencia.reservado:
            raise ErrorDeNegocio(409, f"No se puede dejar {unidades}: hay {existencia.reservado} unidades reservadas",
                                 "STOCK_MENOR_QUE_RESERVADO")
        else:
            existencia.cantidad = unidades
        await self._sesion.commit()
        return a_vista(existencia)

    # ------------------------------------------------------------- idempotencia
    async def respuesta_guardada(self, clave: str) -> tuple[int, dict] | None:
        guardada = await self._sesion.get(RespuestaIdempotenteFila, clave)
        return (guardada.codigo_http, json.loads(guardada.cuerpo_json)) if guardada else None

    # ------------------------------------------------------------- reservas
    async def reservar(self, pedido: ReservaSolicitud, clave: str) -> tuple[int, dict]:
        previa = await self.respuesta_guardada(clave)
        if previa:
            return previa   # mismo reintento => misma respuesta, sin descontar otra vez

        apartado = await self._sesion.execute(
            update(ExistenciaFila)
            .where(ExistenciaFila.sku == pedido.sku,
                   ExistenciaFila.cantidad - ExistenciaFila.reservado >= pedido.cantidad)
            .values(reservado=ExistenciaFila.reservado + pedido.cantidad)
        )
        if apartado.rowcount == 0:
            await self._sesion.rollback()
            if await self._sesion.get(ExistenciaFila, pedido.sku) is None:
                raise ErrorDeNegocio(404, f"No hay inventario para {pedido.sku}")
            raise ErrorDeNegocio(409, f"Stock insuficiente para {pedido.sku}", "STOCK_INSUFICIENTE")

        reserva_nueva = ReservaFila(reserva_id=f"R-{uuid.uuid4().hex[:12]}", sku=pedido.sku,
                                    cantidad=pedido.cantidad, pedido_id=pedido.pedido_id, estado="ACTIVA")
        self._sesion.add(reserva_nueva)
        cuerpo = ReservaVista.model_validate(reserva_nueva).model_dump()
        self._sesion.add(RespuestaIdempotenteFila(clave=clave, codigo_http=201, cuerpo_json=json.dumps(cuerpo)))
        try:
            await self._sesion.commit()     # reserva + respuesta guardada en UNA transacción
        except IntegrityError:
            # Llegaron dos peticiones con la misma clave al mismo tiempo: gana la primera.
            await self._sesion.rollback()
            ganadora = await self.respuesta_guardada(clave)
            if ganadora:
                return ganadora
            raise
        return 201, cuerpo

    async def _reserva(self, reserva_id: str) -> ReservaFila:
        reserva = await self._sesion.get(ReservaFila, reserva_id)
        if reserva is None:
            raise ErrorDeNegocio(404, f"No existe la reserva {reserva_id}")
        return reserva

    async def liberar(self, reserva_id: str) -> ReservaVista:
        """Compensación de la saga: devuelve las unidades. Liberar dos veces no devuelve doble."""
        reserva = await self._reserva(reserva_id)
        if reserva.estado == "CONFIRMADA":
            raise ErrorDeNegocio(409, "La reserva ya fue confirmada; no se puede liberar", "RESERVA_CONFIRMADA")
        if reserva.estado == "ACTIVA":
            await self._sesion.execute(
                update(ExistenciaFila).where(ExistenciaFila.sku == reserva.sku)
                .values(reservado=ExistenciaFila.reservado - reserva.cantidad)
            )
            reserva.estado = "LIBERADA"
            await self._sesion.commit()
        return ReservaVista.model_validate(reserva)

    async def confirmar(self, reserva_id: str) -> ReservaVista:
        """Venta cerrada: las unidades salen de bodega definitivamente (idempotente)."""
        reserva = await self._reserva(reserva_id)
        if reserva.estado == "LIBERADA":
            raise ErrorDeNegocio(409, "La reserva fue liberada; no se puede confirmar", "RESERVA_LIBERADA")
        if reserva.estado == "ACTIVA":
            await self._sesion.execute(
                update(ExistenciaFila).where(ExistenciaFila.sku == reserva.sku)
                .values(cantidad=ExistenciaFila.cantidad - reserva.cantidad,
                        reservado=ExistenciaFila.reservado - reserva.cantidad)
            )
            reserva.estado = "CONFIRMADA"
            await self._sesion.commit()
        return ReservaVista.model_validate(reserva)

    async def hay_existencias(self) -> bool:
        return await self._sesion.scalar(select(ExistenciaFila.sku).limit(1)) is not None
