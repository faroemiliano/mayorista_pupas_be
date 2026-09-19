from datetime import datetime

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.pedido import Pedido


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
