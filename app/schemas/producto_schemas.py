from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# =========================================================
# CATEGORÍA
# =========================================================

class CategoriaSimpleResponse(BaseModel):
    id: int
    dux_id: int | None
    nombre: str
    slug: str

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# SUBCATEGORÍA
# =========================================================

class SubcategoriaSimpleResponse(BaseModel):
    id: int
    dux_id: int | None
    nombre: str
    slug: str

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# MARCA
# =========================================================

class MarcaSimpleResponse(BaseModel):
    id: int
    dux_id: int | None
    nombre: str
    slug: str

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# STOCK
# =========================================================

class StockProductoResponse(BaseModel):
    id: int

    dux_id_deposito: int
    nombre_deposito: str

    stock_real: Decimal
    stock_reservado: Decimal
    stock_disponible: Decimal

    dux_id_det_item: int | None
    codigo_barra_detalle: str | None

    talle: str | None
    color: str | None

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# IMAGEN
# =========================================================

class ImagenProductoResponse(BaseModel):
    id: int
    url: str
    orden: int
    principal: bool

    model_config = ConfigDict(
        from_attributes=True,
    )

class StockTalleResponse(BaseModel):
    talle: int
    cantidad: int
    disponible: int
    model_config = ConfigDict(from_attributes=True)


# =========================================================
# CÓDIGO DE BARRA
# =========================================================

class CodigoBarraProductoResponse(BaseModel):
    id: int
    codigo: str

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# PRODUCTO BASE
# =========================================================

class ProductoBaseResponse(BaseModel):
    id: int

    dux_codigo: str
    nombre: str
    slug: str

    codigo_externo: str | None
    descripcion: str | None

    porcentaje_iva: Decimal | None

    precio_mayorista: Decimal | None
    precio_24_productos: Decimal | None

    stock_disponible: Decimal
    tiene_stock: bool

    imagen_url: str | None
    talles: list[StockTalleResponse] = []

    cantidad_unidades_por_bulto: Decimal | None

    habilitado: bool
    visible_tienda: bool

    fecha_creacion_dux: date | None

    creado_en: datetime
    actualizado_en: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# PRODUCTO LISTADO
# =========================================================

class ProductoListadoItemResponse(
    ProductoBaseResponse
):
    categoria: CategoriaSimpleResponse | None
    subcategoria: SubcategoriaSimpleResponse | None
    marca: MarcaSimpleResponse | None

    imagenes: list[ImagenProductoResponse] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# PRODUCTO DETALLE
# =========================================================

class ProductoDetalleResponse(
    ProductoBaseResponse
):
    categoria: CategoriaSimpleResponse | None

    subcategoria: (
        SubcategoriaSimpleResponse | None
    )

    marca: MarcaSimpleResponse | None

    stocks: list[
        StockProductoResponse
    ] = []

    imagenes: list[
        ImagenProductoResponse
    ] = []

    codigos_barra: list[
        CodigoBarraProductoResponse
    ] = []

    model_config = ConfigDict(
        from_attributes=True,
    )


# =========================================================
# RESPUESTA PAGINADA
# =========================================================

class ProductoListadoResponse(BaseModel):
    items: list[
        ProductoListadoItemResponse
    ]

    total: int
    page: int
    limit: int
    total_paginas: int
