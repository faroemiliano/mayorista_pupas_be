from math import ceil
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.dux.client import DuxClient
from app.models.producto import Producto

from app.repositories.producto_repository import (
    get_producto,
    get_producto_by_slug,
    get_imagen_producto_url,
    get_producto_imagen_url,
    get_productos,
)
from app.repositories.reserva_stock_repository import cantidades_reservadas, cantidades_reservadas_por_talle


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


def get_imagen_producto_service(
    db: Session,
    producto_id: int,
    imagen_id: int,
) -> tuple[bytes, str] | None:
    imagen_url = get_imagen_producto_url(
        db=db,
        producto_id=producto_id,
        imagen_id=imagen_id,
    )

    if imagen_url is None:
        return None

    return DuxClient().get_imagen(imagen_url)


# =========================================================
# PRECIOS DEL CATÁLOGO MAYORISTA
# =========================================================

def aplicar_datos_catalogo(
    producto: Producto,
    mostrar_precios: bool = True,
    reserva_local: Decimal = Decimal("0.00"),
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
        stock_disponible - reserva_local,
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

    producto = aplicar_datos_catalogo(
        producto,
        mostrar_precios,
        Decimal(cantidades_reservadas(db, {producto.id}).get(producto.id, 0)),
    )
    reservas_talle = cantidades_reservadas_por_talle(db, {producto.id})
    producto.talles = [{"talle": item.talle, "cantidad": item.cantidad, "disponible": max(item.cantidad-reservas_talle.get((producto.id,item.talle),0),0)} for item in producto.stocks_talles]
    return producto


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

    producto = aplicar_datos_catalogo(
        producto,
        mostrar_precios,
        Decimal(cantidades_reservadas(db, {producto.id}).get(producto.id, 0)),
    )
    reservas_talle = cantidades_reservadas_por_talle(db, {producto.id})
    producto.talles = [{"talle": item.talle, "cantidad": item.cantidad, "disponible": max(item.cantidad-reservas_talle.get((producto.id,item.talle),0),0)} for item in producto.stocks_talles]
    return producto


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

    reservas = cantidades_reservadas(db, {producto.id for producto in productos})
    reservas_talle = cantidades_reservadas_por_talle(db, {producto.id for producto in productos})
    for producto in productos:
        aplicar_datos_catalogo(
            producto,
            mostrar_precios,
            Decimal(reservas.get(producto.id, 0)),
        )
        producto.talles = [{"talle": item.talle, "cantidad": item.cantidad, "disponible": max(item.cantidad-reservas_talle.get((producto.id,item.talle),0),0)} for item in producto.stocks_talles]

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
