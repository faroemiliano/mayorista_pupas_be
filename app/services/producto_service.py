from math import ceil
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.producto import Producto

from app.repositories.producto_repository import (
    get_producto,
    get_producto_by_slug,
    get_productos,
)


# =========================================================
# PRECIOS DEL CATÁLOGO MAYORISTA
# =========================================================

def aplicar_precios_catalogo(
    producto: Producto,
) -> Producto:

    precios_por_lista = {
        precio.dux_id_lista: precio.precio
        for precio in producto.precios
        if precio.precio > 0
    }

    precio_mayorista: Decimal | None = (
        precios_por_lista.get(
            settings.DUX_LISTA_PRECIO_MAYORISTA_ID
        )
    )

    precio_24_productos: Decimal | None = (
        precios_por_lista.get(
            settings.DUX_LISTA_PRECIO_24_ID
        )
        or precio_mayorista
    )

    producto.precio_mayorista = precio_mayorista
    producto.precio_24_productos = (
        precio_24_productos
    )

    return producto


# =========================================================
# OBTENER PRODUCTO POR ID
# =========================================================

def get_producto_service(
    db: Session,
    producto_id: int,
) -> Producto | None:

    producto = get_producto(
        db,
        producto_id,
    )

    if producto is None:
        return None

    return aplicar_precios_catalogo(
        producto
    )


# =========================================================
# OBTENER PRODUCTO POR SLUG
# =========================================================

def get_producto_by_slug_service(
    db: Session,
    slug: str,
) -> Producto | None:

    producto = get_producto_by_slug(
        db,
        slug,
    )

    if producto is None:
        return None

    return aplicar_precios_catalogo(
        producto
    )


# =========================================================
# LISTAR PRODUCTOS
# =========================================================

def get_productos_service(
    db: Session,
    buscar: str | None = None,
    categoria_id: int | None = None,
    subcategoria_id: int | None = None,
    marca_id: int | None = None,
    solo_habilitados: bool = True,
    con_stock: bool | None = None,
    page: int = 1,
    limit: int = 20,
    orden: str = "nombre_asc",
) -> dict:

    productos, total = get_productos(
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

    for producto in productos:
        aplicar_precios_catalogo(
            producto
        )

    total_paginas = (
        ceil(total / limit)
        if total > 0
        else 0
    )

    return {
        "items": productos,
        "total": total,
        "page": page,
        "limit": limit,
        "total_paginas": total_paginas,
    }
