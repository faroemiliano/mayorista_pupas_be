from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import Response
import httpx
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.security import get_usuario_opcional
from app.models.usuario import Usuario

from app.schemas.producto_schemas import (
    ProductoDetalleResponse,
    ProductoListadoResponse,
)

from app.services.producto_service import (
    get_producto_by_slug_service,
    get_producto_imagen_service,
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
    usuario: Usuario | None = Depends(get_usuario_opcional),
):

    if not solo_habilitados and (usuario is None or usuario.rol != "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sólo un administrador puede ver productos ocultos.")

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
        mostrar_precios=usuario is not None,
    )


# =========================================================
# IMAGEN DEL PRODUCTO
# =========================================================

@router.get(
    "/{producto_id}/imagen",
    response_class=Response,
    responses={
        200: {
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/gif": {},
                "image/webp": {},
            },
            "description": "Imagen del producto.",
        }
    },
)
def obtener_imagen_producto(
    producto_id: int,
    db: Session = Depends(get_db),
):

    try:
        resultado = get_producto_imagen_service(
            db=db,
            producto_id=producto_id,
        )
    except (
        httpx.HTTPError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener la imagen desde Dux.",
        ) from error

    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El producto no tiene imagen.",
        )

    imagen, media_type = resultado

    return Response(
        content=imagen,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
        },
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
    usuario: Usuario | None = Depends(get_usuario_opcional),
):

    producto = get_producto_by_slug_service(
        db,
        slug, mostrar_precios=usuario is not None,
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
    usuario: Usuario | None = Depends(get_usuario_opcional),
):

    producto = get_producto_service(
        db,
        producto_id, mostrar_precios=usuario is not None,
    )

    if producto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    return producto
