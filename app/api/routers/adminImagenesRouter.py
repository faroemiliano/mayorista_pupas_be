from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_admin_total
from app.database.session import get_db
from app.services.diagnostico_imagenes_r2_service import (
    ejecutar_diagnostico_imagenes_r2_background,
    ejecutar_optimizacion_imagenes_r2_background,
    obtener_estado_diagnostico_imagenes_r2,
    obtener_estado_optimizacion_imagenes_r2,
    preparar_diagnostico_imagenes_r2,
    preparar_optimizacion_imagenes_r2,
)


router = APIRouter(
    prefix="/api/admin/imagenes",
    tags=["Administración - Imágenes"],
    dependencies=[Depends(require_admin_total)],
)


@router.get("/diagnostico-r2")
def diagnostico_r2(db: Session = Depends(get_db)):
    """Devuelve el estado o el informe del último análisis de sólo lectura."""
    return obtener_estado_diagnostico_imagenes_r2(db)


@router.post("/diagnostico-r2/ejecutar", status_code=status.HTTP_202_ACCEPTED)
def ejecutar_diagnostico_r2(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Inicia una auditoría asíncrona: no cambia URLs ni objetos de R2."""
    try:
        estado_actual = preparar_diagnostico_imagenes_r2(db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(502, "No se pudo iniciar el diagnóstico de imágenes.") from error
    background_tasks.add_task(ejecutar_diagnostico_imagenes_r2_background)
    return estado_actual


@router.get("/optimizacion-r2")
def estado_optimizacion_r2(db: Session = Depends(get_db)):
    return obtener_estado_optimizacion_imagenes_r2(db)


@router.post("/optimizacion-r2/ejecutar", status_code=status.HTTP_202_ACCEPTED)
def ejecutar_optimizacion_r2(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Optimiza las fotos pesadas del último informe, con confirmación de UI."""
    try:
        estado_actual = preparar_optimizacion_imagenes_r2(db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(502, "No se pudo iniciar la optimización de imágenes.") from error
    background_tasks.add_task(ejecutar_optimizacion_imagenes_r2_background)
    return estado_actual
