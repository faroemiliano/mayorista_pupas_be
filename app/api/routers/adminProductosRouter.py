from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.core.security import require_admin
from app.schemas.admin_producto_schemas import ProductoAnaliticaResponse
from app.services.admin_producto_service import get_analitica_productos_service
from app.schemas.admin_cliente_schemas import EstadoSincronizacionDuxResponse
from app.services.sincronizacion_catalogo_background_service import (
    ejecutar_sincronizacion_catalogo_background,
    obtener_estado_catalogo,
    preparar_sincronizacion_catalogo,
)


router = APIRouter(prefix="/api/admin/productos", tags=["Administración - Productos"], dependencies=[Depends(require_admin)])

class VisibilidadProductoRequest(BaseModel):
    visible: bool

class VisibilidadProductoResponse(BaseModel):
    id: int
    visible_tienda: bool

class CantidadTalleRequest(BaseModel):
    talle: int = Field(ge=1, le=5)
    cantidad: int = Field(ge=0)

class StockTallesRequest(BaseModel):
    talles: list[CantidadTalleRequest] = Field(min_length=5, max_length=5)

@router.get("/stock-talles")
def listar_stock_talles(buscar:str|None=None,page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),db:Session=Depends(get_db)):
    from app.models.producto import Producto
    query=select(Producto).options(selectinload(Producto.stocks),selectinload(Producto.stocks_talles))
    count=select(func.count(Producto.id))
    if buscar and buscar.strip():
        filtro=or_(Producto.nombre.ilike(f"%{buscar.strip()}%"),Producto.dux_codigo.ilike(f"%{buscar.strip()}%"))
        query=query.where(filtro);count=count.where(filtro)
    total=db.scalar(count) or 0
    productos=db.scalars(query.order_by(Producto.nombre,Producto.id).offset((page-1)*limit).limit(limit)).all()
    return {"items":[{"id":p.id,"codigo":p.dux_codigo,"nombre":p.nombre,"stock_dux":int(sum(s.stock_disponible for s in p.stocks)),"origen":next((s.origen for s in p.stocks_talles),"sin_configurar"),"talles":{str(i):next((s.cantidad for s in p.stocks_talles if s.talle==i),0) for i in range(1,6)}} for p in productos],"total":total,"page":page,"limit":limit,"total_paginas":((total+limit-1)//limit if total else 0)}

@router.post("/{producto_id}/stock-talles")
def guardar_stock_talles(producto_id:int,data:StockTallesRequest,db:Session=Depends(get_db)):
    from app.models.producto import Producto
    from app.models.stock_talle_producto import StockTalleProducto
    from app.repositories.reserva_stock_repository import cantidades_reservadas_por_talle
    if {item.talle for item in data.talles}!={1,2,3,4,5}:raise HTTPException(422,"Deben informarse una vez los talles del 1 al 5.")
    producto=db.scalar(select(Producto).options(selectinload(Producto.stocks),selectinload(Producto.stocks_talles)).where(Producto.id==producto_id).with_for_update())
    if producto is None:raise HTTPException(404,"Producto no encontrado.")
    stock_dux=int(sum(s.stock_disponible for s in producto.stocks))
    if sum(item.cantidad for item in data.talles)>stock_dux:raise HTTPException(422,f"La suma por talles no puede superar el stock Dux ({stock_dux}).")
    reservadas=cantidades_reservadas_por_talle(db,{producto_id})
    existentes={item.talle:item for item in producto.stocks_talles}
    for item in data.talles:
        if item.cantidad<reservadas.get((producto_id,item.talle),0):raise HTTPException(422,f"El talle {item.talle} tiene unidades reservadas y no puede reducirse a esa cantidad.")
        fila=existentes.get(item.talle) or StockTalleProducto(producto_id=producto_id,talle=item.talle)
        fila.cantidad=item.cantidad;fila.origen="manual";db.add(fila)
    db.commit()
    return {"id":producto_id,"stock_dux":stock_dux,"total_distribuido":sum(item.cantidad for item in data.talles),"talles":{str(item.talle):item.cantidad for item in data.talles}}

@router.patch("/{producto_id}/visibilidad",response_model=VisibilidadProductoResponse)
def cambiar_visibilidad(producto_id:int,data:VisibilidadProductoRequest,db:Session=Depends(get_db)):
    from app.models.producto import Producto
    producto=db.get(Producto,producto_id)
    if producto is None:raise HTTPException(status_code=404,detail="Producto no encontrado.")
    producto.visible_tienda=data.visible;db.commit();db.refresh(producto)
    return producto


@router.get("/sincronizacion", response_model=EstadoSincronizacionDuxResponse)
def estado_sincronizacion_catalogo(db: Session = Depends(get_db)):
    return obtener_estado_catalogo(db)


@router.post(
    "/sincronizar",
    response_model=EstadoSincronizacionDuxResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sincronizar_catalogo(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        estado = preparar_sincronizacion_catalogo(db)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    background_tasks.add_task(ejecutar_sincronizacion_catalogo_background)
    return estado


@router.get("/analitica", response_model=ProductoAnaliticaResponse)
def obtener_analitica_productos(
    dias: int = Query(default=30, ge=0, le=3650),
    limit: int = Query(default=10, ge=1, le=50),
    agrupacion: str = Query(default="dia", pattern="^(dia|semana|mes|anio)$"),
    db: Session = Depends(get_db),
):
    return get_analitica_productos_service(db, None if dias == 0 else dias, limit, agrupacion)
