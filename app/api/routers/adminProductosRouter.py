import base64
import binascii
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from slugify import slugify
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database.session import get_db
from app.core.security import require_admin, require_admin_total
from app.core.config import settings
from app.schemas.admin_producto_schemas import ProductoAnaliticaResponse
from app.models.producto import Producto
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

class DestacadoProductoRequest(BaseModel):
    destacado: bool

class DestacadoProductoResponse(BaseModel):
    id: int
    destacado: bool
    orden_destacado: int | None

class CantidadTalleRequest(BaseModel):
    talle: str = Field(min_length=1, max_length=30)
    cantidad: int = Field(ge=0)

    @field_validator("talle", mode="before")
    @classmethod
    def normalizar_talle(cls, valor): return str(valor).strip()

class StockTallesRequest(BaseModel):
    talles: list[CantidadTalleRequest] = Field(min_length=1, max_length=30)

class ProductoAdminRequest(BaseModel):
    codigo: str = Field(default="", max_length=100)
    nombre: str = Field(min_length=2, max_length=200)
    descripcion: str | None = Field(default=None, max_length=10000)
    categoria_id: int | None = Field(default=None, gt=0)
    subcategoria_id: int | None = Field(default=None, gt=0)
    marca_id: int | None = Field(default=None, gt=0)
    precio_mayorista: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    precio_24_productos: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    cantidad_unidades_por_bulto: Decimal | None = Field(default=None, ge=0)
    talles: list[CantidadTalleRequest] = Field(min_length=1, max_length=30)
    habilitado: bool = True
    visible_tienda: bool = True

    @field_validator("codigo", "nombre", mode="before")
    @classmethod
    def limpiar_texto(cls, valor): return str(valor or "").strip()

    @model_validator(mode="after")
    def validar_talles(self):
        nombres=[item.talle.casefold() for item in self.talles]
        if len(nombres) != len(set(nombres)): raise ValueError("Los talles deben ser únicos.")
        return self

class ImagenProductoAdminRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=180)
    media_type: str = Field(pattern=r"^image/(jpeg|png|webp|gif)$")
    contenido_base64: str = Field(min_length=4)
    principal: bool = False

def _slug_producto(db:Session,nombre:str,producto_id:int|None=None)->str:
    base=slugify(nombre) or "producto"; candidato=base; numero=2
    while (existente:=db.scalar(select(Producto.id).where(Producto.slug==candidato))) is not None and existente!=producto_id:
        candidato=f"{base}-{numero}";numero+=1
    return candidato

