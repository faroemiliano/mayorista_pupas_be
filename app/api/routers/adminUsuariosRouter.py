from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typing import Literal
from app.core.security import require_admin
from app.database.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth_schemas import UsuarioResponse
from app.services.notificacion_service import notificar

router=APIRouter(prefix="/api/admin/usuarios",tags=["Administración - Usuarios"],dependencies=[Depends(require_admin)])
class EstadoRequest(BaseModel): estado:str


@router.get("/paginados")
def listar_clientes_paginados(
    estado: Literal["pendiente", "aprobado", "rechazado"] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    base = Usuario.rol == "cliente"
    estados = {"pendiente": 0, "aprobado": 0, "rechazado": 0}
    for estado_registro, cantidad in db.execute(
        select(Usuario.estado_registro, func.count(Usuario.id))
        .where(base)
        .group_by(Usuario.estado_registro)
    ):
        if estado_registro in estados:
            estados[estado_registro] = cantidad

    filtros = [base]
    if estado:
        filtros.append(Usuario.estado_registro == estado)
    total = db.scalar(select(func.count(Usuario.id)).where(*filtros)) or 0
    items = list(db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.creado_en.desc(), Usuario.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all())
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_paginas": (total + limit - 1) // limit if total else 0,
        "totales_estado": estados,
    }

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
    usuario.estado_registro=data.estado;db.commit();db.refresh(usuario)
    titulo="Tu cuenta mayorista fue aprobada" if data.estado=="aprobado" else "Actualización de tu solicitud mayorista"
    mensaje="Ya podés ingresar, ver precios y realizar pedidos." if data.estado=="aprobado" else "Tu solicitud fue rechazada. Contactate con la empresa si necesitás más información."
    notificar(db,audiencia="cliente",tipo=f"registro_{data.estado}",titulo=titulo,mensaje=mensaje,usuario_id=usuario.id,email=usuario.email,enviar_email=False)
    return usuario
