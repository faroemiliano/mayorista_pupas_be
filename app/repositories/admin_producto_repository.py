from datetime import datetime

from sqlalchemy import distinct, func, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.categoria import Categoria
from app.models.producto import Producto
from app.models.stock_producto import StockProducto
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.services.stock_fuente_service import filtro_stock_fuente_activa


def get_analitica_productos(
    db: Session,
    desde: datetime | None,
    hasta: datetime | None = None,
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
    if hasta is not None:
        ventas_tienda = ventas_tienda.where(Pedido.creado_en < hasta)

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
    if hasta is not None:
        ventas_wordpress = ventas_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress < hasta)

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
        .where(filtro_stock_fuente_activa(StockProducto.dux_id_deposito))
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


def get_compras_de_producto(
    db: Session,
    producto: Producto,
    desde: datetime | None,
    hasta: datetime | None,
) -> list[dict]:
    """Obtiene líneas vendidas del producto desde la base propia de la tienda."""
    filtros_tienda = [
        PedidoItem.producto_id == producto.id,
        Pedido.estado != "cancelado",
    ]
    if desde is not None:
        filtros_tienda.append(Pedido.creado_en >= desde)
    if hasta is not None:
        filtros_tienda.append(Pedido.creado_en < hasta)
    consulta_tienda = (
        select(
            Pedido.id.label("pedido_id"),
            Pedido.usuario_id,
            Pedido.cliente_nombre.label("cliente"),
            Pedido.cliente_email.label("email"),
            Pedido.creado_en.label("fecha"),
            PedidoItem.talle,
            PedidoItem.cantidad,
        )
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(*filtros_tienda)
    )
    resultado = [
        {**dict(fila), "pedido_clave": f"tienda:{fila['pedido_id']}"}
        for fila in db.execute(consulta_tienda).mappings()
    ]

    identidad_historica = PedidoItemHistoricoWordpress.producto_id == producto.id
    if producto.dux_codigo:
        identidad_historica = or_(
            identidad_historica,
            (
                PedidoItemHistoricoWordpress.producto_id.is_(None)
                & (PedidoItemHistoricoWordpress.sku == producto.dux_codigo)
            ),
        )
    filtros_historicos = [
        PedidoHistoricoWordpress.estado.not_in(("cancelled", "refunded", "failed")),
        identidad_historica,
    ]
    if desde is not None:
        filtros_historicos.append(PedidoHistoricoWordpress.creado_en_wordpress >= desde)
    if hasta is not None:
        filtros_historicos.append(PedidoHistoricoWordpress.creado_en_wordpress < hasta)
    consulta_historica = (
        select(
            PedidoHistoricoWordpress.id.label("pedido_id"),
            PedidoHistoricoWordpress.usuario_id,
            PedidoHistoricoWordpress.facturacion,
            PedidoHistoricoWordpress.creado_en_wordpress.label("fecha"),
            PedidoItemHistoricoWordpress.metadatos,
            PedidoItemHistoricoWordpress.cantidad,
        )
        .join(
            PedidoHistoricoWordpress,
            PedidoHistoricoWordpress.id == PedidoItemHistoricoWordpress.pedido_id,
        )
        .where(*filtros_historicos)
    )
    for fila in db.execute(consulta_historica).mappings():
        facturacion = fila["facturacion"] or {}
        cliente = " ".join(filter(None, (
            facturacion.get("first_name"), facturacion.get("last_name"),
        ))).strip()
        talle = None
        for dato in fila["metadatos"] or []:
            nombre = str(dato.get("display_key") or dato.get("key") or "").casefold()
            if any(token in nombre for token in ("talle", "talla", "size")):
                talle = str(dato.get("display_value") or dato.get("value") or "").strip() or None
                break
        resultado.append({
            "pedido_id": fila["pedido_id"],
            "pedido_clave": f"historico:{fila['pedido_id']}",
            "usuario_id": fila["usuario_id"],
            "cliente": cliente or "Cliente sin nombre",
            "email": facturacion.get("email"),
            "fecha": fila["fecha"],
            "talle": talle,
            "cantidad": fila["cantidad"],
        })
    return resultado


