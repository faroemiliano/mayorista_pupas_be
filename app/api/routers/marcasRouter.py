from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.marca_schemas import (
    MarcaResponse,
)
from app.services.marca_service import (
    get_marca_by_slug_service,
    get_marca_service,
    get_marcas_service,
)


router = APIRouter(
    prefix="/api/marcas",
    tags=["Marcas"],
)


# =========================================================
# LISTAR MARCAS
# =========================================================

@router.get(
    "/",
    response_model=list[MarcaResponse],
)
def listar_marcas(
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    return get_marcas_service(
        db=db,
        solo_activas=solo_activas,
    )


# =========================================================
# MARCA POR SLUG
# IMPORTANTE:
# esta ruta debe estar antes de /{marca_id}
# =========================================================

@router.get(
    "/slug/{slug}",
    response_model=MarcaResponse,
)
def obtener_marca_por_slug(
    slug: str,
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    marca = get_marca_by_slug_service(
        db=db,
        slug=slug,
        solo_activas=solo_activas,
    )

    if marca is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marca no encontrada.",
        )

    return marca


# =========================================================
# MARCA POR ID
# =========================================================

@router.get(
    "/{marca_id}",
    response_model=MarcaResponse,
)
def obtener_marca(
    marca_id: int = Path(gt=0),
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    marca = get_marca_service(
        db=db,
        marca_id=marca_id,
        solo_activas=solo_activas,
    )

    if marca is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Marca no encontrada.",
        )

    return marca
