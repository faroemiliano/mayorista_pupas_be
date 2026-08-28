from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.producto import Producto
from app.models.stock_producto import StockProducto


def get_analitica_productos(
    db: Session,
    desde: datetime | None,
) -> list[dict]:
    ventas = (
        select(
            PedidoItem.producto_id.label("producto_id"),
            func.coalesce(func.sum(PedidoItem.cantidad), 0).label("unidades_vendidas"),
            func.count(distinct(PedidoItem.pedido_id)).label("cantidad_pedidos"),
            func.coalesce(func.sum(PedidoItem.subtotal), 0).label("importe_vendido"),
        )
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(Pedido.estado != "cancelado")
        .group_by(PedidoItem.producto_id)
    )
    if desde is not None:
        ventas = ventas.where(Pedido.creado_en >= desde)
    ventas = ventas.subquery()

    stock = (
        select(
            StockProducto.producto_id,
            func.coalesce(func.sum(StockProducto.stock_disponible), 0).label("stock_disponible"),
        )
        .group_by(StockProducto.producto_id)
        .subquery()
    )

    query = (
        select(
            Producto.id.label("producto_id"),
            Producto.dux_codigo,
            Producto.nombre,
            func.coalesce(ventas.c.unidades_vendidas, 0).label("unidades_vendidas"),
            func.coalesce(ventas.c.cantidad_pedidos, 0).label("cantidad_pedidos"),
            func.coalesce(ventas.c.importe_vendido, 0).label("importe_vendido"),
            func.coalesce(stock.c.stock_disponible, 0).label("stock_disponible"),
        )
        .outerjoin(ventas, ventas.c.producto_id == Producto.id)
        .outerjoin(stock, stock.c.producto_id == Producto.id)
        .where(Producto.habilitado.is_(True))
    )
    return [dict(row) for row in db.execute(query).mappings().all()]