def get_ventas_temporales(
    db: Session,
    desde: datetime | None,
    hasta: datetime | None = None,
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
    if hasta is not None:
        query_tienda = query_tienda.where(Pedido.creado_en < hasta)

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
    if hasta is not None:
        query_wordpress = query_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress < hasta)
    ventas = union_all(query_tienda, query_wordpress).subquery()
    query = select(ventas.c.creado_en, ventas.c.total, ventas.c.cantidad_unidades).order_by(ventas.c.creado_en)
    return [dict(row) for row in db.execute(query).mappings().all()]


def get_ventas_categorias_destacadas(
    db: Session,
    desde: datetime | None,
    hasta: datetime | None = None,
) -> list[dict]:
    """Devuelve los modelos vendidos de las categorías principales.

    No depende de que el producto siga habilitado hoy: una prenda que fue
    deshabilitada igualmente forma parte de la venta histórica del período.
    """
    ventas_tienda = (
        select(
            PedidoItem.producto_id.label("producto_id"),
            func.coalesce(func.sum(PedidoItem.cantidad), 0).label("unidades_vendidas"),
            func.coalesce(func.sum(PedidoItem.subtotal), 0).label("importe_vendido"),
        )
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(Pedido.estado != "cancelado")
        .group_by(PedidoItem.producto_id)
    )
    if desde is not None:
        ventas_tienda = ventas_tienda.where(Pedido.creado_en >= desde)
    if hasta is not None:
        ventas_tienda = ventas_tienda.where(Pedido.creado_en < hasta)

    ventas_wordpress = (
        select(
            PedidoItemHistoricoWordpress.producto_id.label("producto_id"),
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0).label("unidades_vendidas"),
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.total), 0).label("importe_vendido"),
        )
        .join(PedidoHistoricoWordpress, PedidoHistoricoWordpress.id == PedidoItemHistoricoWordpress.pedido_id)
        .where(
            PedidoHistoricoWordpress.estado != "cancelled",
            PedidoItemHistoricoWordpress.producto_id.is_not(None),
        )
        .group_by(PedidoItemHistoricoWordpress.producto_id)
    )
    if desde is not None:
        ventas_wordpress = ventas_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress >= desde)
    if hasta is not None:
        ventas_wordpress = ventas_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress < hasta)

    ventas_union = union_all(ventas_tienda, ventas_wordpress).subquery()
    ventas = (
        select(
            ventas_union.c.producto_id,
            func.sum(ventas_union.c.unidades_vendidas).label("unidades_vendidas"),
            func.sum(ventas_union.c.importe_vendido).label("importe_vendido"),
        )
        .group_by(ventas_union.c.producto_id)
        .subquery()
    )

    query = (
        select(
            Categoria.slug.label("categoria_slug"),
            Categoria.nombre.label("categoria"),
            Producto.id.label("producto_id"),
            Producto.nombre,
            func.coalesce(ventas.c.unidades_vendidas, 0).label("unidades_vendidas"),
            func.coalesce(ventas.c.importe_vendido, 0).label("importe_vendido"),
        )
        .join(Producto, Producto.categoria_id == Categoria.id)
        .join(ventas, ventas.c.producto_id == Producto.id)
        # La migración conservó categorías históricas y actuales con slugs
        # distintos (por ejemplo ``bikinis`` y ``bikinis-wp-37``). El nombre
        # es la identidad comercial común que permite agrupar ambas.
        .where(func.lower(Categoria.nombre).in_(("bikinis", "pijamas")))
        .order_by(Categoria.nombre, ventas.c.unidades_vendidas.desc(), ventas.c.importe_vendido.desc(), Producto.nombre)
    )
    return [dict(row) for row in db.execute(query).mappings().all()]


