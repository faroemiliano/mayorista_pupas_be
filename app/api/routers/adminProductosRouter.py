from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.core.security import require_admin
from app.core.config import settings
from app.schemas.admin_producto_schemas import ProductoAnaliticaResponse
from app.services.admin_producto_service import get_analitica_productos_service
from app.schemas.admin_cliente_schemas import EstadoSincronizacionDuxResponse
from app.services.sincronizacion_catalogo_background_service import (
    ejecutar_sincronizacion_catalogo_background,
    obtener_estado_catalogo,
    preparar_sincronizacion_catalogo,
)
from app.services.stock_fuente_service import sumar_stock_fuente_activa


router = APIRouter(prefix="/api/admin/productos", tags=["Administración - Productos"], dependencies=[Depends(require_admin)])

class VisibilidadProductoRequest(BaseModel):
    visible: bool

class VisibilidadProductoResponse(BaseModel):
    id: int
    visible_tienda: bool

class CantidadTalleRequest(BaseModel):
    talle: str = Field(min_length=1, max_length=30)
    cantidad: int = Field(ge=0)

    @field_validator("talle", mode="before")
    @classmethod
    def normalizar_talle(cls, valor): return str(valor).strip()

class StockTallesRequest(BaseModel):
    talles: list[CantidadTalleRequest] = Field(min_length=1, max_length=30)

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
    return {"items":[{"id":p.id,"codigo":p.dux_codigo,"nombre":p.nombre,"stock_dux":int(sumar_stock_fuente_activa(p.stocks)),"origen":next((s.origen for s in p.stocks_talles),"sin_configurar"),"talles":{s.talle:s.cantidad for s in p.stocks_talles}} for p in productos],"total":total,"page":page,"limit":limit,"total_paginas":((total+limit-1)//limit if total else 0)}

@router.post("/{producto_id}/stock-talles")
def guardar_stock_talles(producto_id:int,data:StockTallesRequest,db:Session=Depends(get_db)):
    from app.models.producto import Producto
    from app.models.stock_talle_producto import StockTalleProducto
    from app.repositories.reserva_stock_repository import cantidades_reservadas_por_talle
    talles_limpios=[item.talle.strip() for item in data.talles]
    if any(not talle for talle in talles_limpios) or len(set(talles_limpios))!=len(talles_limpios):raise HTTPException(422,"Los talles deben ser únicos y no pueden estar vacíos.")
    producto=db.scalar(select(Producto).options(selectinload(Producto.stocks),selectinload(Producto.stocks_talles)).where(Producto.id==producto_id).with_for_update())
    if producto is None:raise HTTPException(404,"Producto no encontrado.")
    stock_dux=int(sumar_stock_fuente_activa(producto.stocks))
    if sum(item.cantidad for item in data.talles)>stock_dux:raise HTTPException(422,f"La suma por talles no puede superar el stock Dux ({stock_dux}).")
    reservadas=cantidades_reservadas_por_talle(db,{producto_id})
    existentes={item.talle:item for item in producto.stocks_talles}
    omitidos=set(existentes)-set(talles_limpios)
    for talle in omitidos:
        if reservadas.get((producto_id,talle),0)>0:raise HTTPException(422,f"El talle {talle} tiene unidades reservadas y no puede eliminarse.")
        db.delete(existentes[talle])
    for item,talle in zip(data.talles,talles_limpios):
        if item.cantidad<reservadas.get((producto_id,talle),0):raise HTTPException(422,f"El talle {talle} tiene unidades reservadas y no puede reducirse a esa cantidad.")
        fila=existentes.get(talle) or StockTalleProducto(producto_id=producto_id,talle=talle)
        fila.cantidad=item.cantidad;fila.origen="manual";db.add(fila)
    db.commit()
    return {"id":producto_id,"stock_dux":stock_dux,"total_distribuido":sum(item.cantidad for item in data.talles),"talles":{talle:item.cantidad for item,talle in zip(data.talles,talles_limpios)}}

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
    if not settings.DUX_SINCRONIZACION_HABILITADA:
        raise HTTPException(status_code=409, detail="La sincronización con Dux está pausada mientras la tienda funciona con la copia de WordPress.")
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
