from datetime import datetime

from sqlalchemy import distinct, func, select, union_all
from sqlalchemy.orm import Session

from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress


def get_analitica_productos(
    db: Session,
    desde: datetime | None,
) -> list[dict]:
    ventas_tienda = (
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
        ventas_tienda = ventas_tienda.where(Pedido.creado_en >= desde)

    ventas_wordpress = (
        select(
            PedidoItemHistoricoWordpress.producto_id.label("producto_id"),
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0).label("unidades_vendidas"),
            func.count(distinct(PedidoItemHistoricoWordpress.pedido_id)).label("cantidad_pedidos"),
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.total), 0).label("importe_vendido"),
        )
        .join(PedidoHistoricoWordpress, PedidoHistoricoWordpress.id == PedidoItemHistoricoWordpress.pedido_id)
        .where(PedidoHistoricoWordpress.estado != "cancelled", PedidoItemHistoricoWordpress.producto_id.is_not(None))
        .group_by(PedidoItemHistoricoWordpress.producto_id)
    )
    if desde is not None:
        ventas_wordpress = ventas_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress >= desde)

    ventas_union = union_all(ventas_tienda, ventas_wordpress).subquery()
    ventas = (
        select(
            ventas_union.c.producto_id,
            func.sum(ventas_union.c.unidades_vendidas).label("unidades_vendidas"),
            func.sum(ventas_union.c.cantidad_pedidos).label("cantidad_pedidos"),
            func.sum(ventas_union.c.importe_vendido).label("importe_vendido"),
        )
        .group_by(ventas_union.c.producto_id)
        .subquery()
    )

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


def get_ventas_temporales(
    db: Session,
    desde: datetime | None,
) -> list[dict]:
    query_tienda = (
        select(
            Pedido.creado_en,
            Pedido.total,
            Pedido.cantidad_unidades,
        )
        .where(Pedido.estado != "cancelado")
    )
    if desde is not None:
        query_tienda = query_tienda.where(Pedido.creado_en >= desde)

    unidades_historicas = (
        select(
            PedidoItemHistoricoWordpress.pedido_id,
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0).label("cantidad_unidades"),
        )
        .group_by(PedidoItemHistoricoWordpress.pedido_id)
        .subquery()
    )
    query_wordpress = (
        select(
            PedidoHistoricoWordpress.creado_en_wordpress.label("creado_en"),
            PedidoHistoricoWordpress.total,
            unidades_historicas.c.cantidad_unidades,
        )
        .join(unidades_historicas, unidades_historicas.c.pedido_id == PedidoHistoricoWordpress.id)
        .where(PedidoHistoricoWordpress.estado != "cancelled")
    )
    if desde is not None:
        query_wordpress = query_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress >= desde)
    ventas = union_all(query_tienda, query_wordpress).subquery()
    query = select(ventas.c.creado_en, ventas.c.total, ventas.c.cantidad_unidades).order_by(ventas.c.creado_en)
    return [dict(row) for row in db.execute(query).mappings().all()]
