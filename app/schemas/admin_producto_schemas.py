from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductoVentaRankingResponse(BaseModel):
    producto_id: int
    dux_codigo: str
    nombre: str
    unidades_vendidas: int
    cantidad_pedidos: int
    importe_vendido: Decimal
    stock_disponible: Decimal


class ProductoAnaliticaResumenResponse(BaseModel):
    unidades_vendidas: int
    importe_vendido: Decimal
    productos_con_ventas: int
    productos_sin_ventas: int


class ProductoAnaliticaResponse(BaseModel):
    origen: str
    alcance: str
    dias: int | None
    desde: datetime | None
    hasta: datetime
    resumen: ProductoAnaliticaResumenResponse
    mas_vendidos: list[ProductoVentaRankingResponse]
    menos_vendidos: list[ProductoVentaRankingResponse]
    sin_ventas: list[ProductoVentaRankingResponse]
