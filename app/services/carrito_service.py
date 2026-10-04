from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.producto import Producto
from app.models.reserva_carrito import ReservaCarrito
from sqlalchemy import select
from app.repositories.carrito_repository import (
    get_productos_carrito,
)
from app.repositories.reserva_stock_repository import cantidades_reservadas, cantidades_reservadas_por_talle
from app.services.stock_fuente_service import sumar_stock_fuente_activa
from app.schemas.carrito_schemas import (
    CarritoCalcularRequest,
    CarritoReservaRequest,
)
from app.repositories.reserva_stock_repository import bloquear_productos, liberar_reservas_carrito


CANTIDAD_UNIDADES_PRECIO_ESPECIAL = 24


class CarritoError(ValueError):
    pass


def reservar_carrito_service(db: Session, carrito: CarritoReservaRequest, usuario_id: int) -> dict:
    cantidades: dict[tuple[int, str], int] = defaultdict(int)
    for item in carrito.items:
        cantidades[(item.producto_id, item.talle.strip())] += item.cantidad
    producto_ids = {producto_id for producto_id, _ in cantidades}
    bloquear_productos(db, producto_ids)
    existentes = list(db.scalars(select(ReservaCarrito).where(ReservaCarrito.usuario_id == usuario_id)).all())
    if not cantidades:
        for reserva in existentes: db.delete(reserva)
        db.commit()
        return {"items": [], "expira_en": None}
    calcular_carrito_service(db, CarritoCalcularRequest(items=[
        {"producto_id": producto_id, "talle": talle, "cantidad": cantidad}
        for (producto_id, talle), cantidad in cantidades.items()
    ]), usuario_id)
    expira = datetime.now(timezone.utc) + timedelta(minutes=settings.CARRITO_RESERVA_MINUTOS)
    por_clave = {(item.producto_id, item.talle): item for item in existentes}
    for clave, reserva in por_clave.items():
        if clave not in cantidades: db.delete(reserva)
    for (producto_id, talle), cantidad in cantidades.items():
        reserva = por_clave.get((producto_id, talle))
        if reserva is None:
            reserva = ReservaCarrito(usuario_id=usuario_id, producto_id=producto_id, talle=talle, cantidad=cantidad, expira_en=expira)
            db.add(reserva)
        else:
            reserva.cantidad = cantidad; reserva.reservada_en = datetime.now(timezone.utc); reserva.expira_en = expira
    db.commit()
    return {"items": [{"producto_id": p, "talle": t, "cantidad": c} for (p,t),c in cantidades.items()], "expira_en": expira.isoformat()}


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
    usuario_id: int | None = None,
) -> dict:

    cantidades: dict[tuple[int, str], int] = defaultdict(int)

    for item in carrito.items:
        cantidades[(item.producto_id, item.talle.strip())] += (
            item.cantidad
        )

    cantidades_por_producto: dict[int, int] = defaultdict(int)
    for (producto_id, _talle), cantidad in cantidades.items():
        cantidades_por_producto[producto_id] += cantidad

    producto_ids = {producto_id for producto_id, _ in cantidades}
    productos = get_productos_carrito(
        db=db,
        producto_ids=producto_ids,
    )
    productos_por_id = {
        producto.id: producto
        for producto in productos
    }
    reservas_por_producto = cantidades_reservadas(db, producto_ids, usuario_id)
    reservas_por_talle = cantidades_reservadas_por_talle(db, producto_ids, usuario_id)

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
    cantidad_unidades = sum(cantidades.values())
    aplica_precio_24 = (
        cantidad_unidades
        >= CANTIDAD_UNIDADES_PRECIO_ESPECIAL
    )

    items_resultado = []
    total = Decimal("0.00")
    subtotal_sin_descuento = Decimal("0.00")

    for producto_id, talle in sorted(cantidades):
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

        cantidad = cantidades[(producto_id, talle)]
        stock_talle = next((item.cantidad for item in producto.stocks_talles if item.talle == talle), None)
        if stock_talle is None:
            raise CarritoError(f"El producto {producto.id} no tiene configurado el talle {talle}.")
        disponible_talle = max(stock_talle - reservas_por_talle.get((producto_id, talle), 0), 0)
        if cantidad > disponible_talle:
            raise CarritoError(f"El producto {producto.id}, talle {talle}, tiene {disponible_talle} unidades disponibles.")

        stock_dux = max(
            sumar_stock_fuente_activa(producto.stocks),
            Decimal("0.00"),
        )
        stock_disponible = max(
            stock_dux - Decimal(reservas_por_producto.get(producto_id, 0)),
            Decimal("0.00"),
        )

        cantidad_total_producto = cantidades_por_producto[producto_id]
        if cantidad_total_producto > stock_disponible:
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
            "talle": talle,
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
