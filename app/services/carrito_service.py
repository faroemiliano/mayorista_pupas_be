from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.producto import Producto
from app.repositories.carrito_repository import (
    get_productos_carrito,
)
from app.schemas.carrito_schemas import (
    CarritoCalcularRequest,
)


CANTIDAD_UNIDADES_PRECIO_ESPECIAL = 24


class CarritoError(ValueError):
    pass


def _obtener_precio(
    producto: Producto,
    dux_id_lista: int,
) -> Decimal | None:

    for precio in producto.precios:
        if (
            precio.dux_id_lista == dux_id_lista
            and precio.precio > 0
        ):
            return Decimal(precio.precio)

    return None


# =========================================================
# CALCULAR CARRITO
# =========================================================

def calcular_carrito_service(
    db: Session,
    carrito: CarritoCalcularRequest,
) -> dict:

    cantidades: dict[int, int] = defaultdict(int)

    for item in carrito.items:
        cantidades[item.producto_id] += (
            item.cantidad
        )

    producto_ids = set(cantidades)
    productos = get_productos_carrito(
        db=db,
        producto_ids=producto_ids,
    )
    productos_por_id = {
        producto.id: producto
        for producto in productos
    }

    productos_no_disponibles = sorted(
        producto_ids - set(productos_por_id)
    )

    if productos_no_disponibles:
        ids = ", ".join(
            str(producto_id)
            for producto_id
            in productos_no_disponibles
        )
        raise CarritoError(
            "Productos inexistentes o no habilitados: "
            f"{ids}."
        )

    cantidad_diferentes = len(producto_ids)
    cantidad_unidades = sum(
        cantidades.values()
    )
    aplica_precio_24 = (
        cantidad_unidades
        >= CANTIDAD_UNIDADES_PRECIO_ESPECIAL
    )

    items_resultado = []
    total = Decimal("0.00")
    subtotal_sin_descuento = Decimal("0.00")

    for producto_id in sorted(producto_ids):
        producto = productos_por_id[producto_id]

        precio_mayorista = _obtener_precio(
            producto,
            settings.DUX_LISTA_PRECIO_MAYORISTA_ID,
        )

        if precio_mayorista is None:
            raise CarritoError(
                f"El producto {producto.id} no tiene "
                "un precio mayorista válido."
            )

        precio_unitario = precio_mayorista

        if aplica_precio_24:
            precio_24 = _obtener_precio(
                producto,
                settings.DUX_LISTA_PRECIO_24_ID,
            )

            if precio_24 is not None:
                precio_unitario = precio_24

        cantidad = cantidades[producto_id]

        stock_disponible = max(
            sum(
                (
                    Decimal(stock.stock_disponible)
                    for stock in producto.stocks
                ),
                start=Decimal("0.00"),
            ),
            Decimal("0.00"),
        )

        if cantidad > stock_disponible:
            raise CarritoError(
                f"El producto {producto.id} tiene "
                f"{stock_disponible} unidades disponibles."
            )

        subtotal = precio_unitario * cantidad
        subtotal_mayorista = (
            precio_mayorista * cantidad
        )
        descuento_item = (
            subtotal_mayorista - subtotal
        )
        total += subtotal
        subtotal_sin_descuento += (
            subtotal_mayorista
        )

        items_resultado.append({
            "producto_id": producto.id,
            "dux_codigo": producto.dux_codigo,
            "nombre": producto.nombre,
            "slug": producto.slug,
            "imagen_url": producto.imagen_url,
            "cantidad": cantidad,
            "precio_mayorista": precio_mayorista,
            "precio_unitario": precio_unitario,
            "subtotal_sin_descuento": (
                subtotal_mayorista
            ),
            "descuento_aplicado": descuento_item,
            "subtotal": subtotal,
        })

    return {
        "items": items_resultado,
        "cantidad_productos_diferentes": (
            cantidad_diferentes
        ),
        "cantidad_unidades": cantidad_unidades,
        "aplica_precio_24_productos": (
            aplica_precio_24
        ),
        "faltantes_para_precio_24": max(
            CANTIDAD_UNIDADES_PRECIO_ESPECIAL
            - cantidad_unidades,
            0,
        ),
        "subtotal_sin_descuento": (
            subtotal_sin_descuento
        ),
        "descuento_aplicado": (
            subtotal_sin_descuento - total
        ),
        "total": total,
    }
