from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.sincronizacion_dux import SincronizacionDux
from app.services.dux_sync_service import sincronizar_catalogo_dux


RECURSO = "catalogo"


def _obtener(db: Session, bloquear: bool = False) -> SincronizacionDux:
    consulta = select(SincronizacionDux).where(
        SincronizacionDux.recurso == RECURSO
    )
    if bloquear:
        consulta = consulta.with_for_update()
    estado = db.scalar(consulta)
    if estado is None:
        estado = SincronizacionDux(recurso=RECURSO, estado="pendiente")
        db.add(estado)
        db.flush()
    return estado


def obtener_estado_catalogo(db: Session) -> SincronizacionDux:
    estado = _obtener(db)
    db.commit()
    db.refresh(estado)
    return estado


def preparar_sincronizacion_catalogo(db: Session) -> SincronizacionDux:
    estado = _obtener(db, bloquear=True)
    ahora = datetime.now(timezone.utc)
    sigue_activa = (
        estado.estado == "en_progreso"
        and estado.iniciada_en is not None
        and estado.iniciada_en > ahora - timedelta(hours=1)
    )
    if sigue_activa:
        raise ValueError("Ya hay una sincronización del catálogo en curso.")
    estado.estado = "en_progreso"
    estado.procesados = estado.creados = estado.actualizados = 0
    estado.total_local = 0
    estado.error = None
    estado.iniciada_en = ahora
    estado.finalizada_en = None
    db.commit()
    db.refresh(estado)
    return estado


def ejecutar_sincronizacion_catalogo_background() -> None:
    try:
        with SessionLocal() as db:
            resultado = sincronizar_catalogo_dux(db)
    except Exception as error:
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
        estado.total_local = resultado["procesados"]
        estado.error = None
        estado.finalizada_en = datetime.now(timezone.utc)
        db.commit()
