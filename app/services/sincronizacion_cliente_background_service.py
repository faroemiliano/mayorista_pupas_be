from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.sincronizacion_dux import SincronizacionDux
from app.services.admin_cliente_dux_service import sincronizar_clientes_dux


RECURSO = "clientes"


def _obtener(db: Session, bloquear: bool = False) -> SincronizacionDux:
    consulta = select(SincronizacionDux).where(SincronizacionDux.recurso == RECURSO)
    if bloquear:
        consulta = consulta.with_for_update()
    estado = db.scalar(consulta)
    if estado is None:
        estado = SincronizacionDux(recurso=RECURSO, estado="pendiente")
        db.add(estado)
        db.flush()
    return estado


def obtener_estado(db: Session) -> SincronizacionDux:
    estado = _obtener(db)
    db.commit()
    db.refresh(estado)
    return estado


def preparar_sincronizacion(db: Session) -> SincronizacionDux:
    estado = _obtener(db, bloquear=True)
    ahora = datetime.now(timezone.utc)
    sigue_activa = (
        estado.estado == "en_progreso"
        and estado.iniciada_en is not None
        and estado.iniciada_en > ahora - timedelta(hours=1)
    )
    if sigue_activa:
        raise ValueError("Ya hay una sincronización de clientes en curso.")
    estado.estado = "en_progreso"
    estado.procesados = estado.creados = estado.actualizados = 0
    estado.error = None
    estado.iniciada_en = ahora
    estado.finalizada_en = None
    db.commit()
    db.refresh(estado)
    return estado


def _guardar_progreso(procesados: int, creados: int, actualizados: int) -> None:
    with SessionLocal() as db:
        estado = _obtener(db)
        estado.procesados = procesados
        estado.creados = creados
        estado.actualizados = actualizados
        db.commit()


def ejecutar_sincronizacion_background() -> None:
    with SessionLocal() as db:
        try:
            resultado = sincronizar_clientes_dux(db, progreso=_guardar_progreso)
        except Exception as error:
            db.rollback()
            with SessionLocal() as estado_db:
                estado = _obtener(estado_db)
                estado.estado = "error"
                estado.error = str(error)[:2000]
                estado.finalizada_en = datetime.now(timezone.utc)
                estado_db.commit()
            return

    with SessionLocal() as db:
        estado = _obtener(db)
        estado.estado = "completada"
        estado.procesados = resultado["procesados"]
        estado.creados = resultado["creados"]
        estado.actualizados = resultado["actualizados"]
        estado.total_local = resultado["total_local"]
        estado.error = None
        estado.finalizada_en = datetime.now(timezone.utc)
        db.commit()
