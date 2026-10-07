from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session
from typing import Literal
from app.core.security import require_admin
from app.database.session import get_db
from app.models.usuario import Usuario
from app.models.pedido import Pedido
from app.models.pedido_historico_wordpress import PedidoHistoricoWordpress, PedidoItemHistoricoWordpress
from app.schemas.auth_schemas import UsuarioResponse
from app.services.notificacion_service import notificar

router=APIRouter(prefix="/api/admin/usuarios",tags=["Administración - Usuarios"],dependencies=[Depends(require_admin)])
class EstadoRequest(BaseModel): estado:str


def _resumen_compras_tienda(db: Session, usuario_id: int, desde: datetime | None, hasta: datetime | None) -> dict:
    filtros = [Pedido.usuario_id == usuario_id, Pedido.estado != "cancelado"]
    if desde is not None: filtros.append(Pedido.creado_en >= desde)
    if hasta is not None: filtros.append(Pedido.creado_en < hasta)
    pedidos, unidades, importe = db.execute(select(
        func.count(Pedido.id),
        func.coalesce(func.sum(Pedido.cantidad_unidades), 0),
        func.coalesce(func.sum(Pedido.total), 0),
    ).where(*filtros)).one()
    return {"pedidos": int(pedidos or 0), "unidades": int(unidades or 0), "importe": Decimal(importe or 0)}


def _resumen_compras_wordpress(db: Session, usuario_id: int, desde: datetime | None, hasta: datetime | None) -> dict:
    filtros = [
        PedidoHistoricoWordpress.usuario_id == usuario_id,
        PedidoHistoricoWordpress.estado.not_in(("cancelled", "refunded", "failed")),
    ]
    if desde is not None: filtros.append(PedidoHistoricoWordpress.creado_en_wordpress >= desde)
    if hasta is not None: filtros.append(PedidoHistoricoWordpress.creado_en_wordpress < hasta)
    pedidos, importe = db.execute(select(
        func.count(PedidoHistoricoWordpress.id),
        func.coalesce(func.sum(PedidoHistoricoWordpress.total), 0),
    ).where(*filtros)).one()
    unidades = db.scalar(select(func.coalesce(func.sum(PedidoItemHistoricoWordpress.cantidad), 0)).join(
        PedidoHistoricoWordpress, PedidoHistoricoWordpress.id == PedidoItemHistoricoWordpress.pedido_id,
    ).where(*filtros)) or 0
    return {"pedidos": int(pedidos or 0), "unidades": int(unidades or 0), "importe": Decimal(importe or 0)}


def _combinar_resumenes(*resumenes: dict) -> dict:
    return {
        "pedidos": sum(item["pedidos"] for item in resumenes),
        "unidades": sum(item["unidades"] for item in resumenes),
        "importe": sum((item["importe"] for item in resumenes), Decimal("0")),
    }


@router.get("/paginados")
def listar_clientes_paginados(
    estado: Literal["pendiente", "aprobado", "rechazado"] | None = Query(default=None),
    cambio_clave: Literal["todos", "pendiente", "creada"] = Query(default="todos"),
    buscar: str | None = Query(default=None, max_length=150),
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
    if cambio_clave == "pendiente":
        filtros.append(Usuario.requiere_migracion_password.is_(True))
    elif cambio_clave == "creada":
        filtros.append(Usuario.requiere_migracion_password.is_(False))
    if buscar and (termino := buscar.strip()):
        patron = f"%{termino}%"
        filtros.append(or_(
            Usuario.nombre.ilike(patron), Usuario.apellido.ilike(patron),
            Usuario.email.ilike(patron), Usuario.telefono.ilike(patron),
            Usuario.documento.ilike(patron), Usuario.localidad_partido.ilike(patron),
            Usuario.provincia.ilike(patron), cast(Usuario.id, String).ilike(patron),
        ))
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


@router.get("/{usuario_id}/balance-compras")
def obtener_balance_compras_cliente(
    usuario_id: int,
    fecha_desde: date | None = Query(default=None),
    fecha_hasta: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.rol != "cliente":
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=422, detail="La fecha desde no puede ser posterior a la fecha hasta.")

    desde = datetime.combine(fecha_desde, time.min, timezone.utc) if fecha_desde else None
    hasta = datetime.combine(fecha_hasta + timedelta(days=1), time.min, timezone.utc) if fecha_hasta else None
    acumulado = _combinar_resumenes(
        _resumen_compras_tienda(db, usuario_id, None, None),
        _resumen_compras_wordpress(db, usuario_id, None, None),
    )
    periodo = _combinar_resumenes(
        _resumen_compras_tienda(db, usuario_id, desde, hasta),
        _resumen_compras_wordpress(db, usuario_id, desde, hasta),
    )
    return {
        "cliente_id": usuario.id,
        "cliente": f"{usuario.nombre} {usuario.apellido}".strip(),
        "acumulado": acumulado,
        "periodo": periodo,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "alcance": "Incluye pedidos de la tienda y el historial migrado de WordPress; excluye cancelados, reembolsados y fallidos.",
    }

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
