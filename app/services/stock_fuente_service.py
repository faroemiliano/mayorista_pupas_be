from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import true

from app.core.config import settings


def dux_es_fuente_stock() -> bool:
    """Indica si el stock comercial debe salir exclusivamente de Dux."""

    return settings.DUX_SINCRONIZACION_HABILITADA


def es_stock_del_deposito_dux(dux_id_deposito: int) -> bool:
    """Valida que el stock pueda abastecer los pedidos de la tienda.

    Cuando existe un depósito configurado para los pedidos, sólo se ofrece
    mercadería de ese depósito. Sin esa configuración se aceptan todos los
    depósitos reales de Dux y se excluye el depósito temporal de WordPress
    (identificado con ``-1``).
    """

    if settings.DUX_ID_DEPOSITO is not None:
        return dux_id_deposito == settings.DUX_ID_DEPOSITO
    return dux_id_deposito >= 0


def es_stock_de_fuente_activa(dux_id_deposito: int) -> bool:
    if not dux_es_fuente_stock():
        return True
    return es_stock_del_deposito_dux(dux_id_deposito)


def filtro_stock_fuente_activa(columna_deposito):
    """Versión SQL del filtro usado al calcular el stock del catálogo."""

    if not dux_es_fuente_stock():
        return true()
    if settings.DUX_ID_DEPOSITO is not None:
        return columna_deposito == settings.DUX_ID_DEPOSITO
    return columna_deposito >= 0


def sumar_stock_fuente_activa(stocks: Iterable) -> Decimal:
    return sum(
        (
            Decimal(stock.stock_disponible)
            for stock in stocks
            if es_stock_de_fuente_activa(stock.dux_id_deposito)
        ),
        start=Decimal("0.00"),
    )


def sumar_stock_deposito_dux(stocks: Iterable) -> Decimal:
    return sum(
        (
            Decimal(stock.stock_disponible)
            for stock in stocks
            if es_stock_del_deposito_dux(stock.dux_id_deposito)
        ),
        start=Decimal("0.00"),
    )
