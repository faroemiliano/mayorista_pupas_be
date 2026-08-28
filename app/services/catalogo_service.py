from sqlalchemy.orm import Session

from app.services.categoria_service import (
    get_categorias_service,
)
from app.services.marca_service import (
    get_marcas_service,
)


# =========================================================
# FILTROS PÚBLICOS DEL CATÁLOGO
# =========================================================

def get_catalogo_filtros_service(
    db: Session,
) -> dict:

    return {
        "categorias": get_categorias_service(
            db=db,
            solo_activas=True,
        ),
        "marcas": get_marcas_service(
            db=db,
            solo_activas=True,
        ),
    }
