from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.producto import Producto
from app.models.pedido import Pedido
from app.models.reserva_stock import ReservaStock
from app.models.reserva_carrito import ReservaCarrito
from app.core.config import settings


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


def cantidades_reservadas(db: Session, producto_ids: set[int], excluir_usuario_carrito: int | None = None) -> dict[int, int]:
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
    resultado = {producto_id: int(cantidad) for producto_id, cantidad in filas}
    consulta_carrito = select(ReservaCarrito.producto_id, func.sum(ReservaCarrito.cantidad)).where(
        ReservaCarrito.producto_id.in_(producto_ids), ReservaCarrito.expira_en > datetime.now(timezone.utc),
    )
    if excluir_usuario_carrito is not None:
        consulta_carrito = consulta_carrito.where(ReservaCarrito.usuario_id != excluir_usuario_carrito)
    for producto_id, cantidad in db.execute(consulta_carrito.group_by(ReservaCarrito.producto_id)).all():
        resultado[producto_id] = resultado.get(producto_id, 0) + int(cantidad)
    return resultado


def cantidades_reservadas_por_talle(db: Session, producto_ids: set[int], excluir_usuario_carrito: int | None = None) -> dict[tuple[int, str], int]:
    if not producto_ids:
        return {}
    filas = db.execute(
        select(ReservaStock.producto_id, ReservaStock.talle, func.sum(ReservaStock.cantidad))
        .where(ReservaStock.producto_id.in_(producto_ids), ReservaStock.talle.is_not(None), ReservaStock.estado.in_(ESTADOS_QUE_DESCUENTAN))
        .group_by(ReservaStock.producto_id, ReservaStock.talle)
    ).all()
    resultado = {(producto_id, talle): int(cantidad) for producto_id, talle, cantidad in filas}
    consulta_carrito = select(ReservaCarrito.producto_id, ReservaCarrito.talle, func.sum(ReservaCarrito.cantidad)).where(
        ReservaCarrito.producto_id.in_(producto_ids), ReservaCarrito.expira_en > datetime.now(timezone.utc),
    )
    if excluir_usuario_carrito is not None:
        consulta_carrito = consulta_carrito.where(ReservaCarrito.usuario_id != excluir_usuario_carrito)
    for producto_id, talle, cantidad in db.execute(consulta_carrito.group_by(ReservaCarrito.producto_id, ReservaCarrito.talle)).all():
        clave = (producto_id, talle); resultado[clave] = resultado.get(clave, 0) + int(cantidad)
    return resultado


def liberar_reservas_carrito(db: Session, usuario_id: int) -> None:
    for reserva in db.scalars(select(ReservaCarrito).where(ReservaCarrito.usuario_id == usuario_id)).all():
        db.delete(reserva)


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
    ahora = datetime.now(timezone.utc)
    limite = ahora - timedelta(
        minutes=settings.DUX_RECONCILIACION_RESERVA_MINUTOS
    )
    reservas = db.scalars(
        select(ReservaStock)
        .join(Pedido, Pedido.id == ReservaStock.pedido_id)
        .where(
            ReservaStock.estado == "enviada_dux",
            Pedido.sincronizado_dux_en.is_not(None),
            Pedido.sincronizado_dux_en <= limite,
        )
    ).all()
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
