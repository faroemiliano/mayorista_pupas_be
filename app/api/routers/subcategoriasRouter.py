from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.categoria_schemas import (
    SubcategoriaDetalleResponse,
)
from app.services.subcategoria_service import (
    get_subcategoria_by_slug_service,
    get_subcategoria_service,
    get_subcategorias_service,
)


router = APIRouter(
    prefix="/api/subcategorias",
    tags=["Subcategorías"],
)


# =========================================================
# LISTAR SUBCATEGORÍAS
# =========================================================

@router.get(
    "/",
    response_model=list[
        SubcategoriaDetalleResponse
    ],
)
def listar_subcategorias(
    categoria_id: int | None = Query(
        default=None,
        gt=0,
    ),
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    return get_subcategorias_service(
        db=db,
        categoria_id=categoria_id,
        solo_activas=solo_activas,
    )


# =========================================================
# SUBCATEGORÍA POR SLUG
# IMPORTANTE:
# esta ruta debe estar antes de /{subcategoria_id}
# =========================================================

@router.get(
    "/slug/{slug}",
    response_model=SubcategoriaDetalleResponse,
)
def obtener_subcategoria_por_slug(
    slug: str,
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    subcategoria = (
        get_subcategoria_by_slug_service(
            db=db,
            slug=slug,
            solo_activas=solo_activas,
        )
    )

    if subcategoria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategoría no encontrada.",
        )

    return subcategoria


# =========================================================
# SUBCATEGORÍA POR ID
# =========================================================

@router.get(
    "/{subcategoria_id}",
    response_model=SubcategoriaDetalleResponse,
)
def obtener_subcategoria(
    subcategoria_id: int = Path(gt=0),
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    subcategoria = get_subcategoria_service(
        db=db,
        subcategoria_id=subcategoria_id,
        solo_activas=solo_activas,
    )

    if subcategoria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategoría no encontrada.",
        )

    return subcategoria
