from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.producto import Producto
from app.models.reserva_stock import ReservaStock


ESTADOS_QUE_DESCUENTAN = ("activa", "enviada_dux")


def bloquear_productos(db: Session, producto_ids: set[int]) -> None:
    if not producto_ids:
        return
    db.execute(
        select(Producto.id)
        .where(Producto.id.in_(producto_ids))
        .order_by(Producto.id)
        .with_for_update()
    ).all()


def cantidades_reservadas(db: Session, producto_ids: set[int]) -> dict[int, int]:
    if not producto_ids:
        return {}
    filas = db.execute(
        select(ReservaStock.producto_id, func.sum(ReservaStock.cantidad))
        .where(
            ReservaStock.producto_id.in_(producto_ids),
            ReservaStock.estado.in_(ESTADOS_QUE_DESCUENTAN),
        )
        .group_by(ReservaStock.producto_id)
    ).all()
    return {producto_id: int(cantidad) for producto_id, cantidad in filas}


def cantidades_reservadas_por_talle(db: Session, producto_ids: set[int]) -> dict[tuple[int, int], int]:
    if not producto_ids:
        return {}
    filas = db.execute(
        select(ReservaStock.producto_id, ReservaStock.talle, func.sum(ReservaStock.cantidad))
        .where(ReservaStock.producto_id.in_(producto_ids), ReservaStock.talle.is_not(None), ReservaStock.estado.in_(ESTADOS_QUE_DESCUENTAN))
        .group_by(ReservaStock.producto_id, ReservaStock.talle)
    ).all()
    return {(producto_id, talle): int(cantidad) for producto_id, talle, cantidad in filas}


def liberar_reservas_pedido(db: Session, pedido_id: int) -> None:
    reservas = db.scalars(
        select(ReservaStock).where(
            ReservaStock.pedido_id == pedido_id,
            ReservaStock.estado == "activa",
        )
    ).all()
    ahora = datetime.now(timezone.utc)
    for reserva in reservas:
        reserva.estado = "liberada"
        reserva.liberada_en = ahora


def marcar_reservas_enviadas_dux(db: Session, pedido_id: int) -> None:
    reservas = db.scalars(
        select(ReservaStock).where(
            ReservaStock.pedido_id == pedido_id,
            ReservaStock.estado == "activa",
        )
    ).all()
    for reserva in reservas:
        reserva.estado = "enviada_dux"


def reconciliar_reservas_enviadas(db: Session) -> int:
    from app.models.stock_talle_producto import StockTalleProducto
    reservas = db.scalars(
        select(ReservaStock).where(ReservaStock.estado == "enviada_dux")
    ).all()
    ahora = datetime.now(timezone.utc)
    for reserva in reservas:
        if reserva.talle is not None:
            stock_talle = db.scalar(select(StockTalleProducto).where(
                StockTalleProducto.producto_id == reserva.producto_id,
                StockTalleProducto.talle == reserva.talle,
            ).with_for_update())
            if stock_talle is not None and stock_talle.origen != "dux":
                stock_talle.cantidad = max(stock_talle.cantidad - reserva.cantidad, 0)
        reserva.estado = "reconciliada"
        reserva.reconciliada_en = ahora
    return len(reservas)
