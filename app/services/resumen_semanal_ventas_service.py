"""Resumen semanal visible para administración.

No requiere un proceso de fondo: al consultar las notificaciones un viernes,
genera una única alerta con las ventas acumuladas desde el lunes. Esto evita
servicios cron adicionales y conserva el detalle completo en Analítica.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notificacion import Notificacion
from app.repositories.admin_producto_repository import get_ventas_temporales
from app.services.notificacion_service import notificar


ZONA_ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def _importe_pesos(valor: Decimal) -> str:
    return f"${valor:,.0f}".replace(",", ".")


def crear_resumen_semanal_si_corresponde(
    db: Session,
    ahora: datetime | None = None,
) -> Notificacion | None:
    """Crea una sola notificación cada viernes con el acumulado semanal.

    El período comienza el lunes a las 00:00 de Argentina y termina al momento
    de generarse el aviso. Si nadie abre el panel un viernes, no se inserta una
    notificación artificial: los datos siguen disponibles desde Analítica.
    """
    instante_utc = (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    instante_argentina = instante_utc.astimezone(ZONA_ARGENTINA)
    if instante_argentina.weekday() != 4:  # viernes
        return None

    clave = f"resumen_semanal_{instante_argentina.date().isoformat()}"
    existente = db.scalar(
        select(Notificacion.id).where(
            Notificacion.audiencia == "admin",
            Notificacion.tipo == clave,
        )
    )
    if existente is not None:
        return None

    lunes_argentina = (instante_argentina - timedelta(days=instante_argentina.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    desde = lunes_argentina.astimezone(timezone.utc)
    ventas = get_ventas_temporales(db, desde, instante_utc)
    pedidos = len(ventas)
    unidades = sum(int(item["cantidad_unidades"] or 0) for item in ventas)
    importe = sum((Decimal(item["total"] or 0) for item in ventas), Decimal("0"))
    periodo = f"{lunes_argentina.strftime('%d/%m')} al {instante_argentina.strftime('%d/%m')}"

    return notificar(
        db,
        audiencia="admin",
        tipo=clave,
        titulo=f"Balance semanal · {periodo}",
        mensaje=(
            f"Hasta hoy se registraron {pedidos} pedido{'s' if pedidos != 1 else ''}, "
            f"{unidades} {'unidad' if unidades == 1 else 'unidades'} y {_importe_pesos(importe)} "
            "en ventas. Tocá este aviso para ver el detalle completo."
        ),
        enlace_url="/admin/analitica?periodo=semana",
    )
