from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.categoria import Categoria
from app.models.subcategoria import Subcategoria


# =========================================================
# OBTENER CATEGORÍA POR ID
# =========================================================

def get_categoria(
    db: Session,
    categoria_id: int,
    solo_activas: bool = True,
) -> Categoria | None:

    subcategorias = Categoria.subcategorias

    if solo_activas:
        subcategorias = subcategorias.and_(
            Subcategoria.activo.is_(True)
        )

    query = (
        select(Categoria)
        .options(
            selectinload(subcategorias)
        )
        .where(
            Categoria.id == categoria_id
        )
    )

    if solo_activas:
        query = query.where(
            Categoria.activo.is_(True)
        )

    return db.scalar(query)


# =========================================================
# OBTENER CATEGORÍA POR SLUG
# =========================================================

def get_categoria_by_slug(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Categoria | None:

    subcategorias = Categoria.subcategorias

    if solo_activas:
        subcategorias = subcategorias.and_(
            Subcategoria.activo.is_(True)
        )

    query = (
        select(Categoria)
        .options(
            selectinload(subcategorias)
        )
        .where(
            Categoria.slug == slug
        )
    )

    if solo_activas:
        query = query.where(
            Categoria.activo.is_(True)
        )

    return db.scalar(query)


# =========================================================
# LISTAR CATEGORÍAS
# =========================================================

def get_categorias(
    db: Session,
    solo_activas: bool = True,
) -> list[Categoria]:

    subcategorias = Categoria.subcategorias

    if solo_activas:
        subcategorias = subcategorias.and_(
            Subcategoria.activo.is_(True)
        )

    query = (
        select(Categoria)
        .options(
            selectinload(subcategorias)
        )
        .order_by(
            Categoria.nombre.asc()
        )
    )

    if solo_activas:
        query = query.where(
            Categoria.activo.is_(True)
        )

    return list(
        db.scalars(query).all()
    )
