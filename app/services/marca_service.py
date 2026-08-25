from sqlalchemy.orm import Session

from app.models.marca import Marca
from app.repositories.marca_repository import (
    get_marca,
    get_marca_by_slug,
    get_marcas,
)


# =========================================================
# OBTENER MARCA POR ID
# =========================================================

def get_marca_service(
    db: Session,
    marca_id: int,
    solo_activas: bool = True,
) -> Marca | None:

    return get_marca(
        db=db,
        marca_id=marca_id,
        solo_activas=solo_activas,
    )


# =========================================================
# OBTENER MARCA POR SLUG
# =========================================================

def get_marca_by_slug_service(
    db: Session,
    slug: str,
    solo_activas: bool = True,
) -> Marca | None:

    return get_marca_by_slug(
        db=db,
        slug=slug,
        solo_activas=solo_activas,
    )


# =========================================================
# LISTAR MARCAS
# =========================================================

def get_marcas_service(
    db: Session,
    solo_activas: bool = True,
) -> list[Marca]:

    return get_marcas(
        db=db,
        solo_activas=solo_activas,
    )
