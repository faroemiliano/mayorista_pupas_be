from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.services.conciliacion_productos_service import (
    aplicar_coincidencias_seguras,
    generar_conciliacion,
)
from app.services.migracion_woocommerce_service import _guardar


TIPO_ESTADO = "estado_conciliacion"
ID_ESTADO = "productos-wordpress-dux"
TIEMPO_EJECUCION_ACTIVA = timedelta(hours=1)


def _fila_estado(db: Session, *, bloquear: bool = False) -> MigracionWooCommerce | None:
    consulta = select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == TIPO_ESTADO,
        MigracionWooCommerce.id_externo == ID_ESTADO,
    )
    if bloquear:
        consulta = consulta.with_for_update()
    return db.scalar(consulta)


def _estado(db: Session, **cambios) -> dict:
    fila = _fila_estado(db)
    datos = dict(fila.datos) if fila else {}
    datos.update(cambios)
    _guardar(db, TIPO_ESTADO, ID_ESTADO, datos)
    return datos


def _fecha_utc(fecha: datetime | None) -> datetime | None:
    if fecha is None:
        return None
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


def _ejecucion_sigue_activa(fila: MigracionWooCommerce | None) -> bool:
    if fila is None or fila.datos.get("estado") != "en_progreso":
        return False
    actualizado_en = _fecha_utc(fila.actualizado_en)
    return bool(
        actualizado_en
        and datetime.now(timezone.utc) - actualizado_en < TIEMPO_EJECUCION_ACTIVA
    )


def obtener_estado_conciliacion(db: Session) -> dict:
    fila = _fila_estado(db)
    if fila is None:
        return {
            "estado": "pendiente",
            "accion": None,
            "etapa": None,
            "progreso": None,
            "resultado": None,
            "error": None,
            "actualizado_en": None,
        }
    datos = dict(fila.datos)
    datos["actualizado_en"] = (
        fila.actualizado_en.isoformat() if fila.actualizado_en else None
    )
    return datos


def preparar_generacion_conciliacion(db: Session) -> dict:
    cantidad_productos = db.scalar(
        select(func.count(MigracionWooCommerce.id)).where(
            MigracionWooCommerce.tipo == "producto"
        )
    ) or 0
    if cantidad_productos == 0:
        raise ValueError(
            "No hay productos de WordPress importados para conciliar."
        )

    fila = _fila_estado(db, bloquear=True)
    if _ejecucion_sigue_activa(fila):
        raise ValueError("La conciliación de productos ya está en progreso.")

    ejecucion_id = uuid4().hex
    return _estado(
        db,
        estado="en_progreso",
        accion="generar",
        etapa="preparando",
        progreso={"procesados": 0, "total": None},
        resultado=None,
        error=None,
        ejecucion_id=ejecucion_id,
        iniciada_en=datetime.now(timezone.utc).isoformat(),
        finalizada_en=None,
    )


def _actualizar_ejecucion(db: Session, ejecucion_id: str, **cambios) -> dict | None:
    fila = _fila_estado(db)
    if fila is None or fila.datos.get("ejecucion_id") != ejecucion_id:
        return None
    return _estado(db, **cambios)


def ejecutar_generacion_conciliacion_background(ejecucion_id: str) -> None:
    with SessionLocal() as db:
        try:
            if _actualizar_ejecucion(
                db,
                ejecucion_id,
                etapa="consultando_dux",
            ) is None:
                return

            def guardar_progreso(procesados: int, total: int) -> None:
                if _actualizar_ejecucion(
                    db,
                    ejecucion_id,
                    progreso={"procesados": procesados, "total": total},
                ) is None:
                    raise RuntimeError(
                        "La ejecución de conciliación fue reemplazada por otra más reciente."
                    )

            resultado = generar_conciliacion(db, progreso=guardar_progreso)
            _actualizar_ejecucion(
                db,
                ejecucion_id,
                estado="completada",
                etapa="finalizada",
                progreso=None,
                resultado={"totales": resultado.get("totales", {})},
                error=None,
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as error:
            db.rollback()
            _actualizar_ejecucion(
                db,
                ejecucion_id,
                estado="error",
                etapa="error",
                progreso=None,
                error=str(error)[:2000],
                finalizada_en=datetime.now(timezone.utc).isoformat(),
            )


def aplicar_coincidencias_seguras_con_estado(db: Session) -> dict:
    fila = _fila_estado(db, bloquear=True)
    if _ejecucion_sigue_activa(fila):
        raise ValueError(
            "No se pueden aplicar coincidencias mientras la conciliación está en progreso."
        )

    ejecucion_id = uuid4().hex
    _estado(
        db,
        estado="en_progreso",
        accion="aplicar",
        etapa="aplicando_coincidencias",
        progreso=None,
        error=None,
        ejecucion_id=ejecucion_id,
        iniciada_en=datetime.now(timezone.utc).isoformat(),
        finalizada_en=None,
    )
    try:
        resultado = aplicar_coincidencias_seguras(db)
    except Exception as error:
        db.rollback()
        _actualizar_ejecucion(
            db,
            ejecucion_id,
            estado="error",
            etapa="error",
            error=str(error)[:2000],
            finalizada_en=datetime.now(timezone.utc).isoformat(),
        )
        raise

    _actualizar_ejecucion(
        db,
        ejecucion_id,
        estado="completada",
        etapa="finalizada",
        resultado={"aplicacion": resultado},
        error=None,
        finalizada_en=datetime.now(timezone.utc).isoformat(),
    )
    return resultado
