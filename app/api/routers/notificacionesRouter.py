from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import es_administrador, require_admin, require_cliente
from app.database.session import get_db
from app.models.notificacion import Notificacion
from app.models.usuario import Usuario
from app.schemas.notificacion_schemas import (
    CampanaNotificacionRequest,
    CampanaNotificacionResponse,
    NotificacionResponse,
    NotificacionesResponse,
)
from app.services.notificacion_service import crear_campana


router=APIRouter(prefix="/api/notificaciones",tags=["Notificaciones"])

def _listar(db:Session,condicion)->dict:
    items=list(db.scalars(select(Notificacion).where(condicion).order_by(Notificacion.creada_en.desc()).limit(50)).all())
    no_leidas=db.scalar(select(func.count()).select_from(Notificacion).where(condicion,Notificacion.leida.is_(False))) or 0
    return {"items":items,"no_leidas":no_leidas}

@router.get("/mias",response_model=NotificacionesResponse)
def mias(db:Session=Depends(get_db),usuario:Usuario=Depends(require_cliente)):
    return _listar(db,Notificacion.usuario_id==usuario.id)

@router.get("/admin",response_model=NotificacionesResponse)
def admin(db:Session=Depends(get_db),usuario:Usuario=Depends(require_admin)):
    return _listar(db,Notificacion.audiencia=="admin")


@router.post(
    "/admin/campanas",
    response_model=CampanaNotificacionResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_campana_admin(
    data: CampanaNotificacionRequest,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_admin),
):
    del usuario
    try:
        creadas, emails, ids = crear_campana(
            db,
            tipo=data.tipo,
            titulo=data.titulo,
            mensaje=data.mensaje,
            destinatarios=data.destinatarios,
            usuario_ids=data.usuario_ids,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"notificaciones_creadas": creadas, "emails_programados": emails}

@router.patch("/{notificacion_id}/leer",response_model=NotificacionResponse)
def leer(notificacion_id:int,db:Session=Depends(get_db),usuario:Usuario=Depends(require_cliente)):
    item=db.get(Notificacion,notificacion_id)
    permitida=item is not None and (item.usuario_id==usuario.id or (es_administrador(usuario) and item.audiencia=="admin"))
    if not permitida:raise HTTPException(status_code=404,detail="Notificación no encontrada.")
    item.leida=True;db.commit();db.refresh(item);return item
