from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.database.session import get_db
from app.models.migracion_woocommerce import MigracionWooCommerce
from app.models.producto import Producto
from app.services.conciliacion_productos_service import vincular_coincidencia_manual


router = APIRouter(
    prefix="/api/admin/migracion-wordpress",
    tags=["Administración - Migración WordPress"],
    dependencies=[Depends(require_admin)],
)


class VincularProductoRequest(BaseModel):
    wordpress_id: int = Field(gt=0)
    dux_codigo: str = Field(min_length=1, max_length=100)


def _texto(valor) -> str | None:
    if valor is None or valor == "":
        return None
    return str(valor)


def _resumir_producto(datos: dict) -> dict:
    variaciones = datos.get("_variaciones_completas") or []
    talles: list[str] = []
    stock_total = 0
    precios: set[str] = set()
    for variacion in variaciones:
        stock_total += int(variacion.get("stock_quantity") or 0)
        precio = _texto(variacion.get("price"))
        if precio:
            precios.add(precio)
        for atributo in variacion.get("attributes") or []:
            opcion = _texto(atributo.get("option"))
            if opcion and opcion not in talles:
                talles.append(opcion)
    imagenes = datos.get("images") or []
    return {
        "id": str(datos.get("id", "")),
        "nombre": datos.get("name") or "Producto sin nombre",
        "estado": datos.get("status"),
        "tipo": datos.get("type"),
        "precio": _texto(datos.get("price")),
        "precios_variaciones": sorted(precios),
        "cantidad_variaciones": len(variaciones),
        "talles": talles,
        "stock_total": stock_total,
        "imagen": imagenes[0].get("src") if imagenes else None,
    }


def _resumir_cliente(datos: dict) -> dict:
    facturacion = datos.get("billing") or {}
    return {
        "id": str(datos.get("id", "")),
        "email": datos.get("email"),
        "nombre": " ".join(filter(None, [datos.get("first_name"), datos.get("last_name")])).strip(),
        "telefono": facturacion.get("phone"),
        "localidad": facturacion.get("city"),
        "provincia": facturacion.get("state"),
        "tiene_direccion": bool(facturacion.get("address_1")),
        "creado_en": datos.get("date_created"),
    }


def _resumir_pedido(datos: dict) -> dict:
    items = datos.get("line_items") or []
    return {
        "id": str(datos.get("id", "")),
        "numero": _texto(datos.get("number")),
        "estado": datos.get("status"),
        "fecha": datos.get("date_created"),
        "cliente_id": _texto(datos.get("customer_id")),
        "total": _texto(datos.get("total")),
        "moneda": datos.get("currency"),
        "cantidad_items": len(items),
        "cantidad_unidades": sum(int(item.get("quantity") or 0) for item in items),
    }


@router.get("/resumen")
def obtener_resumen(db: Session = Depends(get_db)):
    def filas(tipo: str, limite: int):
        return list(db.scalars(
            select(MigracionWooCommerce)
            .where(MigracionWooCommerce.tipo == tipo)
            .order_by(MigracionWooCommerce.id.desc())
            .limit(limite)
        ).all())

    totales = dict(db.execute(
        select(MigracionWooCommerce.tipo, func.count(MigracionWooCommerce.id))
        .group_by(MigracionWooCommerce.tipo)
    ).all())
    productos = [_resumir_producto(fila.datos) for fila in filas("producto", 10)]
    clientes = [_resumir_cliente(fila.datos) for fila in filas("cliente", 20)]
    pedidos = [_resumir_pedido(fila.datos) for fila in filas("pedido", 20)]
    return {
        "solo_lectura": True,
        "totales": {
            "productos": totales.get("producto", 0),
            "clientes": totales.get("cliente", 0),
            "pedidos": totales.get("pedido", 0),
        },
        "limite_vista_previa": {"productos": 10, "clientes": 20, "pedidos": 20},
        "productos": productos,
        "clientes": clientes,
        "pedidos": pedidos,
    }


@router.get("/conciliacion-productos")
def obtener_conciliacion_productos(db: Session = Depends(get_db)):
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == "conciliacion",
        MigracionWooCommerce.id_externo == "productos-wordpress-dux",
    ))
    if fila is None:
        return {"disponible": False}
    datos = fila.datos
    vinculados = db.scalar(select(func.count(Producto.id)).where(Producto.conciliacion_estado == "vinculado")) or 0
    return {
        "disponible": True,
        "totales": {**datos["totales"], "vinculados": vinculados},
        "muestras": {
            "coincidencias": datos["coincidencias"][:20],
            "dudosos": datos["dudosos"][:20],
            "solo_wordpress": datos["solo_wordpress"][:20],
            "solo_dux": datos["solo_dux"][:20],
        },
    }


@router.get("/conciliacion-productos/dudosos")
def listar_productos_dudosos(
    page: int = Query(default=1, ge=1), limit: int = Query(default=20, ge=1, le=100),
    buscar: str | None = Query(default=None, max_length=150), db: Session = Depends(get_db),
):
    fila = db.scalar(select(MigracionWooCommerce).where(
        MigracionWooCommerce.tipo == "conciliacion",
        MigracionWooCommerce.id_externo == "productos-wordpress-dux",
    ))
    if fila is None:
        return {"items": [], "total": 0, "page": page, "limit": limit, "total_paginas": 0}
    vinculados = set(db.scalars(select(Producto.wordpress_id).where(
        Producto.conciliacion_estado == "vinculado", Producto.wordpress_id.is_not(None),
    )).all())
    codigos_usados = set(db.scalars(select(Producto.dux_codigo).where(
        Producto.conciliacion_estado == "vinculado",
    )).all())
    items = []
    for original in fila.datos.get("dudosos") or []:
        if int(original["wordpress_id"]) in vinculados:
            continue
        item = dict(original)
        if item.get("dux_codigo_sugerido") in codigos_usados:
            item["motivo"] = "Este producto Dux ya está vinculado con otro producto de WordPress."
        items.append(item)
    if buscar and (termino := buscar.strip().lower()):
        items = [item for item in items if termino in " ".join(str(valor or "").lower() for valor in item.values())]
    total = len(items)
    inicio = (page - 1) * limit
    return {"items": items[inicio:inicio + limit], "total": total, "page": page, "limit": limit,
            "total_paginas": (total + limit - 1) // limit if total else 0}


@router.post("/conciliacion-productos/vincular")
def vincular_producto(data: VincularProductoRequest, db: Session = Depends(get_db)):
    try:
        producto = vincular_coincidencia_manual(db, data.wordpress_id, data.dux_codigo)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"producto_id": producto.id, "wordpress_id": producto.wordpress_id,
            "dux_codigo": producto.dux_codigo, "estado": producto.conciliacion_estado}
