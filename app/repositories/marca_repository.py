from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.marca import Marca


# =========================================================
# OBTENER MARCA POR ID
# =========================================================

def get_marca(
    db: Session,
    marca_id: int,
    solo_activas: bool = True,
) -> Marca | None:

    query = select(Marca).where(
        Marca.id == marca_id
    )

    if solo_activas:
        query = query.where(
            Marca.activo.is_(True)
        )

    return db.scalar(query)


# =========================================================
# OBTENER MARCA POR SLUG
# =========================================================

def get_marca_by_slug(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Marca | None:

    query = select(Marca).where(
        Marca.slug == slug
    )

    if solo_activas:
        query = query.where(
            Marca.activo.is_(True)
        )

    return db.scalar(query)


# =========================================================
# LISTAR MARCAS
# =========================================================

def get_marcas(
    db: Session,
    solo_activas: bool = True,
) -> list[Marca]:

    query = select(Marca).order_by(
        Marca.nombre.asc()
    )

    if solo_activas:
        query = query.where(
            Marca.activo.is_(True)
        )

    return list(
        db.scalars(query).all()
    )
