from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.categoria_schemas import (
    CategoriaResponse,
)
from app.services.categoria_service import (
    get_categoria_by_slug_service,
    get_categoria_service,
    get_categorias_service,
)


router = APIRouter(
    prefix="/api/categorias",
    tags=["Categorías"],
)


# =========================================================
# LISTAR CATEGORÍAS
# =========================================================

@router.get(
    "/",
    response_model=list[CategoriaResponse],
)
def listar_categorias(
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    return get_categorias_service(
        db=db,
        solo_activas=solo_activas,
    )


# =========================================================
# CATEGORÍA POR SLUG
# IMPORTANTE:
# esta ruta debe estar antes de /{categoria_id}
# =========================================================

@router.get(
    "/slug/{slug}",
    response_model=CategoriaResponse,
)
def obtener_categoria_por_slug(
    slug: str,
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    categoria = get_categoria_by_slug_service(
        db=db,
        slug=slug,
        solo_activas=solo_activas,
    )

    if categoria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )

    return categoria


# =========================================================
# CATEGORÍA POR ID
# =========================================================

@router.get(
    "/{categoria_id}",
    response_model=CategoriaResponse,
)
def obtener_categoria(
    categoria_id: int = Path(gt=0),
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):

    categoria = get_categoria_service(
        db=db,
        categoria_id=categoria_id,
        solo_activas=solo_activas,
    )

    if categoria is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoría no encontrada.",
        )

    return categoria
