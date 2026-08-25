from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.categoria import Categoria
from app.models.subcategoria import Subcategoria


# =========================================================
# OBTENER SUBCATEGORÍA POR ID
# =========================================================

def get_subcategoria(
    db: Session,
    subcategoria_id: int,
    solo_activas: bool = True,
) -> Subcategoria | None:

    query = (
        select(Subcategoria)
        .options(
            joinedload(
                Subcategoria.categoria
            )
        )
        .where(
            Subcategoria.id == subcategoria_id
        )
    )

    if solo_activas:
        query = query.where(
            Subcategoria.activo.is_(True),
            Subcategoria.categoria.has(
                Categoria.activo.is_(True)
            ),
        )

    return db.scalar(query)


# =========================================================
# OBTENER SUBCATEGORÍA POR SLUG
# =========================================================

def get_subcategoria_by_slug(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Subcategoria | None:

    query = (
        select(Subcategoria)
        .options(
            joinedload(
                Subcategoria.categoria
            )
        )
        .where(
            Subcategoria.slug == slug
        )
    )

    if solo_activas:
        query = query.where(
            Subcategoria.activo.is_(True),
            Subcategoria.categoria.has(
                Categoria.activo.is_(True)
            ),
        )

    return db.scalar(query)


# =========================================================
# LISTAR SUBCATEGORÍAS
# =========================================================

def get_subcategorias(
    db: Session,
    categoria_id: int | None = None,
    solo_activas: bool = True,
) -> list[Subcategoria]:

    query = (
        select(Subcategoria)
        .options(
            joinedload(
                Subcategoria.categoria
            )
        )
        .order_by(
            Subcategoria.nombre.asc()
        )
    )

    if categoria_id is not None:
        query = query.where(
            Subcategoria.categoria_id
            == categoria_id
        )

    if solo_activas:
        query = query.where(
            Subcategoria.activo.is_(True),
            Subcategoria.categoria.has(
                Categoria.activo.is_(True)
            ),
        )

    return list(
        db.scalars(query).all()
    )
