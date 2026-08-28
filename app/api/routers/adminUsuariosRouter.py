from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Literal
from app.core.security import require_admin
from app.database.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth_schemas import UsuarioResponse

router=APIRouter(prefix="/api/admin/usuarios",tags=["Administración - Usuarios"],dependencies=[Depends(require_admin)])
class EstadoRequest(BaseModel): estado:str

@router.get("/pendientes",response_model=list[UsuarioResponse])
def pendientes(db:Session=Depends(get_db)):
    return list(db.scalars(select(Usuario).where(Usuario.rol=="cliente",Usuario.estado_registro=="pendiente").order_by(Usuario.creado_en.asc())).all())

@router.get("/",response_model=list[UsuarioResponse])
def listar_clientes(
    estado:Literal["pendiente","aprobado","rechazado"]|None=Query(default=None),
    db:Session=Depends(get_db),
):
    consulta=select(Usuario).where(Usuario.rol=="cliente")
    if estado:consulta=consulta.where(Usuario.estado_registro==estado)
    return list(db.scalars(consulta.order_by(Usuario.creado_en.desc())).all())

@router.patch("/{usuario_id}/estado",response_model=UsuarioResponse)
def cambiar_estado(usuario_id:int,data:EstadoRequest,db:Session=Depends(get_db)):
    if data.estado not in {"aprobado","rechazado"}:raise HTTPException(status_code=422,detail="Estado inválido.")
    usuario=db.get(Usuario,usuario_id)
    if usuario is None or usuario.rol=="admin":raise HTTPException(status_code=404,detail="Cliente no encontrado.")
    usuario.estado_registro=data.estado;db.commit();db.refresh(usuario);return usuario
