from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.carrito_schemas import CarritoItemRequest


PedidoEstado = Literal[
    "pendiente",
    "contactado",
    "confirmado",
    "cancelado",
]


class PedidoCreateRequest(BaseModel):
    cliente_nombre: str = Field(min_length=2, max_length=150)
    cliente_telefono: str = Field(min_length=6, max_length=50)
    cliente_email: str | None = Field(default=None, max_length=200)
    provincia: str = Field(min_length=2, max_length=100)
    localidad: str = Field(min_length=2, max_length=100)
    direccion: str = Field(min_length=4, max_length=250)
    observaciones: str | None = Field(default=None, max_length=1000)
    items: list[CarritoItemRequest] = Field(min_length=1)


class PedidoEstadoRequest(BaseModel):
    estado: PedidoEstado


class PedidoItemResponse(BaseModel):
    id: int
    producto_id: int | None
    dux_codigo: str
    producto_nombre: str
    cantidad: int
    talle: int | None
    precio_mayorista: Decimal
    precio_unitario: Decimal
    subtotal_sin_descuento: Decimal
    descuento_aplicado: Decimal
    subtotal: Decimal

    model_config = ConfigDict(from_attributes=True)


class PedidoResponse(BaseModel):
    id: int
    codigo: str
    estado: str
    cliente_nombre: str
    cliente_telefono: str
    cliente_email: str | None
    provincia: str
    localidad: str
    direccion: str
    observaciones: str | None
    cantidad_productos_diferentes: int
    cantidad_unidades: int
    aplica_precio_24_productos: bool
    subtotal_sin_descuento: Decimal
    descuento_aplicado: Decimal
    total: Decimal
    creado_en: datetime
    actualizado_en: datetime
    dux_id_pedido: int | None
    dux_nro_pedido: int | None
    dux_id_personal: int | None
    estado_sync_dux: str
    error_sync_dux: str | None
    sincronizado_dux_en: datetime | None
    items: list[PedidoItemResponse]

    model_config = ConfigDict(from_attributes=True)


class PedidoListadoResponse(BaseModel):
    items: list[PedidoResponse]
    total: int
    page: int
    limit: int
    total_paginas: int


class EnviarDuxRequest(BaseModel):
    id_personal: int
