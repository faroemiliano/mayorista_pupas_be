from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.admin_producto_repository import get_analitica_productos


def get_analitica_productos_service(
    db: Session,
    dias: int | None,
    limit: int,
) -> dict:
    hasta = datetime.now(timezone.utc)
    desde = hasta - timedelta(days=dias) if dias is not None else None
    productos = get_analitica_productos(db, desde)
    con_ventas = [item for item in productos if item["unidades_vendidas"] > 0]
    sin_ventas = [item for item in productos if item["unidades_vendidas"] == 0]

    mas_vendidos = sorted(
        con_ventas,
        key=lambda item: (-item["unidades_vendidas"], -item["importe_vendido"], item["nombre"]),
    )[:limit]
    menos_vendidos = sorted(
        con_ventas,
        key=lambda item: (item["unidades_vendidas"], item["importe_vendido"], item["nombre"]),
    )[:limit]
    sin_ventas = sorted(sin_ventas, key=lambda item: item["nombre"])[:limit]

    return {
        "origen": "pedidos_tienda",
        "alcance": "Incluye pedidos de esta tienda, excepto los cancelados. No incluye todavía ventas históricas de Dux.",
        "dias": dias,
        "desde": desde,
        "hasta": hasta,
        "resumen": {
            "unidades_vendidas": sum(item["unidades_vendidas"] for item in con_ventas),
            "importe_vendido": sum((item["importe_vendido"] for item in con_ventas), Decimal("0")),
            "productos_con_ventas": len(con_ventas),
            "productos_sin_ventas": len(productos) - len(con_ventas),
        },
        "mas_vendidos": mas_vendidos,
        "menos_vendidos": menos_vendidos,
        "sin_ventas": sin_ventas,
    }
