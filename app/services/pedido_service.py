from datetime import date, datetime, time, timedelta
from math import ceil
import secrets
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pedido import Pedido
from app.models.pedido_item import PedidoItem
from app.models.reserva_stock import ReservaStock
from app.models.usuario import Usuario
from app.repositories.pedido_repository import (
    get_pedido,
    get_pedido_by_codigo,
    get_pedidos,
)
from app.schemas.carrito_schemas import CarritoCalcularRequest
from app.schemas.pedido_schemas import PedidoCreateRequest
from app.repositories.reserva_stock_repository import (
    bloquear_productos,
    liberar_reservas_pedido,
)
from app.services.carrito_service import CarritoError, calcular_carrito_service
from app.services.notificacion_service import notificar


class PedidoError(ValueError):
    pass


def _generar_codigo(db: Session) -> str:
    while True:
        codigo = f"PUP-{secrets.token_hex(6).upper()}"
        if get_pedido_by_codigo(db, codigo) is None:
            return codigo


def crear_pedido_service(db: Session, data: PedidoCreateRequest, usuario: Usuario) -> Pedido:
    producto_ids = {item.producto_id for item in data.items}
    # Serializa pedidos concurrentes sobre los mismos productos. La validación,
    # el pedido y sus reservas se confirman en una única transacción.
    bloquear_productos(db, producto_ids)
    try:
        calculo = calcular_carrito_service(
            db,
            CarritoCalcularRequest(items=data.items),
        )
    except CarritoError as error:
        raise PedidoError(str(error)) from error

    if calculo["cantidad_unidades"] < settings.COMPRA_MINIMA_UNIDADES:
        raise PedidoError(
            "La compra mínima es de "
            f"{settings.COMPRA_MINIMA_UNIDADES} prendas en total."
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
            talle=item["talle"],
            precio_mayorista=item["precio_mayorista"],
            precio_unitario=item["precio_unitario"],
            subtotal_sin_descuento=item["subtotal_sin_descuento"],
            descuento_aplicado=item["descuento_aplicado"],
            subtotal=item["subtotal"],
        ))
        pedido.reservas_stock.append(ReservaStock(
            producto_id=item["producto_id"],
            cantidad=item["cantidad"],
            talle=item["talle"],
            estado="activa",
        ))

    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    notificar(db,audiencia="admin",tipo="pedido_nuevo",titulo=f"Nuevo pedido {pedido.codigo}",
              mensaje=f"{pedido.cliente_nombre} realizó un pedido por ${pedido.total} con {pedido.cantidad_unidades} unidades.",
              pedido_id=pedido.id,email=settings.EMAIL_ADMIN or None)
    return get_pedido(db, pedido.id) or pedido


def get_pedidos_service(
    db: Session,
    estado: str | None,
    page: int,
    limit: int,
    usuario_id: int | None = None,
    buscar: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> dict:
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise PedidoError("La fecha desde no puede ser posterior a la fecha hasta.")
    zona_local = ZoneInfo("America/Argentina/Buenos_Aires")
    desde_dt = datetime.combine(fecha_desde, time.min, zona_local) if fecha_desde else None
    hasta_dt = datetime.combine(fecha_hasta + timedelta(days=1), time.min, zona_local) if fecha_hasta else None
    pedidos, total = get_pedidos(db, estado, page, limit, usuario_id, buscar, desde_dt, hasta_dt)
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
    if pedido.estado == "cancelado" and estado != "cancelado":
        raise PedidoError("Un pedido cancelado no puede reabrirse porque su stock ya fue liberado.")
    if estado == "cancelado":
        if pedido.dux_id_pedido is not None:
            raise PedidoError("El pedido ya fue enviado. Cancelalo primero en Dux y luego sincronizá el catálogo.")
        liberar_reservas_pedido(db, pedido.id)
    pedido.estado = estado
    db.commit()
    db.refresh(pedido)
    if pedido.usuario_id:
        notificar(db,audiencia="cliente",tipo="estado_pedido",titulo=f"Tu pedido {pedido.codigo} fue actualizado",
                  mensaje=f"El nuevo estado de tu pedido es: {estado}.",usuario_id=pedido.usuario_id,
                  pedido_id=pedido.id,email=pedido.cliente_email)
    return pedido
