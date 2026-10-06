from datetime import datetime

from sqlalchemy import String, and_, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.models.usuario import Usuario


ESTADO_GESTION_POR_ESTADO_WOOCOMMERCE = {
    "pending": "pendiente",
    "on-hold": "pendiente",
    "processing": "confirmado",
    "completed": "confirmado",
    "cancelled": "cancelado",
    "refunded": "cancelado",
    "failed": "cancelado",
}
ESTADOS_GESTION_PEDIDO = {"pendiente", "contactado", "confirmado", "cancelado"}


def estado_gestion_pedido_historico(estado_original: str, estado_gestion: str | None) -> str:
    return estado_gestion or ESTADO_GESTION_POR_ESTADO_WOOCOMMERCE.get(estado_original, "pendiente")


def _filtro_estado_historico(estado: str):
    estados_originales = tuple(
        original
        for original, gestion in ESTADO_GESTION_POR_ESTADO_WOOCOMMERCE.items()
        if gestion == estado
    )
    if not estados_originales and estado not in ESTADOS_GESTION_PEDIDO:
        estados_originales = (estado,)

    condiciones = [PedidoHistoricoWordpress.estado_gestion == estado]
    if estados_originales:
        condiciones.append(and_(
            PedidoHistoricoWordpress.estado_gestion.is_(None),
            PedidoHistoricoWordpress.estado.in_(estados_originales),
        ))
    return or_(*condiciones)


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


def get_pedido_historico(
    db: Session,
    pedido_id: int,
    usuario_id: int | None = None,
) -> PedidoHistoricoWordpress | None:
    query = (
        select(PedidoHistoricoWordpress)
        .options(
            selectinload(PedidoHistoricoWordpress.items),
            selectinload(PedidoHistoricoWordpress.usuario),
        )
        .where(PedidoHistoricoWordpress.id == pedido_id)
    )
    if usuario_id is not None:
        query = query.where(PedidoHistoricoWordpress.usuario_id == usuario_id)
    return db.scalar(query)


