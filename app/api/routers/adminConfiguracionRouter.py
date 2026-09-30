from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import require_admin
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services.auditoria_stock_dux_background_service import (
    ejecutar_auditoria_stock_dux_background,
    obtener_auditoria_stock_dux,
    preparar_auditoria_stock_dux,
)


router = APIRouter(
    prefix="/api/admin/configuracion",
    tags=["Administración - Configuración"],
    dependencies=[Depends(require_admin)],
)


class EstadoDuxResponse(BaseModel):
    escritura_habilitada: bool
    sincronizacion_habilitada: bool
    modo: str


class ModoDuxRequest(BaseModel):
    habilitado: bool


@router.get("/dux", response_model=EstadoDuxResponse)
def estado_dux():
    escritura_habilitada = settings.DUX_ESCRITURA_HABILITADA
    sincronizacion_habilitada = settings.DUX_SINCRONIZACION_HABILITADA
    return {
        "escritura_habilitada": escritura_habilitada,
        "sincronizacion_habilitada": sincronizacion_habilitada,
        "modo": "produccion" if sincronizacion_habilitada else "wordpress",
    }


@router.patch("/dux/modo", response_model=EstadoDuxResponse)
def cambiar_modo_dux(data: ModoDuxRequest):
    settings.DUX_SINCRONIZACION_HABILITADA = data.habilitado
    return estado_dux()


@router.get("/dux/auditoria-stock")
def obtener_auditoria_stock(db: Session = Depends(get_db)):
    return obtener_auditoria_stock_dux(db)


@router.post("/dux/comparar-stock", status_code=status.HTTP_202_ACCEPTED)
def comparar_stock(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        estado_actual = preparar_auditoria_stock_dux(db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    background_tasks.add_task(
        ejecutar_auditoria_stock_dux_background,
        estado_actual["ejecucion_id"],
    )
    return estado_actual
