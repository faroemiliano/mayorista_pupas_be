from datetime import datetime

from sqlalchemy import String, and_, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress
from app.models.usuario import Usuario


def get_pedido_by_codigo(db: Session, codigo: str) -> Pedido | None:
    return db.scalar(
        select(Pedido)
        .options(selectinload(Pedido.items))
        .where(Pedido.codigo == codigo)
    )


def get_pedido(db: Session, pedido_id: int) -> Pedido | None:
    return db.scalar(
        select(Pedido)
        .options(selectinload(Pedido.items))
        .where(Pedido.id == pedido_id)
    )


def get_pedidos(
    db: Session,
    estado: str | None,
    page: int,
    limit: int,
    usuario_id: int | None = None,
    buscar: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
) -> tuple[list[Pedido], int]:
    query = select(Pedido).options(
        selectinload(Pedido.items)
    )
    count_query = select(func.count(Pedido.id))

    if usuario_id is not None:
        query = query.where(Pedido.usuario_id == usuario_id)
        count_query = count_query.where(Pedido.usuario_id == usuario_id)

    if estado:
        query = query.where(Pedido.estado == estado)
        count_query = count_query.where(Pedido.estado == estado)

    if buscar and (termino := buscar.strip()):
        patron = f"%{termino}%"
        filtro = or_(
            Pedido.codigo.ilike(patron),
            Pedido.cliente_nombre.ilike(patron),
            Pedido.cliente_email.ilike(patron),
            Pedido.cliente_telefono.ilike(patron),
            cast(Pedido.id, String).ilike(patron),
        )
        query = query.where(filtro)
        count_query = count_query.where(filtro)

    if fecha_desde is not None:
        query = query.where(Pedido.creado_en >= fecha_desde)
        count_query = count_query.where(Pedido.creado_en >= fecha_desde)

    if fecha_hasta is not None:
        query = query.where(Pedido.creado_en < fecha_hasta)
        count_query = count_query.where(Pedido.creado_en < fecha_hasta)

    query = (
        query.order_by(Pedido.creado_en.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )

    return (
        list(db.scalars(query).all()),
        db.scalar(count_query) or 0,
    )


def get_referencias_pedidos_admin(
    db: Session,
    estado: str | None,
    page: int,
    limit: int,
    buscar: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    origen: str = "todos",
) -> tuple[list[tuple[str, int]], int]:
    consultas = []
    if origen in ("todos", "tienda"):
        tienda = select(
            literal("tienda").label("origen"),
            Pedido.id.label("id"),
            Pedido.creado_en.label("fecha"),
        )
        if estado:
            tienda = tienda.where(Pedido.estado == estado)
        if buscar and (termino := buscar.strip()):
            patron = f"%{termino}%"
            tienda = tienda.where(or_(
                Pedido.codigo.ilike(patron), Pedido.cliente_nombre.ilike(patron),
                Pedido.cliente_email.ilike(patron), Pedido.cliente_telefono.ilike(patron),
                cast(Pedido.id, String).ilike(patron),
            ))
        if fecha_desde is not None:
            tienda = tienda.where(Pedido.creado_en >= fecha_desde)
        if fecha_hasta is not None:
            tienda = tienda.where(Pedido.creado_en < fecha_hasta)
        consultas.append(tienda)

    if origen in ("todos", "wordpress"):
        wordpress = select(
            literal("wordpress").label("origen"),
            PedidoHistoricoWordpress.id.label("id"),
            PedidoHistoricoWordpress.creado_en_wordpress.label("fecha"),
        ).outerjoin(Usuario, Usuario.id == PedidoHistoricoWordpress.usuario_id)
        if estado:
            originales = {
                "pendiente": ("pending",), "contactado": ("on-hold",),
                "confirmado": ("processing", "completed"),
                "cancelado": ("cancelled", "refunded", "failed"),
            }.get(estado, (estado,))
            wordpress = wordpress.where(or_(
                PedidoHistoricoWordpress.estado_gestion == estado,
                and_(PedidoHistoricoWordpress.estado_gestion.is_(None), PedidoHistoricoWordpress.estado.in_(originales)),
            ))
        if buscar and (termino := buscar.strip()):
            patron = f"%{termino}%"
            wordpress = wordpress.where(or_(
                PedidoHistoricoWordpress.numero.ilike(patron),
                cast(PedidoHistoricoWordpress.wordpress_id, String).ilike(patron),
                Usuario.nombre.ilike(patron), Usuario.apellido.ilike(patron),
                Usuario.email.ilike(patron), Usuario.telefono.ilike(patron),
            ))
        if fecha_desde is not None:
            wordpress = wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress >= fecha_desde)
        if fecha_hasta is not None:
            wordpress = wordpress.where(PedidoHistoricoWordpress.creado_en_wordpress < fecha_hasta)
        consultas.append(wordpress)

    combinada = union_all(*consultas).subquery()
    total = db.scalar(select(func.count()).select_from(combinada)) or 0
    filas = db.execute(
        select(combinada.c.origen, combinada.c.id)
        .order_by(combinada.c.fecha.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return [(fila.origen, fila.id) for fila in filas], total


def get_pedidos_por_referencias(db: Session, referencias: list[tuple[str, int]]) -> list[Pedido | PedidoHistoricoWordpress]:
    ids_tienda = [identificador for origen, identificador in referencias if origen == "tienda"]
    ids_wordpress = [identificador for origen, identificador in referencias if origen == "wordpress"]
    tienda = {
        pedido.id: pedido for pedido in db.scalars(
            select(Pedido).options(selectinload(Pedido.items)).where(Pedido.id.in_(ids_tienda))
        ).all()
    } if ids_tienda else {}
    wordpress = {
        pedido.id: pedido for pedido in db.scalars(
            select(PedidoHistoricoWordpress)
            .options(selectinload(PedidoHistoricoWordpress.items), selectinload(PedidoHistoricoWordpress.usuario))
            .where(PedidoHistoricoWordpress.id.in_(ids_wordpress))
        ).all()
    } if ids_wordpress else {}
    return [tienda[id_] if origen == "tienda" else wordpress[id_] for origen, id_ in referencias]