def get_pedido_historico_by_codigo(
    db: Session,
    codigo: str,
    usuario_id: int | None = None,
) -> PedidoHistoricoWordpress | None:
    if not codigo.startswith("WP-"):
        return None
    numero = codigo.removeprefix("WP-")
    query = (
        select(PedidoHistoricoWordpress)
        .options(
            selectinload(PedidoHistoricoWordpress.items),
            selectinload(PedidoHistoricoWordpress.usuario),
        )
        .where(PedidoHistoricoWordpress.numero == numero)
        .limit(2)
    )
    if usuario_id is not None:
        query = query.where(PedidoHistoricoWordpress.usuario_id == usuario_id)
    coincidencias = list(db.scalars(query).all())
    return coincidencias[0] if len(coincidencias) == 1 else None


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
    orden: str = "fecha_desc",
) -> tuple[list[tuple[str, int]], int]:
    consultas = []
    if origen in ("todos", "tienda"):
        tienda = select(
            literal("tienda").label("origen"),
            Pedido.id.label("id"),
            Pedido.creado_en.label("fecha"),
            Pedido.total.label("total"),
            Pedido.cantidad_unidades.label("unidades"),
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
            PedidoHistoricoWordpress.total.label("total"),
            func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0).label("unidades"),
        ).outerjoin(Usuario, Usuario.id == PedidoHistoricoWordpress.usuario_id).outerjoin(
            PedidoItemHistoricoWordpress,
            PedidoItemHistoricoWordpress.pedido_id == PedidoHistoricoWordpress.id,
        )
        if estado:
            wordpress = wordpress.where(_filtro_estado_historico(estado))
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
        wordpress = wordpress.group_by(
            PedidoHistoricoWordpress.id,
            PedidoHistoricoWordpress.creado_en_wordpress,
            PedidoHistoricoWordpress.total,
        )
        consultas.append(wordpress)

    combinada = union_all(*consultas).subquery()
    total = db.scalar(select(func.count()).select_from(combinada)) or 0
    ordenamiento = {
        "fecha_desc": (combinada.c.fecha.desc(), combinada.c.id.desc()),
        "total_desc": (combinada.c.total.desc(), combinada.c.fecha.desc(), combinada.c.id.desc()),
        "total_asc": (combinada.c.total.asc(), combinada.c.fecha.desc(), combinada.c.id.desc()),
        "unidades_desc": (combinada.c.unidades.desc(), combinada.c.fecha.desc(), combinada.c.id.desc()),
        "unidades_asc": (combinada.c.unidades.asc(), combinada.c.fecha.desc(), combinada.c.id.desc()),
    }[orden]
    filas = db.execute(
        select(combinada.c.origen, combinada.c.id)
        .order_by(*ordenamiento)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return [(fila.origen, fila.id) for fila in filas], total


def get_conteos_estado_pedidos_admin(
    db: Session,
    buscar: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None,
    origen: str = "todos",
) -> dict[str, int]:
    """Obtiene todos los contadores de estado en una sola consulta.

    La lista de administración combina pedidos propios e históricos. Antes la
    pantalla hacía una consulta completa adicional por cada botón de estado,
    lo cual era costoso con el historial de WooCommerce.
    """
    consultas = []
    if origen in ("todos", "tienda"):
        tienda = select(Pedido.estado.label("estado"))
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
        estado_historico = func.coalesce(
            PedidoHistoricoWordpress.estado_gestion,
            case(
                (PedidoHistoricoWordpress.estado.in_(("pending", "on-hold")), "pendiente"),
                (PedidoHistoricoWordpress.estado.in_(("processing", "completed")), "confirmado"),
                (PedidoHistoricoWordpress.estado.in_(("cancelled", "refunded", "failed")), "cancelado"),
                else_="pendiente",
            ),
        ).label("estado")
        wordpress = select(estado_historico).outerjoin(
            Usuario, Usuario.id == PedidoHistoricoWordpress.usuario_id,
        )
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

    if not consultas:
        return {estado: 0 for estado in ESTADOS_GESTION_PEDIDO}
    combinada = union_all(*consultas).subquery()
    filas = db.execute(
        select(combinada.c.estado, func.count()).group_by(combinada.c.estado)
    ).all()
    conteos = {estado: 0 for estado in ESTADOS_GESTION_PEDIDO}
    conteos.update({str(estado): int(total) for estado, total in filas})
    return conteos


def get_referencias_pedidos_usuario(
    db: Session,
    usuario_id: int,
    page: int,
    limit: int,
) -> tuple[list[tuple[str, int]], int]:
    tienda = select(
        literal("tienda").label("origen"),
        Pedido.id.label("id"),
        Pedido.creado_en.label("fecha"),
    ).where(Pedido.usuario_id == usuario_id)
    wordpress = select(
        literal("wordpress").label("origen"),
        PedidoHistoricoWordpress.id.label("id"),
        PedidoHistoricoWordpress.creado_en_wordpress.label("fecha"),
    ).where(PedidoHistoricoWordpress.usuario_id == usuario_id)

    combinada = union_all(tienda, wordpress).subquery()
    total = db.scalar(select(func.count()).select_from(combinada)) or 0
    filas = db.execute(
        select(combinada.c.origen, combinada.c.id)
        .order_by(combinada.c.fecha.desc(), combinada.c.origen.asc(), combinada.c.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return [(fila.origen, fila.id) for fila in filas], total


def get_pedidos_por_referencias(db: Session, referencias: list[tuple[str, int]]) -> list[Pedido | PedidoHistoricoWordpress]:
    ids_tienda = [identificador for origen, identificador in referencias if origen == "tienda"]
    ids_wordpress = [identificador for origen, identificador in referencias if origen == "wordpress"]
    tienda = {
        pedido.id: pedido for pedido in db.scalars(
            select(Pedido)
            .options(selectinload(Pedido.items), selectinload(Pedido.usuario))
            .where(Pedido.id.in_(ids_tienda))
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
