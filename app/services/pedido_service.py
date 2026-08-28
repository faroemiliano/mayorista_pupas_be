from math import ceil
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.usuario import Usuario
from app.repositories.pedido_repository import (
    get_pedido,
    get_pedido_by_codigo,
    get_pedidos,
)
from app.schemas.carrito_schemas import CarritoCalcularRequest
from app.schemas.pedido_schemas import PedidoCreateRequest
from app.services.carrito_service import CarritoError, calcular_carrito_service


class PedidoError(ValueError):
    pass


def _generar_codigo(db: Session) -> str:
    while True:
        codigo = f"PUP-{secrets.token_hex(6).upper()}"
        if get_pedido_by_codigo(db, codigo) is None:
            return codigo


def crear_pedido_service(db: Session, data: PedidoCreateRequest, usuario: Usuario) -> Pedido:
    try:
        calculo = calcular_carrito_service(
            db,
            CarritoCalcularRequest(items=data.items),
        )
    except CarritoError as error:
        raise PedidoError(str(error)) from error

    if calculo["total"] < settings.COMPRA_MINIMA:
        raise PedidoError(
            "La compra mínima es de "
            f"${settings.COMPRA_MINIMA:,.2f}."
        )

    pedido = Pedido(
        usuario_id=usuario.id,
        codigo=_generar_codigo(db),
        estado="pendiente",
        cliente_nombre=data.cliente_nombre.strip(),
        cliente_telefono=data.cliente_telefono.strip(),
        cliente_email=data.cliente_email.strip() if data.cliente_email else None,
        provincia=data.provincia.strip(),
        localidad=data.localidad.strip(),
        direccion=data.direccion.strip(),
        observaciones=data.observaciones.strip() if data.observaciones else None,
        cantidad_productos_diferentes=calculo["cantidad_productos_diferentes"],
        cantidad_unidades=calculo["cantidad_unidades"],
        aplica_precio_24_productos=calculo["aplica_precio_24_productos"],
        subtotal_sin_descuento=calculo["subtotal_sin_descuento"],
        descuento_aplicado=calculo["descuento_aplicado"],
        total=calculo["total"],
    )

    for item in calculo["items"]:
        pedido.items.append(PedidoItem(
            producto_id=item["producto_id"],
            dux_codigo=item["dux_codigo"],
            producto_nombre=item["nombre"],
            cantidad=item["cantidad"],
            precio_mayorista=item["precio_mayorista"],
            precio_unitario=item["precio_unitario"],
            subtotal_sin_descuento=item["subtotal_sin_descuento"],
            descuento_aplicado=item["descuento_aplicado"],
            subtotal=item["subtotal"],
        ))

    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return get_pedido(db, pedido.id) or pedido


def get_pedidos_service(db: Session, estado: str | None, page: int, limit: int, usuario_id: int | None = None) -> dict:
    pedidos, total = get_pedidos(db, estado, page, limit, usuario_id)
    return {
        "items": pedidos,
        "total": total,
        "page": page,
        "limit": limit,
        "total_paginas": ceil(total / limit) if total else 0,
    }


def actualizar_estado_pedido_service(db: Session, pedido_id: int, estado: str) -> Pedido | None:
    pedido = get_pedido(db, pedido_id)
    if pedido is None:
        return None
    pedido.estado = estado
    db.commit()
    db.refresh(pedido)
    return pedido
