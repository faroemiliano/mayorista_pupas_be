from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.admin_producto_repository import get_analitica_productos, get_ventas_temporales


MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _inicio_intervalo(fecha: datetime, agrupacion: str) -> datetime:
    fecha = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
    if agrupacion == "semana":
        return fecha - timedelta(days=fecha.weekday())
    if agrupacion == "mes":
        return fecha.replace(day=1)
    if agrupacion == "anio":
        return fecha.replace(month=1, day=1)
    return fecha


def _siguiente_intervalo(fecha: datetime, agrupacion: str) -> datetime:
    if agrupacion == "dia":
        return fecha + timedelta(days=1)
    if agrupacion == "semana":
        return fecha + timedelta(days=7)
    if agrupacion == "mes":
        return fecha.replace(year=fecha.year + 1, month=1) if fecha.month == 12 else fecha.replace(month=fecha.month + 1)
    return fecha.replace(year=fecha.year + 1)


def _etiqueta_intervalo(fecha: datetime, agrupacion: str) -> str:
    if agrupacion == "dia":
        return f"{fecha.day} {MESES[fecha.month - 1]}"
    if agrupacion == "semana":
        return f"Sem. {fecha.day} {MESES[fecha.month - 1]}"
    if agrupacion == "mes":
        return f"{MESES[fecha.month - 1].title()} {fecha.year}"
    return str(fecha.year)


def _crear_serie_ventas(db: Session, desde: datetime | None, hasta: datetime, agrupacion: str) -> list[dict]:
    ventas = get_ventas_temporales(db, desde, hasta + timedelta(microseconds=1))
    inicio = _inicio_intervalo(desde or (ventas[0]["creado_en"] if ventas else hasta), agrupacion)
    fin = _inicio_intervalo(hasta, agrupacion)
    puntos: dict[datetime, dict] = {}
    cursor = inicio
    while cursor <= fin:
        puntos[cursor] = {"pedidos": 0, "unidades": 0, "importe": Decimal("0")}
        cursor = _siguiente_intervalo(cursor, agrupacion)

    for venta in ventas:
        fecha = venta["creado_en"]
        if fecha.tzinfo is None and hasta.tzinfo is not None:
            fecha = fecha.replace(tzinfo=hasta.tzinfo)
        clave = _inicio_intervalo(fecha, agrupacion)
        punto = puntos.setdefault(clave, {"pedidos": 0, "unidades": 0, "importe": Decimal("0")})
        punto["pedidos"] += 1
        punto["unidades"] += int(venta["cantidad_unidades"])
        punto["importe"] += Decimal(venta["total"])

    resultado = []
    anterior: Decimal | None = None
    for fecha, punto in sorted(puntos.items()):
        importe = punto["importe"]
        variacion = None if anterior in (None, Decimal("0")) else round(float((importe - anterior) / anterior * 100), 1)
        resultado.append({
            "clave": fecha.isoformat(),
            "etiqueta": _etiqueta_intervalo(fecha, agrupacion),
            "inicio": fecha,
            **punto,
            "variacion_porcentual": variacion,
        })
        anterior = importe
    return resultado


def _resumen_ventas(ventas: list[dict]) -> dict:
    return {
        "pedidos": len(ventas),
        "unidades": sum(int(item["cantidad_unidades"]) for item in ventas),
        "importe": sum((Decimal(item["total"]) for item in ventas), Decimal("0")),
    }


def get_analitica_productos_service(
    db: Session,
    dias: int | None,
    limit: int,
    agrupacion: str = "dia",
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> dict:
    if fecha_desde is not None and fecha_hasta is not None:
        desde = datetime.combine(fecha_desde, time.min, timezone.utc)
        hasta_exclusivo = datetime.combine(fecha_hasta + timedelta(days=1), time.min, timezone.utc)
        hasta = hasta_exclusivo - timedelta(microseconds=1)
    else:
        hasta = datetime.now(timezone.utc)
        hasta_exclusivo = hasta + timedelta(microseconds=1)
        desde = hasta - timedelta(days=dias) if dias is not None else None
    productos = get_analitica_productos(db, desde, hasta_exclusivo)
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
    comparacion_anterior = None
    if desde is not None:
        duracion = hasta_exclusivo - desde
        anterior_desde = desde - duracion
        anterior_hasta = desde
        comparacion_anterior = {
            "desde": anterior_desde,
            "hasta": anterior_hasta - timedelta(microseconds=1),
            "resumen": _resumen_ventas(
                get_ventas_temporales(db, anterior_desde, anterior_hasta)
            ),
        }

    return {
        "origen": "pedidos_tienda",
        "alcance": "Incluye el historial migrado de WordPress y los pedidos nuevos de esta tienda, excepto los cancelados. No incluye ventas externas registradas solamente en Dux.",
        "dias": None if fecha_desde is not None else dias,
        "desde": desde,
        "hasta": hasta,
        "resumen": {
            "unidades_vendidas": sum(item["unidades_vendidas"] for item in con_ventas),
            "importe_vendido": sum((item["importe_vendido"] for item in con_ventas), Decimal("0")),
            "productos_con_ventas": len(con_ventas),
            "productos_sin_ventas": len(productos) - len(con_ventas),
        },
        "agrupacion": agrupacion,
        "serie_ventas": _crear_serie_ventas(db, desde, hasta, agrupacion),
        "mas_vendidos": mas_vendidos,
        "menos_vendidos": menos_vendidos,
        "sin_ventas": sin_ventas,
        "comparacion_anterior": comparacion_anterior,
    }
