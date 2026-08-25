from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.database.session import get_db

from app.schemas.producto_schemas import (
    ProductoDetalleResponse,
    ProductoListadoResponse,
)

from app.services.producto_service import (
    get_producto_by_slug_service,
    get_producto_service,
    get_productos_service,
)


router = APIRouter(
    prefix="/api/productos",
    tags=["Productos"],
)


# =========================================================
# LISTAR PRODUCTOS
# =========================================================

@router.get(
    "/",
    response_model=ProductoListadoResponse,
)
def listar_productos(
    buscar: str | None = None,

    categoria_id: int | None = Query(
        default=None,
        gt=0,
    ),

    subcategoria_id: int | None = Query(
        default=None,
        gt=0,
    ),

    marca_id: int | None = Query(
        default=None,
        gt=0,
    ),

    solo_habilitados: bool = True,

    con_stock: bool | None = None,

    page: int = Query(
        default=1,
        ge=1,
    ),

    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    orden: str = "nombre_asc",

    db: Session = Depends(get_db),
):

    return get_productos_service(
        db=db,
        buscar=buscar,
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        marca_id=marca_id,
        solo_habilitados=solo_habilitados,
        con_stock=con_stock,
        page=page,
        limit=limit,
        orden=orden,
    )


# =========================================================
# PRODUCTO POR SLUG
# IMPORTANTE:
# esta ruta debe estar antes de /{producto_id}
# =========================================================

@router.get(
    "/slug/{slug}",
    response_model=ProductoDetalleResponse,
)
def obtener_producto_por_slug(
    slug: str,
    db: Session = Depends(get_db),
):

    producto = get_producto_by_slug_service(
        db,
        slug,
    )

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    return producto


# =========================================================
# PRODUCTO POR ID
# =========================================================

@router.get(
    "/{producto_id}",
    response_model=ProductoDetalleResponse,
)
def obtener_producto(
    producto_id: int,
    db: Session = Depends(get_db),
):

    producto = get_producto_service(
        db,
        producto_id,
    )

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    return producto