def get_ranking_clientes(
    db: Session,
    desde: datetime | None,
    hasta: datetime | None = None,
    limit: int = 10,
) -> list[dict]:
    """Agrupa pedidos actuales e históricos por cliente, sin usar datos de Dux.

    El historial de WordPress puede no estar vinculado a una cuenta nueva. En
    ese caso el email (y, como último recurso, el nombre) conserva un ranking
    útil sin inventar ni modificar clientes.
    """
    pedidos_tienda = select(
        Pedido.usuario_id,
        Pedido.cliente_nombre.label("cliente"),
        Pedido.cliente_email.label("email"),
        Pedido.total.label("importe"),
        Pedido.cantidad_unidades.label("unidades"),
        Pedido.creado_en.label("fecha"),
    ).where(Pedido.estado != "cancelado")
    if desde is not None:
        pedidos_tienda = pedidos_tienda.where(Pedido.creado_en >= desde)
    if hasta is not None:
        pedidos_tienda = pedidos_tienda.where(Pedido.creado_en < hasta)

    unidades_historicas = (
        select(
            PedidoItemHistoricoWordpress.pedido_id,
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0).label("unidades"),
        )
        .group_by(PedidoItemHistoricoWordpress.pedido_id)
        .subquery()
    )
    pedidos_wordpress = (
        select(
            PedidoHistoricoWordpress.usuario_id,
            PedidoHistoricoWordpress.facturacion.label("facturacion"),
            PedidoHistoricoWordpress.total.label("importe"),
            unidades_historicas.c.unidades,
            PedidoHistoricoWordpress.creado_en_wordpress.label("fecha"),
        )
        .outerjoin(unidades_historicas, unidades_historicas.c.pedido_id == PedidoHistoricoWordpress.id)
        .where(PedidoHistoricoWordpress.estado != "cancelled")
    )
    if desde is not None:
        pedidos_wordpress = pedidos_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress >= desde)
    if hasta is not None:
        pedidos_wordpress = pedidos_wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress < hasta)

    ranking: dict[str, dict] = {}

    def acumular(usuario_id, cliente, email, importe, unidades, fecha) -> None:
        nombre = str(cliente or "Cliente sin nombre").strip() or "Cliente sin nombre"
        correo = str(email or "").strip().lower()
        key = f"usuario:{usuario_id}" if usuario_id else (f"email:{correo}" if correo else f"nombre:{nombre.casefold()}")
        item = ranking.setdefault(key, {
            "cliente": nombre,
            "email": correo or None,
            "pedidos": 0,
            "unidades": 0,
            "importe_comprado": 0,
            "ultima_compra": fecha,
        })
        # Preferimos una identidad con nombre real ante registros históricos
        # que sólo hayan quedado con un email o nombre incompleto.
        if item["cliente"] == "Cliente sin nombre" and nombre != item["cliente"]:
            item["cliente"] = nombre
        if not item["email"] and correo:
            item["email"] = correo
        item["pedidos"] += 1
        item["unidades"] += int(unidades or 0)
        item["importe_comprado"] += importe or 0
        if fecha and (item["ultima_compra"] is None or fecha > item["ultima_compra"]):
            item["ultima_compra"] = fecha

    for row in db.execute(pedidos_tienda).mappings():
        acumular(**dict(row))
    for row in db.execute(pedidos_wordpress).mappings():
        facturacion = row["facturacion"] or {}
        cliente = " ".join(filter(None, [facturacion.get("first_name"), facturacion.get("last_name")])).strip()
        acumular(
            usuario_id=row["usuario_id"],
            cliente=cliente,
            email=facturacion.get("email"),
            importe=row["importe"],
            unidades=row["unidades"],
            fecha=row["fecha"],
        )

    return sorted(
        ranking.values(),
        key=lambda item: (-item["importe_comprado"], -item["pedidos"], item["cliente"].casefold()),
    )[:limit]
