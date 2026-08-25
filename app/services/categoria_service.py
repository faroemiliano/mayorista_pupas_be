from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.repositories.categoria_repository import (
    get_categoria,
    get_categoria_by_slug,
    get_categorias,
)


# =========================================================
# OBTENER CATEGORÍA POR ID
# =========================================================

def get_categoria_service(
    db: Session,
    categoria_id: int,
    solo_activas: bool = True,
) -> Categoria | None:

    return get_categoria(
        db=db,
        categoria_id=categoria_id,
        solo_activas=solo_activas,
    )


# =========================================================
# OBTENER CATEGORÍA POR SLUG
# =========================================================

def get_categoria_by_slug_service(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Categoria | None:

    return get_categoria_by_slug(
        db=db,
        slug=slug,
        solo_activas=solo_activas,
    )


# =========================================================
# LISTAR CATEGORÍAS
# =========================================================

def get_categorias_service(
    db: Session,
    solo_activas: bool = True,
) -> list[Categoria]:

    return get_categorias(
        db=db,
        solo_activas=solo_activas,
    )
