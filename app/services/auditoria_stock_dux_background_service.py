from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.dux_sync_service import comparar_stock_dux
from app.services.migracion_woocommerce_service import _guardar


TIPO = "auditoria_stock_dux"
ID_EXTERNO = "catalogo"


def _fila_auditoria(db, bloquear: bool = False):
    consulta = select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO,
        MigracionWooCommerce.id_externo == ID_EXTERNO,
    )
    if bloquear:
        consulta = consulta.with_for_update()
    return db.scalar(consulta)


def obtener_auditoria_stock_dux(db) -> dict:
    fila = _fila_auditoria(db)
    if fila is None:
        return {
            "estado": "pendiente",
            "resultado": None,
            "error": None,
            "iniciada_en": None,
            "finalizada_en": None,
        }
    return dict(fila.datos)


def preparar_auditoria_stock_dux(db) -> dict:
    fila = _fila_auditoria(db, bloquear=True)
    actual = dict(fila.datos) if fila is not None else {
        "estado": "pendiente",
        "iniciada_en": None,
    }
    iniciada_en = actual.get("iniciada_en")
    inicio = datetime.fromisoformat(iniciada_en) if iniciada_en else None
    if inicio is not None and inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if (
        actual.get("estado") == "en_progreso"
        and inicio is not None
        and inicio > datetime.now(timezone.utc) - timedelta(hours=1)
    ):
        raise ValueError("Ya hay una auditoría de stock Dux en curso.")

    datos = {
        "estado": "en_progreso",
        "ejecucion_id": uuid4().hex,
        "resultado": None,
        "error": None,
        "iniciada_en": datetime.now(timezone.utc).isoformat(),
        "finalizada_en": None,
    }
    _guardar(db, TIPO, ID_EXTERNO, datos)
    return datos


def _guardar_si_es_ejecucion_actual(db, ejecucion_id: str, datos: dict) -> bool:
    fila = _fila_auditoria(db)
    if fila is None or fila.datos.get("ejecucion_id") != ejecucion_id:
        return False
    _guardar(db, TIPO, ID_EXTERNO, datos)
    return True


def ejecutar_auditoria_stock_dux_background(ejecucion_id: str) -> None:
    try:
        with SessionLocal() as db:
            actual = obtener_auditoria_stock_dux(db)
            if actual.get("ejecucion_id") != ejecucion_id:
                return
            resultado = comparar_stock_dux(db)
    except Exception as error:
        with SessionLocal() as db:
            actual = obtener_auditoria_stock_dux(db)
            _guardar_si_es_ejecucion_actual(db, ejecucion_id, {
                **actual,
                "estado": "error",
                "resultado": None,
                "error": str(error)[:2000],
                "finalizada_en": datetime.now(timezone.utc).isoformat(),
            })
        return

    with SessionLocal() as db:
        actual = obtener_auditoria_stock_dux(db)
        _guardar_si_es_ejecucion_actual(db, ejecucion_id, {
            **actual,
            "estado": "completada",
            "resultado": resultado,
            "error": None,
            "finalizada_en": datetime.now(timezone.utc).isoformat(),
        })
