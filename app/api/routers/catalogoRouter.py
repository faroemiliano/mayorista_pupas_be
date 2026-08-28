from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.catalogo_schemas import (
    CatalogoFiltrosResponse,
)
from app.services.catalogo_service import (
    get_catalogo_filtros_service,
)


router = APIRouter(
    prefix="/api/catalogo",
    tags=["Catálogo"],
)


# =========================================================
# FILTROS DEL CATÁLOGO
# =========================================================

@router.get(
    "/filtros",
    response_model=CatalogoFiltrosResponse,
)
def obtener_filtros_catalogo(
    db: Session = Depends(get_db),
):

    return get_catalogo_filtros_service(
        db=db,
    )