def _guardar_producto(db:Session,producto,data:ProductoAdminRequest):
    from app.models.categoria import Categoria
    from app.models.marca import Marca
    from app.models.precio_producto import PrecioProducto
    from app.models.stock_producto import StockProducto
    from app.models.stock_talle_producto import StockTalleProducto
    from app.models.subcategoria import Subcategoria
    from app.repositories.reserva_stock_repository import cantidades_reservadas_por_talle
    categoria=db.get(Categoria,data.categoria_id) if data.categoria_id else None
    subcategoria=db.get(Subcategoria,data.subcategoria_id) if data.subcategoria_id else None
    marca=db.get(Marca,data.marca_id) if data.marca_id else None
    if data.categoria_id and categoria is None: raise HTTPException(422,"La categoría seleccionada no existe.")
    if data.subcategoria_id and (subcategoria is None or subcategoria.categoria_id!=data.categoria_id): raise HTTPException(422,"La subcategoría no pertenece a la categoría seleccionada.")
    if data.marca_id and marca is None: raise HTTPException(422,"La marca seleccionada no existe.")
    if data.codigo:
        producto.dux_codigo=data.codigo
        producto.codigo_externo=data.codigo
    producto.nombre=data.nombre
    producto.slug=_slug_producto(db,data.nombre,getattr(producto,'id',None));producto.descripcion=data.descripcion or None
    producto.categoria=categoria;producto.subcategoria=subcategoria;producto.marca=marca
    producto.cantidad_unidades_por_bulto=data.cantidad_unidades_por_bulto
    producto.habilitado=data.habilitado;producto.visible_tienda=data.visible_tienda
    precios={p.dux_id_lista:p for p in producto.precios}
    for lista_id,nombre,valor in ((settings.DUX_LISTA_PRECIO_MAYORISTA_ID,"Mayorista web",data.precio_mayorista),(settings.DUX_LISTA_PRECIO_24_ID,"24 productos web",data.precio_24_productos or data.precio_mayorista)):
        precio=precios.get(lista_id) or PrecioProducto(dux_id_lista=lista_id,nombre_lista=nombre)
        precio.precio=valor;producto.precios.append(precio) if precio not in producto.precios else None
    total=sum(item.cantidad for item in data.talles)
    manual=next((s for s in producto.stocks if s.dux_id_deposito==-1 and s.dux_id_det_item is None),None)
    if manual is None:
        manual=StockProducto(dux_id_deposito=-1,nombre_deposito="Stock web",stock_real=0,stock_reservado=0,stock_disponible=0)
        producto.stocks.append(manual)
    manual.stock_real=total;manual.stock_disponible=total
    reservadas=cantidades_reservadas_por_talle(db,{producto.id}) if getattr(producto,'id',None) else {}
    actuales={item.talle.casefold():item for item in producto.stocks_talles}
    enviados={item.talle.casefold() for item in data.talles}
    for clave,item in actuales.items():
        if clave not in enviados:
            if reservadas.get((producto.id,item.talle),0): raise HTTPException(422,f"El talle {item.talle} tiene reservas y no puede eliminarse.")
            db.delete(item)
    for item in data.talles:
        fila=actuales.get(item.talle.casefold()) or StockTalleProducto(talle=item.talle,origen="web")
        if getattr(producto,'id',None) and item.cantidad<reservadas.get((producto.id,fila.talle),0): raise HTTPException(422,f"El talle {fila.talle} tiene más unidades reservadas.")
        fila.talle=item.talle;fila.cantidad=item.cantidad;fila.origen="web"
        if fila not in producto.stocks_talles: producto.stocks_talles.append(fila)
    return producto

@router.post("/",status_code=201)
def crear_producto(data:ProductoAdminRequest,db:Session=Depends(get_db)):
    from app.models.producto import Producto
    if data.codigo and db.scalar(select(Producto.id).where(Producto.dux_codigo==data.codigo)): raise HTTPException(409,"Ya existe un producto con ese código.")
    producto=Producto(dux_codigo=f"WEB-TEMP-{uuid4().hex}",nombre=data.nombre,slug="temporal",origen="web",conciliacion_estado="pendiente")
    db.add(producto);db.flush()
    if not data.codigo:
        producto.dux_codigo=f"WEB-{producto.id}"
    _guardar_producto(db,producto,data);db.commit();db.refresh(producto)
    return {"id":producto.id,"mensaje":"Producto creado correctamente."}

@router.put("/{producto_id}")
def editar_producto(producto_id:int,data:ProductoAdminRequest,db:Session=Depends(get_db)):
    from app.models.producto import Producto
    producto=db.scalar(select(Producto).options(selectinload(Producto.precios),selectinload(Producto.stocks),selectinload(Producto.stocks_talles)).where(Producto.id==producto_id).with_for_update())
    if producto is None: raise HTTPException(404,"Producto no encontrado.")
    if data.codigo and db.scalar(select(Producto.id).where(Producto.dux_codigo==data.codigo,Producto.id!=producto_id)): raise HTTPException(409,"Ya existe otro producto con ese código.")
    _guardar_producto(db,producto,data);db.commit()
    return {"id":producto.id,"mensaje":"Producto actualizado correctamente."}

