from math import ceil
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.dux.client import DuxClient
from app.models.producto import Producto

from app.repositories.producto_repository import (
    get_producto,
    get_producto_by_slug,
    get_producto_imagen_url,
    get_productos,
)


# =========================================================
# OBTENER IMAGEN PROTEGIDA DE DUX
# =========================================================

def get_producto_imagen_service(
    db: Session,
    producto_id: int,
) -> tuple[bytes, str] | None:

    imagen_url = get_producto_imagen_url(
        db=db,
        producto_id=producto_id,
    )

    if imagen_url is None:
        return None

    return DuxClient().get_imagen(
        imagen_url
    )


# =========================================================
# PRECIOS DEL CATÁLOGO MAYORISTA
# =========================================================

def aplicar_datos_catalogo(
    producto: Producto,
    mostrar_precios: bool = True,
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

    producto.precio_mayorista = precio_mayorista if mostrar_precios else None
    producto.precio_24_productos = (
        precio_24_productos if mostrar_precios else None
    )

    stock_disponible = sum(
        (
            Decimal(stock.stock_disponible)
            for stock in producto.stocks
        ),
        start=Decimal("0.00"),
    )

    producto.stock_disponible = max(
        stock_disponible,
        Decimal("0.00"),
    )
    producto.tiene_stock = (
        producto.stock_disponible > 0
    )

    return producto


# =========================================================
# OBTENER PRODUCTO POR ID
# =========================================================

def get_producto_service(
    db: Session,
    producto_id: int,
    mostrar_precios: bool = True,
) -> Producto | None:

    producto = get_producto(
        db,
        producto_id,
    )

    if producto is None:
        return None

    return aplicar_datos_catalogo(
        producto, mostrar_precios
    )


# =========================================================
# OBTENER PRODUCTO POR SLUG
# =========================================================

def get_producto_by_slug_service(
    db: Session,
    slug: str,
    mostrar_precios: bool = True,
) -> Producto | None:

    producto = get_producto_by_slug(
        db,
        slug,
    )

    if producto is None:
        return None

    return aplicar_datos_catalogo(
        producto, mostrar_precios
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
    mostrar_precios: bool = True,
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
        aplicar_datos_catalogo(
            producto, mostrar_precios
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
