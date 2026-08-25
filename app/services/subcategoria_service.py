from sqlalchemy.orm import Session

from app.models.subcategoria import Subcategoria
from app.repositories.subcategoria_repository import (
    get_subcategoria,
    get_subcategoria_by_slug,
    get_subcategorias,
)


# =========================================================
# OBTENER SUBCATEGORÍA POR ID
# =========================================================

def get_subcategoria_service(
    db: Session,
    subcategoria_id: int,
    solo_activas: bool = True,
) -> Subcategoria | None:

    return get_subcategoria(
        db=db,
        subcategoria_id=subcategoria_id,
        solo_activas=solo_activas,
    )


# =========================================================
# OBTENER SUBCATEGORÍA POR SLUG
# =========================================================

def get_subcategoria_by_slug_service(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Subcategoria | None:

    return get_subcategoria_by_slug(
        db=db,
        slug=slug,
        solo_activas=solo_activas,
    )


# =========================================================
# LISTAR SUBCATEGORÍAS
# =========================================================

def get_subcategorias_service(
    db: Session,
    categoria_id: int | None = None,
    solo_activas: bool = True,
) -> list[Subcategoria]:

    return get_subcategorias(
        db=db,
        categoria_id=categoria_id,
        solo_activas=solo_activas,
    )
