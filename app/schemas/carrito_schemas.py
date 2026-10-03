from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CarritoItemRequest(BaseModel):
    producto_id: int = Field(gt=0)
    talle: str = Field(default="1", min_length=1, max_length=30)
    cantidad: int = Field(gt=0)

    @field_validator("talle", mode="before")
    @classmethod
    def normalizar_talle(cls, valor):
        return str(valor).strip()


class CarritoCalcularRequest(BaseModel):
    items: list[CarritoItemRequest] = Field(
        min_length=1,
    )


class CarritoReservaRequest(BaseModel):
    items: list[CarritoItemRequest] = Field(default_factory=list, max_length=100)


class CarritoReservaResponse(BaseModel):
    items: list[CarritoItemRequest]
    expira_en: str | None


class CarritoItemResponse(BaseModel):
    producto_id: int
    dux_codigo: str
    nombre: str
    slug: str
    imagen_url: str | None
    cantidad: int
    talle: str
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
    compra_minima_unidades: int
    faltantes_para_compra_minima: int
    cumple_compra_minima: bool
