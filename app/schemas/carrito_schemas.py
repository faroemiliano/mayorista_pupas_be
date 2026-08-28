from decimal import Decimal

from pydantic import BaseModel, Field


class CarritoItemRequest(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class CarritoCalcularRequest(BaseModel):
    items: list[CarritoItemRequest] = Field(
        min_length=1,
    )


class CarritoItemResponse(BaseModel):
    producto_id: int
    dux_codigo: str
    nombre: str
    slug: str
    imagen_url: str | None
    cantidad: int
    precio_mayorista: Decimal
    precio_unitario: Decimal
    subtotal_sin_descuento: Decimal
    descuento_aplicado: Decimal
    subtotal: Decimal


class CarritoCalcularResponse(BaseModel):
    items: list[CarritoItemResponse]
    cantidad_productos_diferentes: int
    cantidad_unidades: int
    aplica_precio_24_productos: bool
    faltantes_para_precio_24: int
    subtotal_sin_descuento: Decimal
    descuento_aplicado: Decimal
    total: Decimal