@router.post("/{producto_id}/imagenes",status_code=201)
def agregar_imagen(producto_id:int,data:ImagenProductoAdminRequest,db:Session=Depends(get_db)):
    from app.models.imagen_producto import ImagenProducto
    from app.models.producto import Producto
    producto=db.scalar(select(Producto).options(selectinload(Producto.imagenes)).where(Producto.id==producto_id))
    if producto is None: raise HTTPException(404,"Producto no encontrado.")
    try: contenido=base64.b64decode(data.contenido_base64,validate=True)
    except (binascii.Error,ValueError) as error: raise HTTPException(422,"La imagen enviada no es válida.") from error
    if len(contenido)>8*1024*1024: raise HTTPException(413,"Cada imagen puede pesar hasta 8 MB.")
    firmas={"image/jpeg":contenido.startswith(b'\xff\xd8\xff'),"image/png":contenido.startswith(b'\x89PNG\r\n\x1a\n'),"image/webp":contenido.startswith(b'RIFF') and contenido[8:12]==b'WEBP',"image/gif":contenido.startswith((b'GIF87a',b'GIF89a'))}
    if not firmas.get(data.media_type,False): raise HTTPException(422,"El contenido no coincide con el formato de la imagen.")
    orden=max((i.orden for i in producto.imagenes),default=-1)+1
    principal=data.principal or not producto.imagenes
    if principal:
        for anterior in producto.imagenes: anterior.principal=False
    imagen=ImagenProducto(producto_id=producto_id,url="pendiente",contenido=contenido,media_type=data.media_type,orden=orden,principal=principal)
    db.add(imagen);db.flush();imagen.url=f"db:{imagen.id}"
    if principal: producto.imagen_url=imagen.url
    db.commit();db.refresh(imagen)
    return {"id":imagen.id,"url":imagen.url,"orden":imagen.orden,"principal":imagen.principal}

@router.patch("/{producto_id}/imagenes/{imagen_id}/principal")
def elegir_imagen_principal(producto_id:int,imagen_id:int,db:Session=Depends(get_db)):
    from app.models.imagen_producto import ImagenProducto
    from app.models.producto import Producto
    producto=db.scalar(select(Producto).options(selectinload(Producto.imagenes)).where(Producto.id==producto_id))
    imagen=next((i for i in producto.imagenes if i.id==imagen_id),None) if producto else None
    if imagen is None: raise HTTPException(404,"Imagen no encontrada.")
    for item in producto.imagenes:item.principal=item.id==imagen_id
    producto.imagen_url=imagen.url;db.commit();return {"id":imagen.id,"principal":True}

@router.delete("/{producto_id}/imagenes/{imagen_id}",status_code=204)
def eliminar_imagen(producto_id:int,imagen_id:int,db:Session=Depends(get_db)):
    from app.models.imagen_producto import ImagenProducto
    from app.models.producto import Producto
    producto=db.scalar(select(Producto).options(selectinload(Producto.imagenes)).where(Producto.id==producto_id))
    imagen=next((i for i in producto.imagenes if i.id==imagen_id),None) if producto else None
    if imagen is None: raise HTTPException(404,"Imagen no encontrada.")
    era_principal=imagen.principal;db.delete(imagen);db.flush()
    restantes=[i for i in producto.imagenes if i.id!=imagen_id]
    if era_principal:
        siguiente=restantes[0] if restantes else None
        if siguiente:siguiente.principal=True
        producto.imagen_url=siguiente.url if siguiente else None
    db.commit()

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

@router.patch("/{producto_id}/destacado", response_model=DestacadoProductoResponse)
def cambiar_destacado(producto_id: int, data: DestacadoProductoRequest, db: Session = Depends(get_db)):
    producto = db.scalar(select(Producto).where(Producto.id == producto_id).with_for_update())
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    if data.destacado and not producto.destacado:
        destacados = db.scalars(
            select(Producto).where(Producto.destacado.is_(True)).with_for_update()
        ).all()
        if len(destacados) >= 4:
            raise HTTPException(422, "Podés tener hasta 4 productos destacados. Quitá uno antes de agregar otro.")
        producto.destacado = True
        producto.orden_destacado = max((item.orden_destacado or 0 for item in destacados), default=0) + 1
    elif not data.destacado:
        producto.destacado = False
        producto.orden_destacado = None
    db.commit()
    db.refresh(producto)
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
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin_total),
):
    if (fecha_desde is None) != (fecha_hasta is None):
        raise HTTPException(422, "Indicá ambas fechas para comparar un período.")
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(422, "La fecha inicial no puede ser posterior a la final.")
    return get_analitica_productos_service(
        db, None if dias == 0 else dias, limit, agrupacion, fecha_desde, fecha_hasta,
    )
